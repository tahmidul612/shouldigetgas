"""Shared pytest fixtures / path setup for the backend test suite."""
import sys
import pathlib

ROOT    = pathlib.Path(__file__).resolve().parents[2]   # repo root
BACKEND = ROOT / "backend"

# The backend modules import each other as top-level names (e.g. `import db`),
# so both backend/ and backend/analytics/ must be importable.
for p in (str(BACKEND), str(BACKEND / "analytics")):
    if p not in sys.path:
        sys.path.insert(0, p)

import pytest


def _have_eia_key() -> bool:
    from config import EIA_API_KEY
    return bool(EIA_API_KEY)


requires_eia = pytest.mark.skipif(not _have_eia_key(), reason="EIA_API_KEY not set")
