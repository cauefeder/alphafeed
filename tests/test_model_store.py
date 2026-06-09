"""TDD coverage for model_store: next_version_dir + load_current.

Versioning contract:
- models/CURRENT is a text file holding the active version name (e.g. "v1").
- Versions live under models/v{N}/ with three artifacts:
  xgboost_model.json, calibration_params.json, training_metrics.json.
- next_version_dir picks max(N) + 1, ignoring non-version directories.
- load_current reads CURRENT, returns (version_dir, metrics_dict).
- A clear error is raised when CURRENT or the pinned version is missing.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "backend/adapters"))
from model_store import (
    ModelStoreError,
    load_current,
    next_version_dir,
)


# ---------- next_version_dir ----------


def test_next_version_dir_on_empty_models_returns_v1(tmp_path: Path) -> None:
    path = next_version_dir(tmp_path)
    assert path == tmp_path / "v1"


def test_next_version_dir_picks_max_plus_one(tmp_path: Path) -> None:
    (tmp_path / "v1").mkdir()
    (tmp_path / "v2").mkdir()
    path = next_version_dir(tmp_path)
    assert path == tmp_path / "v3"


def test_next_version_dir_ignores_non_version_dirs(tmp_path: Path) -> None:
    (tmp_path / "v1").mkdir()
    (tmp_path / "archive").mkdir()
    (tmp_path / "scratch").mkdir()
    (tmp_path / "CURRENT").write_text("v1")
    path = next_version_dir(tmp_path)
    assert path == tmp_path / "v2"


def test_next_version_dir_handles_sparse_numbering(tmp_path: Path) -> None:
    """If v1 and v5 exist (someone deleted v2-v4), next is v6 (max+1)."""
    (tmp_path / "v1").mkdir()
    (tmp_path / "v5").mkdir()
    assert next_version_dir(tmp_path) == tmp_path / "v6"


def test_next_version_dir_creates_models_root_if_missing(tmp_path: Path) -> None:
    """Caller doesn't have to pre-create the models root."""
    root = tmp_path / "fresh_models"
    path = next_version_dir(root)
    assert path == root / "v1"
    assert root.exists()


# ---------- load_current ----------


def _seed_version(root: Path, name: str, *, metrics: dict | None = None) -> Path:
    """Create models_root/<name>/ with a minimal metrics file."""
    vdir = root / name
    vdir.mkdir(parents=True)
    payload = metrics if metrics is not None else {"modelVersion": name, "testAuc": 0.7}
    (vdir / "training_metrics.json").write_text(json.dumps(payload))
    (vdir / "xgboost_model.json").write_text("{}")
    (vdir / "calibration_params.json").write_text("{}")
    return vdir


def test_load_current_returns_pinned_version(tmp_path: Path) -> None:
    _seed_version(tmp_path, "v1", metrics={"modelVersion": "v1-tag", "testAuc": 0.62})
    _seed_version(tmp_path, "v2", metrics={"modelVersion": "v2-tag", "testAuc": 0.71})
    (tmp_path / "CURRENT").write_text("v1")  # pinned to v1, NOT auto-latest

    vdir, metrics = load_current(tmp_path)
    assert vdir == tmp_path / "v1"
    assert metrics["modelVersion"] == "v1-tag"
    assert metrics["testAuc"] == 0.62


def test_load_current_strips_whitespace(tmp_path: Path) -> None:
    """CURRENT may have trailing newline from editors."""
    _seed_version(tmp_path, "v3")
    (tmp_path / "CURRENT").write_text("  v3\n")
    vdir, _ = load_current(tmp_path)
    assert vdir == tmp_path / "v3"


def test_load_current_raises_when_pointer_missing(tmp_path: Path) -> None:
    _seed_version(tmp_path, "v1")  # version exists, but no CURRENT
    with pytest.raises(ModelStoreError, match="CURRENT"):
        load_current(tmp_path)


def test_load_current_raises_when_pinned_version_missing(tmp_path: Path) -> None:
    (tmp_path / "CURRENT").write_text("v7")  # points to nothing
    with pytest.raises(ModelStoreError, match="v7"):
        load_current(tmp_path)


def test_load_current_raises_when_metrics_missing(tmp_path: Path) -> None:
    """Version dir exists but training_metrics.json is gone — caller should know."""
    (tmp_path / "v1").mkdir()
    (tmp_path / "CURRENT").write_text("v1")
    with pytest.raises(ModelStoreError, match="training_metrics.json"):
        load_current(tmp_path)


# ---------- write_current ----------


def test_write_current_promotes_existing_version(tmp_path: Path) -> None:
    from model_store import write_current
    _seed_version(tmp_path, "v1")
    _seed_version(tmp_path, "v2")
    (tmp_path / "CURRENT").write_text("v1")

    write_current(tmp_path, "v2")
    assert (tmp_path / "CURRENT").read_text(encoding="utf-8") == "v2"
    # The promotion is durable across load_current()
    vdir, _ = load_current(tmp_path)
    assert vdir == tmp_path / "v2"


def test_write_current_rejects_missing_version(tmp_path: Path) -> None:
    from model_store import write_current
    with pytest.raises(ModelStoreError, match="v99"):
        write_current(tmp_path, "v99")
    # CURRENT must not be created when promotion is rejected
    assert not (tmp_path / "CURRENT").exists()


# ---------- model_paths_for ----------


def test_model_paths_for_returns_three_paths(tmp_path: Path) -> None:
    from model_store import model_paths_for
    vdir = tmp_path / "v1"
    model_p, calib_p, metrics_p = model_paths_for(vdir)
    assert model_p == vdir / "xgboost_model.json"
    assert calib_p == vdir / "calibration_params.json"
    assert metrics_p == vdir / "training_metrics.json"
