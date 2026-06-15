"""E1b: same walk-forward harness as run_backtest.py, but with the two
leaked features (yes_price + price_extremity) masked from the model.

Drops feature indices 0 (yes_price) and 5 (price_extremity) from X. The
betting math still needs yes_price for stake sizing and side selection,
so we keep it in the test_df for the simulator — only the model never
sees it.

This answers: "do the remaining features (info_ratio, log_volume_total,
log_liquidity, days_left) carry any signal at all?"

Outputs go to backtest/no_leakage/ to keep them separate from the
original run.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

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
OUT_DIR = _HERE.parent / "no_leakage"
CHARTS_DIR = OUT_DIR / "charts"
REPORT_PATH = OUT_DIR / "report.md"

# Mask indices map to FEATURE_NAMES order from train_model:
# [yes_price, info_ratio, log_volume_total, log_liquidity, days_left, price_extremity]
LEAKED_COLS = (0, 5)
KEPT_NAMES = ["info_ratio", "log_volume_total", "log_liquidity", "days_left"]

STARTING_BANKROLL = 100.0
KELLY_MULTIPLIER = 0.5
MAX_BET_PCT = 0.05
MIN_EDGE = 0.03
COST = 0.01


def _mask(X: np.ndarray) -> np.ndarray:
    keep = [i for i in range(X.shape[1]) if i not in LEAKED_COLS]
    return X[:, keep]


def _platt(probas: np.ndarray, a: float, b: float) -> np.ndarray:
    z = a + b * probas
    return 1.0 / (1.0 + np.exp(-z))


def _crowd_wrong_to_p_yes(p_crowd_wrong: np.ndarray, yes_price: np.ndarray) -> np.ndarray:
    crowd_yes = yes_price >= 0.5
    return np.where(crowd_yes, 1.0 - p_crowd_wrong, p_crowd_wrong)


def _run_one_fold(
    df: pd.DataFrame, train_idx: range, test_idx: range, fold_id: int,
) -> dict:
    import xgboost as xgb
    from sklearn.metrics import brier_score_loss, roc_auc_score

    train_df = df.iloc[list(train_idx)]
    test_df = df.iloc[list(test_idx)]

    X_train_full, y_train = build_feature_matrix(train_df)
    X_test_full, y_test = build_feature_matrix(test_df)

    X_train = _mask(X_train_full)
    X_test = _mask(X_test_full)

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

    importance = dict(zip(KEPT_NAMES, [float(v) for v in model.feature_importances_]))

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

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(portfolio.index, portfolio["bankroll"], lw=1.5, color="#1f77b4")
    ax.axhline(STARTING_BANKROLL, ls="--", color="gray", lw=0.8)
    ax.set_title("Walk-forward equity curve — leaked features REMOVED")
    ax.set_xlabel("Bet # (chronological)")
    ax.set_ylabel("Bankroll ($)")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(CHARTS_DIR / "equity_curve.png", dpi=110)
    plt.close(fig)

    peaks = portfolio["bankroll"].cummax()
    dd = (portfolio["bankroll"] - peaks) / peaks
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.fill_between(portfolio.index, dd, 0, color="#d62728", alpha=0.4)
    ax.set_title("Drawdown — leaked features REMOVED")
    ax.set_xlabel("Bet # (chronological)")
    ax.set_ylabel("Drawdown")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(CHARTS_DIR / "drawdown.png", dpi=110)
    plt.close(fig)

    feat_names = list(fold_results[0]["feature_importance"].keys())
    fig, ax = plt.subplots(figsize=(8, 5))
    width = 0.15
    x = np.arange(len(feat_names))
    for k, fr in enumerate(fold_results):
        vals = [fr["feature_importance"][n] for n in feat_names]
        ax.bar(x + k * width, vals, width, label=f"Fold {fr['fold']}")
    ax.set_xticks(x + width * (len(fold_results) - 1) / 2)
    ax.set_xticklabels(feat_names, rotation=20, ha="right")
    ax.set_title("Feature importance per fold — leaked features REMOVED")
    ax.legend()
    ax.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(CHARTS_DIR / "feature_importance.png", dpi=110)
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

    mean_auc = np.mean([fr["test_auc"] for fr in fold_results])
    verdict = _verdict_text(mean_auc, sharpe, wr, mdd)

    report = f"""# E1b — AlphaFeed XGBoost backtest, leaked features REMOVED

Same walk-forward harness as `backtest/report.md`, but with `yes_price`
and `price_extremity` masked from the model's feature matrix. The four
remaining features (`info_ratio`, `log_volume_total`, `log_liquidity`,
`days_left`) are the only inputs.

## Verdict

{verdict}

## Headline numbers

| Metric | Leaked features OFF (this run) | Leaked features ON (original) |
|---|---|---|
| Mean test AUC | **{mean_auc:.3f}** | 0.975 |
| Win rate | **{wr * 100:.1f}%** | 35.7% |
| Max drawdown | **{mdd * 100:.1f}%** | −98.8% |
| Bets taken | {bets_taken:,} | 1,729 |
| Final bankroll | ${final_bankroll:,.2f} | $9.0 × 10¹⁵ |
| Total return | {total_return * 100:+.1f}% | meaningless |
| Per-bet annualised Sharpe | {sharpe:.2f} | 1.14 |

## Per-fold model quality

| Fold | n_train | n_test | Test AUC | Brier (raw) | Brier (calibrated) |
|---|---|---|---|---|---|
{chr(10).join(fold_rows)}

## Feature importance (5-fold mean ± std)

| Feature | Mean importance | Std |
|---|---|---|
{chr(10).join(feat_rows)}

## Charts

- ![Equity curve](charts/equity_curve.png)
- ![Drawdown](charts/drawdown.png)
- ![Feature importance](charts/feature_importance.png)

## Bet-policy parameters (unchanged from E1)

| Param | Value |
|---|---|
| Kelly multiplier | 0.5 (half-Kelly) |
| Max bet % of bankroll | 5.0% |
| Min net edge to bet | 3.0% |
| Effective cost (fee + slippage proxy) | 1.0% |
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def _verdict_text(mean_auc: float, sharpe: float, wr: float, mdd: float) -> str:
    if mean_auc < 0.52:
        return (
            "**No residual edge.** With the leaked features removed, mean AUC "
            f"is {mean_auc:.3f} — statistically indistinguishable from a coin "
            "flip (0.50). The four remaining features carry no useful signal "
            "for predicting whether the crowd is wrong. Recommended: retire "
            "the XGBoost mispricing pipeline or rebuild it on data that has "
            "yes_price snapshots from *before* market convergence."
        )
    if mean_auc < 0.57:
        return (
            f"**Marginal residual edge.** Mean AUC {mean_auc:.3f}, just above "
            "random. Some signal exists but it's thin. Whether to keep the "
            "pipeline depends on how much operational complexity costs "
            f"(annualised Sharpe {sharpe:.2f}, win rate {wr * 100:.1f}%, max "
            f"DD {mdd * 100:.1f}%). Lean toward simplification."
        )
    if mean_auc < 0.62:
        return (
            f"**Real but modest edge.** Mean AUC {mean_auc:.3f} — the "
            "industry's normal range for prediction-markets models. The "
            f"backtest Sharpe is {sharpe:.2f}, win rate {wr * 100:.1f}%, max "
            f"DD {mdd * 100:.1f}%. Worth keeping the pipeline if the "
            "live-cost economics work."
        )
    return (
        f"**Strong residual edge.** Mean AUC {mean_auc:.3f} from four "
        "non-price features alone is unusually high — double-check there's "
        "no second leakage channel before trusting it."
    )


def main() -> int:
    print(f"[E1b] Loading {DATA_PATH}")
    df = pd.read_csv(DATA_PATH)
    df = df.iloc[::-1].reset_index(drop=True)
    n_markets = len(df)
    print(f"[E1b] {n_markets:,} resolved markets")

    folds = split_folds(n_rows=n_markets, n_folds=5)
    fold_results: list[dict] = []
    all_bets: list[pd.DataFrame] = []
    for k, (tr, te) in enumerate(folds, start=1):
        print(f"[E1b] Fold {k}: train [0:{tr.stop}] -> test [{te.start}:{te.stop}]")
        fr = _run_one_fold(df, tr, te, fold_id=k)
        print(
            f"      AUC={fr['test_auc']:.3f}  "
            f"Brier raw={fr['brier_raw']:.4f}  cal={fr['brier_calibrated']:.4f}",
        )
        fold_results.append(fr)
        all_bets.append(fr["bets"])

    bets_concat = pd.concat(all_bets, ignore_index=True)
    print(f"[E1b] Simulating {len(bets_concat):,} candidate bets")
    portfolio = simulate_portfolio(
        bets_concat,
        starting_bankroll=STARTING_BANKROLL,
        kelly_multiplier=KELLY_MULTIPLIER,
        max_bet_pct=MAX_BET_PCT,
        min_edge=MIN_EDGE,
        cost=COST,
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    _write_charts(portfolio, fold_results)
    _write_report(
        n_markets=n_markets,
        fold_results=fold_results,
        portfolio=portfolio,
    )

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
    (OUT_DIR / "diagnostics.json").write_text(json.dumps(diag, indent=2))
    print("[E1b] Done. See backtest/no_leakage/report.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
