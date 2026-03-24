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


# ── score_markets ──────────────────────────────────────────────────────────────

EXPOSURE = {"asset": "BTC", "direction": "long", "risk_type": "risk-off", "scenario": "tariff shock drives BTC down"}

STAGE2_RESPONSE = json.dumps([
    {"slug": "will-bitcoin-dip-to-65000-in-march", "hedge_side": "YES", "correlation_score": 8.5, "narrative": "Pays out directly if BTC crashes."},
    {"slug": "will-the-fed-decrease-interest-rates-march", "hedge_side": "NO", "correlation_score": 5.0, "narrative": "Fed on hold signals risk-off."},
    {"slug": "will-bitcoin-reach-90000-in-march", "hedge_side": "NO", "correlation_score": 7.0, "narrative": "BTC won't reach ATH in a crash."},
])

FLAT_MARKETS = [
    {"slug": "will-bitcoin-dip-to-65000-in-march", "question": "Will Bitcoin dip to $65,000?", "yes_price": 0.25, "volume_24h": 512750.0, "days_left": 14.0},
    {"slug": "will-the-fed-decrease-interest-rates-march", "question": "Will the Fed cut rates?", "yes_price": 0.01, "volume_24h": 12000000.0, "days_left": 0.0},
    {"slug": "will-bitcoin-reach-90000-in-march", "question": "Will Bitcoin reach $90K?", "yes_price": 0.04, "volume_24h": 578852.0, "days_left": 14.0},
]


def test_score_markets_returns_at_most_8():
    from adapters.hedge_engine import score_markets
    # Build 10 items in LLM response
    many = [{"slug": f"slug-{i}", "hedge_side": "YES", "correlation_score": float(10 - i), "narrative": "x"} for i in range(10)]
    markets = [{"slug": f"slug-{i}", "question": f"Q{i}", "yes_price": 0.5, "volume_24h": 1000.0, "days_left": 5.0} for i in range(10)]
    with patch("adapters.hedge_engine.llm_complete", return_value=json.dumps(many)):
        results = score_markets(EXPOSURE, markets, [])
    assert len(results) <= 8


def test_score_markets_sorted_by_correlation_descending():
    from adapters.hedge_engine import score_markets
    with patch("adapters.hedge_engine.llm_complete", return_value=STAGE2_RESPONSE):
        results = score_markets(EXPOSURE, FLAT_MARKETS, [])
    scores = [r["correlation_score"] for r in results]
    assert scores == sorted(scores, reverse=True)


def test_score_markets_filters_below_threshold():
    from adapters.hedge_engine import score_markets
    low_score = json.dumps([
        {"slug": "will-bitcoin-dip-to-65000-in-march", "hedge_side": "YES", "correlation_score": 1.5, "narrative": "weak"},
    ])
    with patch("adapters.hedge_engine.llm_complete", return_value=low_score):
        results = score_markets(EXPOSURE, FLAT_MARKETS, [])
    assert len(results) == 0


def test_score_markets_skips_malformed_items():
    from adapters.hedge_engine import score_markets
    malformed = json.dumps([
        {"slug": "will-bitcoin-dip-to-65000-in-march", "hedge_side": "YES"},  # missing correlation_score
        {"slug": "will-bitcoin-reach-90000-in-march", "hedge_side": "NO", "correlation_score": 7.0, "narrative": "valid"},
    ])
    with patch("adapters.hedge_engine.llm_complete", return_value=malformed):
        results = score_markets(EXPOSURE, FLAT_MARKETS, [])
    assert len(results) == 1
    assert results[0]["slug"] == "will-bitcoin-reach-90000-in-march"


# ── _enrich (cross_signal) ─────────────────────────────────────────────────────

def test_enrich_sets_kelly_data_on_slug_match():
    from adapters.hedge_engine import _enrich
    result = {"slug": "will-bitcoin-dip-to-65000-in-march", "hedge_side": "YES", "correlation_score": 8.5, "narrative": "x"}
    enriched = _enrich(result, KELLY_OPPS)
    assert enriched["kelly_bet"] == 3.5
    assert enriched["smart_money_exposure"] == 78465.0


def test_enrich_cross_signal_true_when_slug_match_and_direction_match():
    from adapters.hedge_engine import _enrich
    # Kelly outcome is "Yes" → normalized to "YES" → matches hedge_side "YES"
    result = {"slug": "will-bitcoin-dip-to-65000-in-march", "hedge_side": "YES", "correlation_score": 8.5, "narrative": "x"}
    enriched = _enrich(result, KELLY_OPPS)
    assert enriched["cross_signal"] is True


def test_enrich_cross_signal_false_when_direction_mismatch():
    from adapters.hedge_engine import _enrich
    # hedge_side NO but Kelly outcome is "Yes" → mismatch
    result = {"slug": "will-bitcoin-dip-to-65000-in-march", "hedge_side": "NO", "correlation_score": 8.5, "narrative": "x"}
    enriched = _enrich(result, KELLY_OPPS)
    assert enriched["cross_signal"] is False


def test_enrich_cross_signal_false_when_no_slug_match():
    from adapters.hedge_engine import _enrich
    result = {"slug": "nonexistent-slug", "hedge_side": "YES", "correlation_score": 5.0, "narrative": "x"}
    enriched = _enrich(result, KELLY_OPPS)
    assert enriched["cross_signal"] is False
    assert enriched["kelly_bet"] is None
    assert enriched["smart_money_exposure"] is None


def test_enrich_normalizes_named_outcome_to_yes():
    from adapters.hedge_engine import _enrich
    # "Stars" is a named outcome → normalized to YES; uses the NHL fixture entry
    result = {"slug": "nhl-dal-min-2026-03-21", "hedge_side": "YES", "correlation_score": 6.0, "narrative": "x"}
    enriched = _enrich(result, KELLY_OPPS)  # KELLY_OPPS fixture has outcome="Stars" for this slug
    assert enriched["cross_signal"] is True


def test_score_markets_propagates_enrichment_fields():
    """score_markets must include kelly_bet, smart_money_exposure, cross_signal in its returned items."""
    from adapters.hedge_engine import score_markets
    with patch("adapters.hedge_engine.llm_complete", return_value=STAGE2_RESPONSE):
        results = score_markets(EXPOSURE, FLAT_MARKETS, KELLY_OPPS)
    btc_result = next((r for r in results if r["slug"] == "will-bitcoin-dip-to-65000-in-march"), None)
    assert btc_result is not None
    assert btc_result["kelly_bet"] == 3.5
    assert btc_result["smart_money_exposure"] == 78465.0
    assert btc_result["cross_signal"] is True  # Kelly outcome "Yes" == hedge_side "YES"
