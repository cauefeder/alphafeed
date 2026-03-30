"""
quant_features.py — Pure functions for the Quant Report pipeline.

All functions in this module are side-effect-free (no file I/O, no model loading).
Import this module to compute features, calibrate scores, and generate insights
without requiring XGBoost or any trained model.
"""
from __future__ import annotations

from datetime import datetime, timezone
from math import exp, log1p

# ── Feature names — canonical order, single source of truth ───────────────────
# Inference must build numpy arrays using this exact order.
# Training must use the same order in the feature matrix.

FEATURE_NAMES: list[str] = [
    "yes_price",          # crowd probability
    "info_ratio",         # volume_24h / sqrt(days_left_raw + 1) / 10_000
    "log_volume_total",   # log1p(volume_total)
    "log_liquidity",      # log1p(liquidity)
    "days_left",          # time to resolution, clamped >= 0.5
    "price_extremity",    # abs(yes_price - 0.5) * 2
]


def compute_features(opp: dict) -> dict[str, float]:
    """
    Compute the 6 model features from an enriched opportunity dict.

    opp must have:
      - curPrice (float, required)
    opp may have:
      - volume_24h, volumeTotal, liquidity, days_left  (all optional, default 0/0/0/0)

    Returns a dict with exactly the keys in FEATURE_NAMES.
    Uses days_left RAW (before clamping) for info_ratio, clamped for the days_left feature.
    """
    p = float(opp["curPrice"])
    vol = float(opp.get("volume_24h") or 0)
    volume_total = float(opp.get("volumeTotal") or 0)
    liquidity = float(opp.get("liquidity") or 0)
    days_raw = float(opp.get("days_left") or 0)
    days_feat = max(days_raw, 0.5)

    return {
        "yes_price":        p,
        "info_ratio":       vol / ((days_raw + 1) ** 0.5) / 10_000,
        "log_volume_total": log1p(volume_total),
        "log_liquidity":    log1p(liquidity),
        "days_left":        days_feat,
        "price_extremity":  abs(p - 0.5) * 2,
    }


def calibrate(raw_score: float, calibration: dict) -> float:
    """
    Apply Platt scaling to a model output score.

    calibration must contain platt_a (intercept) and platt_b (coefficient),
    matching sklearn LogisticRegression.intercept_[0] / coef_[0][0] convention.

    Returns a value in [0, 1].
    """
    raw = calibration["platt_b"] * raw_score + calibration["platt_a"]
    return 1.0 / (1.0 + exp(-raw))


def build_category_trends(poly2: dict) -> dict:
    """
    Summarise poly2 categories as top-3-by-volume market cards.

    Returns {category_name: {totalMarkets, top3Markets}} for non-empty categories.
    Does NOT average yes_price across markets (that number is dominated by question
    framing and category composition, not by crowd belief).
    """
    trends: dict = {}
    for cat_name, cat_data in poly2.get("categories", {}).items():
        markets = cat_data.get("markets", [])
        if not markets:
            continue
        top3 = sorted(markets, key=lambda m: m.get("volume_24h", 0), reverse=True)[:3]
        trends[cat_name] = {
            "totalMarkets": len(markets),
            "top3Markets": [
                {
                    "question": m["question"],
                    "yes_price": m["yes_price"],
                    "volume_24h": m.get("volume_24h", 0),
                    "url": m["url"],
                }
                for m in top3
            ],
        }
    return trends


_EDGE_LABELS: list[tuple[float, str]] = [
    (0.65, "Strong edge"),
    (0.50, "Good edge"),
    (0.40, "Moderate edge"),
    (0.30, "Weak edge"),
]


def _edge_label(score: float) -> str:
    for threshold, label in _EDGE_LABELS:
        if score >= threshold:
            return label
    return "Skip"


def compute_edge_ranking(category_report: dict) -> list[dict]:
    """
    Rank categories by avgQuantScore (the dominant reliable signal at ~32 opps/week).

    Returns list sorted by edgeScore descending, each entry contains:
      category, edgeScore, label, avgQuantScore, tierACount, count
    """
    ranking = []
    for cat, data in category_report.items():
        score = round(data["avgQuantScore"], 3)
        ranking.append({
            "category":      cat,
            "edgeScore":     score,
            "label":         _edge_label(score),
            "avgQuantScore": data["avgQuantScore"],
            "tierACount":    data["tierACount"],
            "count":         data["count"],
        })
    ranking.sort(key=lambda r: r["edgeScore"], reverse=True)
    return ranking


def generate_insights(
    edge_ranking: list[dict],
    opportunities: list[dict],
    model_version: str,
) -> list[str]:
    """
    Generate up to 5 plain-English insight strings from the weekly report data.
    All logic is deterministic — no LLM, no randomness.
    """
    insights: list[str] = []

    # 1. Top edge category
    if edge_ranking:
        top = edge_ranking[0]
        insights.append(
            f"{top['category'].title()} offers the strongest edge this week "
            f"(signal {top['avgQuantScore']:.0%})."
        )

    # 2. Best Tier A opportunity
    tier_a = [o for o in opportunities if o.get("signalTier") == "A"]
    if tier_a:
        best = tier_a[0]  # already sorted by quantScore desc
        insights.append(
            f"Top opportunity: '{best['title']}' — signal {best['quantScore']:.2f}, "
            f"crowd at {best['curPrice']:.0%}."
        )

    # 3. Signal margin of best opportunity
    if tier_a:
        best = tier_a[0]
        margin = round(best["quantScore"] - 0.65, 2)
        if margin > 0:
            insights.append(
                f"'{best['title']}' is {margin:.2f} above the Tier A threshold. "
                f"Crowd is at {best['curPrice']:.0%}."
            )

    # 4. Skip categories
    skip = [r for r in edge_ranking if r["label"] == "Skip"]
    if skip:
        names = ", ".join(r["category"] for r in skip)
        insights.append(f"Low signal this week: {names} — skip unless you have domain edge.")

    # 5. Model staleness alert (fires only if model is > 60 days old)
    try:
        model_date = datetime.strptime(model_version, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        days_since = (datetime.now(timezone.utc) - model_date).days
        if days_since > 60:
            insights.append(
                f"Model is {days_since} days old (trained {model_version}). "
                f"Consider retraining with fresh historical data."
            )
    except (ValueError, TypeError):
        pass

    return insights
