# Phase 1 Error UI & Retry

**Feature**: Surface Phase 1 (Component Identification) failures to the user with a clear error state and a one-click retry, mirroring the Phase 2 fix.
**Plan Created:** 2026-04-18
**Status:** Plan
**Reference**:
- [Plan — Phase 2 Error UI & Retry](./260418_phase2_error_handling.md) — the pattern this plan replicates for Phase 1.
- [Issues — 260414](../issues/260414.md) (the unchecked item under "Should fix")
- [Abstract — Component Identification](../abstract/dish_analysis/component_identification.md)
- [Technical — Component Identification](../technical/dish_analysis/component_identification.md)
- [Technical — Meal Upload](../technical/meal_upload.md) (host of `analyze_image_background` today)
- [Technical — Nutritional Analysis](../technical/dish_analysis/nutritional_analysis.md) (the already-shipped Phase 2 reference implementation)

---

## Problem Statement

1. `analyze_image_background` (`backend/src/api/date.py:74-75`) catches every exception in Phase 1 and only logs it. The DB row is left with `result_gemini = NULL`.
2. `ItemV2.jsx:51-53` enters Phase 1 polling whenever `result_gemini` is null and never stops because there is no error signal in the response. The user sees the `AnalysisLoading` spinner with the message "Analyzing dish components..." indefinitely.
3. Failure modes that hit this code path today: missing `GEMINI_API_KEY`, missing prompt file, transient Gemini 5xx/429, schema parse failure, Pydantic validation failure on `Step1ComponentIdentification`, image bytes unreadable.
4. The Phase 2 fix (shipped in commit `4d91c99`) introduced a clean pattern — `step2_error` blob + `POST /retry-step2` + `Step2ErrorCard` — but Phase 1 still has the original "polls forever" gap, called out explicitly in `docs/technical/dish_analysis/component_identification.md` Constraints & Edge Cases.
5. Phase 1 differs from Phase 2 in one structural way: when Phase 1 fails, `result_gemini` is `NULL` (not an existing JSON blob with a key added). The persistence helper has to initialize the blob from scratch.

---

## Proposed Solution

Apply the Phase 2 pattern to Phase 1 with two refinements that also clean up the Phase 2 code:

1. **Persist `result_gemini.step1_error`** when the Phase 1 background task catches an exception. If `result_gemini` is `NULL` (the common case for Phase 1 failures), initialize an empty dict before adding the error block. Frontend stops polling on either `step1_data` or `step1_error`.
2. **One-click retry** via `POST /api/item/{record_id}/retry-step1`. Re-invokes `analyze_image_background` with the existing image file and an incremented `retry_count`. Same auth/ownership/state guards as Phase 2.
3. **Refactor**: extract the shared error helpers — `ERROR_USER_MESSAGE`, `_classify_phase_error`, and a generic `_persist_phase_error(query_id, exc, retry_count, error_key)` — into a new `backend/src/api/_phase_errors.py`. Phase 2's `_classify_step2_error` / `_persist_step2_error` get rewritten as thin wrappers around the shared module so behavior is unchanged for the already-shipped feature. Same idea on the frontend: extract `Step2ErrorCard` into a generic `PhaseErrorCard` parametrized by `headline`/`loadingMessage` and reuse it for both phases.
4. **Relocate** `analyze_image_background` from `date.py` (currently 296 / 300 lines — 4 lines of headroom) to a new `backend/src/api/item_step1_tasks.py`, mirroring how Phase 2's background task lives in `item_tasks.py`. `date.py` continues to import the function from its new home.

Schema diff — Phase 1 failure path (no SQL change, JSON-only):

```json
// Today on Phase 1 failure: result_gemini = NULL  (frontend polls forever)
//
// New on Phase 1 failure:
{
  "step": 0,
  "step1_data": null,
  "step1_error": {
    "error_type":  "api_error",
    "message":     "Component identification failed temporarily. Try again in a moment.",
    "occurred_at": "2026-04-18T12:34:56.789Z",
    "retry_count": 0
  }
}
```

`step` is `0` to signal "no successful phase landed yet" (today the only `result_gemini` null state). Phase 1 success continues to set `step = 1` and clear `step1_error`. Retry endpoint clears `step1_error` and re-schedules the background task, which on success will overwrite the blob with the full `step1_data` payload (and the `iterations[0]` bookkeeping the existing happy path produces).

---

## Current Implementation Analysis

### What Exists (keep as-is)

| Component | File | Status |
|-----------|------|--------|
| `Step1ComponentIdentification` Pydantic schema | `backend/src/service/llm/models.py` | Keep — schema unchanged |
| `analyze_step1_component_identification_async` | `backend/src/service/llm/gemini_analyzer.py` | Keep — Gemini call surface unchanged |
| `get_step1_component_identification_prompt` | `backend/src/service/llm/prompts.py` | Keep — prompt unchanged |
| `update_dish_image_query_results` CRUD | `backend/src/crud/dish_query_basic.py` | Keep — reused for the error write and retry-clear |
| `GET /api/item/{record_id}` | `backend/src/api/item.py` | Keep — already returns `result_gemini` wholesale; will pass `step1_error` through with no schema change |
| `Step1ComponentEditor.jsx` | `frontend/src/components/item/Step1ComponentEditor.jsx` | Keep — only rendered when `step1_data` is set |
| `apiService.getItem` | `frontend/src/services/api.js` | Keep — same payload shape |
| Upload endpoints in `date.py` | `backend/src/api/date.py` | Keep — they still call `analyze_image_background`, but import it from the new `item_step1_tasks.py` |

### What Changes

| Component | Current | Proposed |
|-----------|---------|----------|
| `analyze_image_background` | Lives in `date.py`. Catches and logs every exception, returns silently. | Moves to new `backend/src/api/item_step1_tasks.py`. Catches, classifies, persists `result_gemini.step1_error` via shared helper. Accepts new optional `retry_count: int = 0`. On success, clears any prior `step1_error`. |
| `ItemV2.jsx` polling logic | Stops only when `result_gemini` arrives with a recognized state. | Also stops when `result_gemini.step1_error` is set; renders `PhaseErrorCard` instead of `AnalysisLoading`. |
| `result_gemini` JSON blob | No error key. | Adds optional `step1_error: { error_type, message, occurred_at, retry_count }`. |
| Retry path | None — user must abandon record. | New `POST /api/item/{id}/retry-step1` clears `step1_error`, re-schedules background task. |
| Phase 2 helpers | `_classify_step2_error`, `_persist_step2_error`, `ERROR_USER_MESSAGE` live in `item_tasks.py`. | Extracted into shared `backend/src/api/_phase_errors.py`. Phase 2 helpers become thin wrappers that pin the `error_key="step2_error"`. |
| `Step2ErrorCard.jsx` | Hardcodes "Nutritional analysis failed" headline and the `step2_error` shape. | Renamed/refactored to generic `PhaseErrorCard.jsx` taking a `headline` prop and the same `error` shape. Both Phase 1 and Phase 2 use it. Unit tests updated. |

---

## Implementation Plan

### Key Workflow

#### To Delete

None.

#### To Update

- `analyze_image_background` — rewrite the `except` block to call the shared `_persist_phase_error(..., error_key="step1_error", retry_count=retry_count)`. Also clear any prior `step1_error` on success (the same pattern the Phase 2 task uses for `step2_error`).
- `Step2ErrorCard.jsx` — rename to `PhaseErrorCard.jsx`, add `headline` prop. Update import sites.

#### To Add New

```
[User] sees PhaseErrorCard for Phase 1 → clicks "Try Again"
   │
   ▼
[Frontend] apiService.retryStep1(recordId)
   │
   ▼
[Backend] POST /api/item/{record_id}/retry-step1
   │
   ├── auth + ownership checks (mirror Phase 2)
   ├── guard: result_gemini.step1_data is null     (Phase 1 hasn't succeeded)
   ├── guard: result_gemini.step1_error is set     (else 400 — "nothing to retry")
   ├── guard: image file still on disk
   ├── re-read image_url
   ├── clear step1_error from result_gemini
   ├── persist
   └── BackgroundTasks.add_task(analyze_image_background, query_id, file_path, retry_count + 1)
   │
   ▼
[Backend] returns { success, retry_count }
   │
   ▼
[Frontend] resume 3s polling
   │
   ▼
[Backend task] succeeds → step1_data set, step1_error cleared    OR
              fails    → step1_error written with retry_count++
```

### Database Schema

#### To Delete

None.

#### To Update

None — `result_gemini` is JSON; no DDL change. The new `step1_error` key is additive and optional.

#### To Add New

None.

### CRUD

#### To Delete

None.

#### To Update

None — all writes go through `update_dish_image_query_results`.

#### To Add New

None.

### Services

#### To Delete

- The `_classify_step2_error` and `_persist_step2_error` function bodies in `backend/src/api/item_tasks.py` (replaced by thin wrappers around the shared module). The `ERROR_USER_MESSAGE` dict literal in `item_tasks.py` (moved to shared module).

#### To Update

- `backend/src/api/item_tasks.py`:
  - Import `_classify_phase_error`, `_persist_phase_error`, `ERROR_USER_MESSAGE` from the new `_phase_errors`.
  - `_classify_step2_error` becomes `_classify_phase_error` re-exported under its old name (for the existing tests) or deleted with tests pointed at the new name. Same for `_persist_step2_error`. **Recommendation**: rename in-place and update the tests; pure refactor, no behavior change.
  - `trigger_step2_analysis_background`'s `except` becomes `_persist_phase_error(query_id, exc, retry_count, "step2_error")`.

- `backend/src/api/date.py`:
  - Remove `analyze_image_background` definition (moves to `item_step1_tasks.py`).
  - Update import from `from src.service.llm.gemini_analyzer ...` chain — those are no longer needed in `date.py` and should be removed if unused after the move.
  - Replace local references with `from src.api.item_step1_tasks import analyze_image_background`.

#### To Add New

- `backend/src/api/_phase_errors.py` — shared module:

  ```python
  """
  Shared error classification and persistence for the two-phase Gemini
  pipeline. Used by:
    - src/api/item_step1_tasks.py     (Phase 1)
    - src/api/item_tasks.py           (Phase 2)
  """

  from datetime import datetime, timezone
  from src.crud.crud_food_image_query import (
      get_dish_image_query_by_id,
      update_dish_image_query_results,
  )

  ERROR_USER_MESSAGE = {
      "config_error":  "An internal configuration issue is preventing analysis. "
                       "Please try again later.",
      "image_missing": "The dish image is no longer available. Please re-upload the meal.",
      "parse_error":   "The AI response could not be parsed. Try again — this is "
                       "usually transient.",
      "api_error":     "The nutrition service is temporarily unavailable. Try again "
                       "in a moment.",
      "unknown":       "Something went wrong. Try again.",
  }

  def classify_phase_error(exc: Exception) -> str:
      msg = str(exc).lower()
      type_name = type(exc).__name__.lower()
      if "gemini_api_key" in msg or "api key" in msg:
          return "config_error"
      if type_name == "filenotfounderror" or ("image" in msg and "not found" in msg):
          return "image_missing"
      if "parse" in msg or "validation" in msg or "schema" in msg:
          return "parse_error"
      if any(t in msg for t in ("503", "429", "timeout", "connection")) or (
          type_name == "timeouterror"
      ):
          return "api_error"
      return "unknown"

  def persist_phase_error(
      query_id: int, exc: Exception, retry_count: int, error_key: str
  ) -> None:
      """Write `error_key` (e.g. 'step1_error' / 'step2_error') into result_gemini."""
      record = get_dish_image_query_by_id(query_id)
      if not record:
          return
      base = (record.result_gemini or {}).copy()
      error_type = classify_phase_error(exc)
      base[error_key] = {
          "error_type":  error_type,
          "message":     ERROR_USER_MESSAGE[error_type],
          "occurred_at": datetime.now(timezone.utc).isoformat(),
          "retry_count": retry_count,
      }
      update_dish_image_query_results(
          query_id=query_id, result_openai=None, result_gemini=base
      )
  ```

- `backend/src/api/item_step1_tasks.py` — new home for the Phase 1 background task:

  ```python
  """Background task for Phase 1 (Component Identification)."""

  from datetime import datetime, timezone
  import logging

  from src.api._phase_errors import persist_phase_error
  from src.crud.crud_food_image_query import (
      get_dish_image_query_by_id,
      update_dish_image_query_results,
  )
  from src.service.llm.gemini_analyzer import analyze_step1_component_identification_async
  from src.service.llm.prompts import get_step1_component_identification_prompt

  logger = logging.getLogger(__name__)


  async def analyze_image_background(
      query_id: int, file_path: str, retry_count: int = 0
  ) -> None:
      logger.info(
          "Starting Step 1 background analysis for query %s (retry_count=%s)",
          query_id, retry_count,
      )
      try:
          step1_prompt = get_step1_component_identification_prompt()
          step1_result = await analyze_step1_component_identification_async(
              image_path=file_path,
              analysis_prompt=step1_prompt,
              gemini_model="gemini-2.5-pro",
              thinking_budget=-1,
          )

          # Preserve any prior result_gemini fields (e.g., from a partial earlier
          # state); replace step1_data, clear step1_error.
          record = get_dish_image_query_by_id(query_id)
          base = (record.result_gemini or {}).copy() if record else {}

          base.update({
              "step": 1,
              "step1_data": step1_result,
              "step2_data": base.get("step2_data"),
              "step1_confirmed": base.get("step1_confirmed", False),
              "iterations": [
                  {
                      "iteration_number": 1,
                      "created_at": datetime.now(timezone.utc).isoformat(),
                      "step": 1,
                      "step1_data": step1_result,
                      "step2_data": None,
                      "metadata": {},
                  }
              ],
              "current_iteration": 1,
          })
          base.pop("step1_error", None)

          update_dish_image_query_results(
              query_id=query_id, result_openai=None, result_gemini=base
          )
          logger.info("Query %s Step 1 completed successfully", query_id)

      except Exception as exc:  # pylint: disable=broad-exception-caught
          logger.error("Failed Phase 1 for query %s: %s", query_id, exc, exc_info=True)
          persist_phase_error(query_id, exc, retry_count, "step1_error")
  ```

- `backend/src/api/item_retry.py` — extend with the new `retry_step1_analysis` handler (currently 89 lines; +~50 puts it at ~140, well under cap):

  ```python
  @router.post("/{record_id}/retry-step1")
  async def retry_step1_analysis(
      record_id: int, request: Request, background_tasks: BackgroundTasks,
  ) -> JSONResponse:
      user = authenticate_user_from_request(request)
      if not user:
          raise HTTPException(401, "Not authenticated")

      record = get_dish_image_query_by_id(record_id)
      if not record or record.user_id != user.id:
          raise HTTPException(404, "Record not found")

      result_gemini = record.result_gemini or {}
      if result_gemini.get("step1_data"):
          raise HTTPException(400, "Step 1 is already complete")
      if not result_gemini.get("step1_error"):
          raise HTTPException(400, "No prior error to retry")

      if not record.image_url:
          raise HTTPException(400, "No image found for this record")
      image_path = IMAGE_DIR / Path(record.image_url).name
      if not image_path.exists():
          raise HTTPException(404, "Image file no longer exists on disk")

      prior_retry = int(result_gemini["step1_error"].get("retry_count", 0))
      new_retry_count = prior_retry + 1

      cleared = result_gemini.copy()
      cleared.pop("step1_error", None)
      update_dish_image_query_results(
          query_id=record_id, result_openai=None, result_gemini=cleared
      )

      background_tasks.add_task(
          analyze_image_background, record_id, str(image_path), new_retry_count
      )
      return JSONResponse(content={
          "success": True,
          "message": "Step 1 analysis re-scheduled.",
          "record_id": record_id,
          "retry_count": new_retry_count,
          "step1_in_progress": True,
      })
  ```

### API Endpoints

#### To Delete

None.

#### To Update

| Method | Path | Change |
|--------|------|--------|
| GET | `/api/item/{record_id}` | Response now may include `result_gemini.step1_error` (additive). |

#### To Add New

| Method | Path | File | Auth | Request | Response (success) | Status |
|--------|------|------|------|---------|--------------------|--------|
| POST | `/api/item/{record_id}/retry-step1` | `backend/src/api/item_retry.py` | Cookie | empty body | `{ "success": true, "record_id": 42, "retry_count": 2, "step1_in_progress": true }` | 200 / 400 / 401 / 404 |

400 covers: Step 1 already complete, no prior error to retry, missing `image_url`. 404 covers: record not found / not owned, image file missing on disk.

### Testing

#### To Delete

None.

#### To Update

- `backend/tests/test_item_tasks.py`:
  - Rename `TestClassifyStep2Error` → `TestClassifyPhaseError` (since the helper is now the shared one); update import to `from src.api._phase_errors import classify_phase_error`.
  - Rename `TestPersistStep2Error` → `TestPersistPhaseError`; tests now invoke `persist_phase_error(query_id, exc, retry_count, error_key="step2_error")` for the existing assertions, and add new assertions for `error_key="step1_error"`.
  - All existing assertions stay valid because the helpers are pure refactors.

- `frontend/src/components/item/__tests__/Step2ErrorCard.test.jsx`:
  - Rename to `PhaseErrorCard.test.jsx`; component imported as `PhaseErrorCard`.
  - Add a new test case asserting the `headline` prop is rendered.

#### To Add New

- `backend/tests/test_item_step1_tasks.py` — covers the new background task wrapper:
  - `test_analyze_image_background_success_persists_step1_data`
  - `test_analyze_image_background_failure_persists_step1_error`
  - `test_analyze_image_background_clears_prior_step1_error_on_success`

- `backend/tests/test_item_retry.py` — extend with retry-step1 cases mirroring the retry-step2 set:
  - `test_retry_step1_returns_401_when_not_authenticated`
  - `test_retry_step1_returns_404_for_other_users_record`
  - `test_retry_step1_400_when_step1_already_complete`
  - `test_retry_step1_400_when_no_prior_error`
  - `test_retry_step1_404_when_image_file_missing`
  - `test_retry_step1_success_clears_error_and_schedules_task`
  - `test_retry_step1_increments_retry_count_from_prior_value`

- `frontend/src/components/item/__tests__/PhaseErrorCard.test.jsx` already covers the parametrized component. Add one case rendering with the Phase 1 headline ("Component identification failed").

Pre-commit loop:

1. `source venv/bin/activate && pre-commit run --all-files` — including the new `pytest-backend` and `jest-frontend` hooks added in the prior PR.
2. Fix any lint or line-count violations.
3. Re-run; Prettier may reformat. Repeat until clean.

### Frontend

#### To Delete

- `frontend/src/components/item/Step2ErrorCard.jsx` (renamed to `PhaseErrorCard.jsx`).

#### To Update

- `frontend/src/pages/ItemV2.jsx` (currently 266 lines — comfortable headroom):
  1. **Polling stop condition.** In both `loadItem` and the `setInterval` callback, treat `step1_error` as terminal:

     ```js
     if (resultGemini && (resultGemini.step1_data || resultGemini.step1_error)) {
       setPollingStep1(false);
       /* keep step2 logic unchanged */
     }
     ```

  2. **Render branch for the Phase 1 error.** Insert before the `Step1ComponentEditor` branch:

     ```jsx
     {resultGemini?.step1_error && !step1Data && viewStep === null && (
       <PhaseErrorCard
         headline="Component identification failed"
         error={resultGemini.step1_error}
         onRetry={handleStep1Retry}
         isRetrying={retryingStep1}
       />
     )}
     ```

  3. **Retry handler.** Add `handleStep1Retry` analogous to `handleStep2Retry`:

     ```js
     const handleStep1Retry = async () => {
       try {
         setRetryingStep1(true);
         await apiService.retryStep1(recordId);
         setPollingStep1(true);
         startPolling();
         await loadItem();
       } catch (err) {
         alert("Failed to retry. Please try again in a moment.");
       } finally {
         setRetryingStep1(false);
       }
     };
     ```

  4. **`Step2ErrorCard` import and JSX** — switch to `PhaseErrorCard` with `headline="Nutritional analysis failed"`.

- `frontend/src/services/api.js` — add `retryStep1(recordId)` mirroring `retryStep2`.

- `frontend/src/components/item/index.js` — replace `Step2ErrorCard` export with `PhaseErrorCard`.

#### To Add New

- `frontend/src/components/item/PhaseErrorCard.jsx` — generic version of `Step2ErrorCard` with new `headline` prop:

  ```jsx
  const PhaseErrorCard = ({ headline, error, onRetry, isRetrying }) => {
    if (!error) return null;
    /* identical body to today's Step2ErrorCard, but the <h3> uses {headline} */
  };
  ```

  Default `headline` value optional; both call sites pass it explicitly so the prop is required in practice.

### Documentation

#### Abstract (`docs/abstract/`)

- **Update** `docs/abstract/dish_analysis/component_identification.md`:
  - **Solution** — add: "If the AI call fails, the user sees a clear error message and can retry with one click."
  - **User Flow** — append an error branch under the existing flow:

    ```
    AI first pass runs in the background
      |
      +--> AI returns proposals --> Component Identification screen (existing)
      |
      +--> AI call fails
             |
             v
         Error card with reason + "Try Again" button
             |
             +--> Click Try Again --> Loading indicator --> AI re-runs
             +--> "Try Anyway" warning appears after 5 failed attempts
    ```
  - **Scope → Included** — add: "Visible error state with retry when the AI call fails."
  - **Acceptance Criteria** — add two new items:
    - `[ ] If the Phase 1 AI call fails, the user sees an error card explaining what went wrong instead of an indefinite loading spinner`
    - `[ ] The user can retry from the error card; on success the component proposals appear as normal`

- **No update needed** to `docs/abstract/dish_analysis/nutritional_analysis.md` — the Phase 2 abstract already documents the equivalent flow.

#### Technical (`docs/technical/`)

- **Update** `docs/technical/dish_analysis/component_identification.md`:
  - **Architecture** — add `step1_error` to the `result_gemini` blob description; add `PhaseErrorCard.jsx` to the React box.
  - **Data Model** — extend the `result_gemini` JSON example with the `step1_error` shape; reference the shared `error_type` enum documented in `_phase_errors.py`.
  - **Pipeline** — extend the bottom of the pipeline diagram to show the failure → `persist_phase_error` → frontend error card path; add a parallel retry sub-pipeline.
  - **Backend — API Layer** — add the `POST /api/item/{record_id}/retry-step1` row to the table.
  - **Backend — Service Layer** — note that `analyze_image_background` lives in `src/api/item_step1_tasks.py`, not `date.py`; document `persist_phase_error` and `classify_phase_error` (one-line summary, full doc lives in the Phase 2 technical doc since both phases share the helpers).
  - **Frontend — Components** — add `PhaseErrorCard.jsx` (note the `headline` prop differentiates Phase 1 vs Phase 2 use).
  - **Frontend — Services & Hooks** — add `apiService.retryStep1`.
  - **Constraints & Edge Cases** — replace the "frontend polls forever" note with the actual retry semantics; flag that `config_error` hides the retry button by reusing the same UX rule from Phase 2.
  - **Component Checklist** — add `[x]` rows for `analyze_image_background` (in new file), `_phase_errors.py`, retry-step1 endpoint, `PhaseErrorCard.jsx`, `apiService.retryStep1`.

- **Update** `docs/technical/dish_analysis/nutritional_analysis.md`:
  - **Backend — Service Layer** — note that `_classify_step2_error` / `_persist_step2_error` are now thin re-exports from `src/api/_phase_errors.py` (or deleted in favor of direct calls to the shared functions, depending on the refactor outcome).
  - **Frontend — Components** — rename `Step2ErrorCard.jsx` to `PhaseErrorCard.jsx` in the listing.
  - **Component Checklist** — flip the corresponding rows to reference the new names.

- **Update** `docs/technical/meal_upload.md`:
  - **Pipeline** — `analyze_image_background` now imported from `src/api/item_step1_tasks.py`; update the inline reference.

#### API Documentation (`docs/api_doc/`)

This project does not maintain a `docs/api_doc/` tree. API surface is documented inline in the per-feature technical docs.

No changes needed — covered by the technical doc updates above.

### Chrome Claude Extension Execution

Skipped at plan time, mirroring the Phase 2 plan's Open Question #5 outcome. The error card + retry button surface is small and covered by Jest unit tests + a 1-minute manual smoke (unset `GEMINI_API_KEY` → upload a meal → observe error card → restore key → click Try Again).

---

## Dependencies

- **Builds on**: Phase 2 error handling shipped in commit `4d91c99`. The shared module + generic component are extractions from that work, not new infrastructure.
- **No new database tables, third-party services, or Python/JS dependencies.**
- Test infrastructure (`pytest`, `pytest-asyncio`, `httpx`, Jest with `@testing-library`) already in place from the prior PR.

## Open Questions

1. **Refactor `Step2ErrorCard` → `PhaseErrorCard` and the Phase 2 helpers into shared `_phase_errors.py`?** The cleanest implementation reuses both, but it touches code that just shipped.

   **Recommendation: yes, refactor.** Reasons: (a) duplication would diverge over time — error message wording, classifier rules, soft-cap UX would drift between phases as fixes land in only one; (b) the refactor is mechanical (same logic, parameterized); (c) all the existing Phase 2 tests act as regression coverage for the rename. Risk is low because the change is structural, not behavioral.

2. **Retain backward-compatible re-exports of `_classify_step2_error` / `_persist_step2_error` in `item_tasks.py`?** Some external code (none in this repo) might import them.

   **Recommendation: no — delete them and update the internal callers + tests.** Both functions are leading-underscore "private" and the only consumers are `trigger_step2_analysis_background` and the test file. Keeping shim functions adds noise without real benefit.

3. **Auto-retry on transient errors for Phase 1?** Same trade-off as Phase 2.

   **Recommendation: no — manual retry only.** Same justification as Phase 2: no observability, retry hides outages from telemetry, manual click costs nothing extra. Keeps the two phases consistent.

4. **Soft retry cap for Phase 1?** Phase 2 swaps the button label to "Try Anyway" at `retry_count >= 5`.

   **Recommendation: yes — reuse the same `SOFT_RETRY_CAP = 5` constant.** Move the constant into `PhaseErrorCard.jsx` (or a tiny shared `constants.js`) so it stays single-source.

5. **`step` value when `result_gemini` is created from scratch by an error.** Should it be `0` (sentinel for "nothing succeeded yet") or absent entirely?

   **Recommendation: `step = 0`.** Simplifies the frontend's branching logic — every successful read of `result_gemini` has a `step` field. The frontend can switch on `step in (0, 1, 2)` without null-checking the field separately.

6. **Chrome E2E test spec?** Same trade-off as Phase 2.

   **Recommendation: skip.** Same reasoning. One card, one button, one endpoint — Jest covers the UI, pytest covers the endpoint, manual smoke covers the integration. Save Chrome E2E for richer multi-page flows.
