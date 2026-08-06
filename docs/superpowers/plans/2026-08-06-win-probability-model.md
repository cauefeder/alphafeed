# Empirical Win-Probability Model — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the hardcoded `focus_win_prob` lookup with a small, calibrated, auto-refit logistic model that produces a per-opportunity win probability `q` for expected-value ranking.

**Architecture:** A self-contained model library (`win_prob.py`) fits an L2-logistic regression over the features that actually predict (price, point-market, same-day, log-liquidity, category), validated walk-forward against a price-Brier baseline. A refit script (`fit_win_prob.py`) writes a gated JSON artifact that `quant_report.py` loads to compute `q`/EV, with a safe fallback to the existing lookup.

**Tech Stack:** Python 3.11, numpy, scikit-learn (LogisticRegression, IsotonicRegression), sqlite3, pytest. Run tooling via `uv run --no-project --python 3.11 --with ...`.

**Spec:** `docs/superpowers/specs/2026-08-05-win-probability-model-design.md`

**Conventions in this repo:**
- Tests live in `tests/`, import adapters via `sys.path.insert(0, ".../backend/adapters")`.
- Run tests: `UV="$HOME/.local/bin/uv.exe"; "$UV" run --no-project --python 3.11 --with pytest,numpy,scikit-learn,httpx python -m pytest <path> -q`
- Commit after every green step. Branch: `feat/win-prob-model`.

---

## File Structure

- **Create** `backend/adapters/win_prob.py` — model library: `featurize`, `WinProbModel` (predict + serialize), `fit`, metrics, `passes_gate`. Owns all model math.
- **Create** `backend/adapters/fit_win_prob.py` — refit script: read `signal_tracker.db`, fit, gate, atomic-write artifact.
- **Create** `models/win_prob_model.json` — produced by the script (not hand-written).
- **Modify** `backend/adapters/quant_features.py` — new shared home for slug helpers (`_is_point_market`, `_infer_category_from_slug`) so both `win_prob` and `quant_report` import them without a cycle.
- **Modify** `backend/adapters/quant_report.py` — re-import relocated helpers; use `WinProbModel` for `q`/EV with fallback; emit `qSource`.
- **Modify** `.github/workflows/refresh-reports.yml` and `../scheduler.py` — run `fit_win_prob.py` before the quant report.
- **Modify** `frontend/src/tabs/QuantReport.jsx` — surface `qSource` in the Exp. ROI tooltip.
- **Create** `tests/test_win_prob.py`, extend `tests/test_quant_report.py`.

---

## Task 1: Relocate shared slug helpers to `quant_features.py`

Prevents a `quant_report → win_prob → quant_report` import cycle; DRY single home.

**Files:**
- Modify: `backend/adapters/quant_features.py` (add helpers)
- Modify: `backend/adapters/quant_report.py:70-120` (remove definitions, import instead)
- Test: `tests/test_quant_features.py`

- [ ] **Step 1: Write failing test** in `tests/test_quant_features.py`

```python
def test_point_market_and_category_helpers_exposed():
    from quant_features import is_point_market, infer_category_from_slug
    assert is_point_market("mlb-a-b-2026-08-06-total-8pt5") is True
    assert is_point_market("will-x-win-election") is False
    assert infer_category_from_slug("mlb-nyy-bos-2026-08-06") == "sports"
    assert infer_category_from_slug("presidential-election-winner") == "politics"
```

- [ ] **Step 2: Run — expect FAIL** (`ImportError`)

Run: `"$UV" run --no-project --python 3.11 --with pytest,numpy python -m pytest tests/test_quant_features.py::test_point_market_and_category_helpers_exposed -q`
Expected: FAIL — cannot import `is_point_market`.

- [ ] **Step 3: Implement** — move `_CATEGORY_KEYWORDS`, `_infer_category_from_slug`, `_POINT_MARKET_TOKENS`, `_is_point_market` from `quant_report.py` into `quant_features.py`. Expose public aliases at the bottom of `quant_features.py`:

```python
# Public aliases (imported by quant_report and win_prob)
is_point_market = _is_point_market
infer_category_from_slug = _infer_category_from_slug
```

In `quant_report.py`, delete those four definitions and add to the `from quant_features import (...)` block: `_is_point_market`, `_infer_category_from_slug` (keep the leading-underscore names it already calls, aliasing on import: `is_point_market as _is_point_market, infer_category_from_slug as _infer_category_from_slug`).

- [ ] **Step 4: Run full suite — expect PASS** (no behavior change)

Run: `"$UV" run --no-project --python 3.11 --with pytest,numpy,httpx,scikit-learn python -m pytest tests/test_quant_features.py tests/test_quant_report.py -q`
Expected: PASS (same count as before this task).

- [ ] **Step 5: Commit**

```bash
git add backend/adapters/quant_features.py backend/adapters/quant_report.py tests/test_quant_features.py
git commit -m "refactor(alphafeed): move slug helpers to quant_features (shared home)"
```

---

## Task 2: `win_prob.featurize`

**Files:**
- Create: `backend/adapters/win_prob.py`
- Test: `tests/test_win_prob.py`

- [ ] **Step 1: Write failing test** in `tests/test_win_prob.py`

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend/adapters"))

from win_prob import FEATURES, featurize

def test_featurize_from_opportunity_dict():
    opp = {"curPrice": 0.30, "slug": "mlb-a-b-2026-08-06-total-8pt5",
           "days_left": 0.5, "liquidity": 50000, "category": "sports"}
    f = featurize(opp)
    assert list(f.keys()) == FEATURES            # canonical order
    assert f["price"] == 0.30
    assert f["is_point_market"] == 1.0
    assert f["same_day"] == 1.0
    assert f["log_liquidity"] > 0
    assert f["cat_sports"] == 1.0 and f["cat_politics"] == 0.0

def test_featurize_from_tracker_row_infers_category_and_price():
    # tracker rows have no 'category'/'curPrice'; use slug + entry_price/market_price
    row = {"market_slug": "presidential-election-2026", "entry_price": 0.135,
           "days_left": 40, "liquidity": 0}
    f = featurize(row)
    assert f["price"] == 0.135
    assert f["is_point_market"] == 0.0
    assert f["same_day"] == 0.0
    assert f["cat_politics"] == 1.0

def test_featurize_defaults_when_fields_missing():
    f = featurize({"slug": "mlb-a-b-2026-08-06"})
    assert f["price"] == 0.5          # default mid
    assert f["log_liquidity"] == 0.0  # log1p(0)
```

- [ ] **Step 2: Run — expect FAIL** (`ImportError`)

Run: `"$UV" run --no-project --python 3.11 --with pytest,numpy,scikit-learn python -m pytest tests/test_win_prob.py -q`
Expected: FAIL — `win_prob` not found.

- [ ] **Step 3: Implement** the top of `backend/adapters/win_prob.py`:

```python
"""Empirical win-probability model for AlphaFeed opportunities.

Produces q = P(the bet on this opportunity's side wins) from features that are
actually predictive (price, point-market, same-day, liquidity, category) — NOT
the anti-predictive XGBoost score. See
docs/superpowers/specs/2026-08-05-win-probability-model-design.md.
"""
from __future__ import annotations

import math
from typing import Any

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
```

- [ ] **Step 4: Run — expect PASS**

Run: `"$UV" run --no-project --python 3.11 --with pytest,numpy,scikit-learn python -m pytest tests/test_win_prob.py -q`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/adapters/win_prob.py tests/test_win_prob.py
git commit -m "feat(alphafeed): win_prob.featurize"
```

---

## Task 3: `WinProbModel` predict + (de)serialization

Test `predict` against a hand-built params dict (no fit needed yet).

**Files:** Modify `backend/adapters/win_prob.py`; extend `tests/test_win_prob.py`.

- [ ] **Step 1: Write failing test**

```python
from win_prob import WinProbModel

def _toy_params():
    # single active feature: price with a strong NEGATIVE coefficient
    # (cheaper -> higher q). Others zero. Standardizer: identity-ish.
    n = len(FEATURES)
    mean = [0.0] * n
    std = [1.0] * n
    coef = [0.0] * n
    coef[FEATURES.index("price")] = -4.0
    return {"features": FEATURES, "standardizer": {"mean": mean, "std": std},
            "coefficients": coef, "intercept": 0.0, "isotonic": None,
            "clip": [0.02, 0.98]}

def test_predict_monotonic_decreasing_in_price():
    m = WinProbModel.from_dict(_toy_params())
    cheap = m.predict({"curPrice": 0.20, "slug": "mlb-a-b-2026-08-06-total-8pt5"})
    dear = m.predict({"curPrice": 0.45, "slug": "mlb-a-b-2026-08-06-total-8pt5"})
    assert 0.02 <= dear < cheap <= 0.98

def test_predict_respects_clip():
    p = _toy_params(); p["coefficients"][FEATURES.index("price")] = -50.0
    m = WinProbModel.from_dict(p)
    assert m.predict({"curPrice": 0.01, "slug": "x"}) <= 0.98
    assert m.predict({"curPrice": 0.99, "slug": "x"}) >= 0.02

def test_to_from_dict_roundtrip():
    m = WinProbModel.from_dict(_toy_params())
    m2 = WinProbModel.from_dict(m.to_dict())
    assert m2.predict({"curPrice": 0.3, "slug": "x"}) == m.predict({"curPrice": 0.3, "slug": "x"})
```

- [ ] **Step 2: Run — expect FAIL** (`ImportError: WinProbModel`)

Run: `"$UV" run --no-project --python 3.11 --with pytest,numpy,scikit-learn python -m pytest tests/test_win_prob.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement** in `win_prob.py`:

```python
import numpy as np


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
```

- [ ] **Step 4: Run — expect PASS**; **Step 5: Commit**

```bash
git add backend/adapters/win_prob.py tests/test_win_prob.py
git commit -m "feat(alphafeed): WinProbModel predict + serialization"
```

---

## Task 4: metrics (`brier`, `ece`) + `fit` with walk-forward

**Files:** Modify `win_prob.py`; extend `tests/test_win_prob.py`.

- [ ] **Step 1: Write failing tests**

```python
import numpy as np
from win_prob import brier, ece, fit

def test_brier_and_ece_basic():
    y = np.array([1, 0, 1, 0]); p = np.array([0.9, 0.1, 0.8, 0.2])
    assert brier(y, p) == pytest.approx(np.mean((p - y) ** 2))
    assert 0.0 <= ece(y, p, bins=5) <= 1.0

def test_fit_learns_cheap_wins_more():
    # synthetic: cheaper price -> more wins. Model must recover q decreasing in price.
    import random; random.seed(0)
    rows = []
    for _ in range(600):
        price = random.uniform(0.15, 0.45)
        win = 1 if random.random() < (0.75 - price) else 0   # cheaper -> higher win
        rows.append({"market_slug": "mlb-a-b-2026-08-06-total-8pt5",
                     "entry_price": price, "days_left": 0.5, "liquidity": 40000,
                     "outcome": "WIN" if win else "LOSS",
                     "created_at": f"2026-06-{1 + (_ % 28):02d}T00:00:00+00:00"})
    params, metrics = fit(rows)
    m = WinProbModel.from_dict(params)
    assert m.predict({"curPrice": 0.18, "slug": rows[0]["market_slug"]}) > \
           m.predict({"curPrice": 0.42, "slug": rows[0]["market_slug"]})
    assert metrics["n_train"] == 600
    assert "brier" in metrics and "brier_price_baseline" in metrics and "ece" in metrics
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement** in `win_prob.py`:

```python
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
    mean = X.mean(axis=0); std = X.std(axis=0); std_safe = np.where(std == 0, 1.0, std)
    Xs = (X - mean) / std_safe

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
```

- [ ] **Step 4: Run — expect PASS**; **Step 5: Commit**

```bash
git add backend/adapters/win_prob.py tests/test_win_prob.py
git commit -m "feat(alphafeed): win_prob.fit + brier/ece metrics (walk-forward)"
```

---

## Task 5: `passes_gate`

**Files:** Modify `win_prob.py`; extend `tests/test_win_prob.py`.

- [ ] **Step 1: Write failing tests**

```python
from win_prob import passes_gate

GOOD = {"n_train": 500, "brier": 0.20, "brier_price_baseline": 0.24, "ece": 0.04}

def test_gate_accepts_good():
    assert passes_gate(GOOD) is True

def test_gate_rejects_small_sample():
    assert passes_gate({**GOOD, "n_train": 200}) is False

def test_gate_rejects_worse_than_price():
    assert passes_gate({**GOOD, "brier": 0.25}) is False

def test_gate_rejects_poor_calibration():
    assert passes_gate({**GOOD, "ece": 0.10}) is False
```

- [ ] **Step 2: Run — expect FAIL**
- [ ] **Step 3: Implement**

```python
MIN_TRAIN = 300
MAX_ECE = 0.06

def passes_gate(metrics: dict) -> bool:
    return (metrics.get("n_train", 0) >= MIN_TRAIN
            and metrics.get("brier", 1.0) <= metrics.get("brier_price_baseline", 0.0)
            and metrics.get("ece", 1.0) <= MAX_ECE)
```

- [ ] **Step 4: Run — expect PASS**; **Step 5: Commit**

```bash
git add backend/adapters/win_prob.py tests/test_win_prob.py
git commit -m "feat(alphafeed): win_prob.passes_gate"
```

---

## Task 6: `fit_win_prob.py` refit script (gated, atomic write)

**Files:** Create `backend/adapters/fit_win_prob.py`; extend `tests/test_win_prob.py`.

- [ ] **Step 1: Write failing test** (tests the promote/keep logic via a helper, no real DB)

```python
from win_prob import maybe_write_artifact   # thin helper we will add
import json, os

def test_artifact_written_only_when_gate_passes(tmp_path):
    path = tmp_path / "win_prob_model.json"
    good_params = {"features": FEATURES, "standardizer": {"mean": [0]*len(FEATURES), "std":[1]*len(FEATURES)},
                   "coefficients": [0]*len(FEATURES), "intercept": 0.0, "isotonic": None, "clip":[0.02,0.98]}
    assert maybe_write_artifact(str(path), good_params, {"n_train":500,"brier":0.2,"brier_price_baseline":0.24,"ece":0.04}) is True
    assert path.exists()
    before = path.read_text()
    # a failing gate must NOT overwrite the existing good artifact
    assert maybe_write_artifact(str(path), good_params, {"n_train":100,"brier":0.9,"brier_price_baseline":0.2,"ece":0.5}) is False
    assert path.read_text() == before
```

- [ ] **Step 2: Run — expect FAIL**
- [ ] **Step 3: Implement** `maybe_write_artifact` in `win_prob.py`:

```python
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
```

Then create `backend/adapters/fit_win_prob.py`:

```python
"""Refit the win-probability model from signal_tracker.db and gate-write the artifact.

Run before quant_report.py in the refresh pipeline. Never raises for a bad fit —
logs, leaves the previous artifact in place, and exits 0 so the report run continues.
"""
from __future__ import annotations
import json, logging, os, sqlite3, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from win_prob import fit, maybe_write_artifact  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("fit_win_prob")

REPO_ROOT = Path(__file__).resolve().parents[2]           # AlphaFeed/
ARTIFACT = REPO_ROOT / "models" / "win_prob_model.json"
DB = Path(os.environ.get("SIGNAL_TRACKER_DB", REPO_ROOT.parent / "signal_tracker.db"))


def load_rows(db_path: Path) -> list[dict]:
    if not db_path.exists():
        log.warning("signal_tracker.db not found at %s", db_path); return []
    con = sqlite3.connect(str(db_path)); con.row_factory = sqlite3.Row
    rows = con.execute(
        """SELECT market_slug, entry_price, market_price, raw_features, outcome, created_at
           FROM signals WHERE system='alphafeed' AND outcome IN ('WIN','LOSS')"""
    ).fetchall()
    out = []
    for r in rows:
        try:
            rf = json.loads(r["raw_features"] or "{}")
        except Exception:
            rf = {}
        out.append({"market_slug": r["market_slug"], "entry_price": r["entry_price"],
                    "market_price": r["market_price"], "outcome": r["outcome"],
                    "created_at": r["created_at"], "days_left": rf.get("days_left"),
                    "liquidity": rf.get("liquidity")})
    return out


def main() -> int:
    rows = load_rows(DB)
    if len(rows) < 300:
        log.warning("only %d resolved rows — keeping previous artifact", len(rows)); return 0
    params, metrics = fit(rows)
    wrote = maybe_write_artifact(str(ARTIFACT), params, metrics)
    log.info("fit n=%d brier=%.4f baseline=%.4f ece=%.4f -> %s",
             metrics["n_train"], metrics.get("brier", 1), metrics.get("brier_price_baseline", 0),
             metrics.get("ece", 1), "WROTE" if wrote else "KEPT PREVIOUS (gate failed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run — expect PASS** (unit test); then a real smoke run:

Run: `"$UV" run --no-project --python 3.11 --with numpy,scikit-learn python backend/adapters/fit_win_prob.py`
Expected: logs a fit line and writes `models/win_prob_model.json` (or "KEPT PREVIOUS"). Inspect the JSON has `validation` + `gate_passed`.

- [ ] **Step 5: Commit**

```bash
git add backend/adapters/win_prob.py backend/adapters/fit_win_prob.py tests/test_win_prob.py
git commit -m "feat(alphafeed): fit_win_prob refit script + gated atomic artifact"
```

---

## Task 7: Integrate model into `quant_report.py` (q / EV / qSource + fallback)

**Files:** Modify `backend/adapters/quant_report.py`; extend `tests/test_quant_report.py`.

- [ ] **Step 1: Write failing tests** in `tests/test_quant_report.py`

```python
def test_uses_model_q_when_artifact_present(tmp_path, monkeypatch):
    from win_prob import WinProbModel, FEATURES
    # build a toy model: constant-ish q via large positive intercept
    params = {"features": FEATURES, "standardizer": {"mean":[0]*len(FEATURES),"std":[1]*len(FEATURES)},
              "coefficients":[0]*len(FEATURES), "intercept": 0.4, "isotonic": None, "clip":[0.02,0.98]}
    import quant_report
    monkeypatch.setattr(quant_report, "_WIN_PROB_MODEL", WinProbModel.from_dict(params))
    r = quant_report.score_opportunity(
        _make_opp(curPrice=0.30, category="sports", days_left=0.5,
                  slug="mlb-a-b-2026-08-06-total-8pt5"),
        _make_model(0.7), _make_calibration())
    assert r["qSource"] == "model"
    assert 0.02 <= r["winProbEst"] <= 0.98
    # EV consistent with q/price - 1 - cost
    from quant_features import LIVE_BET_COST
    assert r["expectedValue"] == pytest.approx(r["winProbEst"]/0.30 - 1 - LIVE_BET_COST, abs=1e-4)

def test_falls_back_to_lookup_when_no_model(monkeypatch):
    import quant_report
    monkeypatch.setattr(quant_report, "_WIN_PROB_MODEL", None)
    r = quant_report.score_opportunity(
        _make_opp(curPrice=0.30, category="sports", days_left=0.5,
                  slug="mlb-a-b-2026-08-06-total-8pt5"),
        _make_model(0.7), _make_calibration())
    assert r["qSource"] == "lookup"
    assert r["winProbEst"] > 0
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement** in `quant_report.py`:

Add near imports:
```python
from win_prob import WinProbModel

_WIN_PROB_ARTIFACT = REPO_ROOT / "models" / "win_prob_model.json"

def _load_win_prob_model():
    try:
        import json
        with open(_WIN_PROB_ARTIFACT, encoding="utf-8") as fh:
            doc = json.load(fh)
        if not doc.get("gate_passed"):
            return None
        return WinProbModel.from_dict(doc)
    except Exception as exc:                    # missing/corrupt -> fallback
        logger.info("win_prob model unavailable (%s) — using fallback", exc)
        return None

_WIN_PROB_MODEL = _load_win_prob_model()
```

Replace the `win_prob`/`exp_value` block in `score_opportunity` (currently `win_prob = focus_win_prob(...) if focus_eligible else 0.0`) with:
```python
    if _WIN_PROB_MODEL is not None:
        win_prob = _WIN_PROB_MODEL.predict(opp)
        q_source = "model"
    elif focus_eligible:
        win_prob = focus_win_prob(cur_price)
        q_source = "lookup"
    else:
        win_prob = cur_price
        q_source = "price"
    exp_value = expected_value(win_prob, cur_price)
```

Add `"qSource": q_source` to the returned dict (next to `winProbEst`).

> Note: `expectedValue` is now computed for **all** opportunities (was 0 for ineligible). Staking (`kellyBet`) remains gated on `focus_eligible`; ranking stays `(expectedValue, focusScore, quantScore)`. This is intended per the spec (EV for all).

- [ ] **Step 4: Run full suite — expect PASS**

Run: `"$UV" run --no-project --python 3.11 --with pytest,numpy,pandas,httpx,requests,scikit-learn,xgboost,fastapi,starlette,slowapi python -m pytest tests/ -q`
Expected: PASS (previous count + new tests).

- [ ] **Step 5: Commit**

```bash
git add backend/adapters/quant_report.py tests/test_quant_report.py
git commit -m "feat(alphafeed): quant_report uses win-prob model for q/EV with fallback"
```

---

## Task 8: Pipeline wiring (refit before report)

**Files:** Modify `.github/workflows/refresh-reports.yml`; modify `../scheduler.py` (`ALPHAFEED_ADAPTERS`).

- [ ] **Step 1: Edit `refresh-reports.yml`** — add a step **before** "Run quant_report":

```yaml
      - name: Refit win-probability model
        run: python backend/adapters/fit_win_prob.py
        timeout-minutes: 5
```

And add the artifact to the commit step's `git add` line:
`git add -f reports/poly2.json reports/polytraders.json reports/hedgepoly.json reports/quant_report.json models/win_prob_model.json 2>/dev/null || true`

- [ ] **Step 2: Edit `scheduler.py`** — in `ALPHAFEED_ADAPTERS`, insert before the "AlphaFeed: quant XGBoost report" entry:

```python
    {
        "name": "AlphaFeed: refit win-prob model",
        "cwd": ALPHAFEED_DIR,
        "cmd": [UV, "run", "--no-project", "--python", "3.11",
                "--with", "numpy,scikit-learn",
                "python", "backend/adapters/fit_win_prob.py"],
        "timeout": 180,
        "capture_to_telegram": False,
    },
```

- [ ] **Step 3: Verify** the ordered adapter list locally (dry, no Telegram):

Run: `"$UV" run --no-project --python 3.11 --with numpy,scikit-learn python backend/adapters/fit_win_prob.py && "$UV" run --no-project --python 3.11 --with httpx,xgboost,scikit-learn,numpy,pandas python backend/adapters/quant_report.py 2>&1 | tail -2`
Expected: model refits, then quant report regenerates; inspect `reports/quant_report.json` — opportunities have `qSource` and `expectedValue`.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/refresh-reports.yml
git commit -m "ci(alphafeed): refit win-prob model before quant report + commit artifact"
```
> `scheduler.py` is tracked by the **Projetos root repo**, not AlphaFeed. Commit it there separately with:
> `cd "D:/OMNP - Quant/Projetos" && git add scheduler.py && git commit -m "chore: refit alphafeed win-prob before quant report"`
> (leave any unrelated working-tree changes in that repo untouched).

---

## Task 9: Frontend — surface `qSource` in the Exp. ROI tooltip

**Files:** Modify `frontend/src/tabs/QuantReport.jsx`.

- [ ] **Step 1: Update the Exp. ROI cell `title`** to include the source:

```jsx
<td title={opp.winProbEst ? `est. win prob ${(opp.winProbEst*100).toFixed(0)}% @ ${(opp.curPrice*100).toFixed(0)}¢ · source: ${opp.qSource ?? "—"}` : "not in the focus book"}
```

- [ ] **Step 2: Build — expect success**

Run: `cd frontend && npm run build`
Expected: `✓ built`.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/tabs/QuantReport.jsx
git commit -m "feat(alphafeed): show win-prob source in Exp. ROI tooltip"
```

---

## Final verification (before merge/deploy — separate from this plan's execution)

- [ ] Full test suite green: `"$UV" run --no-project --python 3.11 --with pytest,numpy,pandas,httpx,requests,scikit-learn,xgboost,fastapi,starlette,slowapi python -m pytest tests/ -q`
- [ ] `models/win_prob_model.json` exists with `gate_passed: true` (or fallback engaged cleanly).
- [ ] Re-scored `reports/quant_report.json` shows `qSource: "model"` on opportunities.
- [ ] Frontend builds.

Merge/deploy (push master, trigger refresh-reports, verify live `qSource`) is a **user-gated** step handled after execution — not part of this plan.
