# Phase 2 Error UI & Retry

**Feature**: Surface Phase 2 (Nutritional Analysis) failures to the user with a clear error state and a one-click retry, replacing today's silent "Calculating nutritional values…" infinite spinner.
**Plan Created:** 2026-04-18
**Status:** Plan
**Reference**:
- [Discussion — Known Issues on Shipped Features](../discussion/260418_key_technical_features_status.md)
- [Issues — 260414](../issues/260414.md) (under "Known Issues on Shipped Features → Should fix")
- [Abstract — Nutritional Analysis](../abstract/dish_analysis/nutritional_analysis.md)
- [Technical — Nutritional Analysis](../technical/dish_analysis/nutritional_analysis.md)
- [Technical — Component Identification](../technical/dish_analysis/component_identification.md)

---

## Problem Statement

1. `trigger_step2_analysis_background` (`backend/src/api/item_tasks.py:80-81`) catches every exception and only logs it. The DB row is left at `step1_confirmed=true, step2_data=null` with no error marker.
2. `ItemV2.jsx` polls `/api/item/{id}` every 3 s and stops only when `step2_data` is present (`ItemV2.jsx:106-114`). With no `step2_data` and no error signal, the loop runs forever.
3. The user sees the `AnalysisLoading` component with the message "Calculating nutritional values..." indefinitely. They cannot retry, cannot tell the difference between "still working" and "permanently failed", and have no path forward without abandoning the record.
4. Failure modes that hit this code path today: missing `GEMINI_API_KEY`, missing prompt file, transient Gemini 5xx/429, schema parse failure, network timeout, image file deleted between Phase 1 and Phase 2.
5. The "Constraints & Edge Cases" section of the technical doc and the "Component Checklist" both flag this gap (`[ ] Retry / error-state UI for Phase 2 failures`). It is the highest-severity open item under shipped features.

---

## Proposed Solution

Persist a `step2_error` object inside `result_gemini` whenever the Phase 2 background task fails. The frontend's existing 3-second poller learns to recognize that field, stops polling, and renders a new `Step2ErrorCard` component with a one-click **Try Again** button. Retry is a new endpoint that re-reads `confirmed_dish_name` + `confirmed_components` from the existing record, clears the error marker, and re-schedules the same background task.

Design choices:

- **Persisted error, not in-memory.** The error survives page refresh and remains visible to the user even if they close the tab and come back. Symmetric with how `step2_data` is persisted.
- **No DB migration.** `result_gemini` is already JSON; we only add one nested key. The `DishImageQuery` table is untouched.
- **Single retry endpoint, no auto-retry.** Avoids quietly burning Gemini cost on persistent failures. The user explicitly opts in. A retry counter is incremented for telemetry / future cap.
- **No new failure-mode classification beyond a small enum** (`api_error | config_error | parse_error | image_missing | unknown`). Enough to render distinct user-facing messages without overengineering.
- **Phase 1 is out of scope for this plan**, even though it has the identical gap. Same pattern can be applied next; called out in Open Questions.

Schema diff (no SQL change, JSON-only):

```json
{
  "step": 1,
  "step1_data":      { ... },
  "step1_confirmed": true,
  "confirmed_dish_name":   "...",
  "confirmed_components":  [ ... ],
  "step2_data":      null,
  "step2_error": {
    "error_type":    "api_error",
    "message":       "Gemini returned 503 after 20s. The service may be temporarily unavailable.",
    "occurred_at":   "2026-04-18T12:34:56.789Z",
    "retry_count":   1
  }
}
```

Lifecycle:

```
Step 2 succeeds  → step2_data set,  step2_error absent
Step 2 fails     → step2_data null, step2_error set
User retries     → step2_error cleared, background task re-scheduled
                   on success: step2_data set
                   on failure: step2_error set again with retry_count + 1
```

---

## Current Implementation Analysis

### What Exists (keep as-is)

| Component | File | Status |
|-----------|------|--------|
| `Step2NutritionalAnalysis` Pydantic schema | `backend/src/service/llm/models.py` | Keep — output schema is unchanged |
| `analyze_step2_nutritional_analysis_async` | `backend/src/service/llm/gemini_analyzer.py` | Keep — Gemini call surface unchanged |
| `get_step2_nutritional_analysis_prompt` | `backend/src/service/llm/prompts.py` | Keep — prompt unchanged |
| `update_dish_image_query_results` CRUD | `backend/src/crud/dish_query_basic.py` | Keep — reused for the error write and retry-clear |
| `GET /api/item/{record_id}` | `backend/src/api/item.py` | Keep — already returns `result_gemini` wholesale, will pass `step2_error` through with no schema change |
| `Step2Results.jsx` | `frontend/src/components/item/Step2Results.jsx` | Keep — only rendered when `step2_data` is set |
| `apiService.getItem` | `frontend/src/services/api.js` | Keep — same payload shape |
| `confirm_step1_and_trigger_step2` endpoint | `backend/src/api/item.py` | Keep — same body, schedules same background task |

### What Changes

| Component | Current | Proposed |
|-----------|---------|----------|
| `trigger_step2_analysis_background` | Catches and logs every exception, returns silently | Catches, classifies, writes `step2_error` into `result_gemini`, then returns |
| `ItemV2.jsx` polling logic | Stops only when `step2_data` is set | Also stops when `step2_error` is set; renders `Step2ErrorCard` instead of `AnalysisLoading` |
| `result_gemini` JSON blob | No error key | Adds optional `step2_error: { error_type, message, occurred_at, retry_count }` |
| Retry path | None — user must abandon record | New `POST /api/item/{id}/retry-step2` clears `step2_error`, re-schedules background task |

---

## Implementation Plan

### Key Workflow

#### To Delete

None.

#### To Update

`trigger_step2_analysis_background` — change the existing `except` block from log-and-return to log-and-persist-error.

#### To Add New

New retry workflow:

```
[User] sees Step2ErrorCard → clicks "Try Again"
   │
   ▼
[Frontend] apiService.retryStep2(recordId)
   │
   ▼
[Backend] POST /api/item/{record_id}/retry-step2
   │
   ├── auth + ownership checks (mirror confirm-step1)
   ├── guard: step1_confirmed === true
   ├── guard: step2_data === null
   ├── guard: step2_error is set       (else 400 — "nothing to retry")
   ├── re-read confirmed_dish_name + confirmed_components
   ├── clear step2_error from result_gemini
   ├── persist (step1_confirmed stays true, step2_data stays null)
   └── BackgroundTasks.add_task(trigger_step2_analysis_background, ...)
   │
   ▼
[Backend] returns { success, retry_count }
   │
   ▼
[Frontend] resume 3s polling (same handler as initial Phase 2 wait)
   │
   ▼
[Backend task] succeeds → step2_data set     OR
              fails    → step2_error set with retry_count++
   │
   ▼
[Frontend] poll picks up either step2_data or step2_error
              → render Step2Results OR Step2ErrorCard
```

### Database Schema

#### To Delete

None.

#### To Update

None — `result_gemini` is JSON; no DDL change. The new `step2_error` key is additive and optional.

#### To Add New

None.

### CRUD

#### To Delete

None.

#### To Update

None — all writes go through `update_dish_image_query_results` which already replaces the `result_gemini` blob wholesale.

#### To Add New

None.

### Services

#### To Delete

None.

#### To Update

`backend/src/api/item_tasks.py` — replace the bare `except` at the bottom of `trigger_step2_analysis_background` with classification + persistence:

```python
except Exception as exc:  # pylint: disable=broad-exception-caught
    logger.error("Failed Step 2 analysis for query %s: %s", query_id, exc, exc_info=True)
    _persist_step2_error(query_id, exc)
```

Add a private helper in the same file:

```python
def _persist_step2_error(query_id: int, exc: Exception) -> None:
    """Classify the exception and write step2_error into result_gemini."""
    record = get_dish_image_query_by_id(query_id)
    if not record or not record.result_gemini:
        return  # nothing to attach the error to

    error_type = _classify_step2_error(exc)
    prior_error = record.result_gemini.get("step2_error") or {}
    retry_count = int(prior_error.get("retry_count", 0))

    result_gemini = record.result_gemini.copy()
    result_gemini["step2_error"] = {
        "error_type": error_type,
        "message": _user_message_for(error_type, exc),
        "occurred_at": datetime.now(UTC).isoformat(),
        "retry_count": retry_count,  # incremented by the retry endpoint, not here
    }
    update_dish_image_query_results(
        query_id=query_id, result_openai=None, result_gemini=result_gemini
    )


def _classify_step2_error(exc: Exception) -> str:
    msg = str(exc).lower()
    if "gemini_api_key" in msg or "api key" in msg:
        return "config_error"
    if "filenotfound" in msg or "image" in msg and "not found" in msg:
        return "image_missing"
    if "parse" in msg or "validation" in msg or "schema" in msg:
        return "parse_error"
    if "503" in msg or "429" in msg or "timeout" in msg or "connection" in msg:
        return "api_error"
    return "unknown"


def _user_message_for(error_type: str, exc: Exception) -> str:
    return {
        "config_error":  "The nutrition service is misconfigured. Please contact support.",
        "image_missing": "The dish image is no longer available. Please re-upload the meal.",
        "parse_error":   "The AI response could not be parsed. Try again — this is usually transient.",
        "api_error":     "The nutrition service is temporarily unavailable. Try again in a moment.",
        "unknown":       "Something went wrong while calculating nutrition. Try again.",
    }[error_type]
```

#### To Add New

`backend/src/api/item.py` — new handler `retry_step2_analysis`:

```python
@router.post("/{record_id}/retry-step2")
async def retry_step2_analysis(
    record_id: int,
    request: Request,
    background_tasks: BackgroundTasks,
) -> JSONResponse:
    user = authenticate_user_from_request(request)
    if not user:
        raise HTTPException(401, "Not authenticated")

    record = get_dish_image_query_by_id(record_id)
    if not record or record.user_id != user.id:
        raise HTTPException(404, "Record not found")

    rg = record.result_gemini or {}
    if not rg.get("step1_confirmed"):
        raise HTTPException(400, "Step 1 has not been confirmed")
    if rg.get("step2_data"):
        raise HTTPException(400, "Step 2 is already complete")
    if not rg.get("step2_error"):
        raise HTTPException(400, "No prior error to retry")

    image_path = (IMAGE_DIR / Path(record.image_url).name).resolve()
    if not image_path.exists():
        raise HTTPException(404, "Image file no longer exists on disk")

    prior_retry = int(rg["step2_error"].get("retry_count", 0))
    new_retry_count = prior_retry + 1

    cleared = rg.copy()
    cleared.pop("step2_error", None)
    update_dish_image_query_results(
        query_id=record_id, result_openai=None, result_gemini=cleared
    )

    background_tasks.add_task(
        trigger_step2_analysis_background,
        record_id,
        image_path,
        rg["confirmed_dish_name"],
        rg["confirmed_components"],
        new_retry_count,  # passed so subsequent failure preserves the count
    )

    return JSONResponse({
        "success": True,
        "record_id": record_id,
        "retry_count": new_retry_count,
        "step2_in_progress": True,
    })
```

`trigger_step2_analysis_background` signature gains an optional `retry_count: int = 0` parameter so failures preserve the running count rather than resetting to zero. `_persist_step2_error` writes `retry_count` from this parameter instead of reading the prior value.

### API Endpoints

#### To Delete

None.

#### To Update

| Method | Path | Change |
|--------|------|--------|
| GET | `/api/item/{record_id}` | Response now may include `result_gemini.step2_error` (additive only). No schema-breaking change. |

#### To Add New

| Method | Path | File | Auth | Request | Response (success) | Status |
|--------|------|------|------|---------|--------------------|--------|
| POST | `/api/item/{record_id}/retry-step2` | `backend/src/api/item.py` | Cookie | empty body | `{ "success": true, "record_id": 42, "retry_count": 2, "step2_in_progress": true }` | 200 / 400 / 401 / 404 |

400 responses cover: Step 1 not confirmed, Step 2 already complete, no prior error to retry.
404 responses cover: record not found / not owned, image file missing on disk.

### Testing

#### To Delete

None.

#### To Update

None.

#### To Add New

Unit tests (`backend/tests/`):

- `test_item_tasks.py::test_persist_step2_error_writes_classified_error`
- `test_item_tasks.py::test_classify_step2_error_buckets`
  - `GEMINI_API_KEY missing` → `config_error`
  - `FileNotFoundError(image)` → `image_missing`
  - Pydantic ValidationError → `parse_error`
  - `httpx.TimeoutException` / Gemini 503 / 429 strings → `api_error`
  - generic `RuntimeError("boom")` → `unknown`
- `test_item.py::test_retry_step2_requires_auth_returns_401`
- `test_item.py::test_retry_step2_returns_404_for_other_users_record`
- `test_item.py::test_retry_step2_400_when_step1_not_confirmed`
- `test_item.py::test_retry_step2_400_when_step2_already_complete`
- `test_item.py::test_retry_step2_400_when_no_prior_error`
- `test_item.py::test_retry_step2_clears_error_and_schedules_task`
- `test_item.py::test_retry_step2_increments_retry_count`

Integration tests:

- `test_step2_failure_persists_error_and_polling_stops` — mock `analyze_step2_nutritional_analysis_async` to raise, run the background task in-process, GET `/api/item/{id}` and assert `step2_error` is set.
- `test_step2_retry_round_trip` — same as above, then POST `/retry-step2`, mock the analyzer to succeed, assert `step2_error` is gone and `step2_data` is set.

Frontend tests (Jest):

- `Step2ErrorCard.test.jsx` — renders message + retry button, calls `onRetry` on click, disables button while `isRetrying`.
- `ItemV2.test.jsx::renders_error_card_when_step2_error_present`
- `ItemV2.test.jsx::stops_polling_when_step2_error_appears`
- `ItemV2.test.jsx::resumes_polling_after_retry_click`

Pre-commit loop:

1. Run `source venv/bin/activate && pre-commit run --all-files`.
2. Fix any lint or line-count violations.
3. Re-run pre-commit; Prettier may push files over the 300-line frontend cap. Extract to separate components if so (see Frontend section — `ItemV2.jsx` is already at 297 lines).
4. Repeat until pre-commit passes cleanly.

### Frontend

#### To Delete

None.

#### To Update

`frontend/src/pages/ItemV2.jsx` — three changes:

1. **Polling stop condition.** In both `loadItem` and the `setInterval` callback, treat `step2_error` as a polling-terminal state alongside `step2_data`:

   ```js
   if (resultGemini.step2_data || resultGemini.step2_error) {
     setPollingStep1(false);
     setPollingStep2(false);
     stopPolling();
   }
   ```

2. **Render branch for the error.** Insert before the `Step2Results` branch:

   ```jsx
   {resultGemini?.step2_error && !step2Data && viewStep === null && (
     <Step2ErrorCard
       error={resultGemini.step2_error}
       onRetry={handleStep2Retry}
       isRetrying={retryingStep2}
     />
   )}
   ```

3. **Retry handler.** Add `handleStep2Retry` analogous to `handleStep1Confirmation`:

   ```js
   const handleStep2Retry = async () => {
     try {
       setRetryingStep2(true);
       await apiService.retryStep2(recordId);
       setPollingStep2(true);
       startPolling();
       await loadItem();
     } catch (err) {
       console.error("Retry failed:", err);
     } finally {
       setRetryingStep2(false);
     }
   };
   ```

`ItemV2.jsx` is currently 297 lines (cap is 300). Adding the three changes above will exceed the cap; extract one of the existing inline blocks (the Step 1 / Step 2 progress tab row at lines 213-259) into a new `ItemStepTabs.jsx` component as part of this PR to stay under the cap durably.

`frontend/src/services/api.js` — add `retryStep2(recordId)` mirroring `confirmStep1`:

```js
retryStep2: async (recordId) => {
  const res = await fetch(`${API_URL}/api/item/${recordId}/retry-step2`, {
    method: "POST",
    credentials: "include",
  });
  if (!res.ok) throw new Error(`Retry failed: ${res.status}`);
  return res.json();
},
```

#### To Add New

- `frontend/src/components/item/Step2ErrorCard.jsx` — error UI. Renders:
  - red-tinted card (Tailwind: `bg-red-50 border border-red-200`).
  - icon (use the existing red-X SVG pattern from `ItemV2.jsx:166-178`).
  - `error.message` as the headline.
  - `error_type`-specific hint line (e.g., for `image_missing`: link back to the meal upload page; for `config_error`: hide the retry button — retrying won't help).
  - "Try Again" button — disabled when `isRetrying`, hidden when `error_type === "config_error"`.
  - Subtle `retry_count > 0 ? "Previous attempts: {n}" : null` footer.
- `frontend/src/components/item/ItemStepTabs.jsx` — extracted Step 1 / Step 2 progress tab block (mechanical move of the existing JSX from `ItemV2.jsx:213-259` to satisfy the 300-line cap).
- Re-export both from `frontend/src/components/item/index.js`.

### Documentation

#### Abstract (`docs/abstract/`)

- **Update** `docs/abstract/dish_analysis/nutritional_analysis.md`:
  - **Solution** — add: "If the AI call fails, the user sees a clear error message and can retry with one click."
  - **User Flow** — append an error branch under the existing flow:

    ```
    AI returns results --> Results page (existing)
        |
        OR (on failure)
        |
        v
    Error card with reason + "Try Again" button
        |
        +--> Click Try Again --> AI re-runs --> Results page on success
    ```
  - **Scope → Included** — add: "Visible error state with retry when the AI call fails."
  - **Scope → Not included** — remove the implicit gap; no longer applicable.
  - **Acceptance Criteria** — add two new items:
    - `[ ] If the AI call fails, the user sees an error card explaining what went wrong instead of an indefinite loading spinner`
    - `[ ] The user can retry from the error card; on success the results view appears as normal`

#### Technical (`docs/technical/`)

- **Update** `docs/technical/dish_analysis/nutritional_analysis.md`:
  - **Architecture** — add `step2_error` to the `result_gemini` blob description and add a `Step2ErrorCard.jsx` node in the React box.
  - **Data Model** — extend the `result_gemini` JSON example with the `step2_error` shape; document the `error_type` enum (`api_error | config_error | parse_error | image_missing | unknown`).
  - **Pipeline** — extend the bottom of the pipeline diagram to show the failure → `_persist_step2_error` → frontend error card path; add a parallel retry sub-pipeline.
  - **Backend — API Layer** — add the `POST /api/item/{record_id}/retry-step2` row to the table.
  - **Backend — Service Layer** — document `_persist_step2_error`, `_classify_step2_error`, `_user_message_for`, the new optional `retry_count` parameter on `trigger_step2_analysis_background`, and the new `retry_step2_analysis` endpoint handler.
  - **Frontend — Components** — add `Step2ErrorCard.jsx` and `ItemStepTabs.jsx`.
  - **Frontend — Services & Hooks** — add `apiService.retryStep2`.
  - **Constraints & Edge Cases** — replace "There is no retry, no surfaced error state" with the actual retry semantics; flag that `config_error` hides the retry button on purpose.
  - **Component Checklist** — flip `[ ] Retry / error-state UI for Phase 2 failures` to `[x]`; add new checked items for `Step2ErrorCard.jsx`, `ItemStepTabs.jsx`, `retry_step2_analysis` endpoint, `_persist_step2_error`, `_classify_step2_error`.
- **Update** `docs/technical/dish_analysis/component_identification.md`:
  - **Constraints & Edge Cases** — note that Phase 1 still has the same gap (out of scope for this plan; tracked separately).

#### API Documentation (`docs/api_doc/`)

This project does not appear to maintain a dedicated `docs/api_doc/` tree (verified — only `abstract` / `technical` / `discussion` / `plan` / `report` / `issues` exist under `docs/`). API surface is documented inline in the per-feature technical docs.

No changes needed — API documentation lives inside the technical doc above and will be updated there.

### Chrome Claude Extension Execution

Skipped at plan time — see Open Questions. The error UI is a single new card with a single new button; if the team decides a Chrome E2E spec is warranted, invoke `chrome-test-generate` after the plan is approved and link the resulting `docs/chrome_test/{yymmdd}_{hhmm}_phase2_error_handling.md` here. Implementation can ship in parallel.

---

## Dependencies

- No new database tables, no new third-party services, no new Python or JS dependencies.
- Depends on existing: `DishImageQuery` row, `result_gemini` JSON blob, `update_dish_image_query_results` CRUD, `trigger_step2_analysis_background`, `apiService.getItem`, `ItemV2.jsx` polling loop.

## Open Questions

1. **Phase 1 parity.** Phase 1 has the same "polls forever on failure" problem (documented in `docs/technical/dish_analysis/component_identification.md` Constraints & Edge Cases). Should this plan also cover Phase 1, or is it acceptable to ship Phase 2 first and apply the same pattern in a follow-up?

   **Recommendation: ship Phase 2 first; do Phase 1 in a follow-up PR.** Reasons: (a) Phase 2 is the higher-impact gap because the user has already invested time editing components — losing that work to a silent failure is far more frustrating than losing a fresh upload; (b) keeping the PR scoped to one phase keeps the diff reviewable (~1 endpoint, ~1 component, ~1 helper module); (c) the pattern established here (`stepN_error` blob, classify + persist + retry endpoint) ports verbatim to Phase 1, so the second pass is mostly mechanical. Track Phase 1 as a separate item in `docs/issues/260414.md` immediately so it doesn't get forgotten.

2. **Auto-retry on transient errors.** Should the backend auto-retry once on `api_error` (e.g., HTTP 429 or 503) before surfacing the error to the user? Trade-off: better UX vs. silently doubling Gemini cost on persistent outages.

   **Recommendation: no auto-retry in V1; revisit after we have telemetry.** Reasons: (a) we currently have no observability on Gemini failure rates — auto-retry without visibility risks 2x cost during a regional outage; (b) Phase 2 takes 20-30s, so a single retry pushes the user-perceived latency to 40-60s with no UI feedback during the second attempt — a manual retry button gives the same recovery with explicit consent; (c) if telemetry later shows transient errors dominate (>70% of failures), add auto-retry for `api_error` only with `retry_count <= 1`, and surface the second attempt as "Retrying…" in the UI.

3. **Retry cap.** Should we cap `retry_count` (e.g., refuse retry after 5 attempts, force the user to delete the record)? Default proposal: no cap — the user is paying for their own attempts and the failure modes are not infinite-loop friendly.

   **Recommendation: soft cap at 5 attempts, then change the button label and message rather than blocking.** Reasons: (a) hard-blocking is hostile — the user has no recourse and may have a legitimate retry case (e.g., they fixed the missing image by re-uploading); (b) at 5 failed attempts the issue is almost certainly persistent (config, schema, or model regression), not transient; (c) showing "We've tried 5 times — this is unlikely to succeed without a fix. [Try Anyway] [Back to Dashboard]" both warns the user and protects against accidental cost burn, without taking the choice away. Implementation: backend keeps no cap; frontend swaps the button label and adds the warning when `retry_count >= 5`.

4. **`config_error` user message.** "Please contact support" assumes a support channel exists. If there is no support contact, fall back to a generic "An internal configuration issue is preventing analysis. Please try again later."

   **Recommendation: use the generic fallback for V1.** Reasons: (a) MealSnap is an internal R&D tool with no support channel today; (b) the generic message ("An internal configuration issue is preventing analysis. Please try again later.") is honest about the failure being non-user-actionable without making a promise the team can't keep; (c) revisit once a support channel (email, Slack, or in-app feedback form) exists. Also: the `config_error` branch already hides the retry button — that's the right UX, since retrying a missing API key won't fix anything.

5. **Chrome E2E test spec.** Generate one via `chrome-test-generate` for this feature, or rely on Jest unit tests + manual smoke check given the small surface area? Default proposal: rely on unit tests + manual smoke, given the feature is one card and one endpoint.

   **Recommendation: skip Chrome E2E for this feature; rely on Jest + manual smoke.** Reasons: (a) the feature surface is tiny — one new card, one new button, one new endpoint — and the failure modes are easy to mock at the Jest level; (b) the most realistic failure mode (Gemini API outage) cannot be exercised in a Chrome E2E test without injecting an artificial failure, which is exactly what the Jest tests already do; (c) manual smoke is one minute of work: temporarily unset `GEMINI_API_KEY` in `.env`, upload + confirm a meal, observe the error card + retry button, restore the env var. Save the Chrome E2E investment for features with rich multi-page user flows.
