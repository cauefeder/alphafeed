"""
poly2_export.py — Adapter for Poly2 macro market data.

Fetches Polymarket prediction markets, classifies them into macro categories,
and writes structured JSON to reports/poly2.json for the Alpha Feed backend
to serve via GET /api/macro-report.

This is a standalone scraper (no Poly2 import dependency) that mirrors
the Poly2 category classification logic.

Usage
-----
  python backend/adapters/poly2_export.py [--pages 8]

Environment variables
  POLY2_PAGES   Polymarket API pages to scan (default 8 = 800 markets)
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    import requests
except ImportError:
    sys.exit("[ERROR] Run: pip install requests")

# ── Paths ─────────────────────────────────────────────────────────────────────

_HERE = Path(__file__).resolve()
REPORTS_DIR = _HERE.parent.parent.parent / "reports"

GAMMA_API = "https://gamma-api.polymarket.com/markets"

# ── Category definitions (matches Poly2 macro_report1.py) ─────────────────────

CATEGORIES = {
    "macro": {
        "name": "Macroeconomics",
        "emoji": "📊",
        "keywords": [
            "fed", "federal reserve", "interest rate", "rate cut", "rate hike",
            "inflation", "cpi", "pce", "gdp", "recession", "unemployment",
            "jobs", "nonfarm", "payroll", "treasury", "yield", "bond",
            "debt ceiling", "government shutdown", "deficit", "tariff",
            "trade war", "sanctions", "ecb", "bank of japan", "boj",
            "bank of england", "imf", "world bank", "core inflation",
            "consumer price", "producer price", "ppi", "retail sales",
            "housing", "mortgage", "real estate", "home price",
            "manufacturing", "pmi", "ism", "consumer confidence",
            "wage growth", "labor market", "initial claims",
            "quantitative", "balance sheet", "fomc", "dot plot",
            "soft landing", "hard landing", "stagflation",
        ],
    },
    "geopolitics": {
        "name": "Geopolitics & Global Affairs",
        "emoji": "🌍",
        "keywords": [
            "war", "ukraine", "russia", "china", "taiwan", "nato",
            "iran", "israel", "gaza", "hamas", "hezbollah", "north korea",
            "missile", "nuclear", "ceasefire", "peace", "invasion",
            "coup", "regime", "diplomacy", "summit",
            "united nations", "european union", "brexit",
            "middle east", "india", "modi", "xi jinping",
            "putin", "zelensky", "military", "troops", "border",
            "strike", "airstrike", "bomb", "attack", "conflict",
            "houthi", "yemen", "syria", "iraq", "saudi",
            "arms", "weapon", "defense", "pentagon", "escalat",
        ],
    },
    "crypto": {
        "name": "Crypto & Digital Assets",
        "emoji": "₿",
        "keywords": [
            "bitcoin", "btc", "ethereum", "eth", "crypto", "solana", "sol",
            "xrp", "dogecoin", "doge", "defi", "nft", "stablecoin",
            "usdc", "usdt", "binance", "coinbase", "sec crypto",
            "bitcoin etf", "halving", "mining", "blockchain",
            "memecoin", "altcoin", "token",
        ],
    },
    "stocks": {
        "name": "Stocks & Traditional Assets",
        "emoji": "📈",
        "keywords": [
            "s&p", "sp500", "nasdaq", "dow jones", "stock", "equity",
            "earnings", "revenue", "ipo", "market cap",
            "oil", "gold", "silver", "commodity", "wti", "brent",
            "apple", "nvidia", "tesla", "microsoft", "amazon", "google",
            "meta", "netflix", "spy", "qqq",
        ],
    },
    "ai_tech": {
        "name": "AI & Technology",
        "emoji": "🤖",
        "keywords": [
            "openai", "anthropic", "google ai", "deepmind", "claude",
            "gpt", "gemini", "llama", "ai model", "artificial intelligence",
            "agi", "machine learning", "chatbot", "ai regulation",
            "ai safety", "chips act", "semiconductor", "tsmc",
            "ai act", "compute", "data center",
        ],
    },
    "politics": {
        "name": "US & Global Politics",
        "emoji": "🏛️",
        "keywords": [
            "trump", "biden", "harris", "republican", "democrat",
            "congress", "senate", "house", "election", "poll",
            "impeach", "supreme court", "executive order", "veto",
            "governor", "mayor", "primary", "nominee", "campaign",
            "doge ", "elon musk", "musk", "cabinet", "secretary",
            "fbi", "doj", "cia", "pardon", "indictment",
            "uk election", "france", "macron", "germany", "canada",
            "trudeau", "brazil", "lula", "mexico", "president",
        ],
    },
}


# ── Scraper ────────────────────────────────────────────────────────────────────

def _fetch_markets(pages: int = 8) -> list[dict]:
    session = requests.Session()
    session.headers.update({"User-Agent": "AlphaFeedMacro/1.0", "Accept": "application/json"})
    all_markets: list[dict] = []

    for page in range(pages):
        try:
            resp = session.get(
                GAMMA_API,
                params={
                    "limit": 100,
                    "offset": page * 100,
                    "active": "true",
                    "closed": "false",
                    "order": "volume24hr",
                    "ascending": "false",
                },
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            if not data:
                break
            all_markets.extend(data)
        except requests.RequestException as e:
            print(f"  [API] Page {page + 1} failed: {e}")
            break
        time.sleep(0.2)

    print(f"  Fetched {len(all_markets)} markets from {pages} pages")
    return all_markets


def _classify(raw_markets: list[dict]) -> tuple[dict[str, list[dict]], list[dict]]:
    """Classify markets into categories, return (classified, all_markets_flat)."""
    classified: dict[str, list[dict]] = {cat: [] for cat in CATEGORIES}
    seen_in_any: set[str] = set()

    for raw in raw_markets:
        question = (raw.get("question", "") or "").lower()
        group_title = (raw.get("groupItemTitle", "") or "").lower()
        slug = (raw.get("slug", "") or "").lower()
        search_text = f"{question} {group_title} {slug}"

        # Quality filter
        volume_24h = float(raw.get("volume24hr") or 0)
        if volume_24h < 100:
            continue

        # Parse end date
        end_str = raw.get("endDate") or raw.get("end_date_iso")
        days_left: Optional[float] = None
        if end_str:
            try:
                end_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
                days_left = (end_dt - datetime.now(timezone.utc)).total_seconds() / 86400
                if days_left < 0:
                    continue
            except (ValueError, TypeError):
                pass

        # Parse YES price
        yes_price: Optional[float] = None
        prices_str = raw.get("outcomePrices")
        if prices_str:
            try:
                prices = json.loads(prices_str) if isinstance(prices_str, str) else prices_str
                if prices:
                    yes_price = float(prices[0])
            except Exception:
                pass

        raw_slug = raw.get("slug", "")
        market_info = {
            "question": raw.get("question", "Unknown"),
            "slug": raw_slug,
            "url": f"https://polymarket.com/event/{raw_slug}" if raw_slug else "https://polymarket.com",
            "yes_price": round(yes_price, 4) if yes_price is not None else None,
            "volume_24h": round(volume_24h, 0),
            "volume_total": round(float(raw.get("volume") or 0), 0),
            "liquidity": round(float(raw.get("liquidityClob") or raw.get("liquidity") or 0), 0),
            "days_left": round(days_left, 1) if days_left is not None else None,
        }

        assigned = False
        for cat, cat_info in CATEGORIES.items():
            for kw in cat_info["keywords"]:
                if kw in search_text:
                    classified[cat].append(market_info)
                    seen_in_any.add(raw_slug)
                    assigned = True
                    break
            if assigned:
                break

    # Sort by 24h volume, cap at 15 per category
    for cat in classified:
        classified[cat].sort(key=lambda m: m["volume_24h"], reverse=True)
        classified[cat] = classified[cat][:15]

    # Top-volume flat list across all categories (for the report header)
    all_flat: list[dict] = []
    seen_q: set[str] = set()
    for markets in classified.values():
        for m in markets:
            if m["question"] not in seen_q:
                seen_q.add(m["question"])
                all_flat.append(m)
    all_flat.sort(key=lambda m: m["volume_24h"], reverse=True)

    return classified, all_flat[:20]


# ── Export ─────────────────────────────────────────────────────────────────────

def run_export(pages: int = 8) -> dict:
    print(f"  Fetching Polymarket macro data ({pages} pages = ~{pages*100} markets)...")
    raw = _fetch_markets(pages)

    if not raw:
        return {
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "error": "No markets returned from Polymarket API",
            "totalMarkets": 0,
            "categories": {},
            "topVolume": [],
        }

    print("  Classifying into categories...")
    classified, top_volume = _classify(raw)

    total = sum(len(v) for v in classified.values())
    for cat, markets in classified.items():
        cat_name = CATEGORIES[cat]["name"]
        print(f"    {cat_name}: {len(markets)} markets")
    print(f"    Total classified: {total}")

    categories_out: dict = {}
    for cat, markets in classified.items():
        cat_info = CATEGORIES[cat]
        categories_out[cat] = {
            "name": cat_info["name"],
            "emoji": cat_info["emoji"],
            "count": len(markets),
            "markets": markets,
        }

    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "totalMarkets": total,
        "categories": categories_out,
        "topVolume": top_volume,
    }


def main() -> None:
    pages = int(os.getenv("POLY2_PAGES", "8"))
    args = sys.argv[1:]
    for i, a in enumerate(args):
        if a == "--pages" and i + 1 < len(args):
            pages = int(args[i + 1])

    print("[poly2_export] Starting Poly2 macro market classification...")
    result = run_export(pages=pages)

    REPORTS_DIR.mkdir(exist_ok=True)
    out_path = REPORTS_DIR / "poly2.json"
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    n = result.get("totalMarkets", 0)
    print(f"[poly2_export] {n} markets -> {out_path}")


if __name__ == "__main__":
    main()
