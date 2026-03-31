"""
quant_report.py — Weekly XGBoost inference script.

Reads reports/polytraders.json + reports/poly2.json,
scores every polytraders opportunity with the committed model,
writes reports/quant_report.json.

Usage (invoked by GitHub Actions every Sunday):
  python backend/adapters/quant_report.py
"""
from __future__ import annotations

import json
import logging
import pickle
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
import numpy as np

_HERE = Path(__file__).resolve()
REPO_ROOT = _HERE.parent.parent.parent
sys.path.insert(0, str(_HERE.parent))

from quant_features import (
    FEATURE_NAMES,
    build_category_trends,
    calibrate,
    compute_edge_ranking,
    compute_features,
    generate_insights,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("quant_report")

POLYTRADERS_PATH = REPO_ROOT / "reports/polytraders.json"
POLY2_PATH       = REPO_ROOT / "reports/poly2.json"
MODEL_PATH       = REPO_ROOT / "models/xgboost_model.pkl"
CALIBRATION_PATH = REPO_ROOT / "models/calibration_params.json"
METRICS_PATH     = REPO_ROOT / "models/training_metrics.json"
OUTPUT_PATH      = REPO_ROOT / "reports/quant_report.json"

GAMMA_URL = "https://gamma-api.polymarket.com/markets"

# Keyword sets for category inference from slug / event title
_CATEGORY_KEYWORDS: list[tuple[str, list[str]]] = [
    ("sports",    ["nba-", "nfl-", "nhl-", "mlb-", "cbb-", "soccer", "football",
                   "basketball", "baseball", "hockey", "tennis", "golf", "ufc",
                   "mma", "f1-", "formula-", "olympic", "-cup-", "stanley-cup",
                   "world-series", "super-bowl", "uef-", "atp-", "epl-", "laliga",
                   "la-liga", "serie-a", "ligue-", "bundesliga", "champions-league",
                   "world-cup", "wimbledon", "nascar-", "pga-", "masters-",
                   "win-on-202", "will-win-the-202"]),   # "win-on-2026-03-31" pattern
    ("crypto",    ["bitcoin", "btc-", "-btc-", "ethereum", "-eth-", "crypto",
                   "solana", "doge", "xrp", "altcoin", "defi", "nft", "binance",
                   "coinbase", "stablecoin"]),
    ("geopolitics", ["ukraine", "russia", "china", "taiwan", "nato", "iran",
                     "israel", "war-", "conflict", "sanction", "ceasefire",
                     "greenland", "venezuela", "north-korea", "middle-east",
                     "hamas", "hezbollah", "gaza", "nuclear", "missile"]),
    ("politics",  ["election", "president", "senate", "congress", "poll", "vote",
                   "trump", "biden", "harris", "democrat", "republican", "impeach",
                   "prime-minister", "-out-by-", "vance", "newsom", "desantis",
                   "buttigieg", "ossoff", "cornyn", "shapiro", "warsh",
                   "starmer", "orban", "macron", "netanyahu", "maduro", "machado",
                   "mayor", "governor", "nomination", "cabinet"]),
    ("macro",     ["fed-", "-fed-", "inflation", "gdp", "recession", "-rate-",
                   "interest-rate", "mortgage", "dow-jones", "nasdaq", "oil-price",
                   "gold-price", "sp500", "yield", "treasury", "cpi", "pce"]),
    ("ai_tech",   ["openai", "anthropic", "gemini", "gpt", "-llm-", "-ai-", "agi",
                   "deepmind", "mistral", "chatgpt", "claude-"]),
]


def _infer_category_from_slug(slug: str, market: dict | None = None, title: str = "") -> str:
    """Infer a category string from slug keywords, opportunity title, and Gamma market metadata."""
    events = (market or {}).get("events") or []
    ticker = (events[0].get("ticker") or "") if events else ""
    event_title = (events[0].get("title") or "") if events else ""
    combined = f"{slug} {ticker} {event_title} {title}".lower()
    for category, keywords in _CATEGORY_KEYWORDS:
        if any(kw in combined for kw in keywords):
            return category
    return "other"


def _days_left(end_date_str: str | None) -> float:
    if not end_date_str:
        return 14.0
    try:
        dt = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
        delta = (dt - datetime.now(timezone.utc)).total_seconds()
        return max(round(delta / 86400, 1), 0.0)
    except Exception:
        return 14.0


def fetch_gamma_enrichment(slugs: list[str]) -> dict[str, dict]:
    """
    Fetch volume / liquidity / category for a list of slugs from the Gamma API.
    Returns {slug: {volume_24h, volume_total, liquidity, days_left, _category}}.
    Silently skips any slug that errors (network, 404, etc.).
    """
    enrichment: dict[str, dict] = {}
    for slug in slugs:
        try:
            resp = httpx.get(GAMMA_URL, params={"slug": slug}, timeout=12)
            resp.raise_for_status()
            data = resp.json()
            if data:
                m = data[0]
                enrichment[slug] = {
                    "volume_24h":   float(m.get("volume24hr") or 0),
                    "volume_total": float(m.get("volumeNum") or m.get("volume") or 0),
                    "liquidity":    float(m.get("liquidity") or 0),
                    "days_left":    _days_left(m.get("endDate")),
                    "_category":    _infer_category_from_slug(slug, m),
                }
            time.sleep(0.1)
        except Exception as exc:
            logger.debug("Gamma enrichment failed for %s: %s", slug, exc)
    logger.info("Gamma enrichment: %d/%d slugs resolved", len(enrichment), len(slugs))
    return enrichment


def score_opportunity(opp: dict, model, calibration: dict) -> dict:
    """Score one enriched opportunity dict. Returns opp + quantScore/signalTier/infoRatio.

    Also computes:
      convergentScore = quantScore × countSignal  (crowd uncertain AND many traders agree)
      contraryFlag    = True when crowd is certain (quantScore < 0.20) but many traders
                        disagree (countSignal > 0.10) — potential contrarian play
    """
    features = compute_features(opp)
    feat_order = calibration.get("feature_names", FEATURE_NAMES)
    X = np.array([[features[f] for f in feat_order]])
    raw_score = float(model.predict_proba(X)[0][1])
    calibrated_prob = calibrate(raw_score, calibration)
    tier = "A" if raw_score >= 0.65 else "B" if raw_score >= 0.40 else "C"
    count_signal = float(opp.get("countSignal") or 0)
    convergent = round(raw_score * count_signal, 4)
    contrary = raw_score < 0.20 and count_signal > 0.10
    return {
        **opp,
        "quantScore":       round(raw_score, 4),
        "signalTier":       tier,
        "calibratedProb":   round(calibrated_prob, 4),
        "infoRatio":        round(features["info_ratio"], 4),
        "convergentScore":  convergent,
        "contraryFlag":     contrary,
    }


def _build_category_report(scored_opps: list) -> dict:
    """Aggregate scored opportunities by category."""
    cats: dict = {}
    for opp in scored_opps:
        cat = opp.get("category", "other")
        cats.setdefault(cat, []).append(opp)
    report = {}
    for cat, opps in cats.items():
        scores = [o["quantScore"] for o in opps]
        tier_a = sum(1 for o in opps if o["signalTier"] == "A")
        report[cat] = {
            "count":         len(opps),
            "avgQuantScore": round(sum(scores) / len(scores), 4),
            "tierACount":    tier_a,
        }
    return report


def run_inference(
    polytraders: dict,
    poly2: dict,
    model,
    calibration: dict,
    metrics: dict,
    gamma_enrichment: dict | None = None,
) -> dict:
    """Core inference logic (pure function — no file I/O). Called by main() and tests.

    gamma_enrichment: optional dict {slug -> enrichment} fetched from Gamma API for
    slugs not covered by poly2. When provided, it fills in volume/liquidity/category
    for markets outside the poly2 macro universe (e.g., sports, crypto).
    """
    # Build poly2 lookup by slug across all categories
    poly2_by_slug: dict = {}
    for cat_name, cat_data in poly2.get("categories", {}).items():
        for m in cat_data.get("markets", []):
            slug = m.get("slug")
            if slug:
                poly2_by_slug[slug] = {**m, "_category": cat_name}

    gamma_enrichment = gamma_enrichment or {}

    # Score each opportunity
    scored: list = []
    for opp in polytraders.get("opportunities", []):
        if "curPrice" not in opp:
            logger.warning("Skipping opportunity missing curPrice: %s", opp.get("slug"))
            continue
        slug = opp.get("slug", "")
        # poly2 wins (macro/geopolitics/crypto already enriched); Gamma fills the gaps
        enrich = poly2_by_slug.get(slug) or gamma_enrichment.get(slug) or {}
        enriched = {
            **opp,
            "volume_24h":  enrich.get("volume_24h", 0),
            "volumeTotal": enrich.get("volume_total", 0),
            "liquidity":   enrich.get("liquidity", 0),
            "days_left":   enrich.get("days_left", 14),
            "category":    enrich.get("_category", _infer_category_from_slug(slug, title=opp.get("title", ""))),
        }
        scored.append(score_opportunity(enriched, model, calibration))

    scored.sort(key=lambda o: o["quantScore"], reverse=True)

    tier_a = sum(1 for o in scored if o["signalTier"] == "A")
    tier_b = sum(1 for o in scored if o["signalTier"] == "B")
    tier_c = sum(1 for o in scored if o["signalTier"] == "C")

    cat_report = _build_category_report(scored)
    edge_ranking = compute_edge_ranking(cat_report)
    category_trends = build_category_trends(poly2)

    # Top category: require >= 3 markets to avoid single-market outliers dominating
    substantial = [r for r in edge_ranking if r["count"] >= 3]
    top_cat = substantial[0] if substantial else (edge_ranking[0] if edge_ranking else None)
    model_version = metrics.get("modelVersion", "unknown")
    insights = generate_insights(edge_ranking, scored, model_version)

    return {
        "generatedAt":   datetime.now(timezone.utc).isoformat(),
        "weekOf":        datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "modelVersion":  model_version,
        "modelAuc":      metrics.get("testAuc", 0),
        "summary": {
            "totalScored":         len(scored),
            "tierA":               tier_a,
            "tierB":               tier_b,
            "tierC":               tier_c,
            "topSignalCategory":   top_cat["category"] if top_cat else None,
            "topCategoryAvgScore": top_cat["edgeScore"] if top_cat else None,
        },
        "opportunities":  scored,
        "categoryReport": cat_report,
        "edgeRanking":    edge_ranking,
        "insights":       insights,
        "categoryTrends": category_trends,
    }


def main() -> None:
    logger.info("Loading input files...")
    polytraders = json.loads(POLYTRADERS_PATH.read_text(encoding="utf-8"))
    poly2       = json.loads(POLY2_PATH.read_text(encoding="utf-8"))
    metrics     = json.loads(METRICS_PATH.read_text(encoding="utf-8"))

    logger.info("Loading model...")
    with open(MODEL_PATH, "rb") as f:
        model = pickle.load(f)
    calibration = json.loads(CALIBRATION_PATH.read_text(encoding="utf-8"))

    # Build poly2 slug set to find uncovered opportunities
    poly2_slugs: set[str] = set()
    for cat_data in poly2.get("categories", {}).values():
        for m in cat_data.get("markets", []):
            if m.get("slug"):
                poly2_slugs.add(m["slug"])

    uncovered = [
        opp["slug"] for opp in polytraders.get("opportunities", [])
        if opp.get("slug") and opp["slug"] not in poly2_slugs
    ]
    gamma_enrichment: dict = {}
    if uncovered:
        logger.info("Fetching Gamma enrichment for %d uncovered slugs...", len(uncovered))
        gamma_enrichment = fetch_gamma_enrichment(uncovered)

    result = run_inference(polytraders, poly2, model, calibration, metrics, gamma_enrichment)

    OUTPUT_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    n = result["summary"]["totalScored"]
    logger.info("Quant report: %d opportunities scored → %s", n, OUTPUT_PATH)


if __name__ == "__main__":
    main()
