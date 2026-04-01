"""
polytraders_export.py — Adapter for the PolyTraders project.

Imports the PolyTraders signal pipeline, runs it, and writes the results to
reports/polytraders.json so the Alpha Feed backend can serve them via
GET /api/kelly-signals.

Usage
-----
  python backend/adapters/polytraders_export.py [--bankroll 100]

Environment variables (optional — same as PolyTraders .env)
  POLYTRADERS_BANKROLL    Bankroll in USDC (default 100)
  POLYTRADERS_TIME_PERIOD Leaderboard period: DAY|WEEK|MONTH|ALL (default WEEK)
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── Resolve paths ─────────────────────────────────────────────────────────────

_HERE = Path(__file__).resolve()
ALPHA_ROOT  = _HERE.parent.parent.parent           # AlphaFeed/
REPORTS_DIR = ALPHA_ROOT / "reports"

# Allow explicit override via env var (required when cloned standalone)
_pt_env = os.environ.get("POLYTRADERS_DIR", "")
if _pt_env:
    POLYTRADERS_DIR = Path(_pt_env).expanduser().resolve()
else:
    # Default: sibling directory (monorepo layout)
    POLYTRADERS_DIR = ALPHA_ROOT.parent / "PolyTraders"


# ── Category config ───────────────────────────────────────────────────────────

CATEGORIES = [
    ("OVERALL",  50),
    ("CRYPTO",   25),
    ("POLITICS", 25),
]


def fetch_expanded_traders(time_period: str) -> tuple:
    """Fetch traders from multiple leaderboard categories, deduplicate by proxy_wallet."""
    from leaderboard import fetch_top_traders
    seen: set = set()
    traders: list = []
    breakdown: dict = {}
    for category, limit in CATEGORIES:
        batch = fetch_top_traders(time_period=time_period, limit=limit, category=category)
        added = 0
        for t in batch:
            if t.proxy_wallet not in seen:
                seen.add(t.proxy_wallet)
                traders.append(t)
                added += 1
        breakdown[category] = added
    return traders, breakdown


# ── Export ────────────────────────────────────────────────────────────────────

def run_export(
    top_n: int = 25,
    bankroll: float = 100.0,
    time_period: str = "WEEK",
) -> dict:
    from positions import fetch_all_positions
    from kelly import score_opportunities

    print(f"  Fetching traders from OVERALL(50)+CRYPTO(25)+POLITICS(25)...")
    traders, breakdown = fetch_expanded_traders(time_period)
    if not traders:
        return {
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "error": "No traders returned from leaderboard",
            "opportunities": [],
        }
    print(f"  {len(traders)} unique traders found")

    print(f"  Fetching positions (parallel)...")
    positions = fetch_all_positions(traders, max_traders=len(traders))
    print(f"  {len(positions)} qualifying positions")

    opportunities = score_opportunities(
        positions,
        total_traders_checked=len(traders),
        bankroll=bankroll,
    )

    opps_out = []
    for opp in opportunities:
        opps_out.append({
            "title": opp.title,
            "outcome": opp.outcome,
            "slug": opp.slug,
            "url": opp.url,
            "curPrice": round(opp.cur_price, 4),
            "estimatedEdge": round(opp.estimated_edge, 4),
            "kellyBet": round(opp.kelly_bet, 2),
            "kellyFull": round(opp.kelly_full, 4),
            "nSmartTraders": opp.n_smart_traders,
            "totalTradersChecked": opp.total_traders_checked,
            "smartTraderNames": opp.smart_trader_names[:5],
            "countSignal": round(opp.count_signal, 4),
            "sizeSignal": round(opp.size_signal, 4),
            "totalExposure": round(opp.total_exposure, 2),
            "weightedAvgEntry": round(opp.weighted_avg_entry, 4),
        })

    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "timePeriod": time_period,
        "bankroll": bankroll,
        "tradersChecked": len(traders),
        "categoryBreakdown": breakdown,
        "positionsScanned": len(positions),
        "opportunities": opps_out,
    }


def main() -> None:
    if not POLYTRADERS_DIR.exists():
        sys.exit(
            f"[ERROR] PolyTraders directory not found: {POLYTRADERS_DIR}\n"
            f"        Set the POLYTRADERS_DIR environment variable to the correct path.\n"
            f"        Example: POLYTRADERS_DIR=/home/user/projects/PolyTraders"
        )
    sys.path.insert(0, str(POLYTRADERS_DIR))

    bankroll = float(os.getenv("POLYTRADERS_BANKROLL", "100"))
    time_period = os.getenv("POLYTRADERS_TIME_PERIOD", "WEEK")
    args = sys.argv[1:]
    for i, a in enumerate(args):
        if a == "--bankroll" and i + 1 < len(args):
            bankroll = float(args[i + 1])

    print("[polytraders_export] Starting PolyTraders signal pipeline...")
    result = run_export(bankroll=bankroll, time_period=time_period)
    REPORTS_DIR.mkdir(exist_ok=True)
    out_path = REPORTS_DIR / "polytraders.json"
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    n = len(result.get("opportunities", []))
    print(f"[polytraders_export] {n} opportunities -> {out_path}")


if __name__ == "__main__":
    main()
