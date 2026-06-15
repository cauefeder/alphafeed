"""Portfolio metrics: Sharpe, max drawdown, win rate.

All functions take pandas Series; none touch the model or strategy.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def annualised_sharpe(returns: pd.Series, *, bets_per_year: int = 365) -> float:
    """Naïve annualised Sharpe ratio.

    `returns` is per-bet realised return (decimal). Zero / constant series
    return 0.0 (degenerate). `bets_per_year` defaults to 365 — reasonable
    for ~1 bet/day cron cadence; pass a different value for your real
    cadence.
    """
    arr = returns.to_numpy(dtype=float)
    if arr.size == 0:
        return 0.0
    mean = arr.mean()
    if mean == 0.0:
        return 0.0
    std = arr.std(ddof=1) if arr.size > 1 else 0.0
    if std <= 1e-12:
        # Constant return — interpret as infinite Sharpe; clamp to a huge
        # finite value so downstream sorting / printing doesn't NaN out.
        return float(np.sign(mean)) * 1e6
    return float(mean / std * np.sqrt(bets_per_year))


def max_drawdown(equity_curve: pd.Series) -> float:
    """Return the largest peak-to-trough drawdown as a negative fraction.

    Returns 0.0 if the curve never declines from its running peak.
    """
    arr = equity_curve.to_numpy(dtype=float)
    if arr.size == 0:
        return 0.0
    peaks = np.maximum.accumulate(arr)
    dd = (arr - peaks) / peaks
    return float(dd.min())  # already negative or zero


def win_rate(pnls: pd.Series) -> float:
    """Fraction of *non-zero* P&L observations that are positive.

    Zero-P&L observations (no bet taken) are excluded so the rate
    reflects bet quality, not bet frequency.
    """
    arr = pnls.to_numpy(dtype=float)
    nz = arr[arr != 0.0]
    if nz.size == 0:
        return 0.0
    wins = (nz > 0).sum()
    return float(wins / nz.size)
