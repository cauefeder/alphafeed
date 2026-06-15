"""Expanding-window walk-forward fold splitter.

Returns a list of (train_indices, test_indices) tuples. The training set
grows monotonically across folds; the test windows tile the trailing 40%
of the data without overlap. Chronological ordering of the input is the
caller's responsibility — feed a DataFrame already sorted by time.
"""

from __future__ import annotations


def split_folds(*, n_rows: int, n_folds: int = 5) -> list[tuple[range, range]]:
    """Build (train_idx, test_idx) pairs for an expanding-window walk-forward.

    Train always starts at row 0. Test windows split the trailing 40% of
    rows into `n_folds` equal slices. Fold k uses train = [0, 60% + k * slice]
    and test = next slice. Returned as ranges for cheap membership / slicing.
    """
    if n_folds <= 0:
        raise ValueError(f"n_folds must be >= 1, got {n_folds}")

    train_start_pct = 0.60
    train_end = int(n_rows * train_start_pct)
    remaining = n_rows - train_end
    slice_len = remaining // n_folds

    folds: list[tuple[range, range]] = []
    cursor = train_end
    for k in range(n_folds):
        train_idx = range(0, cursor)
        # Last fold absorbs the remainder to ensure we cover up to n_rows - 1
        if k == n_folds - 1:
            test_idx = range(cursor, n_rows)
        else:
            test_idx = range(cursor, cursor + slice_len)
        folds.append((train_idx, test_idx))
        cursor += slice_len

    return folds
