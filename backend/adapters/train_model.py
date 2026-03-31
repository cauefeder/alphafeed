"""
train_model.py — Train the XGBoost mispricing classifier.

Usage:
  python backend/adapters/train_model.py --data data/historical_markets.csv

Outputs (all relative to repo root):
  models/xgboost_model.pkl
  models/calibration_params.json
  models/training_metrics.json

Exits with code 1 if test AUC < 0.58.
"""
from __future__ import annotations

import argparse
import json
import pickle
import sys
from datetime import datetime, timezone
from math import log1p
from pathlib import Path

import numpy as np

_HERE = Path(__file__).resolve()
REPO_ROOT = _HERE.parent.parent.parent
sys.path.insert(0, str(_HERE.parent))
from quant_features import FEATURE_NAMES

MODEL_PATH       = REPO_ROOT / "models/xgboost_model.pkl"
CALIBRATION_PATH = REPO_ROOT / "models/calibration_params.json"
METRICS_PATH     = REPO_ROOT / "models/training_metrics.json"
AUC_THRESHOLD    = 0.58


def build_feature_matrix(df) -> tuple:
    """
    Compute the 6 training features for every row in df.
    Returns (X: np.ndarray of shape (n, 6), y: np.ndarray of shape (n,)).
    Label: 1 = crowd was wrong (market resolved against crowd's >=0.5 direction).
    """
    yes = df["yes_price"].values
    vol = df["volume_24h"].values
    days_raw = np.maximum(df["days_left"].values, 0)  # raw, NOT clamped, for info_ratio
    days_feat = np.maximum(days_raw, 0.5)             # clamped for days_left feature

    X = np.column_stack([
        yes,                                    # yes_price
        vol / ((days_raw + 1) ** 0.5) / 10_000,# info_ratio
        np.log1p(df["volume_total"].values),    # log_volume_total
        np.log1p(df["liquidity"].values),       # log_liquidity
        days_feat,                              # days_left
        np.abs(yes - 0.5) * 2,                  # price_extremity
    ])
    assert X.shape[1] == len(FEATURE_NAMES), f"Feature matrix has {X.shape[1]} cols, expected {len(FEATURE_NAMES)}"

    resolved = df["resolved_yes"].values.astype(int)
    y = ((resolved == 1) != (yes >= 0.5)).astype(int)  # crowd was wrong
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


def check_auc_gate(model, X_test, y_test, threshold: float = AUC_THRESHOLD) -> tuple:
    from sklearn.metrics import roc_auc_score
    proba = model.predict_proba(X_test)[:, 1]
    auc = float(roc_auc_score(y_test, proba))
    return auc >= threshold, auc


def main() -> None:
    import pandas as pd
    import xgboost as xgb
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import TimeSeriesSplit

    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True)
    args = parser.parse_args()

    print("[train_model] Loading data...")
    df = pd.read_csv(args.data)

    # Sort chronologically — endDate_ts or just use row order as proxy
    if "endDate_ts" in df.columns:
        df = df.sort_values("endDate_ts").reset_index(drop=True)

    print(f"[train_model] {len(df):,} resolved markets loaded")

    train_df, val_df, test_df = temporal_split(df)
    print(f"[train_model] Train: {len(train_df):,}  Val: {len(val_df):,}  Test: {len(test_df):,}")

    X_train, y_train = build_feature_matrix(train_df)
    X_val,   y_val   = build_feature_matrix(val_df)
    X_test,  y_test  = build_feature_matrix(test_df)

    # Class imbalance: crowd is right ~70-75% of the time
    n_pos = int(y_train.sum())
    n_neg = len(y_train) - n_pos
    scale_pos_weight = n_neg / max(n_pos, 1)
    print(f"[train_model] Class balance: {n_neg} majority / {n_pos} minority -> scale_pos_weight={scale_pos_weight:.2f}")

    xgb_params = {
        "max_depth":          4,
        "min_child_weight":   10,
        "subsample":          0.8,
        "colsample_bytree":   0.8,
        "reg_alpha":          0.1,
        "reg_lambda":         1.0,
        "scale_pos_weight":   scale_pos_weight,
        "eval_metric":        "auc",
        "use_label_encoder":  False,
        "verbosity":          0,
        "random_state":       42,
    }

    # 5-fold TimeSeriesSplit cross-validation on training set
    tscv = TimeSeriesSplit(n_splits=5)
    cv_aucs = []
    for fold, (tr_idx, vl_idx) in enumerate(tscv.split(X_train)):
        fold_model = xgb.XGBClassifier(**xgb_params, n_estimators=200)
        fold_model.fit(X_train[tr_idx], y_train[tr_idx], verbose=False)
        proba = fold_model.predict_proba(X_train[vl_idx])[:, 1]
        auc = roc_auc_score(y_train[vl_idx], proba)
        cv_aucs.append(auc)

    cv_mean = float(np.mean(cv_aucs))
    cv_std  = float(np.std(cv_aucs))
    print(f"[train_model] CV AUC (5-fold): {cv_mean:.3f} +/- {cv_std:.3f}")

    # Train final model on full training set
    model = xgb.XGBClassifier(**xgb_params, n_estimators=300)
    model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)

    val_auc = float(roc_auc_score(y_val, model.predict_proba(X_val)[:, 1]))
    print(f"[train_model] Validation AUC: {val_auc:.3f}")

    passed, test_auc = check_auc_gate(model, X_test, y_test)
    status = "PASS" if passed else "FAIL"
    print(f"[train_model] Test AUC: {test_auc:.3f}  [{status}] (threshold: {AUC_THRESHOLD})")

    if not passed:
        print(f"[train_model] ERROR: Test AUC {test_auc:.3f} < {AUC_THRESHOLD}. Model NOT saved.")
        sys.exit(1)

    # Feature importance
    importance = dict(zip(FEATURE_NAMES, model.feature_importances_))
    max_feat, max_imp = max(importance.items(), key=lambda kv: kv[1])
    print("[train_model] Feature importance:")
    for feat, imp in sorted(importance.items(), key=lambda kv: kv[1], reverse=True):
        flag = " [HIGH]" if imp > 0.60 else ""
        print(f"               {feat:<22} {imp:.2f}{flag}")
    if max_imp > 0.60:
        print(f"[train_model] WARNING: {max_feat} explains {max_imp:.0%} of variance — possible overfit")

    # Platt scaling on validation set
    platt = LogisticRegression()
    platt.fit(model.predict_proba(X_val)[:, 1].reshape(-1, 1), y_val)
    platt_a = float(platt.intercept_[0])
    platt_b = float(platt.coef_[0][0])
    print(f"[train_model] Platt scaling: a={platt_a:.4f}, b={platt_b:.4f}")

    model_version = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Save outputs
    (REPO_ROOT / "models").mkdir(exist_ok=True)

    with open(MODEL_PATH, "wb") as f:
        pickle.dump(model, f)
    print(f"[train_model] Model saved -> {MODEL_PATH}")

    calibration = {
        "platt_a":       platt_a,
        "platt_b":       platt_b,
        "feature_names": FEATURE_NAMES,
    }
    CALIBRATION_PATH.write_text(json.dumps(calibration, indent=2))
    print(f"[train_model] Calibration saved -> {CALIBRATION_PATH}")

    metrics = {
        "modelVersion":       model_version,
        "trainedAt":          datetime.now(timezone.utc).isoformat(),
        "nSamples":           len(df),
        "cvAuc":              round(cv_mean, 4),
        "cvAucStd":           round(cv_std, 4),
        "valAuc":             round(val_auc, 4),
        "testAuc":            round(test_auc, 4),
        "aucGatePassed":      True,
        "featureImportance":  {k: round(float(v), 4) for k, v in importance.items()},
    }
    METRICS_PATH.write_text(json.dumps(metrics, indent=2))
    print(f"[train_model] Metrics saved -> {METRICS_PATH}")


if __name__ == "__main__":
    main()
