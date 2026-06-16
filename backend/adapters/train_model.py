"""
train_model.py — Train the XGBoost mispricing classifier.

Usage:
  python backend/adapters/train_model.py --data data/historical_markets.csv

Outputs (all relative to repo root):
  models/xgboost_model.json
  models/calibration_params.json
  models/training_metrics.json

Exits with code 1 if test AUC < 0.58.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

_HERE = Path(__file__).resolve()
REPO_ROOT = _HERE.parent.parent.parent
sys.path.insert(0, str(_HERE.parent))
from quant_features import FEATURE_NAMES  # noqa: E402
from model_store import model_paths_for, next_version_dir  # noqa: E402

MODELS_ROOT      = REPO_ROOT / "models"
AUC_THRESHOLD    = 0.58


class AucGateError(RuntimeError):
    """Raised when a trained model fails the test-AUC threshold."""


# ── Feature engineering (pure) ──────────────────────────────────────────────


def build_feature_matrix(df) -> tuple:
    """
    Compute the 3 training features for every row in df.
    Returns (X: np.ndarray of shape (n, 3), y: np.ndarray of shape (n,)).
    Label: 1 = crowd was wrong (market resolved against crowd's >=0.5 direction).

    yes_price is still read to compute the label (the crowd's direction is
    yes >= 0.5), but it is NOT included as a feature — same for the engineered
    `price_extremity = 2 * |yes - 0.5|`. See backtest/report.md for the
    leakage analysis that justified dropping them. `log_liquidity` was cut
    in the same pass after registering 0% importance across all 5 folds.
    """
    yes = df["yes_price"].values
    vol = df["volume_24h"].values
    days_raw = np.maximum(df["days_left"].values, 0)
    days_feat = np.maximum(days_raw, 0.5)

    X = np.column_stack([
        vol / ((days_raw + 1) ** 0.5) / 10_000,   # info_ratio
        np.log1p(df["volume_total"].values),       # log_volume_total
        days_feat,                                 # days_left
    ])
    assert X.shape[1] == len(FEATURE_NAMES), (
        f"Feature matrix has {X.shape[1]} cols, expected {len(FEATURE_NAMES)}"
    )

    resolved = df["resolved_yes"].values.astype(int)
    y = ((resolved == 1) != (yes >= 0.5)).astype(int)
    return X, y


def temporal_split(df):
    """
    Split df chronologically: oldest 70% -> train, next 15% -> val, newest 15% -> test.
    df must already be sorted by time (older rows first).
    """
    n = len(df)
    i_val  = int(n * 0.70)
    i_test = int(n * 0.85)
    return df.iloc[:i_val], df.iloc[i_val:i_test], df.iloc[i_test:]


# ── Training-pipeline helpers (extracted from former main()) ────────────────


def compute_class_imbalance(y: np.ndarray) -> tuple[int, int, float]:
    """Return (n_neg, n_pos, scale_pos_weight). Guards against zero positives."""
    n_pos = int(np.asarray(y).sum())
    n_neg = int(len(y) - n_pos)
    spw = n_neg / max(n_pos, 1)
    return n_neg, n_pos, spw


def xgb_hyperparams(scale_pos_weight: float) -> dict[str, Any]:
    """Frozen XGBoost hyperparameters. Changing values here is a model change."""
    return {
        "max_depth":         4,
        "min_child_weight":  10,
        "subsample":         0.8,
        "colsample_bytree":  0.8,
        "reg_alpha":         0.1,
        "reg_lambda":        1.0,
        "scale_pos_weight":  scale_pos_weight,
        "eval_metric":       "auc",
        "use_label_encoder": False,
        "verbosity":         0,
        "random_state":      42,
    }


def cross_validate(
    X_train: np.ndarray,
    y_train: np.ndarray,
    *,
    model_factory: Callable[[], Any],
    n_splits: int = 5,
) -> tuple[float, float]:
    """TimeSeriesSplit cross-validation. Returns (mean_auc, std_auc).

    `model_factory` is a zero-arg callable returning a fresh sklearn-style
    estimator each call — keeps the function decoupled from xgboost so tests
    can pass a fake model.
    """
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import TimeSeriesSplit

    tscv = TimeSeriesSplit(n_splits=n_splits)
    aucs: list[float] = []
    for tr_idx, vl_idx in tscv.split(X_train):
        m = model_factory()
        m.fit(X_train[tr_idx], y_train[tr_idx])
        proba = m.predict_proba(X_train[vl_idx])[:, 1]
        aucs.append(float(roc_auc_score(y_train[vl_idx], proba)))
    return float(np.mean(aucs)), float(np.std(aucs))


def fit_calibrator(probas: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """Platt-scaling: fit a logistic on raw model probabilities. Returns (a, b)."""
    from sklearn.linear_model import LogisticRegression

    platt = LogisticRegression()
    platt.fit(np.asarray(probas).reshape(-1, 1), np.asarray(y))
    return float(platt.intercept_[0]), float(platt.coef_[0][0])


def check_auc_gate(model, X_test, y_test, threshold: float = AUC_THRESHOLD) -> tuple:
    """Returns (passed, auc). Real model with real test data."""
    from sklearn.metrics import roc_auc_score

    proba = model.predict_proba(X_test)[:, 1]
    auc = float(roc_auc_score(y_test, proba))
    return auc >= threshold, auc


def format_feature_importance(
    importances: np.ndarray,
    names: list[str],
) -> dict[str, float]:
    """Build a {name: importance} dict, sorted by importance desc."""
    paired = list(zip(names, [float(v) for v in importances]))
    paired.sort(key=lambda kv: kv[1], reverse=True)
    return dict(paired)


def save_artifacts(
    *,
    model,
    calibration: dict[str, Any],
    metrics: dict[str, Any],
    model_path: Path,
    calibration_path: Path,
    metrics_path: Path,
) -> None:
    """Persist xgb model + calibration JSON + metrics JSON. Atomic per-file."""
    model_path.parent.mkdir(parents=True, exist_ok=True)
    model.save_model(str(model_path))
    calibration_path.write_text(json.dumps(calibration, indent=2))
    metrics_path.write_text(json.dumps(metrics, indent=2))


# ── Orchestration ───────────────────────────────────────────────────────────


def train_pipeline(
    df,
    *,
    model_path: Path,
    calibration_path: Path,
    metrics_path: Path,
    auc_threshold: float = AUC_THRESHOLD,
) -> dict[str, Any]:
    """End-to-end training. Raises AucGateError if test AUC < threshold
    (no artifacts saved in that case). Returns the metrics dict otherwise.
    """
    import xgboost as xgb

    if "endDate_ts" in df.columns:
        df = df.sort_values("endDate_ts").reset_index(drop=True)

    train_df, val_df, test_df = temporal_split(df)

    X_train, y_train = build_feature_matrix(train_df)
    X_val,   y_val   = build_feature_matrix(val_df)
    X_test,  y_test  = build_feature_matrix(test_df)

    n_neg, n_pos, scale_pos_weight = compute_class_imbalance(y_train)
    print(
        f"[train_model] Class balance: {n_neg} majority / {n_pos} minority "
        f"-> scale_pos_weight={scale_pos_weight:.2f}"
    )

    params = xgb_hyperparams(scale_pos_weight)

    def _factory() -> Any:
        return xgb.XGBClassifier(**params, n_estimators=200)

    cv_mean, cv_std = cross_validate(X_train, y_train, model_factory=_factory)
    print(f"[train_model] CV AUC (5-fold): {cv_mean:.3f} +/- {cv_std:.3f}")

    model = xgb.XGBClassifier(**params, n_estimators=300)
    model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)

    from sklearn.metrics import roc_auc_score
    val_auc = float(roc_auc_score(y_val, model.predict_proba(X_val)[:, 1]))
    print(f"[train_model] Validation AUC: {val_auc:.3f}")

    passed, test_auc = check_auc_gate(model, X_test, y_test, threshold=auc_threshold)
    status = "PASS" if passed else "FAIL"
    print(f"[train_model] Test AUC: {test_auc:.3f}  [{status}] (threshold: {auc_threshold})")

    if not passed:
        raise AucGateError(f"Test AUC {test_auc:.3f} < {auc_threshold}")

    importance = format_feature_importance(model.feature_importances_, FEATURE_NAMES)
    max_feat, max_imp = next(iter(importance.items()))
    print("[train_model] Feature importance:")
    for feat, imp in importance.items():
        flag = " [HIGH]" if imp > 0.60 else ""
        print(f"               {feat:<22} {imp:.2f}{flag}")
    if max_imp > 0.60:
        print(f"[train_model] WARNING: {max_feat} explains {max_imp:.0%} of variance — possible overfit")

    platt_a, platt_b = fit_calibrator(model.predict_proba(X_val)[:, 1], y_val)
    print(f"[train_model] Platt scaling: a={platt_a:.4f}, b={platt_b:.4f}")

    model_version = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    calibration = {
        "platt_a":       platt_a,
        "platt_b":       platt_b,
        "feature_names": FEATURE_NAMES,
    }
    metrics = {
        "modelVersion":      model_version,
        "trainedAt":         datetime.now(timezone.utc).isoformat(),
        "nSamples":          len(df),
        "cvAuc":             round(cv_mean, 4),
        "cvAucStd":          round(cv_std, 4),
        "valAuc":            round(val_auc, 4),
        "testAuc":           round(test_auc, 4),
        "aucGatePassed":     True,
        "featureImportance": {k: round(v, 4) for k, v in importance.items()},
    }

    save_artifacts(
        model=model,
        calibration=calibration,
        metrics=metrics,
        model_path=model_path,
        calibration_path=calibration_path,
        metrics_path=metrics_path,
    )

    print(f"[train_model] Model saved -> {model_path}")
    print(f"[train_model] Calibration saved -> {calibration_path}")
    print(f"[train_model] Metrics saved -> {metrics_path}")

    return metrics


def main() -> None:
    import pandas as pd

    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True)
    args = parser.parse_args()

    print("[train_model] Loading data...")
    df = pd.read_csv(args.data)
    print(f"[train_model] {len(df):,} resolved markets loaded")

    version_dir = next_version_dir(MODELS_ROOT)
    model_path, calibration_path, metrics_path = model_paths_for(version_dir)
    print(f"[train_model] Writing artifacts to {version_dir.name}/ (not yet promoted)")

    try:
        train_pipeline(
            df,
            model_path=model_path,
            calibration_path=calibration_path,
            metrics_path=metrics_path,
        )
    except AucGateError as e:
        print(f"[train_model] ERROR: {e}. Model NOT saved.")
        sys.exit(1)

    print(
        f"[train_model] Trained {version_dir.name}. To activate, run:\n"
        f"  python scripts/promote_model.py {version_dir.name}",
    )


if __name__ == "__main__":
    main()
