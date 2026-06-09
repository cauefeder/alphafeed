"""On-disk versioned model store for the XGBoost mispricing classifier.

Layout (under `models_root`):

    models/
    ├── CURRENT                   # text file: "v3"  (which version is live)
    ├── v1/
    │   ├── xgboost_model.json
    │   ├── calibration_params.json
    │   └── training_metrics.json
    ├── v2/
    │   └── ...
    └── v3/
        └── ...

`next_version_dir` is used by train_model to pick where to *write* the new
model. `load_current` is used by quant_report to find where to *read* the
active model. Promotion (advancing CURRENT) is a separate, manual step —
see scripts/promote_model.py.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


_VERSION_RE = re.compile(r"^v(\d+)$")
METRICS_FILENAME = "training_metrics.json"
MODEL_FILENAME = "xgboost_model.json"
CALIBRATION_FILENAME = "calibration_params.json"
CURRENT_FILENAME = "CURRENT"


class ModelStoreError(RuntimeError):
    """Raised on missing CURRENT pointer, missing version dir, or
    missing metrics inside a version dir."""


def _version_number(name: str) -> int | None:
    m = _VERSION_RE.match(name)
    return int(m.group(1)) if m else None


def next_version_dir(models_root: Path) -> Path:
    """Return the next `models_root/v{N+1}` slot — does NOT create it.

    N = highest existing v{N} integer, ignoring non-version siblings
    (CURRENT, archive/, etc). If no versions exist yet, returns v1.
    The caller (train_model) is responsible for `mkdir(parents=True)`.
    """
    models_root.mkdir(parents=True, exist_ok=True)
    nums = [
        n for n in (
            _version_number(p.name) for p in models_root.iterdir() if p.is_dir()
        )
        if n is not None
    ]
    next_n = max(nums) + 1 if nums else 1
    return models_root / f"v{next_n}"


def load_current(models_root: Path) -> tuple[Path, dict[str, Any]]:
    """Return (active_version_dir, metrics_dict).

    Reads `models_root/CURRENT` (a one-line text file naming the active
    version directory) and loads its training_metrics.json. Raises
    ModelStoreError with a clear message if any of the three required
    pieces are missing.
    """
    pointer = models_root / CURRENT_FILENAME
    if not pointer.exists():
        raise ModelStoreError(
            f"CURRENT pointer missing at {pointer}. "
            "Run scripts/promote_model.py <version> to set it.",
        )
    version_name = pointer.read_text(encoding="utf-8").strip()
    version_dir = models_root / version_name
    if not version_dir.is_dir():
        raise ModelStoreError(
            f"CURRENT points to {version_name!r} but {version_dir} does not exist.",
        )
    metrics_path = version_dir / METRICS_FILENAME
    if not metrics_path.exists():
        raise ModelStoreError(
            f"{METRICS_FILENAME} missing inside {version_dir}.",
        )
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    return version_dir, metrics


def model_paths_for(version_dir: Path) -> tuple[Path, Path, Path]:
    """Return (model, calibration, metrics) paths for a version directory.

    Convenience used by train_model.save_artifacts and quant_report's loader.
    """
    return (
        version_dir / MODEL_FILENAME,
        version_dir / CALIBRATION_FILENAME,
        version_dir / METRICS_FILENAME,
    )


def write_current(models_root: Path, version_name: str) -> None:
    """Atomically promote `version_name` (e.g. 'v3') by writing CURRENT.

    Validates that the version directory exists first.
    """
    version_dir = models_root / version_name
    if not version_dir.is_dir():
        raise ModelStoreError(
            f"Cannot promote {version_name!r}: {version_dir} does not exist.",
        )
    pointer = models_root / CURRENT_FILENAME
    tmp = pointer.with_suffix(pointer.suffix + ".tmp")
    tmp.write_text(version_name, encoding="utf-8")
    tmp.replace(pointer)
