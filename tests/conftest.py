"""
tests/conftest.py — Shared pytest fixtures for the AlphaFeed test suite.
"""
import json
from pathlib import Path

import pytest


@pytest.fixture()
def reports_dir(tmp_path: Path) -> Path:
    """Return a temporary directory suitable for use as REPORTS_DIR."""
    return tmp_path


@pytest.fixture()
def fake_polytraders_report() -> dict:
    """Minimal valid polytraders.json structure."""
    return {
        "generatedAt": "2026-01-01T00:00:00+00:00",
        "timePeriod": "WEEK",
        "bankroll": 100.0,
        "tradersChecked": 1,
        "positionsScanned": 1,
        "opportunities": [
            {
                "title": "Will BTC hit $100K?",
                "outcome": "Yes",
                "slug": "btc-100k",
                "url": "https://polymarket.com/event/btc-100k",
                "curPrice": 0.62,
                "estimatedEdge": 0.048,
                "kellyBet": 2.10,
                "kellyFull": 0.084,
                "nSmartTraders": 4,
                "totalTradersChecked": 25,
                "smartTraderNames": ["trader_a"],
                "countSignal": 0.16,
                "sizeSignal": 0.72,
                "totalExposure": 18400.0,
                "weightedAvgEntry": 0.59,
            }
        ],
    }


@pytest.fixture()
def fake_hedgepoly_report() -> dict:
    """Minimal valid hedgepoly.json structure."""
    return {
        "generatedAt": "2026-01-01T00:00:00+00:00",
        "signalCount": 1,
        "signals": [
            {
                "marketSlug": "btc-100k",
                "question": "Will BTC hit $100K?",
                "side": "YES",
                "yesValue": 22000.0,
                "noValue": 4800.0,
                "totalValue": 26800.0,
                "traderCount": 5,
                "confidence": 0.82,
                "url": "https://polymarket.com/event/btc-100k",
            }
        ],
    }
