"""Bet simulation primitives.

A note on the betting math
==========================

For a binary Polymarket Yes/No contract with `market_price` ∈ (0, 1) for
the Yes side, the model produces `true_prob` = the probability the Yes
side wins. The bet side is chosen automatically:

    side = Yes if true_prob > market_price else No

Decimal odds are 1 / price_of_chosen_side, so the gross win on a stake S is

    win = S * (1 / price_of_chosen_side - 1)
    loss = -S

The Kelly fraction for binary outcomes simplifies to

    f* = (true_prob_of_winning_side - market_price_of_winning_side)
         / (1 - market_price_of_winning_side)

The functions below assume the model has already been calibrated; raw XGB
probabilities should not be fed in.
"""

from __future__ import annotations

import pandas as pd


def kelly_fraction(true_prob: float, market_price: float) -> float:
    """Optimal Kelly fraction for a binary contract.

    Picks the side with positive edge automatically. Returns 0.0 if the
    model agrees with the market price (no edge) or disagrees but the
    chosen side has a negative-edge denominator (degenerate).
    """
    # Decide side: Yes if model is more bullish than market
    if true_prob > market_price:
        winning_prob = true_prob
        winning_price = market_price
    else:
        winning_prob = 1.0 - true_prob
        winning_price = 1.0 - market_price

    edge = winning_prob - winning_price
    if edge <= 0:
        return 0.0
    denom = 1.0 - winning_price
    if denom <= 0:
        return 0.0
    f = edge / denom
    return max(0.0, min(1.0, f))


def compute_edge(true_prob: float, market_price: float, cost: float = 0.0) -> float:
    """Expected return per dollar staked, net of `cost` (fraction of stake).

    Positive means the chosen side has positive expectancy; negative means
    the chosen side is mispriced *against* you. Useful as an entry filter:
    only bet when compute_edge >= min_edge.
    """
    if true_prob > market_price:
        winning_prob = true_prob
        winning_price = market_price
    else:
        winning_prob = 1.0 - true_prob
        winning_price = 1.0 - market_price
    gross = winning_prob / winning_price - 1.0
    return gross - cost


def simulate_bet(
    *,
    true_prob: float,
    market_price: float,
    resolved_yes: int,
    bankroll: float,
    kelly_fraction_cap: float = 1.0,
    kelly_multiplier: float = 0.5,
    max_bet_pct: float = 0.05,
    min_edge: float = 0.03,
    cost: float = 0.01,
) -> float:
    """Simulate a single bet on one market. Returns the realised P&L
    (positive = win, negative = loss, zero = no bet).

    The bet is skipped if the net edge < min_edge OR Kelly fraction is 0.
    Stake is `bankroll * min(kelly_fraction_cap, f* * kelly_multiplier,
    max_bet_pct)`. Cost is deducted from the gross P&L proportional to stake.
    """
    f_star = kelly_fraction(true_prob, market_price)
    if f_star <= 0:
        return 0.0
    edge_net = compute_edge(true_prob, market_price, cost=cost)
    if edge_net < min_edge:
        return 0.0

    sized = min(kelly_fraction_cap, f_star * kelly_multiplier, max_bet_pct)
    stake = bankroll * sized
    if stake <= 0:
        return 0.0

    # Decide side
    bet_yes = true_prob > market_price
    winning_price = market_price if bet_yes else (1.0 - market_price)
    bet_won = (bet_yes and resolved_yes == 1) or (not bet_yes and resolved_yes == 0)

    if bet_won:
        gross = stake * (1.0 / winning_price - 1.0)
        return gross - stake * cost
    return -stake - stake * cost


def simulate_portfolio(
    bets: pd.DataFrame,
    *,
    starting_bankroll: float = 100.0,
    kelly_multiplier: float = 0.5,
    max_bet_pct: float = 0.05,
    min_edge: float = 0.03,
    cost: float = 0.01,
) -> pd.DataFrame:
    """Walk a DataFrame of bets in order, compounding the bankroll.

    Required columns: true_prob, market_price, resolved_yes.

    Returned frame adds bet_taken (bool), stake, pnl, bankroll columns.
    """
    required = {"true_prob", "market_price", "resolved_yes"}
    missing = required - set(bets.columns)
    if missing:
        raise ValueError(f"bets is missing columns: {missing}")

    out = bets.copy().reset_index(drop=True)
    n = len(out)
    bet_taken = [False] * n
    stakes = [0.0] * n
    pnls = [0.0] * n
    bankrolls = [0.0] * n

    bankroll = float(starting_bankroll)
    for i, row in out.iterrows():
        p = float(row["true_prob"])
        m = float(row["market_price"])
        r = int(row["resolved_yes"])

        f_star = kelly_fraction(p, m)
        edge_net = compute_edge(p, m, cost=cost)
        take = f_star > 0 and edge_net >= min_edge
        bet_taken[i] = take

        if take:
            sized = min(f_star * kelly_multiplier, max_bet_pct)
            stake = bankroll * sized
            stakes[i] = stake
            pnls[i] = simulate_bet(
                true_prob=p, market_price=m, resolved_yes=r,
                bankroll=bankroll,
                kelly_multiplier=kelly_multiplier,
                max_bet_pct=max_bet_pct,
                min_edge=min_edge,
                cost=cost,
            )
            bankroll += pnls[i]
        bankrolls[i] = bankroll

    out["bet_taken"] = bet_taken
    out["stake"] = stakes
    out["pnl"] = pnls
    out["bankroll"] = bankrolls
    return out
