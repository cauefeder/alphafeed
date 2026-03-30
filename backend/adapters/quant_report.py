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
from datetime import datetime, timezone
from pathlib import Path

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


def score_opportunity(opp: dict, model, calibration: dict) -> dict:
    """Score one enriched opportunity dict. Returns opp + quantScore/signalTier/infoRatio."""
    features = compute_features(opp)
    feat_order = calibration.get("feature_names", FEATURE_NAMES)
    X = np.array([[features[f] for f in feat_order]])
    raw_score = float(model.predict_proba(X)[0][1])
    calibrated_prob = calibrate(raw_score, calibration)
    tier = "A" if raw_score >= 0.65 else "B" if raw_score >= 0.40 else "C"
    return {
        **opp,
        "quantScore":     round(raw_score, 4),
        "signalTier":     tier,
        "calibratedProb": round(calibrated_prob, 4),
        "infoRatio":      round(features["info_ratio"], 4),
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
) -> dict:
    """Core inference logic (pure function — no file I/O). Called by main() and tests."""
    # Build poly2 lookup by slug across all categories
    poly2_by_slug: dict = {}
    for cat_name, cat_data in poly2.get("categories", {}).items():
        for m in cat_data.get("markets", []):
            slug = m.get("slug")
            if slug:
                poly2_by_slug[slug] = {**m, "_category": cat_name}

    # Score each opportunity
    scored: list = []
    for opp in polytraders.get("opportunities", []):
        if "curPrice" not in opp:
            logger.warning("Skipping opportunity missing curPrice: %s", opp.get("slug"))
            continue
        poly2_data = poly2_by_slug.get(opp.get("slug", ""), {})
        enriched = {
            **opp,
            "volume_24h":  poly2_data.get("volume_24h", 0),
            "volumeTotal": poly2_data.get("volume_total", 0),
            "liquidity":   poly2_data.get("liquidity", 0),
            "days_left":   poly2_data.get("days_left", 14),
            "category":    poly2_data.get("_category", "other"),
        }
        scored.append(score_opportunity(enriched, model, calibration))

    scored.sort(key=lambda o: o["quantScore"], reverse=True)

    tier_a = sum(1 for o in scored if o["signalTier"] == "A")
    tier_b = sum(1 for o in scored if o["signalTier"] == "B")
    tier_c = sum(1 for o in scored if o["signalTier"] == "C")

    cat_report = _build_category_report(scored)
    edge_ranking = compute_edge_ranking(cat_report)
    category_trends = build_category_trends(poly2)

    top_cat = edge_ranking[0] if edge_ranking else None
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

    result = run_inference(polytraders, poly2, model, calibration, metrics)

    OUTPUT_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    n = result["summary"]["totalScored"]
    logger.info("Quant report: %d opportunities scored → %s", n, OUTPUT_PATH)


if __name__ == "__main__":
    main()
