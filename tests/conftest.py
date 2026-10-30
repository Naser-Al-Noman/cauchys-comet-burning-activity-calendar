from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
SYNTHETIC_FIRMS_CSV = REPO_ROOT / "demo_fixtures" / "synthetic_firms_bangladesh.csv"


@pytest.fixture
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture
def synthetic_firms_csv() -> Path:
    assert SYNTHETIC_FIRMS_CSV.is_file()
    return SYNTHETIC_FIRMS_CSV
