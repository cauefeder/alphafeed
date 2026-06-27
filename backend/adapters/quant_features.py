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
#
# History: yes_price + price_extremity were cut after E1 backtest revealed
# label leakage (they are derived from the market price at resolution,
# which the label is also derived from — see backtest/report.md).
# log_liquidity was cut because it had 0% importance across all 5 walk-forward
# folds in both E1 and E1b.

FEATURE_NAMES: list[str] = [
    "info_ratio",         # volume_24h / sqrt(days_left_raw + 1) / 10_000
    "log_volume_total",   # log1p(volume_total)
    "days_left",          # time to resolution, clamped >= 0.5
]

# Live-bet filter: refuse bets when yes_price is at the price tails where
# (a) the model is poorly calibrated and (b) Kelly compounding amplifies
# losses absurdly. See backtest/no_leakage/report.md.
LIVE_BET_PRICE_MIN = 0.10
LIVE_BET_PRICE_MAX = 0.90


def in_live_bet_price_range(yes_price: float) -> bool:
    """True iff `yes_price` is in [LIVE_BET_PRICE_MIN, LIVE_BET_PRICE_MAX]."""
    return LIVE_BET_PRICE_MIN <= yes_price <= LIVE_BET_PRICE_MAX


# ── Live bet sizing policy ────────────────────────────────────────────────────
# These constants encode the live-deployment bet-policy that the backtest
# evaluated. Any change here is a real money policy change.

LIVE_BET_KELLY_MULTIPLIER = 0.5      # Half-Kelly stake sizing
LIVE_BET_MAX_BET_PCT = 0.05          # Cap individual bet at 5% of bankroll
LIVE_BET_MIN_EDGE = 0.03             # Refuse bets with net edge below 3%
LIVE_BET_COST = 0.01                 # Fee + slippage proxy for net-edge gate
LIVE_BET_DEFAULT_BANKROLL = 100.0    # Reference unit when no bankroll passed


def compute_kelly_bet(
    *,
    calibrated_prob_crowd_wrong: float,
    market_price: float,
    bankroll: float = LIVE_BET_DEFAULT_BANKROLL,
) -> tuple[float, str]:
    """Return the live-policy Kelly stake + side selection for a single market.

    Args:
        calibrated_prob_crowd_wrong: model's calibrated probability that the
            crowd's directional belief is wrong (per the alphafeed label
            convention — see backend/adapters/train_model.py).
        market_price: yes_price (the crowd's current YES probability).
        bankroll: reference capital. Defaults to LIVE_BET_DEFAULT_BANKROLL so
            the stake size is comparable across signals.

    Returns:
        (stake_dollars, direction) where direction is "YES" or "NO".
        Stake is zero when (a) price is outside the live-bet range,
        (b) net edge is below LIVE_BET_MIN_EDGE, or (c) the model agrees with
        the market direction. When stake is zero, direction defaults to "YES"
        as a neutral placeholder.

    Side selection is automatic. The function picks the side (YES or NO)
    that the model deems mispriced, then sizes the bet at half-Kelly capped
    at LIVE_BET_MAX_BET_PCT.
    """
    if not in_live_bet_price_range(market_price):
        return 0.0, "YES"

    # Translate model output to p(Yes wins).
    if market_price >= 0.5:
        p_yes_wins = 1.0 - calibrated_prob_crowd_wrong
    else:
        p_yes_wins = calibrated_prob_crowd_wrong

    # Pick the side with positive gross edge and size via binary Kelly.
    if p_yes_wins > market_price:
        direction = "YES"
        side_prob = p_yes_wins
        side_price = market_price
    elif p_yes_wins < market_price:
        direction = "NO"
        side_prob = 1.0 - p_yes_wins
        side_price = 1.0 - market_price
    else:
        return 0.0, "YES"

    gross_edge = side_prob / side_price - 1.0
    net_edge = gross_edge - LIVE_BET_COST
    if net_edge < LIVE_BET_MIN_EDGE:
        return 0.0, direction

    # Closed-form binary Kelly fraction for a one-shot bet.
    kelly_fraction = (side_prob - side_price) / (1.0 - side_price)
    sized = max(0.0, kelly_fraction * LIVE_BET_KELLY_MULTIPLIER)
    capped_fraction = min(sized, LIVE_BET_MAX_BET_PCT)
    return float(bankroll * capped_fraction), direction


def compute_features(opp: dict) -> dict[str, float]:
    """
    Compute the 3 model features from an enriched opportunity dict.

    opp must have:
      - curPrice (float, required) — kept in the input contract for the
        downstream live-bet filter even though it's no longer a feature
    opp may have:
      - volume_24h, volumeTotal, days_left  (all optional, default 0/0/0)

    Returns a dict with exactly the keys in FEATURE_NAMES.
    Uses days_left RAW (before clamping) for info_ratio, clamped for the
    days_left feature.
    """
    _ = float(opp["curPrice"])  # validate presence
    vol = float(opp.get("volume_24h") or 0)
    volume_total = float(opp.get("volumeTotal") or 0)
    days_raw = float(opp.get("days_left") or 0)
    days_feat = max(days_raw, 0.5)

    return {
        "info_ratio":       vol / ((days_raw + 1) ** 0.5) / 10_000,
        "log_volume_total": log1p(volume_total),
        "days_left":        days_feat,
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

    # 5a. Contrary plays — crowd certain but many traders disagree
    contrary = sorted(
        [o for o in opportunities if o.get("contraryFlag")],
        key=lambda o: o.get("countSignal", 0),
        reverse=True,
    )
    if contrary:
        best = contrary[0]
        count_pct = round(best.get("countSignal", 0) * 100)
        insights.append(
            f"Contrarian alert: '{best['title'][:50]}' — crowd priced at "
            f"{best['curPrice']:.0%} but {count_pct}% of smart traders are positioned against it."
        )

    # 6. Model staleness alert (fires only if model is > 60 days old)
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
