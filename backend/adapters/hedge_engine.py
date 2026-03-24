# backend/adapters/hedge_engine.py
"""
Hedge Session pipeline.

Stages:
  1. parse_exposure  — extract structured exposure from user text (Stage 1 LLM)
  2. _flatten_markets — flatten poly2.json categories into a single list
  3. score_markets   — Stage 2 LLM scores markets for correlation, filters, enriches
  4. run_hedge_session — orchestrates all stages, loads cached JSON files
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

# llm_client lives one directory up (backend/), add to path for direct import
sys.path.insert(0, str(Path(__file__).parent.parent))
import llm_client
from llm_client import LLMError

# Re-export so tests can patch via 'adapters.hedge_engine.llm_complete'
llm_complete = llm_client.complete

REPORTS_DIR = Path(__file__).parent.parent.parent / "reports"

# ── File loaders (patchable in tests) ─────────────────────────────────────────

def _load_poly2() -> dict:
    return json.loads((REPORTS_DIR / "poly2.json").read_text(encoding="utf-8"))


def _load_polytraders() -> dict:
    return json.loads((REPORTS_DIR / "polytraders.json").read_text(encoding="utf-8"))


# ── Stage helpers ──────────────────────────────────────────────────────────────

def _flatten_markets() -> list[dict]:
    """Flatten poly2.json categories into a single condensed list for the LLM."""
    data = _load_poly2()
    out = []
    for cat in data.get("categories", {}).values():
        for m in cat.get("markets", []):
            out.append({
                "slug":       m["slug"],
                "question":   m["question"],
                "yes_price":  m["yes_price"],
                "volume_24h": m["volume_24h"],
                "days_left":  m["days_left"],
            })
    return out


def _normalize_outcome(outcome: str) -> str:
    """Map Kelly outcome to YES/NO for direction-match comparison."""
    lo = outcome.lower().strip()
    if lo == "yes":
        return "YES"
    if lo == "no":
        return "NO"
    return "YES"  # named outcomes (team, person) = betting that entity wins = YES


def _enrich(result: dict, kelly_opps: list[dict]) -> dict:
    """
    Join a scored hedge result to polytraders.json by slug.
    Sets kelly_bet, smart_money_exposure, cross_signal.
    """
    slug = result["slug"]
    match = next((k for k in kelly_opps if k.get("slug") == slug), None)

    result["kelly_bet"] = None
    result["smart_money_exposure"] = None
    result["cross_signal"] = False

    if match:
        result["kelly_bet"] = match.get("kellyBet")
        result["smart_money_exposure"] = match.get("totalExposure")
        kelly_direction = _normalize_outcome(match.get("outcome", ""))
        result["cross_signal"] = kelly_direction == result["hedge_side"]

    return result


# ── Stage 1: Exposure extraction ───────────────────────────────────────────────

def parse_exposure(text: str, asset: Optional[str], risk_type: Optional[str]) -> dict:
    """
    Extract { asset, direction, risk_type, scenario } from user text.
    Short-circuit: if both asset and risk_type are non-empty, skip LLM call.
    """
    if asset and risk_type:
        return {
            "asset":     asset,
            "direction": "long",
            "risk_type": risk_type,
            "scenario":  text,
        }

    prompt = f"""Extract the financial exposure from this description. Return JSON only.

User description: "{text}"

Return this exact JSON structure:
{{
  "asset": "the primary asset (e.g. BTC, S&P500, tech stocks)",
  "direction": "long or short",
  "risk_type": "one of: risk-off, rate-hike, recession, geopolitical, crypto-crash, tech-selloff, other",
  "scenario": "one sentence describing the worst case scenario"
}}"""
    raw = llm_complete(prompt)
    return json.loads(raw)


# ── Stage 2: Market scoring ────────────────────────────────────────────────────

def score_markets(exposure: dict, markets: list[dict], kelly_opps: list[dict]) -> list[dict]:
    """
    Call Stage 2 LLM to score each market for hedge correlation.
    Filters to correlation_score >= 2.0, returns at most 8 sorted descending.
    Enriches each result with Kelly data.
    """
    market_lines = "\n".join(
        f'{m["slug"]} | {m["question"]} | yes_price={m["yes_price"]:.2f} | '
        f'vol24h=${m["volume_24h"]:,.0f} | days_left={m["days_left"]:.0f}d'
        for m in markets
    )

    prompt = f"""You are a hedge analyst. A user has the following financial exposure:
Asset: {exposure["asset"]}
Direction: {exposure["direction"]}
Risk type: {exposure["risk_type"]}
Worst case scenario: {exposure["scenario"]}

Find Polymarket prediction markets below that would PAY OUT if the worst case scenario happens.
These are HEDGES — a YES or NO bet that profits if the bad scenario occurs.

Markets:
{market_lines}

Return a JSON array of up to 8 markets where correlation_score >= 2.0, sorted by correlation_score descending.
Each item must have exactly these fields:
[
  {{
    "slug": "exact slug from the market list above",
    "hedge_side": "YES or NO",
    "correlation_score": <number 0-10>,
    "narrative": "<2 sentences: how this pays out if the worst case happens>"
  }}
]

Return ONLY the JSON array. No markdown, no explanation."""

    raw = llm_complete(prompt)
    items = json.loads(raw)

    results = []
    for item in items:
        try:
            score = float(item["correlation_score"])
            if score < 2.0:
                continue
            enriched = _enrich({
                "slug":              item["slug"],
                "hedge_side":        item["hedge_side"],
                "correlation_score": score,
                "narrative":         item["narrative"],
            }, kelly_opps)
            # Add market metadata from original list
            market_meta = next((m for m in markets if m["slug"] == item["slug"]), {})
            enriched["question"]   = market_meta.get("question", "")
            enriched["yes_price"]  = market_meta.get("yes_price")
            enriched["volume_24h"] = market_meta.get("volume_24h")
            enriched["days_left"]  = market_meta.get("days_left")
            enriched["url"]        = f"https://polymarket.com/event/{item['slug']}"
            results.append(enriched)
        except (KeyError, TypeError, ValueError):
            continue  # skip malformed items

    results.sort(key=lambda x: x["correlation_score"], reverse=True)
    return results[:8]


# ── Orchestrator ───────────────────────────────────────────────────────────────

def run_hedge_session(text: str, asset: Optional[str], risk_type: Optional[str]) -> dict:
    """Full pipeline: parse → flatten → score → return."""
    exposure = parse_exposure(text, asset, risk_type)
    markets = _flatten_markets()
    kelly_opps = _load_polytraders().get("opportunities", [])
    hedges = score_markets(exposure, markets, kelly_opps)
    return {"exposure_parsed": exposure, "hedges": hedges}
