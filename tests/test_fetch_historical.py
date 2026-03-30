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


def _make_market(slug="test-slug", outcome_prices="[0.65, 0.35]",
                 volume24hr=10000, volume_total=100000,
                 liquidity=50000, end_date="2026-04-01T00:00:00Z",
                 resolved_yes=1, tags=None):
    return {
        "slug": slug,
        "question": f"Question for {slug}",
        "outcomePrices": outcome_prices,
        "volume24hr": volume24hr,
        "volumeTotal": volume_total,
        "liquidity": liquidity,
        "endDate": end_date,
        "resolvedYes": resolved_yes,
        "tags": tags or [{"label": "Politics"}],
    }


def test_fetch_page_extracts_required_columns(tmp_path):
    from fetch_historical import parse_market
    market = _make_market()
    row = parse_market(market)
    assert row is not None
    for col in REQUIRED_COLUMNS:
        assert col in row, f"Missing column: {col}"


def test_fetch_page_skips_missing_outcome_prices(tmp_path):
    from fetch_historical import parse_market
    market = _make_market(outcome_prices=None)
    assert parse_market(market) is None


def test_fetch_page_skips_empty_outcome_prices():
    from fetch_historical import parse_market
    market = _make_market(outcome_prices="[]")
    assert parse_market(market) is None


def test_parse_market_yes_price_from_outcome_prices():
    from fetch_historical import parse_market
    market = _make_market(outcome_prices="[0.72, 0.28]")
    row = parse_market(market)
    assert float(row["yes_price"]) == pytest.approx(0.72)


def test_parse_market_category_from_tags():
    from fetch_historical import parse_market
    market = _make_market(tags=[{"label": "Crypto"}])
    row = parse_market(market)
    assert row["category"].lower() == "crypto"


def test_csv_output_has_required_columns(tmp_path):
    from fetch_historical import write_csv
    rows = [
        {"slug": "s1", "question": "Q1", "category": "macro",
         "yes_price": 0.6, "volume_24h": 1000, "volume_total": 10000,
         "liquidity": 5000, "days_left": 14, "resolved_yes": 1},
    ]
    out = tmp_path / "test.csv"
    write_csv(rows, out)
    with open(out) as f:
        reader = csv.DictReader(f)
        cols = reader.fieldnames
    for col in REQUIRED_COLUMNS:
        assert col in cols
