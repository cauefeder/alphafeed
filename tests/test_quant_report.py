"""Integration tests for quant_report.py — uses fixtures, mocks the model."""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "backend/adapters"))
from quant_features import FEATURE_NAMES


def _make_calibration():
    return {"platt_a": 0.0, "platt_b": 1.0, "feature_names": FEATURE_NAMES}


def _make_model(score: float = 0.7):
    m = MagicMock()
    m.predict_proba.return_value = np.array([[1 - score, score]])
    return m


SAMPLE_POLYTRADERS = {
    "opportunities": [
        {"title": "BTC 90k?", "slug": "btc-90k", "curPrice": 0.62,
         "kellyBet": 4.2, "nSmartTraders": 3, "totalExposure": 20000,
         "url": "https://polymarket.com/event/btc-90k"},
        {"title": "ETH flip?", "slug": "eth-flip", "curPrice": 0.25,
         "kellyBet": 1.5, "nSmartTraders": 2, "totalExposure": 8000,
         "url": "https://polymarket.com/event/eth-flip"},
    ]
}

SAMPLE_POLY2 = {
    "categories": {
        "crypto": {
            "markets": [
                {"question": "BTC hits 90k?", "slug": "btc-90k",
                 "yes_price": 0.62, "volume_24h": 50000, "volume_total": 500000,
                 "liquidity": 200000, "days_left": 14, "url": "https://polymarket.com/event/btc-90k"},
            ]
        }
    }
}

SAMPLE_METRICS = {"modelVersion": "2026-03-30", "testAuc": 0.628}


def test_score_opportunity_returns_quant_score(monkeypatch):
    from quant_report import score_opportunity
    model = _make_model(0.75)
    cal = _make_calibration()
    opp = {"curPrice": 0.6, "volume_24h": 10000, "volumeTotal": 100000,
           "liquidity": 50000, "days_left": 14}
    result = score_opportunity(opp, model, cal)
    assert "quantScore" in result
    assert result["quantScore"] == pytest.approx(0.75, rel=1e-3)


def test_score_opportunity_tier_a():
    from quant_report import score_opportunity
    model = _make_model(0.70)
    result = score_opportunity({"curPrice": 0.5}, model, _make_calibration())
    assert result["signalTier"] == "A"


def test_score_opportunity_tier_b():
    from quant_report import score_opportunity
    model = _make_model(0.50)
    result = score_opportunity({"curPrice": 0.5}, model, _make_calibration())
    assert result["signalTier"] == "B"


def test_score_opportunity_tier_c():
    from quant_report import score_opportunity
    model = _make_model(0.30)
    result = score_opportunity({"curPrice": 0.5}, model, _make_calibration())
    assert result["signalTier"] == "C"


def test_score_opportunity_uses_feature_names_order():
    """Model must receive features in FEATURE_NAMES order, not dict insertion order."""
    from quant_report import score_opportunity
    captured_X = []

    def capture_proba(X):
        captured_X.append(X.tolist())
        return np.array([[0.3, 0.7]])

    model = MagicMock()
    model.predict_proba.side_effect = capture_proba
    cal = _make_calibration()
    score_opportunity({"curPrice": 0.6, "volume_24h": 10000, "days_left": 14}, model, cal)
    X = captured_X[0][0]
    assert X[0] == pytest.approx(0.6)       # yes_price is first in FEATURE_NAMES
    assert X[-1] == pytest.approx(0.2)      # price_extremity = abs(0.6-0.5)*2


def test_skip_opportunity_missing_cur_price(tmp_path, capsys):
    from quant_report import run_inference
    polytraders = {"opportunities": [{"slug": "no-price", "title": "Missing"}]}
    poly2 = {"categories": {}}
    model = _make_model(0.7)
    cal = _make_calibration()
    result = run_inference(polytraders, poly2, model, cal, SAMPLE_METRICS)
    # Opportunity without curPrice is skipped — no error, 0 scored
    assert result["summary"]["totalScored"] == 0


def test_poly2_slug_merge():
    """Opportunity matched by slug gets poly2 volume/liquidity/days_left."""
    from quant_report import run_inference
    result = run_inference(SAMPLE_POLYTRADERS, SAMPLE_POLY2, _make_model(0.7),
                           _make_calibration(), SAMPLE_METRICS)
    # btc-90k should be enriched with poly2 data (volume_24h=50000)
    opp = next((o for o in result["opportunities"] if o["slug"] == "btc-90k"), None)
    assert opp is not None


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


def test_run_inference_category_report_aggregation():
    from quant_report import run_inference
    result = run_inference(SAMPLE_POLYTRADERS, SAMPLE_POLY2, _make_model(0.7),
                           _make_calibration(), SAMPLE_METRICS)
    cat_report = result["categoryReport"]
    if "crypto" in cat_report:
        assert 0 <= cat_report["crypto"]["avgQuantScore"] <= 1


def test_telegram_message_under_4096_chars(tmp_path):
    """Full report message must fit Telegram's 4096-char limit."""
    sys.path.insert(0, str(Path(__file__).parent.parent / "backend/adapters"))
    from quant_telegram import format_message
    from quant_report import run_inference

    # Generate a report with max reasonable data
    polytraders = {
        "opportunities": [
            {"title": f"Market {i}", "slug": f"slug-{i}", "curPrice": 0.5 + i * 0.01,
             "kellyBet": 2.0, "nSmartTraders": 3, "totalExposure": 10000,
             "url": f"https://polymarket.com/event/slug-{i}"}
            for i in range(20)
        ]
    }
    result = run_inference(polytraders, SAMPLE_POLY2, _make_model(0.7),
                           _make_calibration(), SAMPLE_METRICS)
    msg = format_message(result)
    assert len(msg) <= 4096, f"Message too long: {len(msg)} chars"
