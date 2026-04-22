# Backend tests

`pytest` suite for the FastAPI backend.

## Run

```bash
source venv/bin/activate
cd backend
pytest                       # all tests
pytest -v                    # verbose
pytest tests/test_item_retry.py::test_400_when_no_prior_error  # one test
```

The first run installs nothing — the deps (`pytest`, `pytest-asyncio`, `httpx`) live in `requirements.txt` at the repo root.

## What's covered

| File | Scope |
|------|-------|
| `test_item_tasks.py` | Unit tests for `_classify_step2_error` (5 buckets) and `_persist_step2_error` (mocked CRUD writes). |
| `test_item_retry.py` | FastAPI `TestClient` tests for `POST /api/item/{id}/retry-nutrition` — auth, ownership, 400 guards, success path, retry counter. |

## How fixtures work

`tests/conftest.py` sets enough environment variables (`JWT_SECRET_KEY`, `DB_*`) for the import side effects in `src.database` and `src.auth` to succeed without a real Postgres. The `app` fixture mounts only the API router on a bare `FastAPI()` instance — `create_app()` from `src/main.py` is **not** invoked, because it would call `models.Base.metadata.create_all(bind=engine)` and try to connect to the DB.

CRUD and auth functions are patched per-test via `monkeypatch.setattr(item_retry, "...", ...)`. Reach into the imported names on the endpoint module (e.g. `src.api.item_retry.get_dish_image_query_by_id`), not the source module.

## Not covered yet

- Integration tests that exercise the real DB / real Gemini call. Those require a test Postgres + cassettes and are deferred.
- Pre-commit / CI integration. Adding a `pytest` hook to pre-commit would slow every commit; running tests in CI requires a workflow file in `.github/workflows/`. Both are project-level decisions tracked separately.
