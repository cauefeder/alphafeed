"""End-to-end walk-forward backtest of the AlphaFeed XGBoost model.

Reads data/historical_markets.csv, runs 5-fold expanding-window
walk-forward, simulates calibrated Kelly betting, writes:
  backtest/report.md
  backtest/charts/equity_curve.png
  backtest/charts/drawdown.png
  backtest/charts/calibration.png
  backtest/charts/feature_importance.png
  backtest/charts/monthly_pnl.png

Usage: python backtest/run_backtest.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Windows cp1252 chokes on Unicode arrows/box-drawing in print statements
# (same pattern used by multifactor/refresh.py). Force UTF-8 stdout.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve()
REPO_ROOT = _HERE.parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend" / "adapters"))
sys.path.insert(0, str(REPO_ROOT))

from backtest.metrics import annualised_sharpe, max_drawdown, win_rate  # noqa: E402
from backtest.sim import simulate_portfolio  # noqa: E402
from backtest.walk_forward import split_folds  # noqa: E402
from train_model import (  # noqa: E402
    build_feature_matrix,
    compute_class_imbalance,
    fit_calibrator,
    xgb_hyperparams,
)

DATA_PATH = REPO_ROOT / "data" / "historical_markets.csv"
REPORT_PATH = _HERE.parent / "report.md"
CHARTS_DIR = _HERE.parent / "charts"

STARTING_BANKROLL = 100.0
KELLY_MULTIPLIER = 0.5
MAX_BET_PCT = 0.05
MIN_EDGE = 0.03
COST = 0.01


def _platt(probas: np.ndarray, a: float, b: float) -> np.ndarray:
    """Apply Platt scaling: sigmoid(a + b * p)."""
    z = a + b * probas
    return 1.0 / (1.0 + np.exp(-z))


def _crowd_wrong_to_p_yes(p_crowd_wrong: np.ndarray, yes_price: np.ndarray) -> np.ndarray:
    """Convert model output (p_crowd_wrong) to p(yes_wins).

    train_model labels y=1 when crowd was wrong, with crowd direction =
    Yes if yes_price >= 0.5. So:
      - If yes_price >= 0.5 (crowd thinks Yes): crowd_wrong → No wins
        → p_yes_wins = 1 - p_crowd_wrong
      - If yes_price <  0.5 (crowd thinks No):  crowd_wrong → Yes wins
        → p_yes_wins = p_crowd_wrong
    """
    crowd_yes = yes_price >= 0.5
    return np.where(crowd_yes, 1.0 - p_crowd_wrong, p_crowd_wrong)


def _run_one_fold(
    df: pd.DataFrame, train_idx: range, test_idx: range, fold_id: int,
) -> dict:
    """Train xgb, calibrate Platt, score test, return predictions + metrics."""
    import xgboost as xgb
    from sklearn.metrics import brier_score_loss, roc_auc_score

    train_df = df.iloc[list(train_idx)]
    test_df = df.iloc[list(test_idx)]

    X_train, y_train = build_feature_matrix(train_df)
    X_test, y_test = build_feature_matrix(test_df)

    # Split off last 15% of train for Platt calibration
    val_cut = int(len(X_train) * 0.85)
    X_fit, y_fit = X_train[:val_cut], y_train[:val_cut]
    X_val, y_val = X_train[val_cut:], y_train[val_cut:]

    _, _, spw = compute_class_imbalance(y_fit)
    params = xgb_hyperparams(scale_pos_weight=spw)
    model = xgb.XGBClassifier(**params, n_estimators=300)
    model.fit(X_fit, y_fit, eval_set=[(X_val, y_val)], verbose=False)

    val_probas = model.predict_proba(X_val)[:, 1]
    platt_a, platt_b = fit_calibrator(val_probas, y_val)

    test_probas_raw = model.predict_proba(X_test)[:, 1]
    test_probas_cal = _platt(test_probas_raw, platt_a, platt_b)

    auc = float(roc_auc_score(y_test, test_probas_raw))
    brier_raw = float(brier_score_loss(y_test, test_probas_raw))
    brier_cal = float(brier_score_loss(y_test, test_probas_cal))

    yes_prices = test_df["yes_price"].to_numpy(dtype=float)
    resolved = test_df["resolved_yes"].to_numpy(dtype=int)
    p_yes = _crowd_wrong_to_p_yes(test_probas_cal, yes_prices)

    bets = pd.DataFrame({
        "fold": fold_id,
        "true_prob": p_yes,
        "market_price": yes_prices,
        "resolved_yes": resolved,
    })

    # Track in lockstep with train_model.build_feature_matrix — see
    # quant_features.FEATURE_NAMES for the canonical list.
    from quant_features import FEATURE_NAMES  # noqa: E402
    importance = dict(zip(FEATURE_NAMES, [float(v) for v in model.feature_importances_]))

    return {
        "fold": fold_id,
        "n_train": int(len(X_train)),
        "n_test": int(len(X_test)),
        "test_auc": auc,
        "brier_raw": brier_raw,
        "brier_calibrated": brier_cal,
        "feature_importance": importance,
        "platt": {"a": platt_a, "b": platt_b},
        "bets": bets,
    }


def _write_charts(portfolio: pd.DataFrame, fold_results: list[dict]) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    CHARTS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Equity curve
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(portfolio.index, portfolio["bankroll"], lw=1.5, color="#1f77b4")
    ax.axhline(STARTING_BANKROLL, ls="--", color="gray", lw=0.8)
    ax.set_title("Walk-forward equity curve (half-Kelly, 1% cost)")
    ax.set_xlabel("Bet # (chronological)")
    ax.set_ylabel("Bankroll ($)")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(CHARTS_DIR / "equity_curve.png", dpi=110)
    plt.close(fig)

    # 2. Drawdown
    peaks = portfolio["bankroll"].cummax()
    dd = (portfolio["bankroll"] - peaks) / peaks
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.fill_between(portfolio.index, dd, 0, color="#d62728", alpha=0.4)
    ax.set_title("Drawdown")
    ax.set_xlabel("Bet # (chronological)")
    ax.set_ylabel("Drawdown")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(CHARTS_DIR / "drawdown.png", dpi=110)
    plt.close(fig)

    # 3. Calibration plot — bin probabilities into deciles, plot actual win rate
    bets_with_pnl = portfolio[portfolio["bet_taken"]].copy()
    if len(bets_with_pnl) > 20:
        # We need p_yes vs realized_yes. Re-derive from sim columns:
        # true_prob is p_yes (model), resolved_yes is the outcome.
        bins = np.linspace(0, 1, 11)
        labels = (bins[:-1] + bins[1:]) / 2
        bets_with_pnl["bin"] = pd.cut(
            bets_with_pnl["true_prob"], bins=bins, labels=labels, include_lowest=True,
        )
        agg = bets_with_pnl.groupby("bin", observed=True).agg(
            actual=("resolved_yes", "mean"), count=("resolved_yes", "size"),
        )
        fig, ax = plt.subplots(figsize=(6, 6))
        ax.plot([0, 1], [0, 1], ls="--", color="gray", lw=0.8, label="Perfect")
        ax.scatter(
            agg.index.astype(float), agg["actual"],
            s=np.sqrt(agg["count"]) * 8, alpha=0.6, color="#2ca02c",
            label="Observed (size ~ count)",
        )
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_xlabel("Predicted p(Yes wins)")
        ax.set_ylabel("Actual frequency Yes wins")
        ax.set_title("Calibration plot (held-out bets only)")
        ax.legend()
        ax.grid(alpha=0.3)
        fig.tight_layout()
        fig.savefig(CHARTS_DIR / "calibration.png", dpi=110)
        plt.close(fig)

    # 4. Feature importance stability across folds
    feat_names = list(fold_results[0]["feature_importance"].keys())
    fig, ax = plt.subplots(figsize=(8, 5))
    width = 0.15
    x = np.arange(len(feat_names))
    for k, fr in enumerate(fold_results):
        vals = [fr["feature_importance"][n] for n in feat_names]
        ax.bar(x + k * width, vals, width, label=f"Fold {fr['fold']}")
    ax.set_xticks(x + width * (len(fold_results) - 1) / 2)
    ax.set_xticklabels(feat_names, rotation=20, ha="right")
    ax.set_title("Feature importance per fold (gain)")
    ax.legend()
    ax.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(CHARTS_DIR / "feature_importance.png", dpi=110)
    plt.close(fig)

    # 5. P&L grouped by 100-bet bucket (proxy for time slice since no real ts)
    bucket_size = max(50, len(portfolio) // 30)
    portfolio_with_bucket = portfolio.copy()
    portfolio_with_bucket["bucket"] = portfolio_with_bucket.index // bucket_size
    bucket_pnl = portfolio_with_bucket.groupby("bucket")["pnl"].sum()
    fig, ax = plt.subplots(figsize=(10, 4))
    colors = ["#2ca02c" if v >= 0 else "#d62728" for v in bucket_pnl.values]
    ax.bar(bucket_pnl.index, bucket_pnl.values, color=colors, edgecolor="black", lw=0.5)
    ax.axhline(0, color="black", lw=0.8)
    ax.set_title(f"P&L per {bucket_size}-bet bucket")
    ax.set_xlabel("Bucket")
    ax.set_ylabel("P&L ($)")
    ax.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(CHARTS_DIR / "monthly_pnl.png", dpi=110)
    plt.close(fig)


def _write_report(
    *,
    n_markets: int,
    fold_results: list[dict],
    portfolio: pd.DataFrame,
) -> None:
    bets_taken = portfolio["bet_taken"].sum()
    total_pnl = portfolio["pnl"].sum()
    final_bankroll = portfolio["bankroll"].iloc[-1] if len(portfolio) else STARTING_BANKROLL
    total_return = (final_bankroll - STARTING_BANKROLL) / STARTING_BANKROLL

    bet_rows = portfolio[portfolio["bet_taken"]]
    per_bet_return = bet_rows["pnl"] / bet_rows["stake"].clip(lower=1e-9)
    sharpe = annualised_sharpe(per_bet_return, bets_per_year=365) if len(per_bet_return) else 0.0
    mdd = max_drawdown(portfolio["bankroll"])
    wr = win_rate(portfolio["pnl"])

    fold_rows: list[str] = []
    for fr in fold_results:
        fold_rows.append(
            f"| {fr['fold']} | {fr['n_train']:,} | {fr['n_test']:,} | "
            f"{fr['test_auc']:.3f} | {fr['brier_raw']:.4f} | {fr['brier_calibrated']:.4f} |"
        )

    feat_names = list(fold_results[0]["feature_importance"].keys())
    feat_rows: list[str] = []
    for n in feat_names:
        vals = [fr["feature_importance"][n] for fr in fold_results]
        mean = float(np.mean(vals))
        std = float(np.std(vals))
        feat_rows.append(f"| `{n}` | {mean:.3f} | {std:.3f} |")

    report = f"""# AlphaFeed XGBoost backtest — walk-forward, half-Kelly, 1% cost

Generated by `backtest/run_backtest.py`. Underlying data:
**{n_markets:,} resolved Polymarket markets** from `data/historical_markets.csv`,
walk-forward 5-fold expanding window (first 60% always train, trailing 40%
split into five test slices).

## Headline

| Metric | Value |
|---|---|
| Markets evaluated | {n_markets:,} |
| Bets taken | {bets_taken:,} ({bets_taken / max(n_markets, 1) * 100:.1f}% of universe) |
| Starting bankroll | ${STARTING_BANKROLL:.2f} |
| Final bankroll | ${final_bankroll:.2f} |
| Total P&L | ${total_pnl:+.2f} |
| Total return | {total_return * 100:+.1f}% |
| Per-bet annualised Sharpe | {sharpe:.2f} |
| Win rate | {wr * 100:.1f}% |
| Max drawdown | {mdd * 100:.1f}% |

## Per-fold model quality

| Fold | n_train | n_test | Test AUC | Brier (raw) | Brier (calibrated) |
|---|---|---|---|---|---|
{chr(10).join(fold_rows)}

A test AUC consistently above ~0.55 is the threshold the team uses
in `train_model.py` for a deployable model (0.58). If folds drift
below this line in later periods, the model's edge is decaying.

## Feature importance stability

mean ± std of XGBoost `feature_importances_` across the 5 folds:

| Feature | Mean importance | Std |
|---|---|---|
{chr(10).join(feat_rows)}

Features with high mean *and* low std are reliable signal carriers.
A feature that swings (high std) is a red flag for overfitting.

## Charts

- ![Equity curve](charts/equity_curve.png)
- ![Drawdown](charts/drawdown.png)
- ![Calibration plot](charts/calibration.png)
- ![Feature importance](charts/feature_importance.png)
- ![P&L per bucket](charts/monthly_pnl.png)

## Bet-policy parameters

These are the live-system thresholds; vary them in `run_backtest.py`
and rerun to compare strategy variants.

| Param | Value |
|---|---|
| Kelly multiplier | {KELLY_MULTIPLIER} (half-Kelly) |
| Max bet % of bankroll | {MAX_BET_PCT * 100:.1f}% |
| Min net edge to bet | {MIN_EDGE * 100:.1f}% |
| Effective cost (fee + slippage proxy) | {COST * 100:.1f}% |
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def main() -> int:
    print(f"[backtest] Loading {DATA_PATH}")
    df = pd.read_csv(DATA_PATH)
    # CSV is reverse-chronological (newest endDate first). Reverse so older
    # markets train, newer markets test — chronologically honest.
    df = df.iloc[::-1].reset_index(drop=True)
    n_markets = len(df)
    print(f"[backtest] {n_markets:,} resolved markets")

    folds = split_folds(n_rows=n_markets, n_folds=5)
    print(f"[backtest] Built {len(folds)} expanding-window folds")

    fold_results: list[dict] = []
    all_bets: list[pd.DataFrame] = []
    for k, (tr, te) in enumerate(folds, start=1):
        print(f"[backtest] Fold {k}: train [0:{tr.stop}] → test [{te.start}:{te.stop}]")
        fr = _run_one_fold(df, tr, te, fold_id=k)
        print(
            f"           AUC={fr['test_auc']:.3f}  "
            f"Brier raw={fr['brier_raw']:.4f}  cal={fr['brier_calibrated']:.4f}",
        )
        fold_results.append(fr)
        all_bets.append(fr["bets"])

    bets_concat = pd.concat(all_bets, ignore_index=True)

    # Apply the live-bet price-range filter — refuse bets outside [0.10, 0.90]
    # in line with the production policy (quant_features.in_live_bet_price_range).
    from quant_features import LIVE_BET_PRICE_MIN, LIVE_BET_PRICE_MAX  # noqa: E402
    pre_filter_n = len(bets_concat)
    in_range = (bets_concat["market_price"] >= LIVE_BET_PRICE_MIN) & (
        bets_concat["market_price"] <= LIVE_BET_PRICE_MAX
    )
    bets_concat = bets_concat[in_range].reset_index(drop=True)
    print(
        f"[backtest] Price-range filter [{LIVE_BET_PRICE_MIN}, {LIVE_BET_PRICE_MAX}]: "
        f"{len(bets_concat):,} of {pre_filter_n:,} candidates pass",
    )

    print(f"[backtest] Simulating portfolio over {len(bets_concat):,} candidate bets")
    portfolio = simulate_portfolio(
        bets_concat,
        starting_bankroll=STARTING_BANKROLL,
        kelly_multiplier=KELLY_MULTIPLIER,
        max_bet_pct=MAX_BET_PCT,
        min_edge=MIN_EDGE,
        cost=COST,
    )

    print("[backtest] Writing charts ...")
    _write_charts(portfolio, fold_results)

    print(f"[backtest] Writing {REPORT_PATH}")
    _write_report(
        n_markets=n_markets,
        fold_results=fold_results,
        portfolio=portfolio,
    )

    # Also dump the raw fold-by-fold output for downstream analysis
    diag = {
        "n_markets": n_markets,
        "fold_results": [
            {k: v for k, v in fr.items() if k != "bets"}
            for fr in fold_results
        ],
        "final_bankroll": float(portfolio["bankroll"].iloc[-1]),
        "total_pnl": float(portfolio["pnl"].sum()),
        "bets_taken": int(portfolio["bet_taken"].sum()),
    }
    (_HERE.parent / "diagnostics.json").write_text(json.dumps(diag, indent=2))
    print("[backtest] Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
