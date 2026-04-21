"""
Shared pytest fixtures for backend tests.

The app boots in `create_app()` (src/main.py) which calls
`models.Base.metadata.create_all(bind=engine)` against a real Postgres.
That is heavy and not what we want in unit tests, so we mount the API
router on a bare FastAPI app here and patch the CRUD/auth modules per
test.
"""

# pylint: disable=wrong-import-position,missing-function-docstring
# pylint: disable=redefined-outer-name,unused-argument

import os
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List

# Make `src` importable as a top-level package, mirroring run_uvicorn.py.
BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

# Ensure modules that read env at import time get a reasonable default.
# `src.database` raises at import without these; `src.auth` needs JWT_SECRET_KEY.
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key")
os.environ.setdefault("GEMINI_API_KEY", "test-gemini-key")
os.environ.setdefault("DB_USERNAME", "test_user")
os.environ.setdefault("DB_NAME", "test_db")
os.environ.setdefault("DB_URL", "localhost")
os.environ.setdefault("DB_PASSWORD", "test_pw")

import pytest  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from src.api.api_router import api_router  # noqa: E402


@pytest.fixture()
def app() -> FastAPI:
    """Bare FastAPI app with just the API router mounted (no DB connect)."""
    test_app = FastAPI()
    test_app.include_router(api_router)
    return test_app


@pytest.fixture()
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


@pytest.fixture()
def fake_user():
    """Stand-in user object for authenticate_user_from_request mocks."""
    return SimpleNamespace(id=42, username="test_user")


def make_record(
    *,
    record_id: int = 1,
    user_id: int = 42,
    image_url: str = "/images/240418_120000_dish1.jpg",
    result_gemini: Dict[str, Any] = None,
):
    """Build a minimal DishImageQuery-shaped object for CRUD mocks."""
    return SimpleNamespace(
        id=record_id,
        user_id=user_id,
        image_url=image_url,
        result_gemini=result_gemini,
    )


@pytest.fixture()
def captured_writes():
    """Helper that records every (query_id, result_gemini) write."""
    writes: List[Dict[str, Any]] = []

    def _capture(*, query_id, result_openai, result_gemini):  # pylint: disable=unused-argument
        writes.append({"query_id": query_id, "result_gemini": result_gemini})
        return True

    return writes, _capture
