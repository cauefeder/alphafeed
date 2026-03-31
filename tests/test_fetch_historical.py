"""Tests for fetch_historical.py — mock Gamma API."""
import csv
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "backend/adapters"))


REQUIRED_COLUMNS = [
    "slug", "question", "category",
    "yes_price", "volume_24h", "volume_total", "liquidity", "days_left",
    "resolved_yes",
]


def _make_market(slug="test-slug",
                 last_trade_price=0.65,
                 outcome_prices="[1, 0]",      # settled: Yes won
                 volume_total=100000,
                 start_date="2026-01-01T00:00:00Z",
                 end_date="2026-04-01T00:00:00Z",
                 tags=None):
    return {
        "slug": slug,
        "question": f"Question for {slug}",
        "lastTradePrice": last_trade_price,
        "outcomePrices": outcome_prices,
        "volume24hr": None,                  # not available for closed markets
        "volumeNum": volume_total,
        "liquidity": None,                   # not available for closed markets
        "startDate": start_date,
        "endDate": end_date,
        "tags": tags or [{"label": "Politics"}],
    }


def test_fetch_page_extracts_required_columns(tmp_path):
    from fetch_historical import parse_market
    market = _make_market()
    row = parse_market(market)
    assert row is not None
    for col in REQUIRED_COLUMNS:
        assert col in row, f"Missing column: {col}"


def test_fetch_page_skips_missing_last_trade_price():
    from fetch_historical import parse_market
    market = _make_market()
    market["lastTradePrice"] = None
    assert parse_market(market) is None


def test_fetch_page_skips_price_at_boundary():
    """lastTradePrice of 0 or 1 means market was never meaningfully traded — skip."""
    from fetch_historical import parse_market
    assert parse_market(_make_market(last_trade_price=0.0)) is None
    assert parse_market(_make_market(last_trade_price=1.0)) is None


def test_fetch_page_skips_unsettled_outcome_prices():
    """outcomePrices not at 0/1 means market not fully resolved."""
    from fetch_historical import parse_market
    market = _make_market(outcome_prices="[0.65, 0.35]")
    assert parse_market(market) is None


def test_parse_market_yes_price_from_last_trade_price():
    """yes_price should reflect crowd's pre-resolution belief (lastTradePrice)."""
    from fetch_historical import parse_market
    market = _make_market(last_trade_price=0.72, outcome_prices="[1, 0]")
    row = parse_market(market)
    assert row is not None
    assert float(row["yes_price"]) == pytest.approx(0.72)


def test_parse_market_resolved_yes_inferred_no():
    """outcomePrices ['0','1'] => No won => resolved_yes = 0."""
    from fetch_historical import parse_market
    market = _make_market(last_trade_price=0.3, outcome_prices="[0, 1]")
    row = parse_market(market)
    assert row is not None
    assert row["resolved_yes"] == 0


def test_parse_market_category_from_tags():
    from fetch_historical import parse_market
    market = _make_market(tags=[{"label": "Crypto"}])
    row = parse_market(market)
    assert row["category"].lower() == "crypto"


def test_csv_output_has_required_columns(tmp_path):
    from fetch_historical import write_csv
    rows = [
        {"slug": "s1", "question": "Q1", "category": "macro",
         "yes_price": 0.6, "volume_24h": 0, "volume_total": 10000,
         "liquidity": 0, "days_left": 90, "resolved_yes": 1},
    ]
    out = tmp_path / "test.csv"
    write_csv(rows, out)
    with open(out) as f:
        reader = csv.DictReader(f)
        cols = reader.fieldnames
    for col in REQUIRED_COLUMNS:
        assert col in cols
