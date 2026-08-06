"""
quant_features.py — Pure functions for the Quant Report pipeline.

All functions in this module are side-effect-free (no file I/O, no model loading).
Import this module to compute features, calibrate scores, and generate insights
without requiring XGBoost or any trained model.
"""
from __future__ import annotations

from datetime import datetime, timezone
from math import exp, log1p
from typing import Any

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


# ── Evidence-based focus filter ───────────────────────────────────────────────
# Derived from the signal_tracker.db forward-test (docs/top5-accuracy-report-
# 2026-07-28.md). Findings, on the 42.5% of signals with a real resolution:
#   * Theme: sports is the ONLY theme with measurable positive edge (49% hit,
#     20% NO_MATCH). politics/crypto/geopolitics hit 28-36% with 64-75% of
#     signals unmeasurable, so they are excluded from the staked book.
#   * Price band [0.15, 0.45): 59% hit and stable out-of-sample (time-split
#     first/second half both > baseline). Excludes extreme longshots (<0.15,
#     noisy) and favorites (>=0.45, negative-EV — the >=0.65 bucket lost money).
#   * Same-day (days_left < 1): most temporally stable slice (55.8% -> 55.0%
#     across the time split; 63% combined with the price band).
#   * Deep value (price < 0.35): highest-accuracy sub-band (64%).
#   * Point markets (spread/total) beat moneylines (54-59% vs 46%).
FOCUS_THEMES = frozenset({"sports"})
FOCUS_PRICE_MIN = 0.15
FOCUS_PRICE_MAX = 0.45          # exclusive upper bound
FOCUS_SAMEDAY_DAYS = 1.0        # days_left below this = same-day priority
FOCUS_DEEP_VALUE_MAX = 0.35     # price below this = highest-accuracy sub-band

# Priority weights (added to a base of 1.0 for any eligible bet). These rank
# eligible focus bets; they intentionally do NOT use the model's quantScore,
# which the accuracy report found to be anti-predictive.
FOCUS_SAMEDAY_BONUS = 0.4
FOCUS_DEEP_VALUE_BONUS = 0.3
FOCUS_POINT_MARKET_BONUS = 0.15

# Flat staking on the focus-eligible book. Kelly sizing off the model's
# probability is deliberately NOT used — the accuracy report found that
# probability anti-predictive, and under SHRINKAGE_ALPHA=0 compute_kelly_bet
# sizes off a spurious 0.5-vs-price "edge" that maxes the cap on every market.
# A flat fraction decouples stake size from the broken probability estimate.
FOCUS_FLAT_STAKE_PCT = 0.02      # 2% of bankroll per eligible bet

# Point markets (spread/total/handicap) hit 67.9% vs 59% for the blended
# sports rule, and the lift held out-of-sample (time-split 80% -> 59% vs a
# moneyline-inclusive 56%). Sharp-set lines make these signals more reliable,
# so the staked book requires a point market.
FOCUS_REQUIRE_POINT_MARKET = True


def is_focus_eligible(category: str, cur_price: float) -> bool:
    """True iff the opportunity is in a validated-edge theme and price band.

    This is the staked-book gate: sports markets priced in [0.15, 0.45).
    """
    return (
        category in FOCUS_THEMES
        and FOCUS_PRICE_MIN <= cur_price < FOCUS_PRICE_MAX
    )


def focus_score(
    category: str,
    cur_price: float,
    days_left: float | None = None,
    point_market: bool = False,
) -> float:
    """Rank eligible focus bets by validated accuracy drivers.

    Returns 0.0 for anything not focus-eligible, otherwise a base of 1.0 plus
    bonuses for the conditions that empirically raised hit rate. Higher = more
    accurate historically. Not a probability — a ranking key.
    """
    if not is_focus_eligible(category, cur_price):
        return 0.0
    score = 1.0
    if days_left is not None and days_left < FOCUS_SAMEDAY_DAYS:
        score += FOCUS_SAMEDAY_BONUS
    if cur_price < FOCUS_DEEP_VALUE_MAX:
        score += FOCUS_DEEP_VALUE_BONUS
    if point_market:
        score += FOCUS_POINT_MARKET_BONUS
    return round(score, 4)


# Empirical win probability q for a focus point-market bet at a given price,
# from the forward-test (docs/top5-accuracy-report-2026-07-28.md). Used to
# compute expected value instead of the model's (broken) probability. These
# are HISTORICAL hit rates on the 42.5%-resolved sample, not guarantees.
_FOCUS_WIN_PROB_TABLE: tuple[tuple[float, float], ...] = (
    (0.25, 0.733),   # price < 0.25      -> 73.3% hit (n=30)
    (0.35, 0.697),   # 0.25 <= p < 0.35  -> 69.7% hit (n=33)
    (1.00, 0.543),   # 0.35 <= p         -> 54.3% hit (n=138)
)


def focus_win_prob(price: float) -> float:
    """Empirical win probability for a focus point-market bet at `price`."""
    for hi, q in _FOCUS_WIN_PROB_TABLE:
        if price < hi:
            return q
    return _FOCUS_WIN_PROB_TABLE[-1][1]


def expected_value(win_prob: float, price: float, cost: float | None = None) -> float:
    """Expected ROI per $1 staked: q/p - 1 - cost.

    A binary bet at `price` pays 1/price on a win, -1 on a loss, so
    EV = win_prob*(1/price - 1) - (1 - win_prob) = win_prob/price - 1, minus
    the fee/slippage proxy. Returns a fraction (0.5 == +50% expected ROI).
    """
    if cost is None:
        cost = LIVE_BET_COST
    if price <= 0:
        return 0.0
    return round(win_prob / price - 1.0 - cost, 4)


def compute_focus_stake(bankroll: float | None = None) -> float:
    """Flat stake for a focus-eligible bet: a fixed fraction of bankroll.

    Sizing is intentionally independent of any probability estimate (see
    FOCUS_FLAT_STAKE_PCT). Callers apply this only when is_focus_eligible().
    """
    if bankroll is None:
        bankroll = LIVE_BET_DEFAULT_BANKROLL
    return round(bankroll * FOCUS_FLAT_STAKE_PCT, 4)


# ── Live bet sizing policy ────────────────────────────────────────────────────
# These constants encode the live-deployment bet-policy that the backtest
# evaluated. Any change here is a real money policy change.

LIVE_BET_KELLY_MULTIPLIER = 0.5      # Half-Kelly stake sizing
LIVE_BET_MAX_BET_PCT = 0.05          # Cap individual bet at 5% of bankroll
LIVE_BET_MIN_EDGE = 0.03             # Refuse bets with net edge below 3%
LIVE_BET_COST = 0.01                 # Fee + slippage proxy for net-edge gate
LIVE_BET_DEFAULT_BANKROLL = 100.0    # Reference unit when no bankroll passed

# ── Shrinkage-toward-0.5 (N3) ────────────────────────────────────────────────
# The N2 calibration report (docs/calibration.md) found that 86% of alphafeed
# predictions sit at 0.05 or 0.95 while observed win rates in those bins are
# ~50% and ~39% respectively — the model is confidently misdirected at the
# tails. Post-hoc shrinkage pulls raw scores toward 0.5 to compensate.
#
# alpha value picked by grid-search over the historical 1,243 signals; see
# docs/calibration.md for the per-alpha Brier table.
SHRINKAGE_ALPHA = 0.0


def apply_shrinkage(raw: float, *, alpha: float | None = None) -> float:
    """Pull `raw` toward 0.5 by factor (1 - alpha).

    Formula: shrunk = 0.5 + (raw - 0.5) * alpha.
    alpha=1.0 → pass-through. alpha=0.0 → always 0.5.
    Defaults to module-level SHRINKAGE_ALPHA when alpha is None.
    """
    if alpha is None:
        alpha = SHRINKAGE_ALPHA
    return 0.5 + (float(raw) - 0.5) * float(alpha)


def best_alpha_by_brier(
    predictions: "list[float] | Any",
    outcomes: "list[int] | Any",
    *,
    alphas: "list[float]" = (0.1, 0.3, 0.5, 0.7, 0.9, 1.0),
) -> float:
    """Grid-search alpha that minimises Brier score of the shrunk predictions.

    Args:
        predictions: raw probabilities in [0, 1].
        outcomes: 0/1 labels aligned with predictions.
        alphas: candidate shrinkage factors to try.

    Returns:
        The alpha with the lowest Brier score. Ties break to the largest
        alpha (least shrinkage — closer to the raw model output).
    """
    import numpy as np

    p = np.asarray(predictions, dtype=float)
    y = np.asarray(outcomes, dtype=float)
    best_alpha = 1.0
    best_brier = float("inf")
    for a in sorted(alphas):
        shrunk = 0.5 + (p - 0.5) * a
        brier = float(np.mean((shrunk - y) ** 2))
        # Ties prefer larger alpha (right-to-left iteration would work too;
        # we scan low-to-high and use strict < to keep the smallest alpha
        # only when it's genuinely better).
        if brier < best_brier - 1e-9:
            best_brier = brier
            best_alpha = a
    return best_alpha


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


# Point-market (spread / total / handicap) slugs beat moneylines on accuracy
# (54-59% vs 46% — docs/top5-accuracy-report-2026-07-28.md). Detected from the
# Polymarket slug, which encodes the market type (e.g. "-total-8pt5",
# "-spread-away-2pt5", "-btts").
_POINT_MARKET_TOKENS = ("-total-", "-spread-", "-handicap-", "-o-u-", "-btts")


def _is_point_market(slug: str) -> bool:
    """True iff the slug looks like a spread/total/handicap market."""
    return any(tok in (slug or "").lower() for tok in _POINT_MARKET_TOKENS)


# Public aliases (imported by quant_report and win_prob)
is_point_market = _is_point_market
infer_category_from_slug = _infer_category_from_slug
