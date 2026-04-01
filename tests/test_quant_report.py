"""Integration tests for quant_report.py — uses fixtures, mocks the model."""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "backend/adapters"))
from quant_features import FEATURE_NAMES


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_calibration():
    return {"platt_a": 0.0, "platt_b": 1.0, "feature_names": FEATURE_NAMES}


def _make_model(score: float = 0.7):
    m = MagicMock()
    m.predict_proba.return_value = np.array([[1 - score, score]])
    return m


def _make_opp(**kwargs):
    """Minimal valid opportunity with all new fields defaulted."""
    base = {
        "title": "Test Market",
        "slug": "test-slug",
        "curPrice": 0.55,
        "kellyBet": 3.0,
        "nSmartTraders": 2,
        "totalExposure": 10000,
        "countSignal": 0.05,
        "sizeSignal": 1.0,
        "estimatedEdge": 0.05,
        "url": "https://polymarket.com/event/test",
    }
    return {**base, **kwargs}


SAMPLE_POLYTRADERS = {
    "opportunities": [
        _make_opp(title="BTC 90k?", slug="btc-90k", curPrice=0.62,
                  countSignal=0.08, kellyBet=4.2, totalExposure=20000),
        _make_opp(title="ETH flip?", slug="eth-flip", curPrice=0.25,
                  countSignal=0.03, kellyBet=1.5, totalExposure=8000),
    ]
}

SAMPLE_POLY2 = {
    "categories": {
        "crypto": {
            "markets": [
                {"question": "BTC hits 90k?", "slug": "btc-90k",
                 "yes_price": 0.62, "volume_24h": 50000, "volume_total": 500000,
                 "liquidity": 200000, "days_left": 14,
                 "url": "https://polymarket.com/event/btc-90k"},
            ]
        }
    }
}

SAMPLE_METRICS = {"modelVersion": "2026-03-30", "testAuc": 0.628}


# ── score_opportunity — base behaviour ────────────────────────────────────────

def test_score_opportunity_returns_quant_score():
    from quant_report import score_opportunity
    result = score_opportunity(_make_opp(curPrice=0.6, volume_24h=10000,
                                         volumeTotal=100000, liquidity=50000,
                                         days_left=14),
                               _make_model(0.75), _make_calibration())
    assert result["quantScore"] == pytest.approx(0.75, rel=1e-3)


def test_score_opportunity_tier_a():
    from quant_report import score_opportunity
    result = score_opportunity(_make_opp(curPrice=0.5), _make_model(0.70), _make_calibration())
    assert result["signalTier"] == "A"


def test_score_opportunity_tier_b():
    from quant_report import score_opportunity
    result = score_opportunity(_make_opp(curPrice=0.5), _make_model(0.50), _make_calibration())
    assert result["signalTier"] == "B"


def test_score_opportunity_tier_c():
    from quant_report import score_opportunity
    result = score_opportunity(_make_opp(curPrice=0.5), _make_model(0.30), _make_calibration())
    assert result["signalTier"] == "C"


def test_score_opportunity_uses_feature_names_order():
    """Model must receive features in FEATURE_NAMES canonical order."""
    from quant_report import score_opportunity
    captured = []

    def capture_proba(X):
        captured.append(X.tolist())
        return np.array([[0.3, 0.7]])

    model = MagicMock()
    model.predict_proba.side_effect = capture_proba
    score_opportunity(_make_opp(curPrice=0.6, volume_24h=10000, days_left=14),
                      model, _make_calibration())
    X = captured[0][0]
    assert X[0] == pytest.approx(0.6)   # yes_price is index 0 in FEATURE_NAMES
    assert X[-1] == pytest.approx(0.2)  # price_extremity = abs(0.6-0.5)*2


# ── score_opportunity — convergentScore ───────────────────────────────────────

def test_score_opportunity_convergent_score_is_product():
    """convergentScore = quantScore × countSignal."""
    from quant_report import score_opportunity
    opp = _make_opp(curPrice=0.55, countSignal=0.12)
    result = score_opportunity(opp, _make_model(0.80), _make_calibration())
    assert result["convergentScore"] == pytest.approx(0.80 * 0.12, rel=1e-3)


def test_score_opportunity_convergent_score_zero_when_no_count():
    """No countSignal → convergentScore = 0."""
    from quant_report import score_opportunity
    opp = _make_opp(curPrice=0.55, countSignal=0.0)
    result = score_opportunity(opp, _make_model(0.85), _make_calibration())
    assert result["convergentScore"] == pytest.approx(0.0)


def test_score_opportunity_convergent_score_bounded():
    """convergentScore is always <= quantScore (countSignal ∈ [0, 1])."""
    from quant_report import score_opportunity
    opp = _make_opp(curPrice=0.55, countSignal=0.20)
    result = score_opportunity(opp, _make_model(0.90), _make_calibration())
    assert result["convergentScore"] <= result["quantScore"] + 1e-9


# ── score_opportunity — contraryFlag ──────────────────────────────────────────

def test_score_opportunity_contrary_flag_fires():
    """contraryFlag = True when quantScore < 0.20 and countSignal > 0.10."""
    from quant_report import score_opportunity
    # Low quantScore (crowd certain), high countSignal (many traders disagree)
    opp = _make_opp(curPrice=0.05, countSignal=0.15)
    result = score_opportunity(opp, _make_model(0.05), _make_calibration())
    assert result["contraryFlag"] is True


def test_score_opportunity_contrary_flag_false_high_count_but_uncertain():
    """Not contrary when quantScore >= 0.20 (crowd is uncertain)."""
    from quant_report import score_opportunity
    opp = _make_opp(curPrice=0.55, countSignal=0.20)
    result = score_opportunity(opp, _make_model(0.80), _make_calibration())
    assert result["contraryFlag"] is False


def test_score_opportunity_contrary_flag_false_low_count():
    """Not contrary when countSignal <= 0.10 even if crowd is certain."""
    from quant_report import score_opportunity
    opp = _make_opp(curPrice=0.02, countSignal=0.05)
    result = score_opportunity(opp, _make_model(0.02), _make_calibration())
    assert result["contraryFlag"] is False


def test_score_opportunity_contrary_flag_exact_boundary():
    """Boundary conditions: countSignal=0.10 is NOT > 0.10 (strict inequality)."""
    from quant_report import score_opportunity
    opp = _make_opp(curPrice=0.05, countSignal=0.10)
    result = score_opportunity(opp, _make_model(0.10), _make_calibration())
    assert result["contraryFlag"] is False  # 0.10 is not > 0.10


# ── _infer_category_from_slug ─────────────────────────────────────────────────

def test_infer_category_nba_slug():
    from quant_report import _infer_category_from_slug
    assert _infer_category_from_slug("nba-lal-gsw-2026-03-31") == "sports"


def test_infer_category_uef_slug():
    from quant_report import _infer_category_from_slug
    assert _infer_category_from_slug("uef-cze-den-2026-03-31-den") == "sports"


def test_infer_category_atp_slug():
    from quant_report import _infer_category_from_slug
    assert _infer_category_from_slug("atp-ellis-honda-2026-03-29") == "sports"


def test_infer_category_crypto_from_slug():
    from quant_report import _infer_category_from_slug
    assert _infer_category_from_slug("will-bitcoin-hit-100k-in-2026") == "crypto"


def test_infer_category_politics_from_title():
    from quant_report import _infer_category_from_slug
    # 'vance' keyword should map to politics
    assert _infer_category_from_slug("some-random-slug", title="Will JD Vance win 2028") == "politics"


def test_infer_category_geopolitics_from_slug():
    from quant_report import _infer_category_from_slug
    assert _infer_category_from_slug("will-the-us-acquire-any-part-of-greenland-in-2026") == "geopolitics"


def test_infer_category_falls_back_to_other():
    from quant_report import _infer_category_from_slug
    assert _infer_category_from_slug("will-aliens-confirm-existence-2027") == "other"


# ── fetch_gamma_enrichment ────────────────────────────────────────────────────

def test_fetch_gamma_enrichment_returns_expected_fields():
    """When Gamma API returns a valid market, all enrichment fields are present."""
    from quant_report import fetch_gamma_enrichment
    fake_market = [{
        "volume24hr": 12345.0,
        "volumeNum": 987654.0,
        "liquidity": 55000.0,
        "endDate": "2026-06-30T00:00:00Z",
        "events": [],
        "slug": "test-slug",
    }]
    with patch("quant_report.httpx.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.json.return_value = fake_market
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        result = fetch_gamma_enrichment(["test-slug"])

    assert "test-slug" in result
    entry = result["test-slug"]
    assert entry["volume_24h"] == pytest.approx(12345.0)
    assert entry["volume_total"] == pytest.approx(987654.0)
    assert entry["liquidity"] == pytest.approx(55000.0)
    assert "_category" in entry
    assert "days_left" in entry


def test_fetch_gamma_enrichment_skips_on_http_error():
    """Network or HTTP errors are silently swallowed — returns empty dict."""
    from quant_report import fetch_gamma_enrichment
    with patch("quant_report.httpx.get") as mock_get:
        mock_get.side_effect = Exception("timeout")
        result = fetch_gamma_enrichment(["bad-slug"])
    assert result == {}


def test_fetch_gamma_enrichment_skips_empty_response():
    """Empty list response → slug not included in enrichment."""
    from quant_report import fetch_gamma_enrichment
    with patch("quant_report.httpx.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.json.return_value = []
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp
        result = fetch_gamma_enrichment(["no-market"])
    assert "no-market" not in result


# ── run_inference ─────────────────────────────────────────────────────────────

def test_skip_opportunity_missing_cur_price():
    from quant_report import run_inference
    polytraders = {"opportunities": [{"slug": "no-price", "title": "Missing"}]}
    result = run_inference(polytraders, {"categories": {}}, _make_model(0.7),
                           _make_calibration(), SAMPLE_METRICS)
    assert result["summary"]["totalScored"] == 0


def test_poly2_slug_merge():
    """Opportunity matched by slug gets poly2 volume/liquidity enrichment."""
    from quant_report import run_inference
    result = run_inference(SAMPLE_POLYTRADERS, SAMPLE_POLY2, _make_model(0.7),
                           _make_calibration(), SAMPLE_METRICS)
    opp = next((o for o in result["opportunities"] if o["slug"] == "btc-90k"), None)
    assert opp is not None
    assert opp["volume_24h"] == 50000


def test_gamma_enrichment_used_when_poly2_misses():
    """Opportunity with slug missing from poly2 receives gamma_enrichment data."""
    from quant_report import run_inference
    polytraders = {"opportunities": [_make_opp(slug="sports-slug", curPrice=0.55)]}
    gamma = {"sports-slug": {
        "volume_24h": 99000, "volume_total": 500000,
        "liquidity": 30000, "days_left": 3, "_category": "sports",
    }}
    result = run_inference(polytraders, {"categories": {}}, _make_model(0.7),
                           _make_calibration(), SAMPLE_METRICS,
                           gamma_enrichment=gamma)
    opp = result["opportunities"][0]
    assert opp["volume_24h"] == 99000
    assert opp["category"] == "sports"


def test_poly2_takes_priority_over_gamma_enrichment():
    """When both poly2 and gamma have data for a slug, poly2 wins."""
    from quant_report import run_inference
    gamma = {"btc-90k": {
        "volume_24h": 1,  # should be overridden by poly2 value of 50000
        "volume_total": 1, "liquidity": 1, "days_left": 1, "_category": "other",
    }}
    result = run_inference(SAMPLE_POLYTRADERS, SAMPLE_POLY2, _make_model(0.7),
                           _make_calibration(), SAMPLE_METRICS,
                           gamma_enrichment=gamma)
    opp = next(o for o in result["opportunities"] if o["slug"] == "btc-90k")
    assert opp["volume_24h"] == 50000  # poly2 value, not gamma's 1


def test_run_inference_empty_opportunities():
    from quant_report import run_inference
    result = run_inference({"opportunities": []}, SAMPLE_POLY2, _make_model(),
                           _make_calibration(), SAMPLE_METRICS)
    assert result["summary"]["totalScored"] == 0
    assert result["opportunities"] == []


def test_run_inference_output_has_required_keys():
    from quant_report import run_inference
    result = run_inference(SAMPLE_POLYTRADERS, SAMPLE_POLY2, _make_model(0.7),
                           _make_calibration(), SAMPLE_METRICS)
    for key in ["generatedAt", "weekOf", "modelVersion", "modelAuc", "summary",
                "opportunities", "categoryReport", "edgeRanking", "insights",
                "categoryTrends"]:
        assert key in result, f"Missing key: {key}"


def test_run_inference_opportunities_have_new_fields():
    """Every scored opportunity must expose convergentScore and contraryFlag."""
    from quant_report import run_inference
    result = run_inference(SAMPLE_POLYTRADERS, SAMPLE_POLY2, _make_model(0.7),
                           _make_calibration(), SAMPLE_METRICS)
    for opp in result["opportunities"]:
        assert "convergentScore" in opp, "Missing convergentScore"
        assert "contraryFlag" in opp, "Missing contraryFlag"


def test_run_inference_category_report_aggregation():
    from quant_report import run_inference
    result = run_inference(SAMPLE_POLYTRADERS, SAMPLE_POLY2, _make_model(0.7),
                           _make_calibration(), SAMPLE_METRICS)
    cat_report = result["categoryReport"]
    for cat_data in cat_report.values():
        assert 0 <= cat_data["avgQuantScore"] <= 1


def test_topSignalCategory_requires_min_3_markets():
    """topSignalCategory must come from a category with >= 3 opportunities."""
    from quant_report import run_inference
    # Build 5 opps: 1 in "tiny" (very high q) and 4 in "geopolitics" (lower q)
    opps = [_make_opp(slug=f"geo-{i}", title=f"Ukraine {i}", curPrice=0.55,
                      countSignal=0.08)
            for i in range(4)]
    opps.append(_make_opp(slug="one-off", title="Singleton market", curPrice=0.55))
    polytraders = {"opportunities": opps}
    # Tiny category has 1 market; geopolitics has 4
    gamma = {f"geo-{i}": {"volume_24h": 0, "volume_total": 0, "liquidity": 0,
                           "days_left": 30, "_category": "geopolitics"}
             for i in range(4)}
    gamma["one-off"] = {"volume_24h": 0, "volume_total": 0, "liquidity": 0,
                        "days_left": 30, "_category": "tiny_category"}

    def model_fn(score_map):
        """Returns different scores depending on category."""
        m = MagicMock()
        def proba(X):
            # "tiny_category" slug returns 0.99, geopolitics 0.60
            return np.array([[0.01, 0.99]])
        m.predict_proba.side_effect = proba
        return m

    result = run_inference(polytraders, {"categories": {}}, _make_model(0.99),
                           _make_calibration(), SAMPLE_METRICS,
                           gamma_enrichment=gamma)
    # topSignalCategory should NOT be tiny_category (only 1 market)
    # It should be whatever has >= 3 markets (geopolitics in this case)
    assert result["summary"]["topSignalCategory"] != "tiny_category"


# ── Telegram ──────────────────────────────────────────────────────────────────

def test_telegram_message_under_4096_chars():
    """Full report message must fit Telegram's 4096-char limit."""
    sys.path.insert(0, str(Path(__file__).parent.parent / "backend/adapters"))
    from quant_telegram import format_message
    from quant_report import run_inference

    polytraders = {
        "opportunities": [
            _make_opp(title=f"Market {i}", slug=f"slug-{i}",
                      curPrice=0.5 + i * 0.01, countSignal=0.05)
            for i in range(20)
        ]
    }
    result = run_inference(polytraders, SAMPLE_POLY2, _make_model(0.7),
                           _make_calibration(), SAMPLE_METRICS)
    msg = format_message(result)
    assert len(msg) <= 4096, f"Message too long: {len(msg)} chars"
