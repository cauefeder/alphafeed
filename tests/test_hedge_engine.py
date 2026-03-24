# tests/test_hedge_engine.py
import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

FIXTURES = Path(__file__).parent / "fixtures"
POLY2_FIXTURE = json.loads((FIXTURES / "poly2_fixture.json").read_text())
PT_FIXTURE = json.loads((FIXTURES / "polytraders_fixture.json").read_text())
KELLY_OPPS = PT_FIXTURE["opportunities"]

# ── _flatten_markets ───────────────────────────────────────────────────────────

def test_flatten_markets_returns_flat_list():
    from adapters.hedge_engine import _flatten_markets
    with patch("adapters.hedge_engine._load_poly2", return_value=POLY2_FIXTURE):
        markets = _flatten_markets()
    assert len(markets) == 3  # 2 crypto + 1 macro


def test_flatten_markets_required_fields():
    from adapters.hedge_engine import _flatten_markets
    with patch("adapters.hedge_engine._load_poly2", return_value=POLY2_FIXTURE):
        markets = _flatten_markets()
    for m in markets:
        assert "slug" in m
        assert "question" in m
        assert "yes_price" in m
        assert "volume_24h" in m
        assert "days_left" in m
        # Must NOT contain extra fields
        assert "volume_total" not in m
        assert "liquidity" not in m


# ── parse_exposure ─────────────────────────────────────────────────────────────

def test_parse_exposure_short_circuit_skips_llm():
    """When asset + risk_type both supplied, Stage 1 LLM is NOT called."""
    from adapters.hedge_engine import parse_exposure
    call_count = {"n": 0}

    def fake_complete(prompt):
        call_count["n"] += 1
        return '{"asset": "BTC", "direction": "long", "risk_type": "risk-off", "scenario": "test"}'

    with patch("adapters.hedge_engine.llm_complete", side_effect=fake_complete):
        result = parse_exposure("I hold BTC", asset="BTC", risk_type="risk-off")

    assert call_count["n"] == 0  # short-circuit: LLM not called
    assert result["asset"] == "BTC"
    assert result["risk_type"] == "risk-off"
    assert result["direction"] == "long"
    assert result["scenario"] == "I hold BTC"


def test_parse_exposure_calls_llm_when_fields_missing():
    from adapters.hedge_engine import parse_exposure
    llm_response = '{"asset": "BTC", "direction": "long", "risk_type": "risk-off", "scenario": "tariff shock"}'

    with patch("adapters.hedge_engine.llm_complete", return_value=llm_response) as mock_llm:
        result = parse_exposure("I hold 2 BTC, worried about tariffs", asset="", risk_type="")

    mock_llm.assert_called_once()
    assert result["asset"] == "BTC"
    assert result["direction"] == "long"
    assert result["scenario"] == "tariff shock"


def test_parse_exposure_returns_required_keys():
    from adapters.hedge_engine import parse_exposure
    llm_response = '{"asset": "tech stocks", "direction": "long", "risk_type": "recession", "scenario": "GDP shrinks"}'

    with patch("adapters.hedge_engine.llm_complete", return_value=llm_response):
        result = parse_exposure("I work in tech", asset=None, risk_type=None)

    for key in ("asset", "direction", "risk_type", "scenario"):
        assert key in result
