"""Tests for the evidence-based focus filter (quant_features.py).

Derived from signal_tracker.db accuracy analysis (2026-07-28):
  - Sports is the only theme with measurable positive edge (49% hit, 20% NO_MATCH).
  - Politics/crypto/geopolitics: 28-36% hit, 64-75% unmeasurable -> excluded.
  - Entry price 0.15-0.45 is the validated, out-of-sample-robust band (59% hit).
  - Same-day games (days_left < 1) are the most temporally stable slice (63%).
  - Deep value (price < 0.35) is the highest-accuracy sub-band (64%).
  - Point markets (spread/total) beat moneylines (54-59% vs 46%).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend/adapters"))
from quant_features import (
    FOCUS_THEMES,
    FOCUS_PRICE_MIN,
    FOCUS_PRICE_MAX,
    is_focus_eligible,
    focus_score,
)


# ── is_focus_eligible ─────────────────────────────────────────────────────────

def test_sports_in_price_band_is_eligible():
    assert is_focus_eligible("sports", 0.30) is True

def test_nonsports_theme_is_never_eligible():
    assert is_focus_eligible("politics", 0.30) is False
    assert is_focus_eligible("crypto", 0.30) is False

def test_price_above_band_rejected():
    assert is_focus_eligible("sports", 0.85) is False

def test_price_below_band_rejected():
    # 0.10 is inside the legacy [0.10, 0.90] range but below the focus band.
    assert is_focus_eligible("sports", 0.10) is False

def test_band_edges():
    assert is_focus_eligible("sports", FOCUS_PRICE_MIN) is True     # inclusive lower
    assert is_focus_eligible("sports", FOCUS_PRICE_MAX) is False    # exclusive upper


# ── focus_score ───────────────────────────────────────────────────────────────

def test_ineligible_scores_zero():
    assert focus_score("politics", 0.30, days_left=0.5, point_market=True) == 0.0

def test_plain_eligible_scores_base_one():
    # sports, mid-band price, multi-day out, moneyline -> base only
    assert focus_score("sports", 0.40, days_left=5.0, point_market=False) == 1.0

def test_sameday_adds_bonus():
    assert focus_score("sports", 0.40, days_left=0.5, point_market=False) == 1.4

def test_deep_value_and_point_market_stack():
    # sports @ 0.20 (deep value) + same-day + point market
    assert focus_score("sports", 0.20, days_left=0.5, point_market=True) == 1.85

def test_higher_conviction_outranks_lower():
    plain = focus_score("sports", 0.40, days_left=5.0, point_market=False)
    best = focus_score("sports", 0.20, days_left=0.2, point_market=True)
    assert best > plain > 0.0


# ── compute_focus_stake (flat 2% staking) ─────────────────────────────────────

def test_focus_stake_is_two_percent_of_bankroll():
    from quant_features import compute_focus_stake
    assert compute_focus_stake(100.0) == 2.0
    assert compute_focus_stake(250.0) == 5.0


# ── expected_value / focus_win_prob (EV-based ranking) ────────────────────────

def test_expected_value_formula():
    from quant_features import expected_value
    # q/p - 1 - cost. q=0.60 @ 0.30, no cost -> +1.0 (100% ROI)
    assert expected_value(0.60, 0.30, cost=0.0) == 1.0
    # q == price -> zero edge
    assert expected_value(0.30, 0.30, cost=0.0) == 0.0

def test_expected_value_higher_for_cheaper_at_same_absolute_edge():
    from quant_features import expected_value
    cheap = expected_value(0.25, 0.15, cost=0.0)   # +0.667
    dear = expected_value(0.55, 0.45, cost=0.0)     # +0.222
    assert cheap > dear

def test_focus_win_prob_decreases_with_price():
    from quant_features import focus_win_prob
    assert focus_win_prob(0.18) > focus_win_prob(0.40)
