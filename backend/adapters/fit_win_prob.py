"""Refit the win-probability model from signal_tracker.db and gate-write the artifact.

Run before quant_report.py in the refresh pipeline. Never raises for a bad fit —
logs, leaves the previous artifact in place, and exits 0 so the report run continues.
"""
from __future__ import annotations
import json, logging, os, sqlite3, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from win_prob import fit, maybe_write_artifact  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("fit_win_prob")

REPO_ROOT = Path(__file__).resolve().parents[2]           # AlphaFeed/
ARTIFACT = REPO_ROOT / "models" / "win_prob_model.json"
DB = Path(os.environ.get("SIGNAL_TRACKER_DB", REPO_ROOT.parent / "signal_tracker.db"))


def load_rows(db_path: Path) -> list[dict]:
    if not db_path.exists():
        log.warning("signal_tracker.db not found at %s", db_path); return []
    con = sqlite3.connect(str(db_path)); con.row_factory = sqlite3.Row
    rows = con.execute(
        """SELECT market_slug, entry_price, market_price, raw_features, outcome, created_at
           FROM signals WHERE system='alphafeed' AND outcome IN ('WIN','LOSS')"""
    ).fetchall()
    out = []
    for r in rows:
        try:
            rf = json.loads(r["raw_features"] or "{}")
        except Exception:
            rf = {}
        out.append({"market_slug": r["market_slug"], "entry_price": r["entry_price"],
                    "market_price": r["market_price"], "outcome": r["outcome"],
                    "created_at": r["created_at"], "days_left": rf.get("days_left"),
                    "liquidity": rf.get("liquidity")})
    return out


def main() -> int:
    rows = load_rows(DB)
    if len(rows) < 300:
        log.warning("only %d resolved rows — keeping previous artifact", len(rows)); return 0
    params, metrics = fit(rows)
    wrote = maybe_write_artifact(str(ARTIFACT), params, metrics)
    log.info("fit n=%d brier=%.4f baseline=%.4f ece=%.4f -> %s",
             metrics["n_train"], metrics.get("brier", 1), metrics.get("brier_price_baseline", 0),
             metrics.get("ece", 1), "WROTE" if wrote else "KEPT PREVIOUS (gate failed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
