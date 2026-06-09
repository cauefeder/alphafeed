"""Promote a trained model version by updating models/CURRENT.

Usage:
  python scripts/promote_model.py v3

After train_model.py writes artifacts under models/v3/, this script
flips the live pointer. Idempotent — re-running with the same version
is a no-op (but still rewrites CURRENT atomically).
"""

from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve()
REPO_ROOT = _HERE.parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend" / "adapters"))

from model_store import ModelStoreError, write_current  # noqa: E402

MODELS_ROOT = REPO_ROOT / "models"


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python scripts/promote_model.py <version>")
        print("Example: python scripts/promote_model.py v3")
        return 2

    version = sys.argv[1].strip()
    try:
        write_current(MODELS_ROOT, version)
    except ModelStoreError as e:
        print(f"[promote_model] ERROR: {e}")
        return 1

    print(f"[promote_model] Promoted {version}. CURRENT now points to {version}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
