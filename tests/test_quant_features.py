"""Tests for quant_features.py — all pure functions, no model required."""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "backend/adapters"))
from quant_features import (
    FEATURE_NAMES,
    compute_features,
    calibrate,
    build_category_trends,
    compute_edge_ranking,
    generate_insights,
)


# ── FEATURE_NAMES ─────────────────────────────────────────────────────────────

def test_feature_names_length():
    assert len(FEATURE_NAMES) == 6

def test_feature_names_canonical_order():
    assert FEATURE_NAMES == [
        "yes_price", "info_ratio", "log_volume_total",
        "log_liquidity", "days_left", "price_extremity",
    ]


# ── compute_features ──────────────────────────────────────────────────────────

def test_compute_features_known_input():
    opp = {
        "curPrice": 0.6,
        "volume_24h": 10_000,
        "volumeTotal": 100_000,
        "liquidity": 50_000,
        "days_left": 15,
    }
    f = compute_features(opp)
    assert f["yes_price"] == pytest.approx(0.6)
    # info_ratio = 10_000 / sqrt(15 + 1) / 10_000 = 1 / 4 = 0.25
    assert f["info_ratio"] == pytest.approx(0.25, rel=1e-3)
    # price_extremity = abs(0.6 - 0.5) * 2 = 0.2
    assert f["price_extremity"] == pytest.approx(0.2)
    # days_left clamped: max(15, 0.5) = 15
    assert f["days_left"] == pytest.approx(15)

def test_compute_features_days_zero_no_divide_by_zero():
    """days_left=0 → info_ratio uses sqrt(0+1)=1, never divides by zero."""
    opp = {"curPrice": 0.5, "volume_24h": 10_000, "days_left": 0}
    f = compute_features(opp)
    assert f["info_ratio"] == pytest.approx(1.0)   # 10_000 / sqrt(1) / 10_000

def test_compute_features_days_clamped_for_feature():
    """days_left feature is clamped to >= 0.5, but info_ratio uses raw+1."""
    opp = {"curPrice": 0.5, "volume_24h": 0, "days_left": 0}
    f = compute_features(opp)
    assert f["days_left"] == pytest.approx(0.5)    # clamped

def test_compute_features_missing_optionals_default_zero():
    opp = {"curPrice": 0.3}
    f = compute_features(opp)
    assert f["log_volume_total"] == pytest.approx(0.0)
    assert f["log_liquidity"] == pytest.approx(0.0)
    assert f["days_left"] == pytest.approx(0.5)    # default 0, then clamped

def test_compute_features_returns_all_feature_names():
    opp = {"curPrice": 0.5}
    f = compute_features(opp)
    assert set(f.keys()) == set(FEATURE_NAMES)

def test_compute_features_array_matches_feature_names_order():
    """Values extracted in FEATURE_NAMES order must match the dict."""
    opp = {"curPrice": 0.7, "volume_24h": 5_000, "volumeTotal": 80_000,
           "liquidity": 20_000, "days_left": 7}
    f = compute_features(opp)
    arr = [f[name] for name in FEATURE_NAMES]
    assert arr[0] == f["yes_price"]
    assert arr[-1] == f["price_extremity"]


# ── calibrate ─────────────────────────────────────────────────────────────────

def test_calibrate_identity_params():
    """With platt_a=0, platt_b=1, calibrate(0.5) should equal sigmoid(0.5) ≈ 0.622."""
    cal = {"platt_a": 0.0, "platt_b": 1.0}
    result = calibrate(0.5, cal)
    from math import exp
    expected = 1 / (1 + exp(-0.5))
    assert result == pytest.approx(expected, rel=1e-6)

def test_calibrate_zero_params_returns_half():
    """With platt_a=0, platt_b=0, calibrate(anything) = sigmoid(0) = 0.5."""
    cal = {"platt_a": 0.0, "platt_b": 0.0}
    assert calibrate(0.3, cal) == pytest.approx(0.5, rel=1e-6)
    assert calibrate(0.9, cal) == pytest.approx(0.5, rel=1e-6)

def test_calibrate_output_in_01():
    cal = {"platt_a": -0.12, "platt_b": 0.94}
    for p in [0.0, 0.1, 0.5, 0.9, 1.0]:
        result = calibrate(p, cal)
        assert 0.0 <= result <= 1.0


# ── build_category_trends ─────────────────────────────────────────────────────

SAMPLE_POLY2 = {
    "categories": {
        "macro": {
            "markets": [
                {"question": "Q1", "yes_price": 0.3, "volume_24h": 100, "url": "u1"},
                {"question": "Q2", "yes_price": 0.7, "volume_24h": 500, "url": "u2"},
                {"question": "Q3", "yes_price": 0.5, "volume_24h": 200, "url": "u3"},
            ]
        },
        "crypto": {
            "markets": [
                {"question": "C1", "yes_price": 0.9, "volume_24h": 1000, "url": "uc1"},
            ]
        },
        "empty_cat": {"markets": []},
    }
}

def test_build_category_trends_structure():
    trends = build_category_trends(SAMPLE_POLY2)
    assert "macro" in trends
    assert trends["macro"]["totalMarkets"] == 3
    assert len(trends["macro"]["top3Markets"]) == 3

def test_build_category_trends_top_market_by_volume():
    trends = build_category_trends(SAMPLE_POLY2)
    top = trends["macro"]["top3Markets"][0]
    assert top["question"] == "Q2"    # highest volume_24h = 500
    assert top["volume_24h"] == 500

def test_build_category_trends_empty_category_omitted():
    trends = build_category_trends(SAMPLE_POLY2)
    assert "empty_cat" not in trends

def test_build_category_trends_all_categories_included():
    trends = build_category_trends(SAMPLE_POLY2)
    assert set(trends.keys()) == {"macro", "crypto"}

def test_build_category_trends_top3_capped():
    """Category with >3 markets returns only top 3."""
    poly2 = {"categories": {"macro": {"markets": [
        {"question": f"Q{i}", "yes_price": 0.5, "volume_24h": i * 10, "url": f"u{i}"}
        for i in range(10)
    ]}}}
    trends = build_category_trends(poly2)
    assert len(trends["macro"]["top3Markets"]) == 3


# ── compute_edge_ranking ──────────────────────────────────────────────────────

SAMPLE_CAT_REPORT = {
    "crypto":   {"count": 8,  "avgQuantScore": 0.74, "tierACount": 2},
    "politics": {"count": 12, "avgQuantScore": 0.51, "tierACount": 1},
    "sports":   {"count": 6,  "avgQuantScore": 0.25, "tierACount": 0},
    "macro":    {"count": 6,  "avgQuantScore": 0.61, "tierACount": 1},
}

def test_compute_edge_ranking_sorted_descending():
    ranking = compute_edge_ranking(SAMPLE_CAT_REPORT)
    scores = [r["edgeScore"] for r in ranking]
    assert scores == sorted(scores, reverse=True)

def test_compute_edge_ranking_top_is_crypto():
    ranking = compute_edge_ranking(SAMPLE_CAT_REPORT)
    assert ranking[0]["category"] == "crypto"

def test_compute_edge_ranking_edge_score_equals_avg_quant_score():
    ranking = compute_edge_ranking(SAMPLE_CAT_REPORT)
    for r in ranking:
        assert r["edgeScore"] == pytest.approx(r["avgQuantScore"], rel=1e-6)

def test_compute_edge_ranking_labels():
    ranking = compute_edge_ranking(SAMPLE_CAT_REPORT)
    labels = {r["category"]: r["label"] for r in ranking}
    assert labels["crypto"] == "Strong edge"   # 0.74 >= 0.65
    assert labels["macro"] == "Good edge"      # 0.61 >= 0.50
    assert labels["politics"] == "Good edge"   # 0.51 >= 0.50
    assert labels["sports"] == "Skip"          # 0.25 < 0.30


# ── generate_insights ─────────────────────────────────────────────────────────

SAMPLE_RANKING = [
    {"category": "crypto",   "edgeScore": 0.74, "label": "Strong edge", "avgQuantScore": 0.74, "tierACount": 2, "count": 8},
    {"category": "sports",   "edgeScore": 0.25, "label": "Skip",        "avgQuantScore": 0.25, "tierACount": 0, "count": 6},
]

SAMPLE_OPPS = [
    {"title": "BTC 90k?", "quantScore": 0.84, "signalTier": "A",
     "curPrice": 0.62, "countSignal": 0.08, "contraryFlag": False},
    {"title": "ETH flip?", "quantScore": 0.45, "signalTier": "B",
     "curPrice": 0.30, "countSignal": 0.03, "contraryFlag": False},
]


def test_generate_insights_count_between_1_and_6():
    """Max insights = 6 (top-cat, best-A, margin, skip, contrary, staleness)."""
    insights = generate_insights(SAMPLE_RANKING, SAMPLE_OPPS, "2026-03-30")
    assert 1 <= len(insights) <= 6


def test_generate_insights_first_names_top_category():
    insights = generate_insights(SAMPLE_RANKING, SAMPLE_OPPS, "2026-03-30")
    assert "crypto" in insights[0].lower() or "Crypto" in insights[0]


def test_generate_insights_skip_category_mentioned():
    insights = generate_insights(SAMPLE_RANKING, SAMPLE_OPPS, "2026-03-30")
    skip_insight = next((s for s in insights if "skip" in s.lower() or "sports" in s.lower()), None)
    assert skip_insight is not None


def test_generate_insights_stale_model_fires_after_60_days():
    insights = generate_insights(SAMPLE_RANKING, SAMPLE_OPPS, "2024-01-01")
    stale = next((s for s in insights if "days old" in s), None)
    assert stale is not None


def test_generate_insights_fresh_model_no_stale_alert():
    insights = generate_insights(SAMPLE_RANKING, SAMPLE_OPPS, "2026-03-30")
    stale = next((s for s in insights if "days old" in s), None)
    assert stale is None


def test_generate_insights_no_tier_a_still_returns_insights():
    opps_no_a = [{"title": "X", "quantScore": 0.45, "signalTier": "B",
                  "curPrice": 0.5, "countSignal": 0.02, "contraryFlag": False}]
    insights = generate_insights(SAMPLE_RANKING, opps_no_a, "2026-03-30")
    assert len(insights) >= 1


def test_generate_insights_contrarian_alert_fires():
    """contraryFlag = True on any opportunity triggers the contrarian insight."""
    contrary_opps = [
        {"title": "JD Vance 2028", "quantScore": 0.017, "signalTier": "C",
         "curPrice": 0.36, "countSignal": 0.20, "contraryFlag": True},
    ]
    insights = generate_insights(SAMPLE_RANKING, contrary_opps, "2026-03-30")
    contrary_insight = next((s for s in insights if "contrarian" in s.lower()), None)
    assert contrary_insight is not None


def test_generate_insights_contrarian_names_best_market():
    """The contrarian insight should name the market with highest countSignal."""
    opps = [
        {"title": "Market A", "quantScore": 0.01, "signalTier": "C",
         "curPrice": 0.05, "countSignal": 0.15, "contraryFlag": True},
        {"title": "Market B", "quantScore": 0.01, "signalTier": "C",
         "curPrice": 0.05, "countSignal": 0.25, "contraryFlag": True},
    ]
    insights = generate_insights(SAMPLE_RANKING, opps, "2026-03-30")
    contrary_insight = next((s for s in insights if "contrarian" in s.lower()), None)
    assert contrary_insight is not None
    # Market B has higher countSignal — should appear in the insight
    assert "Market B" in contrary_insight


def test_generate_insights_no_contrarian_when_none():
    """If no contraryFlag markets, no contrarian insight is produced."""
    no_contrary = [
        {"title": "M", "quantScore": 0.80, "signalTier": "A",
         "curPrice": 0.55, "countSignal": 0.08, "contraryFlag": False},
    ]
    insights = generate_insights(SAMPLE_RANKING, no_contrary, "2026-03-30")
    assert not any("contrarian" in s.lower() for s in insights)
