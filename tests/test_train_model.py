"""Light tests for train_model.py — no real training, no network."""
import sys
from pathlib import Path
import pytest
import numpy as np

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
    from unittest.mock import MagicMock

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
