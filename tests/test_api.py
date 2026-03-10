"""
tests/test_api.py — FastAPI endpoint tests for Alpha Feed backend.

Run:
    pytest tests/test_api.py -v

Requires:
    pip install pytest httpx fastapi
"""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


# ── Patch REPORTS_DIR before importing server ─────────────────────────────────

@pytest.fixture(autouse=True)
def tmp_reports(tmp_path, monkeypatch):
    """Redirect REPORTS_DIR to a temporary directory for each test."""
    import backend.server as srv
    monkeypatch.setattr(srv, "REPORTS_DIR", tmp_path)
    return tmp_path


@pytest.fixture()
def client():
    import backend.server as srv
    return TestClient(srv.app)


# ── Health ────────────────────────────────────────────────────────────────────

def test_health_ok(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "ts" in body
    assert isinstance(body["reports"], list)


# ── Polymarket ────────────────────────────────────────────────────────────────

_FAKE_MARKET = {
    "question": "Will BTC hit $100K?",
    "slug": "btc-100k",
    "endDate": "2026-06-01T00:00:00Z",
    "outcomePrices": "[0.62, 0.38]",
    "liquidity": 250000,
    "volume24hr": 80000,
    "spread": 0.02,
}


def test_polymarket_returns_list(client, monkeypatch):
    import backend.server as srv
    monkeypatch.setattr(srv, "_fetch_polymarket", lambda: [
        {**_FAKE_MARKET, "yesPrice": 0.62, "noPrice": 0.38,
         "resolvesIn": 85.0, "edgeScore": 0.45,
         "uncertainty": 0.76, "liquidityScore": 1.0,
         "spread": 0.02, "volume24hr": 80000, "liquidity": 250000,
         "endDate": "2026-06-01T00:00:00Z"}
    ])
    # Clear cache
    srv._cache.clear()
    r = client.get("/api/polymarket")
    assert r.status_code == 200
    body = r.json()
    assert "markets" in body
    assert body["count"] == 1
    assert body["markets"][0]["resolvesIn"] == 85.0


def test_resolves_in_computed(monkeypatch):
    """_resolves_in parses ISO dates correctly."""
    import backend.server as srv
    # Far future
    result = srv._resolves_in("2030-01-01T00:00:00Z")
    assert result is not None
    assert result > 365

    # No date
    assert srv._resolves_in(None) is None
    assert srv._resolves_in("") is None

    # Malformed
    assert srv._resolves_in("not-a-date") is None


# ── Kelly signals ─────────────────────────────────────────────────────────────

def test_kelly_signals_404_when_missing(client):
    r = client.get("/api/kelly-signals")
    assert r.status_code == 404


def test_kelly_signals_returns_data(client, tmp_reports):
    payload = {"opportunities": [{"title": "Test", "kellyBet": 1.5}], "tradersChecked": 25}
    (tmp_reports / "polytraders.json").write_text(json.dumps(payload))
    r = client.get("/api/kelly-signals")
    assert r.status_code == 200
    assert r.json()["tradersChecked"] == 25


def test_kelly_signals_500_on_invalid_json(client, tmp_reports):
    (tmp_reports / "polytraders.json").write_text("INVALID JSON{{{")
    r = client.get("/api/kelly-signals")
    assert r.status_code == 500


# ── Smart money ───────────────────────────────────────────────────────────────

def test_smart_money_404_when_missing(client):
    r = client.get("/api/smart-money")
    assert r.status_code == 404


def test_smart_money_returns_signals(client, tmp_reports):
    payload = {"signals": [{"question": "BTC 100K?", "side": "YES", "traderCount": 4}], "signalCount": 1}
    (tmp_reports / "hedgepoly.json").write_text(json.dumps(payload))
    r = client.get("/api/smart-money")
    assert r.status_code == 200
    data = r.json()
    assert data["signalCount"] == 1
    assert data["signals"][0]["side"] == "YES"


# ── Overview ──────────────────────────────────────────────────────────────────

def test_overview_structure(client, monkeypatch):
    import backend.server as srv
    monkeypatch.setattr(srv, "_fetch_polymarket", lambda: [
        {"edgeScore": 0.6, "question": "Q1", "resolvesIn": 10.0,
         "yesPrice": 0.5, "noPrice": 0.5, "volume24hr": 1000, "liquidity": 5000,
         "uncertainty": 0.9, "liquidityScore": 0.5, "spread": 0.01, "endDate": None},
        {"edgeScore": 0.1, "question": "Q2", "resolvesIn": 5.0,
         "yesPrice": 0.8, "noPrice": 0.2, "volume24hr": 500, "liquidity": 2000,
         "uncertainty": 0.4, "liquidityScore": 0.3, "spread": 0.02, "endDate": None},
    ])
    srv._cache.clear()
    r = client.get("/api/overview")
    assert r.status_code == 200
    body = r.json()
    assert "polymarket" in body
    assert body["polymarket"]["total"] == 2
    assert body["polymarket"]["highEdge"] == 1  # only edgeScore > 0.3
