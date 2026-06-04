"""Light tests for train_model.py — no real training, no network."""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "backend/adapters"))
from quant_features import FEATURE_NAMES


def _make_df(n=100):
    """Synthetic DataFrame mimicking historical_markets.csv."""
    import pandas as pd
    rng = np.random.default_rng(42)
    return pd.DataFrame({
        "yes_price":    rng.uniform(0.01, 0.99, n),
        "volume_24h":   rng.uniform(0, 1_000_000, n),
        "volume_total": rng.uniform(0, 10_000_000, n),
        "liquidity":    rng.uniform(0, 2_000_000, n),
        "days_left":    rng.uniform(0, 90, n),
        "resolved_yes": rng.integers(0, 2, n),
        "endDate_ts":   np.arange(n, dtype=float),  # synthetic time ordering
    })


def test_feature_matrix_shape():
    from train_model import build_feature_matrix
    df = _make_df(200)
    X, y = build_feature_matrix(df)
    assert X.shape == (200, len(FEATURE_NAMES)), f"Expected (200, {len(FEATURE_NAMES)}), got {X.shape}"
    assert y.shape == (200,)


def test_feature_matrix_columns_match_feature_names():
    from train_model import build_feature_matrix
    df = _make_df(50)
    X, y = build_feature_matrix(df)
    # X must be ordered per FEATURE_NAMES — verify by checking values
    row = df.iloc[0]
    expected_yes_price = row["yes_price"]
    assert X[0, 0] == pytest.approx(expected_yes_price)


def test_temporal_split_no_leakage():
    from train_model import temporal_split
    df = _make_df(100)
    train, val, test = temporal_split(df)
    # Verify ordering: all train indices < all val < all test
    assert train.index.max() < val.index.min()
    assert val.index.max() < test.index.min()


def test_temporal_split_proportions():
    from train_model import temporal_split
    df = _make_df(100)
    train, val, test = temporal_split(df)
    total = len(train) + len(val) + len(test)
    assert total == 100
    assert 68 <= len(train) <= 72  # ~70%
    assert 13 <= len(val) <= 17    # ~15%
    assert 13 <= len(test) <= 17   # ~15%


def test_auc_gate_rejects_random_model():
    """A model that outputs random probabilities should produce AUC ≈ 0.5 → gate fails."""
    from train_model import check_auc_gate

    rng = np.random.default_rng(0)
    y_true = rng.integers(0, 2, 200)

    mock_model = MagicMock()
    mock_model.predict_proba.return_value = np.column_stack(
        [rng.uniform(0, 1, 200), rng.uniform(0, 1, 200)]
    )
    X_fake = np.zeros((200, len(FEATURE_NAMES)))

    passed, auc = check_auc_gate(mock_model, X_fake, y_true, threshold=0.58)
    assert not passed, f"Random model with AUC {auc:.3f} should not pass gate"
    assert auc < 0.6


# ---------- compute_class_imbalance ----------


def test_class_imbalance_balanced():
    from train_model import compute_class_imbalance
    y = np.array([0] * 50 + [1] * 50)
    n_neg, n_pos, spw = compute_class_imbalance(y)
    assert n_neg == 50 and n_pos == 50
    assert spw == pytest.approx(1.0)


def test_class_imbalance_skewed():
    from train_model import compute_class_imbalance
    y = np.array([0] * 70 + [1] * 30)
    n_neg, n_pos, spw = compute_class_imbalance(y)
    assert n_neg == 70 and n_pos == 30
    assert spw == pytest.approx(70 / 30)


def test_class_imbalance_no_positives_uses_one_in_denominator():
    """max(n_pos, 1) guard prevents ZeroDivisionError."""
    from train_model import compute_class_imbalance
    y = np.array([0] * 100)
    n_neg, n_pos, spw = compute_class_imbalance(y)
    assert n_neg == 100 and n_pos == 0
    assert spw == pytest.approx(100.0)  # 100 / max(0, 1) = 100


# ---------- xgb_hyperparams ----------


def test_xgb_hyperparams_carries_scale_pos_weight():
    from train_model import xgb_hyperparams
    p = xgb_hyperparams(scale_pos_weight=2.5)
    assert p["scale_pos_weight"] == 2.5


def test_xgb_hyperparams_includes_required_keys():
    from train_model import xgb_hyperparams
    p = xgb_hyperparams(scale_pos_weight=1.0)
    required = {
        "max_depth", "min_child_weight", "subsample", "colsample_bytree",
        "reg_alpha", "reg_lambda", "scale_pos_weight", "eval_metric", "random_state",
    }
    assert required <= p.keys()
    assert p["max_depth"] == 4  # locked default — change is a model change
    assert p["random_state"] == 42  # locked for reproducibility


# ---------- cross_validate ----------


class _ConstantModel:
    """Predicts a fixed probability for the positive class. AUC = 0.5 always."""

    def __init__(self, p: float = 0.5) -> None:
        self.p = p

    def fit(self, X, y):  # noqa: D401
        return self

    def predict_proba(self, X):
        col_pos = np.full(len(X), self.p)
        return np.column_stack([1 - col_pos, col_pos])


def test_cross_validate_returns_mean_std_floats():
    from train_model import cross_validate
    rng = np.random.default_rng(0)
    X = rng.standard_normal((120, 6))
    y = np.tile([0, 1], 60)  # balanced, both classes in every fold

    mean, std = cross_validate(X, y, model_factory=lambda: _ConstantModel(0.5), n_splits=5)
    assert isinstance(mean, float)
    assert isinstance(std, float)
    assert 0.0 <= mean <= 1.0


def test_cross_validate_respects_n_splits():
    """n_splits=3 means model_factory is called exactly 3 times."""
    from train_model import cross_validate
    rng = np.random.default_rng(0)
    X = rng.standard_normal((60, 6))
    y = np.tile([0, 1], 30)

    calls = []

    def factory():
        calls.append(1)
        return _ConstantModel(0.5)

    cross_validate(X, y, model_factory=factory, n_splits=3)
    assert len(calls) == 3


# ---------- fit_calibrator ----------


def test_fit_calibrator_returns_two_floats():
    from train_model import fit_calibrator
    rng = np.random.default_rng(0)
    probas = rng.uniform(0, 1, 200)
    y = (probas > 0.5).astype(int)  # perfect calibration on this synthetic set
    a, b = fit_calibrator(probas, y)
    assert isinstance(a, float)
    assert isinstance(b, float)


# ---------- format_feature_importance ----------


def test_format_feature_importance_sorted_desc():
    from train_model import format_feature_importance
    importances = np.array([0.1, 0.5, 0.3, 0.05, 0.04, 0.01])
    out = format_feature_importance(importances, FEATURE_NAMES)
    values = list(out.values())
    assert values == sorted(values, reverse=True)
    assert set(out.keys()) == set(FEATURE_NAMES)


# ---------- save_artifacts ----------


def test_save_artifacts_writes_three_files(tmp_path: Path):
    from train_model import save_artifacts

    mock_model = MagicMock()
    mp = tmp_path / "model.json"
    cp = tmp_path / "calibration.json"
    metp = tmp_path / "metrics.json"
    calibration = {"platt_a": 0.1, "platt_b": 1.2, "feature_names": list(FEATURE_NAMES)}
    metrics = {"testAuc": 0.65, "aucGatePassed": True}

    save_artifacts(
        model=mock_model, calibration=calibration, metrics=metrics,
        model_path=mp, calibration_path=cp, metrics_path=metp,
    )

    mock_model.save_model.assert_called_once_with(str(mp))
    assert json.loads(cp.read_text())["platt_a"] == 0.1
    assert json.loads(metp.read_text())["testAuc"] == 0.65


# ---------- train_pipeline (slow integration smoke) ----------


def _signal_df(n: int = 250) -> "pd.DataFrame":
    """Synthetic data with REAL signal: when yes_price > 0.5 the market resolves
    NO more often, so the 'crowd was wrong' label is predictable from features.
    Lets the smoke test verify the pipeline produces a usable AUC."""
    import pandas as pd

    rng = np.random.default_rng(7)
    yes = rng.uniform(0.05, 0.95, n)
    # Crowd wrong probability rises sharply as yes -> 1.0 (overconfidence bias)
    wrong_prob = 1 / (1 + np.exp(-6 * (yes - 0.85)))
    crowd_wrong = (rng.uniform(0, 1, n) < wrong_prob).astype(int)
    # If yes >= 0.5 and crowd wrong → resolved_yes = 0; else if yes >= 0.5 and crowd right → 1
    # If yes < 0.5 and crowd wrong → resolved_yes = 1; else → 0
    crowd_dir = (yes >= 0.5).astype(int)
    resolved_yes = np.where(crowd_wrong == 1, 1 - crowd_dir, crowd_dir)

    return pd.DataFrame({
        "yes_price":    yes,
        "volume_24h":   rng.uniform(0, 1_000_000, n),
        "volume_total": rng.uniform(0, 10_000_000, n),
        "liquidity":    rng.uniform(0, 2_000_000, n),
        "days_left":    rng.uniform(0, 90, n),
        "resolved_yes": resolved_yes,
        "endDate_ts":   np.arange(n, dtype=float),
    })


def test_train_pipeline_smoke(tmp_path: Path):
    """End-to-end: synthetic data, real xgb, real save. Auc threshold relaxed
    so any model run passes (we're checking plumbing, not model quality)."""
    pytest.importorskip("xgboost")

    from train_model import train_pipeline

    df = _signal_df(300)
    metrics = train_pipeline(
        df,
        model_path=tmp_path / "model.json",
        calibration_path=tmp_path / "calibration.json",
        metrics_path=tmp_path / "metrics.json",
        auc_threshold=0.0,  # accept anything for smoke
    )

    assert (tmp_path / "model.json").exists()
    assert (tmp_path / "calibration.json").exists()
    assert (tmp_path / "metrics.json").exists()
    assert "testAuc" in metrics
    assert "cvAuc" in metrics
    assert metrics["aucGatePassed"] is True


def test_train_pipeline_raises_when_auc_below_threshold(tmp_path: Path):
    """When AUC gate fails, the pipeline raises AucGateError and saves nothing."""
    pytest.importorskip("xgboost")

    from train_model import AucGateError, train_pipeline

    df = _signal_df(300)
    with pytest.raises(AucGateError):
        train_pipeline(
            df,
            model_path=tmp_path / "model.json",
            calibration_path=tmp_path / "calibration.json",
            metrics_path=tmp_path / "metrics.json",
            auc_threshold=0.999,  # impossibly high → raise
        )

    # Verify nothing was saved on failure
    assert not (tmp_path / "model.json").exists()
    assert not (tmp_path / "calibration.json").exists()
    assert not (tmp_path / "metrics.json").exists()
