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

from unittest.mock import patch
from llm_client import LLMError

MOCK_HEDGE_RESPONSE = {
    "exposure_parsed": {"asset": "BTC", "direction": "long", "risk_type": "risk-off", "scenario": "crash"},
    "hedges": [
        {
            "question": "Will BTC dip to $65K?", "url": "https://polymarket.com/event/x",
            "slug": "btc-65k", "hedge_side": "YES", "correlation_score": 8.5,
            "narrative": "Pays out if BTC crashes.", "yes_price": 0.25,
            "volume_24h": 512750.0, "days_left": 14.0,
            "kelly_bet": 3.5, "smart_money_exposure": 78465.0, "cross_signal": True,
        }
    ],
}


def test_hedge_session_200(client):
    with patch("backend.server.run_hedge_session", return_value=MOCK_HEDGE_RESPONSE):
        resp = client.post("/api/hedge-session", json={"exposure": "I hold BTC"})
    assert resp.status_code == 200
    body = resp.json()
    assert "exposure_parsed" in body
    assert "hedges" in body
    assert body["hedges"][0]["cross_signal"] is True


def test_hedge_session_422_on_missing_exposure(client):
    resp = client.post("/api/hedge-session", json={"asset": "BTC"})
    assert resp.status_code == 422


def test_hedge_session_504_on_llm_error(client):
    with patch("backend.server.run_hedge_session", side_effect=LLMError("timeout")):
        resp = client.post("/api/hedge-session", json={"exposure": "I hold BTC"})
    assert resp.status_code == 504


def test_hedge_session_rate_limited(client):
    """POST /api/hedge-session shares the 30/minute rate limit."""
    # Hit the endpoint 31 times — the 31st should be rate-limited (429)
    with patch("backend.server.run_hedge_session", return_value=MOCK_HEDGE_RESPONSE):
        responses = [client.post("/api/hedge-session", json={"exposure": "test"}) for _ in range(31)]
    status_codes = [r.status_code for r in responses]
    assert 429 in status_codes


def test_hedge_session_cors_allows_post(client):
    # Use "*" wildcard origin (server default when ALLOWED_ORIGINS not set in test env)
    resp = client.options(
        "/api/hedge-session",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"},
    )
    # CORSMiddleware returns 200 for preflight if origin + method are allowed
    assert resp.status_code == 200
