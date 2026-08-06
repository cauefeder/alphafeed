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
        std = np.where(self.std == 0, 1.0, self.std)
        z = self.intercept + float(np.dot(self.coef, (x - self.mean) / std))
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
