"""Empirical win-probability model for AlphaFeed opportunities.

Produces q = P(the bet on this opportunity's side wins) from features that are
actually predictive (price, point-market, same-day, liquidity, category) — NOT
the anti-predictive XGBoost score. See
docs/superpowers/specs/2026-08-05-win-probability-model-design.md.
"""
from __future__ import annotations

import math
from typing import Any

from quant_features import infer_category_from_slug, is_point_market

_CATEGORIES = ["sports", "politics", "crypto", "geopolitics", "macro", "other"]
FEATURES: list[str] = ["price", "is_point_market", "same_day", "log_liquidity"] + [
    f"cat_{c}" for c in _CATEGORIES
]


def _price_of(opp: dict[str, Any]) -> float:
    for k in ("curPrice", "entry_price", "market_price"):
        v = opp.get(k)
        if v is not None:
            return float(v)
    return 0.5


def _slug_of(opp: dict[str, Any]) -> str:
    return opp.get("slug") or opp.get("market_slug") or ""


def featurize(opp: dict[str, Any]) -> dict[str, float]:
    """Map an opportunity dict OR a signal_tracker row to the model feature dict."""
    slug = _slug_of(opp)
    price = _price_of(opp)
    days_left = opp.get("days_left")
    liquidity = float(opp.get("liquidity") or 0.0)
    category = opp.get("category") or infer_category_from_slug(slug, title=opp.get("title", ""))
    if category not in _CATEGORIES:
        category = "other"
    feats = {
        "price": price,
        "is_point_market": 1.0 if is_point_market(slug) else 0.0,
        "same_day": 1.0 if (days_left is not None and float(days_left) < 1.0) else 0.0,
        "log_liquidity": math.log1p(max(liquidity, 0.0)),
    }
    for c in _CATEGORIES:
        feats[f"cat_{c}"] = 1.0 if category == c else 0.0
    return {k: feats[k] for k in FEATURES}
