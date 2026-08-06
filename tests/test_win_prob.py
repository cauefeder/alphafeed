import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend/adapters"))

import numpy as np
import pytest

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


import pytest
from win_prob import WinProbModel

def _toy_params():
    # single active feature: price with a strong NEGATIVE coefficient
    # (cheaper -> higher q). Others zero. Standardizer: identity.
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
