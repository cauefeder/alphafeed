"""Empirical win-probability model for AlphaFeed opportunities.

Produces q = P(the bet on this opportunity's side wins) from features that are
actually predictive (price, point-market, same-day, liquidity, category) — NOT
the anti-predictive XGBoost score. See
docs/superpowers/specs/2026-08-05-win-probability-model-design.md.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np

from quant_features import infer_category_from_slug, is_point_market

_CATEGORIES = ["sports", "politics", "crypto", "geopolitics", "macro", "other"]
FEATURES: list[str] = ["price", "is_point_market", "same_day", "log_liquidity"] + [
    f"cat_{c}" for c in _CATEGORIES
]


def _price_of(opp: dict[str, Any]) -> float:
    for k in ("curPrice", "entry_price", "market_price"):
        v = opp.get(k)
        if v is not None:
            return float(v)
    return 0.5


def _slug_of(opp: dict[str, Any]) -> str:
    return opp.get("slug") or opp.get("market_slug") or ""


def featurize(opp: dict[str, Any]) -> dict[str, float]:
    """Map an opportunity dict OR a signal_tracker row to the model feature dict."""
    slug = _slug_of(opp)
    price = _price_of(opp)
    days_left = opp.get("days_left")
    liquidity = float(opp.get("liquidity") or 0.0)
    category = opp.get("category") or infer_category_from_slug(slug, title=opp.get("title", ""))
    if category not in _CATEGORIES:
        category = "other"
    feats = {
        "price": price,
        "is_point_market": 1.0 if is_point_market(slug) else 0.0,
        "same_day": 1.0 if (days_left is not None and float(days_left) < 1.0) else 0.0,
        "log_liquidity": math.log1p(max(liquidity, 0.0)),
    }
    for c in _CATEGORIES:
        feats[f"cat_{c}"] = 1.0 if category == c else 0.0
    return {k: feats[k] for k in FEATURES}


def _sigmoid(z: float) -> float:
    return 1.0 / (1.0 + math.exp(-z))


_STD_EPS = 1e-8  # below this, a feature is treated as constant (avoid amplifying float noise)


class WinProbModel:
    def __init__(self, features, mean, std, coef, intercept, isotonic, clip):
        self.features = list(features)
        self.mean = np.asarray(mean, dtype=float)
        self.std = np.asarray(std, dtype=float)
        self.coef = np.asarray(coef, dtype=float)
        self.intercept = float(intercept)
        self.isotonic = isotonic          # {"x":[...], "y":[...]} or None
        self.clip = tuple(clip)

    def predict(self, opp: dict) -> float:
        f = featurize(opp)
        x = np.array([f[k] for k in self.features], dtype=float)
        low_var = self.std < _STD_EPS
        std = np.where(low_var, 1.0, self.std)
        scaled = (x - self.mean) / std
        scaled = np.where(low_var, 0.0, scaled)  # avoid amplifying float noise on constant features
        z = self.intercept + float(np.dot(self.coef, scaled))
        p = _sigmoid(z)
        if self.isotonic:
            p = float(np.interp(p, self.isotonic["x"], self.isotonic["y"]))
        lo, hi = self.clip
        return float(min(max(p, lo), hi))

    def to_dict(self) -> dict:
        return {"features": self.features,
                "standardizer": {"mean": self.mean.tolist(), "std": self.std.tolist()},
                "coefficients": self.coef.tolist(), "intercept": self.intercept,
                "isotonic": self.isotonic, "clip": list(self.clip)}

    @classmethod
    def from_dict(cls, d: dict) -> "WinProbModel":
        s = d["standardizer"]
        return cls(d["features"], s["mean"], s["std"], d["coefficients"],
                   d["intercept"], d.get("isotonic"), d.get("clip", [0.02, 0.98]))

    @classmethod
    def load(cls, path) -> "WinProbModel":
        import json
        with open(path, encoding="utf-8") as fh:
            return cls.from_dict(json.load(fh))


def brier(y, p):
    y = np.asarray(y, float); p = np.asarray(p, float)
    return float(np.mean((p - y) ** 2))


def ece(y, p, bins=10):
    y = np.asarray(y, float); p = np.asarray(p, float)
    edges = np.linspace(0, 1, bins + 1)
    total = len(y); e = 0.0
    for i in range(bins):
        m = (p >= edges[i]) & (p < edges[i + 1] if i < bins - 1 else p <= edges[i + 1])
        if m.sum() == 0:
            continue
        e += abs(y[m].mean() - p[m].mean()) * m.sum() / total
    return float(e)


def _design_matrix(rows):
    X = np.array([[featurize(r)[k] for k in FEATURES] for r in rows], float)
    y = np.array([1 if r.get("outcome") == "WIN" else 0 for r in rows], float)
    price = np.array([_price_of(r) for r in rows], float)
    return X, y, price


def fit(rows, *, seed=0, folds=5, c=1.0):
    """Fit L2 logistic + optional isotonic; return (params_dict, metrics_dict)."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.isotonic import IsotonicRegression

    rows = sorted(rows, key=lambda r: r.get("created_at") or "")
    X, y, price = _design_matrix(rows)
    n = len(rows)
    mean = X.mean(axis=0); std = X.std(axis=0)
    low_var = std < _STD_EPS
    std_safe = np.where(low_var, 1.0, std)
    Xs = (X - mean) / std_safe
    Xs[:, low_var] = 0.0  # avoid amplifying float noise on near-constant features

    # Walk-forward OOS predictions over the trailing (1 - start) fraction.
    start = 0.5
    seed_end = int(n * start)
    oos_p, oos_y, oos_price = [], [], []
    if n - seed_end >= folds and seed_end >= 50:
        bounds = np.linspace(seed_end, n, folds + 1).astype(int)
        for i in range(folds):
            tr_end, te_end = bounds[i], bounds[i + 1]
            if te_end <= tr_end:
                continue
            clf = LogisticRegression(penalty="l2", C=c, max_iter=1000, random_state=seed)
            clf.fit(Xs[:tr_end], y[:tr_end])
            oos_p.extend(clf.predict_proba(Xs[tr_end:te_end])[:, 1])
            oos_y.extend(y[tr_end:te_end]); oos_price.extend(price[tr_end:te_end])
    oos_p = np.array(oos_p); oos_y = np.array(oos_y); oos_price = np.array(oos_price)

    # Optional isotonic calibration fit on OOS predictions.
    iso = None
    if len(oos_p) >= 100:
        ir = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
        ir.fit(oos_p, oos_y)
        cal = ir.predict(oos_p)
        # keep isotonic only if it does not worsen Brier
        if brier(oos_y, cal) <= brier(oos_y, oos_p) + 1e-6:
            xs = np.linspace(0, 1, 51)
            iso = {"x": xs.tolist(), "y": ir.predict(xs).tolist()}

    # Final model on ALL data (deployed coefficients).
    clf = LogisticRegression(penalty="l2", C=c, max_iter=1000, random_state=seed)
    clf.fit(Xs, y)

    from sklearn.metrics import roc_auc_score
    metrics = {"n_train": n, "n_oos": int(len(oos_y))}
    if len(oos_y):
        eval_p = np.interp(oos_p, iso["x"], iso["y"]) if iso else oos_p
        metrics.update(
            brier=brier(oos_y, eval_p),
            brier_price_baseline=brier(oos_y, oos_price),
            ece=ece(oos_y, eval_p),
            auc=float(roc_auc_score(oos_y, eval_p)) if len(set(oos_y.tolist())) > 1 else 0.5,
        )
    else:
        metrics.update(brier=1.0, brier_price_baseline=0.0, ece=1.0, auc=0.5)

    params = {"features": FEATURES,
              "standardizer": {"mean": mean.tolist(), "std": std.tolist()},
              "coefficients": clf.coef_[0].tolist(), "intercept": float(clf.intercept_[0]),
              "isotonic": iso, "clip": [0.02, 0.98]}
    return params, metrics


MIN_TRAIN = 300
MAX_ECE = 0.06


def passes_gate(metrics: dict) -> bool:
    return (metrics.get("n_train", 0) >= MIN_TRAIN
            and metrics.get("brier", 1.0) <= metrics.get("brier_price_baseline", 0.0)
            and metrics.get("ece", 1.0) <= MAX_ECE)


def maybe_write_artifact(path: str, params: dict, metrics: dict) -> bool:
    """Atomically write the artifact iff the gate passes. Returns wrote?."""
    import json, os, tempfile
    from datetime import datetime, timezone
    if not passes_gate(metrics):
        return False
    doc = {**params, "validation": metrics, "gate_passed": True,
           "fit_date": datetime.now(timezone.utc).isoformat(),
           "model_type": "logistic_l2" + ("+isotonic" if params.get("isotonic") else "")}
    d = os.path.dirname(path) or "."
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2)
    os.replace(tmp, path)
    return True
