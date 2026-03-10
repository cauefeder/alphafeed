"""
hedgepoly_export.py — Adapter for the HedgePoly prediction-market-analysis project.

Imports build_smart_money_signals() from smart_money.py, runs the pipeline,
and writes results to reports/hedgepoly.json so the Alpha Feed backend can
serve them via GET /api/smart-money.

Usage
-----
  python backend/adapters/hedgepoly_export.py [--top-n 25] [--min-value 200]
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── Resolve paths ─────────────────────────────────────────────────────────────

_HERE = Path(__file__).resolve()
ALPHA_ROOT = _HERE.parent.parent.parent
PROJECTS_ROOT = ALPHA_ROOT.parent
HEDGEPOLY_DIR = PROJECTS_ROOT / "HedgePoly" / "prediction-market-analysis"
REPORTS_DIR = ALPHA_ROOT / "reports"

if not HEDGEPOLY_DIR.exists():
    sys.exit(f"[ERROR] HedgePoly directory not found: {HEDGEPOLY_DIR}")

sys.path.insert(0, str(HEDGEPOLY_DIR))


# ── Export ────────────────────────────────────────────────────────────────────

def run_export(
    top_n: int = 25,
    min_position_value: float = 200.0,
    min_traders: int = 2,
) -> dict:
    from smart_money import build_smart_money_signals

    print(f"  Fetching top {top_n} traders, min position value ${min_position_value}...")
    signals = build_smart_money_signals(
        top_n_traders=top_n,
        min_position_value=min_position_value,
        min_traders=min_traders,
    )
    print(f"  {len(signals)} smart money signals found")

    sigs_out = []
    for s in signals:
        sigs_out.append({
            "marketSlug": s.market_slug,
            "question": s.question,
            "side": s.side,
            "yesValue": round(s.yes_value, 2),
            "noValue": round(s.no_value, 2),
            "totalValue": round(s.total_value, 2),
            "traderCount": s.trader_count,
            "confidence": round(s.confidence, 3),
            "url": s.url,
        })

    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "topN": top_n,
        "minPositionValue": min_position_value,
        "minTraders": min_traders,
        "signalCount": len(sigs_out),
        "signals": sigs_out,
    }


def main() -> None:
    top_n = 25
    min_value = 200.0

    args = sys.argv[1:]
    for i, a in enumerate(args):
        if a == "--top-n" and i + 1 < len(args):
            top_n = int(args[i + 1])
        if a == "--min-value" and i + 1 < len(args):
            min_value = float(args[i + 1])

    print("[hedgepoly_export] Starting HedgePoly signal pipeline...")
    result = run_export(top_n=top_n, min_position_value=min_value)

    REPORTS_DIR.mkdir(exist_ok=True)
    out_path = REPORTS_DIR / "hedgepoly.json"
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    n = result.get("signalCount", 0)
    print(f"[hedgepoly_export] {n} signals -> {out_path}")


if __name__ == "__main__":
    main()
