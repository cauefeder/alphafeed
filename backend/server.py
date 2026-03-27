"""
Alpha Feed — FastAPI backend.

Serves as:
  1. CORS proxy + enrichment layer for Polymarket data (adds resolvesIn field)
  2. Reader for reports/*.json written by adapter scripts

Endpoints
---------
  GET /api/health          — liveness check
  GET /api/polymarket      — Polymarket markets with resolvesIn field (5-min cache)
  GET /api/overview        — high-level summary stats (5-min cache)
  GET /api/kelly-signals   — PolyTraders Kelly opportunities (from reports/polytraders.json)
  GET /api/smart-money     — HedgePoly smart-money signals (from reports/hedgepoly.json)
  GET /api/macro-report    — Poly2 macro market categories (from reports/poly2.json)

Run
---
  pip install -r requirements.txt
  uvicorn server:app --reload --port 8000
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
logger = logging.getLogger("alphafeed")

# ── Config ────────────────────────────────────────────────────────────────────

REPORTS_DIR = Path(__file__).parent.parent / "reports"
POLY_URL = "https://gamma-api.polymarket.com/markets"

_raw_origins = os.environ.get("ALLOWED_ORIGINS", "*")
ALLOWED_ORIGINS: list[str] = (
    ["*"] if _raw_origins.strip() == "*"
    else [o.strip() for o in _raw_origins.split(",") if o.strip()]
)

if ALLOWED_ORIGINS == ["*"]:
    logger.warning(
        "ALLOWED_ORIGINS is '*' — set ALLOWED_ORIGINS env var before exposing this API publicly"
    )

CACHE_TTL = {
    "polymarket": 300,   # 5 minutes
    "overview": 300,
}

# ── Scoring constants ─────────────────────────────────────────────────────────
# Liquidity above this value caps the liquidity score at 1.0
_LIQ_NORM: int = 200_000
# 24h volume above this threshold gets full edge weight (below gets 0.5×)
_VOL_BOOST_THRESHOLD: int = 50_000
# edgeScore above this is considered "high edge" for the overview endpoint
_EDGE_HIGH_THRESHOLD: float = 0.3

_cache: dict[str, tuple[float, object]] = {}
_cache_lock = threading.Lock()

# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(title="Alpha Feed API", version="1.0.0", docs_url="/docs", redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET"],
    allow_headers=["Content-Type", "Accept"],
    max_age=600,
)


@app.middleware("http")
async def security_headers(request: Request, call_next) -> Response:
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Cache-Control"] = "no-store"
    return response

# ── Helpers ───────────────────────────────────────────────────────────────────


def _cached(key: str, ttl: int, fetch_fn):
    """Return cached value if fresh, otherwise call fetch_fn and cache result."""
    now = time.monotonic()
    with _cache_lock:
        if key in _cache:
            ts, data = _cache[key]
            if now - ts < ttl:
                return data
    data = fetch_fn()
    with _cache_lock:
        _cache[key] = (now, data)
    return data


def _resolves_in(end_date_str: str | None) -> float | None:
    """Days until market resolution, rounded to 1 decimal. None if unknown."""
    if not end_date_str:
        return None
    try:
        dt = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
        delta = (dt - datetime.now(timezone.utc)).total_seconds()
        return round(max(delta / 86400, 0), 1)
    except Exception:
        return None


def _fetch_polymarket() -> list[dict]:
    try:
        with httpx.Client(timeout=12) as client:
            resp = client.get(
                POLY_URL,
                params={
                    "closed": "false",
                    "limit": 50,
                    "order": "volume24hr",
                    "ascending": "false",
                },
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("Polymarket fetch failed: %s", exc)
        return []

    if not isinstance(data, list):
        return []

    out: list[dict] = []
    for m in data:
        try:
            raw_prices = m.get("outcomePrices") or "[]"
            prices = json.loads(raw_prices) if isinstance(raw_prices, str) else raw_prices
            if not prices:
                continue
            yes = float(prices[0])
            no = float(prices[1]) if len(prices) > 1 else round(1 - yes, 2)
            spread = float(m.get("spread") or abs(1 - yes - no))
            liquidity = float(m.get("liquidity") or 0)
            vol24 = float(m.get("volume24hr") or 0)
            uncertainty = round(1 - abs(yes - 0.5) * 2, 2)
            liq_score = min(1.0, liquidity / _LIQ_NORM)
            edge_score = round(uncertainty * liq_score * (1.0 if vol24 > _VOL_BOOST_THRESHOLD else 0.5), 3)
            out.append({
                "question": m.get("question", ""),
                "slug": m.get("slug", ""),
                "endDate": m.get("endDate"),
                "resolvesIn": _resolves_in(m.get("endDate")),
                "yesPrice": yes,
                "noPrice": no,
                "spread": round(spread, 4),
                "volume24hr": vol24,
                "liquidity": liquidity,
                "uncertainty": uncertainty,
                "liquidityScore": round(liq_score, 2),
                "edgeScore": edge_score,
            })
        except Exception as exc:
            logger.debug("Skipping market entry: %s", exc)

    out.sort(key=lambda x: x["edgeScore"], reverse=True)
    logger.info("Polymarket: enriched %d markets", len(out))
    return out


def _read_report(name: str) -> dict:
    path = REPORTS_DIR / f"{name}.json"
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"{name}.json not found — run the adapter script first:\n"
                   f"  python backend/adapters/{name.replace('-','_')}_export.py",
        )
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.error("Failed to parse %s.json: %s", name, exc)
        raise HTTPException(status_code=500, detail=f"Failed to parse {name}.json: {exc}")


# ── Routes ────────────────────────────────────────────────────────────────────


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "ts": datetime.now(timezone.utc).isoformat(),
        "reports": [p.name for p in REPORTS_DIR.glob("*.json")] if REPORTS_DIR.exists() else [],
    }


@app.get("/api/polymarket")
def polymarket() -> dict:
    markets = _cached("polymarket", CACHE_TTL["polymarket"], _fetch_polymarket)
    return {
        "markets": markets,
        "count": len(markets),
        "fetchedAt": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/overview")
def overview() -> dict:
    def _build():
        markets = _fetch_polymarket()
        high_edge = [m for m in markets if m["edgeScore"] > _EDGE_HIGH_THRESHOLD]
        return {
            "polymarket": {
                "total": len(markets),
                "highEdge": len(high_edge),
                "top3": markets[:3],
            },
            "generatedAt": datetime.now(timezone.utc).isoformat(),
        }

    return _cached("overview", CACHE_TTL["overview"], _build)


@app.get("/api/kelly-signals")
def kelly_signals() -> dict:
    return _read_report("polytraders")


@app.get("/api/smart-money")
def smart_money() -> dict:
    return _read_report("hedgepoly")


@app.get("/api/macro-report")
def macro_report() -> dict:
    return _read_report("poly2")


