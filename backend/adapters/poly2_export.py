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
from typing import Any, Optional

try:
    import requests
except ImportError:
    sys.exit("[ERROR] Run: pip install requests")

# ── Paths ─────────────────────────────────────────────────────────────────────

_HERE = Path(__file__).resolve()
REPORTS_DIR = _HERE.parent.parent.parent / "reports"

# Allow `python backend/adapters/poly2_export.py` to import sibling modules.
# Matches the pattern used by quant_report.py and train_model.py.
sys.path.insert(0, str(_HERE.parent))

from poly2_categories import CATEGORIES, CategorySpec  # noqa: E402

GAMMA_API = "https://gamma-api.polymarket.com/markets"


# ── Scraper ────────────────────────────────────────────────────────────────────


def _fetch_markets(
    pages: int = 8,
    *,
    session: Any | None = None,
    sleep_s: float = 0.2,
) -> list[dict[str, Any]]:
    """Page through the Gamma API. Session is injectable for tests; sleep_s=0
    in tests."""
    if session is None:
        session = requests.Session()
        session.headers.update(
            {"User-Agent": "AlphaFeedMacro/1.0", "Accept": "application/json"}
        )
    all_markets: list[dict[str, Any]] = []

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
        if sleep_s:
            time.sleep(sleep_s)

    print(f"  Fetched {len(all_markets)} markets from {pages} pages")
    return all_markets


# ── Classification helpers (pure functions) ────────────────────────────────────


def _search_text(raw: dict[str, Any]) -> str:
    """Lowercase concatenation of question + groupItemTitle + slug."""
    question = (raw.get("question", "") or "").lower()
    group = (raw.get("groupItemTitle", "") or "").lower()
    slug = (raw.get("slug", "") or "").lower()
    return f"{question} {group} {slug}"


def _parse_market_info(
    raw: dict[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Normalize a raw Gamma market into the report-row shape.

    `now` is injectable so tests can pin the days_left calculation.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    volume_24h = float(raw.get("volume24hr") or 0)

    end_str = raw.get("endDate") or raw.get("end_date_iso")
    days_left: Optional[float] = None
    if end_str:
        try:
            end_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
            days_left = (end_dt - now).total_seconds() / 86400
        except (ValueError, TypeError):
            pass

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
    return {
        "question": raw.get("question", "Unknown"),
        "slug": raw_slug,
        "url": f"https://polymarket.com/event/{raw_slug}" if raw_slug else "https://polymarket.com",
        "yes_price": round(yes_price, 4) if yes_price is not None else None,
        "volume_24h": round(volume_24h, 0),
        "volume_total": round(float(raw.get("volume") or 0), 0),
        "liquidity": round(float(raw.get("liquidityClob") or raw.get("liquidity") or 0), 0),
        "days_left": round(days_left, 1) if days_left is not None else None,
    }


def _passes_quality_filter(info: dict[str, Any]) -> bool:
    """Volume >= 100 and (no end date OR not yet expired)."""
    if (info.get("volume_24h") or 0) < 100:
        return False
    days_left = info.get("days_left")
    if days_left is not None and days_left < 0:
        return False
    return True


def _match_category(
    text: str,
    categories: dict[str, CategorySpec],
) -> Optional[str]:
    """Return first category whose any keyword appears in text, else None."""
    for cat, cat_info in categories.items():
        for kw in cat_info["keywords"]:
            if kw in text:
                return cat
    return None


def _classify(
    raw_markets: list[dict[str, Any]],
    *,
    now: datetime | None = None,
    categories: dict[str, CategorySpec] | None = None,
) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    """Classify markets into categories. Returns (per-category, top-volume-flat)."""
    if categories is None:
        categories = CATEGORIES
    classified: dict[str, list[dict[str, Any]]] = {cat: [] for cat in categories}

    for raw in raw_markets:
        info = _parse_market_info(raw, now=now)
        if not _passes_quality_filter(info):
            continue
        cat = _match_category(_search_text(raw), categories)
        if cat is None:
            continue
        classified[cat].append(info)

    for cat in classified:
        classified[cat].sort(key=lambda m: m["volume_24h"], reverse=True)
        classified[cat] = classified[cat][:15]

    all_flat: list[dict[str, Any]] = []
    seen_q: set[str] = set()
    for markets in classified.values():
        for m in markets:
            if m["question"] not in seen_q:
                seen_q.add(m["question"])
                all_flat.append(m)
    all_flat.sort(key=lambda m: m["volume_24h"], reverse=True)

    return classified, all_flat[:20]


# ── Export ─────────────────────────────────────────────────────────────────────


def run_export(pages: int = 8) -> dict[str, Any]:
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

    categories_out: dict[str, Any] = {}
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
