"""
fetch_historical.py — Pull resolved Polymarket markets for XGBoost training data.

Usage:
  python backend/adapters/fetch_historical.py --pages 150 --output data/historical_markets.csv

Fetches ~8,000–15,000 resolved markets in ~10 minutes.
Data is gitignored (stored in data/ directory).
"""
from __future__ import annotations

import argparse
import csv
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

GAMMA_URL = "https://gamma-api.polymarket.com/markets"
REQUIRED_COLUMNS = [
    "slug", "question", "category",
    "yes_price", "volume_24h", "volume_total", "liquidity", "days_left",
    "resolved_yes",
]


def _infer_category(tags: list) -> str:
    """Extract the first tag label as category, defaulting to 'other'."""
    if not tags:
        return "other"
    return (tags[0].get("label") or "other").lower().replace(" ", "_")


def parse_market(m: dict) -> dict | None:
    """
    Parse a single Gamma API market dict into a training row.
    Returns None if the market lacks required price data.
    """
    raw_prices = m.get("outcomePrices")
    if not raw_prices:
        return None
    try:
        prices = json.loads(raw_prices) if isinstance(raw_prices, str) else raw_prices
        if not prices:
            return None
        yes_price = float(prices[0])
    except (ValueError, TypeError, IndexError):
        return None

    end_date = m.get("endDate")
    days_left = 14.0  # default fallback
    if end_date:
        try:
            dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
            delta = (dt - datetime.now(timezone.utc)).total_seconds()
            days_left = max(round(delta / 86400, 1), 0.0)
        except Exception:
            pass

    resolved_yes = m.get("resolvedYes")
    if resolved_yes is None:
        return None  # skip unresolved

    return {
        "slug":         m.get("slug", ""),
        "question":     m.get("question", ""),
        "category":     _infer_category(m.get("tags") or []),
        "yes_price":    round(yes_price, 4),
        "volume_24h":   float(m.get("volume24hr") or 0),
        "volume_total": float(m.get("volumeTotal") or 0),
        "liquidity":    float(m.get("liquidity") or 0),
        "days_left":    days_left,
        "resolved_yes": int(bool(resolved_yes)),
    }


def fetch_page(page: int, limit: int = 100) -> list[dict]:
    """Fetch one page of closed markets from Gamma API."""
    params = {
        "closed": "true",
        "limit": limit,
        "offset": page * limit,
        "order": "endDate",
        "ascending": "false",
    }
    resp = requests.get(GAMMA_URL, params=params, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, list) else []


def write_csv(rows: list[dict], path: Path) -> None:
    """Write list of row dicts to CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=REQUIRED_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pages", type=int, default=150)
    parser.add_argument("--output", default="data/historical_markets.csv")
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()

    out_path = Path(args.output)
    rows: list[dict] = []
    print(f"[fetch_historical] Fetching {args.pages} pages × {args.limit} markets...")

    for page in range(args.pages):
        try:
            markets = fetch_page(page, args.limit)
        except Exception as exc:
            print(f"  Page {page}: ERROR — {exc}")
            time.sleep(2)
            continue

        if not markets:
            print(f"  Page {page}: empty response, stopping.")
            break

        for m in markets:
            row = parse_market(m)
            if row:
                rows.append(row)

        if page % 10 == 0:
            print(f"  Page {page}: {len(rows)} rows so far")
        time.sleep(0.1)  # gentle rate limiting

    write_csv(rows, out_path)
    print(f"[fetch_historical] {len(rows)} resolved markets → {out_path}")


if __name__ == "__main__":
    main()
