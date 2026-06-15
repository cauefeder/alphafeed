"""TDD coverage for the walk-forward backtest (E1).

Three modules under test:

- backtest.walk_forward — expanding-window fold splitter
- backtest.sim         — pure bet sim primitives (Kelly, edge, single-bet P&L)
- backtest.metrics     — Sharpe, max drawdown, win rate

Tests use synthetic data — no real XGBoost training, no network. The
end-to-end run-on-real-data path is exercised by run_backtest.py and
spot-checked manually rather than in unit tests.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from backtest.metrics import (
    annualised_sharpe,
    max_drawdown,
    win_rate,
)
from backtest.sim import (
    compute_edge,
    kelly_fraction,
    simulate_bet,
    simulate_portfolio,
)
from backtest.walk_forward import split_folds


# ---------- walk_forward.split_folds ----------


def test_split_folds_returns_five_by_default() -> None:
    n = 100
    folds = split_folds(n_rows=n)
    assert len(folds) == 5


def test_split_folds_train_expands_over_folds() -> None:
    folds = split_folds(n_rows=1000)
    train_sizes = [len(tr) for tr, _ in folds]
    assert train_sizes == sorted(train_sizes)
    # Last train > first train
    assert train_sizes[-1] > train_sizes[0]


def test_split_folds_test_disjoint_from_train() -> None:
    """Within each fold, train and test indices must not overlap."""
    folds = split_folds(n_rows=500, n_folds=5)
    for tr, te in folds:
        assert set(tr).isdisjoint(set(te))
        # All train indices are strictly before all test indices (chronological)
        assert max(tr) < min(te)


def test_split_folds_covers_tail() -> None:
    """The union of test indices across folds covers the test portion
    starting at the first 60% boundary."""
    n = 100
    folds = split_folds(n_rows=n)
    all_test: set[int] = set()
    for _, te in folds:
        all_test.update(te)
    assert min(all_test) == 60  # first test starts at 60%
    assert max(all_test) == n - 1  # last test ends at n-1


def test_split_folds_rejects_invalid_n_folds() -> None:
    with pytest.raises(ValueError):
        split_folds(n_rows=100, n_folds=0)


# ---------- sim.kelly_fraction ----------


def test_kelly_fraction_zero_at_fair_price() -> None:
    # p == price → zero edge → zero fraction
    assert kelly_fraction(true_prob=0.50, market_price=0.50) == pytest.approx(0.0)


def test_kelly_fraction_positive_when_underpriced() -> None:
    # Market 0.40, true 0.60 → expected positive fraction
    f = kelly_fraction(true_prob=0.60, market_price=0.40)
    assert f > 0.0
    assert f == pytest.approx((0.60 - 0.40) / (1 - 0.40))  # = 0.333


def test_kelly_fraction_picks_no_side_when_market_overprices_yes() -> None:
    """When model says p_yes=0.30 but market trades at 0.50, the model
    disagrees with the crowd → fraction is positive (bet on No)."""
    f = kelly_fraction(true_prob=0.30, market_price=0.50)
    # Side flips to No: winning_prob=0.70, winning_price=0.50 → f = 0.4
    assert f == pytest.approx(0.40)


def test_kelly_fraction_capped_at_one() -> None:
    """Even extreme p never blows past 100% of bankroll."""
    f = kelly_fraction(true_prob=0.999, market_price=0.01)
    assert 0.0 <= f <= 1.0


# ---------- sim.compute_edge ----------


def test_compute_edge_yes_side() -> None:
    # Stake $1 on Yes at 0.50, true p_yes=0.65, no cost
    # Expected return = 0.65 / 0.50 - 1 = 0.30
    e = compute_edge(true_prob=0.65, market_price=0.50, cost=0.0)
    assert e == pytest.approx(0.30)


def test_compute_edge_after_cost() -> None:
    # Same as above minus a 1% slippage proxy
    e_net = compute_edge(true_prob=0.65, market_price=0.50, cost=0.01)
    assert e_net == pytest.approx(0.30 - 0.01)


def test_compute_edge_negative_when_cost_exceeds_gross() -> None:
    """Even with auto-side picking, a large cost can flip net edge negative.
    Yes price 0.50, p=0.51 → gross 0.02; cost 0.05 → net -0.03."""
    e = compute_edge(true_prob=0.51, market_price=0.50, cost=0.05)
    assert e < 0.0


# ---------- sim.simulate_bet ----------


def test_simulate_bet_yes_winner_pays_decimal_odds_minus_cost() -> None:
    """Bet $5 on Yes at 0.50 (decimal odds 2.0), market resolves Yes.
    Gross P&L = 5 * (1/0.50 - 1) = 5. Cost 1% of stake reduces by 0.05."""
    pnl = simulate_bet(
        true_prob=0.65, market_price=0.50, resolved_yes=1,
        bankroll=100.0, kelly_fraction_cap=1.0,
        kelly_multiplier=1.0, max_bet_pct=1.0,
        min_edge=0.0, cost=0.01,
    )
    # Kelly fraction with p=0.65, price=0.50: (0.65-0.50)/(1-0.50) = 0.30
    # Stake = bankroll * 0.30 = 30. Won → pnl = 30 * (1/0.50 - 1) - 30*0.01 = 30 - 0.30 = 29.70
    assert pnl == pytest.approx(29.70)


def test_simulate_bet_yes_loser_returns_negative_stake_plus_cost() -> None:
    """Same Yes bet, market resolves No → lose stake."""
    pnl = simulate_bet(
        true_prob=0.65, market_price=0.50, resolved_yes=0,
        bankroll=100.0, kelly_fraction_cap=1.0,
        kelly_multiplier=1.0, max_bet_pct=1.0,
        min_edge=0.0, cost=0.01,
    )
    # Stake 30, lost → pnl = -30 - 30*0.01 = -30.30
    assert pnl == pytest.approx(-30.30)


def test_simulate_bet_no_side_winner() -> None:
    """Bet on No when crowd-belief is overconfident. p_yes=0.30, market 0.50.
    Market resolves No (resolved_yes=0) → No bet wins.
    Kelly fraction for No side: (1-p) - (1-price) over 1 - (1-price)
                              = (0.70 - 0.50) / 0.50 = 0.40
    Stake 100*0.40 = 40. No price = 0.50, decimal odds = 2.0
    Win → pnl = 40 * (1/0.50 - 1) - 40*0.01 = 40 - 0.40 = 39.60"""
    pnl = simulate_bet(
        true_prob=0.30, market_price=0.50, resolved_yes=0,
        bankroll=100.0, kelly_fraction_cap=1.0,
        kelly_multiplier=1.0, max_bet_pct=1.0,
        min_edge=0.0, cost=0.01,
    )
    assert pnl == pytest.approx(39.60)


def test_simulate_bet_below_min_edge_returns_zero() -> None:
    """If net edge below threshold, no bet placed."""
    pnl = simulate_bet(
        true_prob=0.51, market_price=0.50, resolved_yes=1,
        bankroll=100.0, kelly_fraction_cap=1.0,
        kelly_multiplier=0.5, max_bet_pct=0.05,
        min_edge=0.03, cost=0.01,  # net edge ≈ 0.02 - 0.01 = 0.01, below 0.03 cutoff
    )
    assert pnl == 0.0


def test_simulate_bet_respects_max_bet_pct_cap() -> None:
    """Kelly might want 30%, but max_bet_pct=0.05 caps stake at 5% of bankroll."""
    pnl = simulate_bet(
        true_prob=0.80, market_price=0.50, resolved_yes=1,
        bankroll=100.0, kelly_fraction_cap=1.0,
        kelly_multiplier=1.0, max_bet_pct=0.05,
        min_edge=0.0, cost=0.0,
    )
    # Stake = 5 (capped). Win → 5 * (1/0.50 - 1) = 5
    assert pnl == pytest.approx(5.0)


# ---------- sim.simulate_portfolio ----------


def _bets_df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def test_simulate_portfolio_compounds_bankroll() -> None:
    """Sequential bets compound off the running bankroll."""
    bets = _bets_df([
        {"true_prob": 0.65, "market_price": 0.50, "resolved_yes": 1},
        {"true_prob": 0.65, "market_price": 0.50, "resolved_yes": 1},
    ])
    out = simulate_portfolio(
        bets,
        starting_bankroll=100.0,
        kelly_multiplier=1.0, max_bet_pct=1.0,
        min_edge=0.0, cost=0.0,
    )
    # First bet: stake 30, win → +30, bankroll 130
    # Second bet: stake 130*0.30 = 39, win → +39, bankroll 169
    assert out["bankroll"].iloc[-1] == pytest.approx(169.0)
    assert out["bankroll"].iloc[0] == pytest.approx(130.0)


def test_simulate_portfolio_records_zero_pnl_for_skipped() -> None:
    bets = _bets_df([
        {"true_prob": 0.51, "market_price": 0.50, "resolved_yes": 1},
    ])
    out = simulate_portfolio(
        bets,
        starting_bankroll=100.0,
        kelly_multiplier=0.5, max_bet_pct=0.05,
        min_edge=0.10, cost=0.0,  # min_edge too high → skip
    )
    assert out["bankroll"].iloc[-1] == 100.0
    assert bool(out["bet_taken"].iloc[0]) is False


# ---------- metrics ----------


def test_max_drawdown_simple() -> None:
    # Curve: 100 → 110 → 90 → 95 → 80
    eq = pd.Series([100, 110, 90, 95, 80])
    dd = max_drawdown(eq)
    # Peak 110 → trough 80 → drawdown = -30/110 = -0.2727
    assert dd == pytest.approx(-30 / 110)


def test_max_drawdown_flat_or_rising_is_zero() -> None:
    assert max_drawdown(pd.Series([100, 110, 120])) == 0.0


def test_win_rate_basic() -> None:
    pnls = pd.Series([5, -3, 7, 0, -1, 2])
    # Wins = 3 (5,7,2), losses = 2 (-3,-1), zeros (0) excluded
    assert win_rate(pnls) == pytest.approx(3 / 5)


def test_annualised_sharpe_zero_returns_zero() -> None:
    assert annualised_sharpe(pd.Series([0.0, 0.0, 0.0])) == 0.0


def test_annualised_sharpe_positive_for_consistent_winner() -> None:
    rets = pd.Series([0.01] * 100)  # constant 1% per bet
    s = annualised_sharpe(rets, bets_per_year=200)
    # mean/std → infinite if std=0; we expect a finite, large positive value
    # because we use a small-epsilon guard
    assert s > 100  # absurdly high — flags that the function returns *something*
