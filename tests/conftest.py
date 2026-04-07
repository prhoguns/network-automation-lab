import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.lab import topology  # noqa: E402


@pytest.fixture(scope="session")
def topo():
    return topology()
