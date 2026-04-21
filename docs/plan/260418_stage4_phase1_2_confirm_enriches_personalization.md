# Stage 4 — Phase 1.2: Confirm Endpoint Enriches the Personalization Row

**Feature**: After the user confirms Step 1, the matching `personalized_food_descriptions` row gains three user-verified columns: `confirmed_dish_name`, `confirmed_portions` (sum of component `number_of_servings`), and `confirmed_tokens` (the tokenized dish name). These enrich the per-user BM25 corpus so future uploads match against human-verified names instead of the Phase 1.1.1 Flash-generated caption alone.
**Plan Created:** 2026-04-18
**Status:** Plan
**Reference**:
- [Issues — 260415, Stage 4](../issues/260415.md)
- [Discussion — Food DB investigation & end-to-end redesign](../discussion/260418_food_db.md)
- [Plan — Stage 0 Personalized Food Index](./260418_stage0_personalized_food_index.md) (foundation)
- [Plan — Stage 2 Phase 1.1.1](./260418_stage2_phase1_1_1_fast_caption.md) (producer of the row this stage enriches)
- [Abstract — User Customization](../abstract/dish_analysis/user_customization.md)
- [Technical — User Customization](../technical/dish_analysis/user_customization.md)
- [Technical — Personalized Food Index](../technical/dish_analysis/personalized_food_index.md)
- [Chrome Test Spec — 260418_2337](../chrome_test/260418_2337_stage4_phase1_2_confirm_enriches_personalization.md)

---

## Problem Statement

1. Stage 0 shipped the `personalized_food_descriptions` schema with the `confirmed_dish_name / confirmed_portions / confirmed_tokens` columns nullable. Stage 2 wrote the row at Phase 1.1.1 time with only the Flash-generated caption's tokens. Nothing in the pipeline yet writes the confirmed columns, so the per-user BM25 corpus never sees the user's verified dish name.
2. Stage 6 (Phase 2.2) is designed to union `tokens` + `confirmed_tokens` at the query side when retrieving historical matches. Without Stage 4 populating `confirmed_tokens`, Stage 6 retrieval degrades to caption-only matching — which is precisely the low-signal path we want to improve upon with personalization.
3. The natural insertion point for this enrichment is `POST /api/item/{record_id}/confirm-step1`. The endpoint already receives `selected_dish_name` and `components` (with `number_of_servings` per component); both map directly to the three enrichment columns. The endpoint also already holds an atomic `confirm_step1_atomic` lock, so we have a clean post-lock hook for side effects.
4. The enrichment must be non-blocking for the user's confirmation flow. A DB error on the peripheral `personalized_food_descriptions` table should not bounce the user to an error card when the primary `DishImageQuery` write already succeeded. Similarly, if the personalization row is absent (Phase 1.1.1 graceful-degraded or the row was manually deleted), the enrichment should log and move on without creating a row — Stage 4 is not a fallback path for Stage 2.

---

## Proposed Solution

A single surgical change to `confirm_step1_and_trigger_step2` plus a log line. No new modules, no schema changes, no new CRUD (Stage 0 already shipped `update_confirmed_fields`).

```
confirm_step1_atomic(...) returns "confirmed"
  │
  ▼  (NEW: Stage 4)
try:
    confirmed_portions = sum(c.number_of_servings for c in confirmation.components)
    confirmed_tokens = personalized_food_index.tokenize(confirmation.selected_dish_name)
    updated_row = crud_personalized_food.update_confirmed_fields(
        query_id=record_id,
        confirmed_dish_name=confirmation.selected_dish_name,
        confirmed_portions=confirmed_portions,
        confirmed_tokens=confirmed_tokens,
    )
    if updated_row is None:
        logger.warning(
            "Stage 4 enrichment skipped: no personalized_food_descriptions row "
            "for query_id=%s (Phase 1.1.1 may have degraded gracefully)", record_id
        )
except Exception as exc:
    logger.warning(
        "Stage 4 enrichment failed for query_id=%s: %s", record_id, exc
    )
  │
  ▼
background_tasks.add_task(trigger_step2_analysis_background, ...)
return 200
```

### Why the swallow-log failure policy (confirmed with user 2026-04-18)

- **The user's primary intent succeeded.** `confirm_step1_atomic` already committed `step1_confirmed=True`, `confirmed_dish_name`, and `confirmed_components` onto `DishImageQuery.result_gemini`. The Phase 2 background task will be scheduled regardless. Returning 500 here would contradict the atomic commit and force the user to retry a confirm that already succeeded.
- **Stage 6 degrades cleanly when `confirmed_tokens` is null.** Stage 0's `personalized_food_index.search_for_user` reads `tokens`, not `confirmed_tokens`; Stage 6 (per the issue spec) unions both at the query side. Missing `confirmed_tokens` means the retrieval signal is weaker for the next upload — not broken.
- **Observability stays intact.** A WARN line (with `query_id`) is synchronous with the endpoint response, so log correlation for debugging is trivial.

### Call ordering (confirmed with user 2026-04-18)

Place the enrichment **after `confirm_step1_atomic(...) == "confirmed"`** and **before `background_tasks.add_task(...)`**. Functionally equivalent to placing after (FastAPI background tasks don't start until after the response), but placing before keeps "all state mutations happen before the dispatch" as a clean read-rule.

### Why this doesn't need a migration

Stage 0 already shipped:
- `confirmed_dish_name TEXT NULL`
- `confirmed_portions FLOAT NULL`
- `confirmed_tokens JSONB NULL`

and `crud_personalized_food.update_confirmed_fields(query_id, *, confirmed_dish_name, confirmed_portions, confirmed_tokens)` as the public write signature. Stage 4 is purely a new caller.

### Why we don't create a row when missing

Two reasons:
1. **Stage 2 is the row's producer of record.** If Stage 2 failed to insert (Phase 1.1.1 graceful-degraded on a caption failure), creating an implicit row here would have null `description` + `tokens` and only the confirmed columns populated — a weird partial state. The BM25 corpus would have a row with `tokens=[]` which is already filtered out by Stage 0's `search_for_user`, so it would not benefit retrieval anyway.
2. **Retry compatibility.** The user can re-run Phase 1.1.1 via `/retry-step1` (or by re-uploading) if they want the row present. Stage 4 staying strictly an updater keeps that path clean.

---

## Current Implementation Analysis

### What Exists (keep as-is)

| Component | File | Status |
|-----------|------|--------|
| `confirm_step1_atomic(record_id, *, confirmed_dish_name, confirmed_components)` | `backend/src/crud/dish_query_basic.py` | Keep — primary commit on `DishImageQuery`; Stage 4 runs strictly after. |
| `Step1ConfirmationRequest` schema | `backend/src/api/item_schemas.py` | Keep — `selected_dish_name` + `components[].number_of_servings` are what Stage 4 reads. No new fields. |
| `crud_personalized_food.update_confirmed_fields(...)` | `backend/src/crud/crud_personalized_food.py` | Keep — Stage 0 CRUD. Stage 4 is the first caller. |
| `personalized_food_index.tokenize(text)` | `backend/src/service/personalized_food_index.py` | Keep — Stage 4 reuses verbatim. |
| `trigger_step2_analysis_background` scheduling | `backend/src/api/item_tasks.py` | Keep — unchanged call site. |
| Confirm endpoint guards (auth, image file, atomic outcome translation) | `backend/src/api/item.py::confirm_step1_and_trigger_step2` | Keep — insert Stage 4 hook between the atomic CRUD and the background-task dispatch. |
| Existing tests | `backend/tests/test_item_confirm.py` | Keep — extend with new test cases; do not modify existing ones. |
| Frontend Step 1 editor (Confirm button) | `frontend/src/pages/ItemV2.jsx`, `frontend/src/components/item/Step1ComponentEditor.jsx` | Keep — no UI changes, no new props. |

### What Changes

| Component | Current | Proposed |
|-----------|---------|----------|
| `backend/src/api/item.py::confirm_step1_and_trigger_step2` | After `confirm_step1_atomic` returns "confirmed", goes directly to `background_tasks.add_task`. | Insert a Stage 4 enrichment block: call `crud_personalized_food.update_confirmed_fields` with swallow-log around it. Return 200 regardless. |
| `docs/abstract/dish_analysis/user_customization.md` | Describes the React editor and the confirm endpoint without mentioning personalization. | Add a one-sentence note: confirming Step 1 now also feeds the user's personalization history with the verified dish name, improving future retrieval. |
| `docs/technical/dish_analysis/user_customization.md` | Pipeline diagram shows `confirm_step1_atomic` → `trigger_step2_analysis_background`. | Extend the Pipeline diagram with the new enrichment hook; add a "Personalization Enrichment" sub-section documenting the three fields written, the failure policy, and the forward-link to [Personalized Food Index](./personalized_food_index.md). |
| `docs/technical/dish_analysis/personalized_food_index.md` | Stage 4 row on the Component Checklist is `[ ]`. | Flip to `[x]` with a one-line link back to `user_customization.md`. |

---

## Implementation Plan

### Key Workflow

No new coroutines, no new modules. The enrichment is a synchronous side effect inside the already-synchronous confirm endpoint.

```
POST /api/item/{record_id}/confirm-step1
  │
  ├── auth + ownership (existing)
  ├── image file exists (existing)
  │
  ▼
outcome = confirm_step1_atomic(record_id, confirmed_dish_name, confirmed_components)
  │
  ├── "not_found"  → 404 (existing)
  ├── "no_step1"   → 400 (existing)
  ├── "duplicate"  → 409 (existing)
  │
  ▼  (outcome == "confirmed")
[NEW] try:
         confirmed_portions = sum(c.number_of_servings for c in confirmation.components)
         confirmed_tokens   = personalized_food_index.tokenize(confirmation.selected_dish_name)
         updated_row = crud_personalized_food.update_confirmed_fields(
             query_id=record_id,
             confirmed_dish_name=confirmation.selected_dish_name,
             confirmed_portions=confirmed_portions,
             confirmed_tokens=confirmed_tokens,
         )
         if updated_row is None:
             log WARN "Stage 4 enrichment skipped: no personalization row ..."
[NEW] except Exception as exc:
         log WARN "Stage 4 enrichment failed: ..."
  │
  ▼
background_tasks.add_task(trigger_step2_analysis_background, ...)
  │
  ▼
return 200 { success, record_id, confirmed_dish_name, step2_in_progress: true }
```

The try/except catches a broad `Exception` because the enrichment is fire-and-forget correctness — a specific catch list would leave us one DB-error class away from a 500 for a non-essential side effect.

#### To Delete

None.

#### To Update

- `backend/src/api/item.py::confirm_step1_and_trigger_step2` — insert the Stage 4 enrichment block described above.
- Import additions in `backend/src/api/item.py`:
  - `from src.crud import crud_personalized_food`
  - `from src.service import personalized_food_index`

#### To Add New

None.

---

### Database Schema

**No changes.** Stage 0 already shipped the three columns and the `update_confirmed_fields` CRUD. Stage 4 is a new caller only.

#### To Delete

None.

#### To Update

None.

#### To Add New

None.

---

### CRUD

**No changes.** `crud_personalized_food.update_confirmed_fields(query_id, *, confirmed_dish_name, confirmed_portions, confirmed_tokens)` already exists (Stage 0) with the exact signature Stage 4 needs. Its contract:

- Returns the updated ORM row on success.
- Returns `None` when no row exists for `query_id` (Stage 4 treats this as a WARN, not an error).
- Raises on DB errors (Stage 4 treats these as WARN + swallow).

Stage 4 adds no new CRUD calls.

#### To Delete

None.

#### To Update

None.

#### To Add New

None.

---

### Services

**No changes.** `personalized_food_index.tokenize(text) -> List[str]` already exists (Stage 0) and is deterministic for the same input.

#### To Delete

None.

#### To Update

None.

#### To Add New

None.

---

### API Endpoints

No new endpoints. `POST /api/item/{record_id}/confirm-step1` behavior changes are:

- **Request body:** unchanged.
- **Response body:** unchanged (still `{ success, record_id, confirmed_dish_name, step2_in_progress }`).
- **Status codes:** unchanged. 200 on success; 400 / 404 / 409 as today. Stage 4 does not introduce any new failure statuses.
- **Side effects (new):** after a successful confirm, `personalized_food_descriptions` row for this `query_id` has `confirmed_dish_name`, `confirmed_portions`, `confirmed_tokens` populated (subject to the row existing).

Because the response contract is unchanged, no API doc file update is required. The project does not yet ship a `docs/api_doc/` tree.

#### To Delete

None.

#### To Update

None.

#### To Add New

None.

---

### Testing

Test location: `backend/tests/`. Extend the existing `test_item_confirm.py`.

**Unit tests — confirm endpoint enrichment (`backend/tests/test_item_confirm.py` — append):**

- `test_enrichment_calls_update_confirmed_fields_with_tokenized_dish_name` — happy path; patch `crud_personalized_food.update_confirmed_fields` and `personalized_food_index.tokenize`; assert the update is called with `confirmed_dish_name` equal to the request body, `confirmed_portions` equal to the sum of component `number_of_servings`, and `confirmed_tokens` equal to the tokenizer output.
- `test_enrichment_confirmed_portions_sums_multiple_components` — request body with three components (0.5, 1.0, 1.5); assert `confirmed_portions=3.0` lands in the CRUD call.
- `test_enrichment_called_before_background_task_dispatch` — capture the ordering of side effects; assert `update_confirmed_fields` runs before `BackgroundTasks.add_task`.
- `test_enrichment_swallows_none_return_and_still_schedules_phase2` — patch the update to return `None` (row missing); assert endpoint returns 200, Phase 2 task is still scheduled, and a WARN log line containing the `query_id` was emitted (via `caplog`).
- `test_enrichment_swallows_exception_and_still_schedules_phase2` — patch the update to raise `RuntimeError("db down")`; assert endpoint returns 200, Phase 2 task is still scheduled, WARN log line names the exception.
- `test_enrichment_not_called_on_duplicate_outcome` — `confirm_step1_atomic` returns `"duplicate"`; assert the endpoint returns 409 AND `update_confirmed_fields` was NOT invoked (idempotency — duplicate confirm must not stomp on the first confirmation's persisted values).
- `test_enrichment_not_called_on_no_step1_outcome` — `confirm_step1_atomic` returns `"no_step1"`; assert 400 and no update call.
- `test_enrichment_not_called_on_not_found_outcome` — `confirm_step1_atomic` returns `"not_found"`; assert 404 and no update call.

**Pre-commit loop (mandatory):**

1. `source venv/bin/activate && pre-commit run --all-files`.
2. Fix any lint / line-count issues. `item.py` is ~262 lines today; Stage 4 adds ~15 lines — well under the 300 cap. `test_item_confirm.py` was ~196 lines; adds ~120 lines for the new tests. Monitor.
3. Re-run pre-commit. Repeat until clean.

**Acceptance check from the issue's "done when":**

- After `POST /confirm-step1`, `SELECT confirmed_dish_name, confirmed_portions, confirmed_tokens FROM personalized_food_descriptions WHERE query_id = <id>` returns non-null values.
- A subsequent upload by the same user whose fast caption token-overlaps the confirmed tokens retrieves the row as its reference (verified end-to-end in Chrome Test 3).

#### To Delete

None.

#### To Update

- `backend/tests/test_item_confirm.py` — append eight tests listed above.

#### To Add New

None.

---

### Frontend

None. Stage 4 ships no UI changes. The Step 1 Confirm button's payload is unchanged; the Confirm button still posts the same request body.

#### To Delete

None.

#### To Update

None.

#### To Add New

None.

---

### Documentation

#### Abstract (`docs/abstract/`)

- **Update** `docs/abstract/dish_analysis/user_customization.md` — append a one-sentence note at the end of the existing Solution section:
  > Confirming Step 1 now also feeds the user's personalization history with the verified dish name and portion count, improving accuracy on future uploads of similar dishes. This enrichment is invisible to the user and per-account — one user's confirmed dishes never affect another user's analyses.

#### Technical (`docs/technical/`)

- **Update** `docs/technical/dish_analysis/user_customization.md`:
  - Under the **Pipeline** section, extend the ASCII flow so the `confirm_step1_atomic` → `trigger_step2_analysis_background` chain shows the Stage 4 enrichment hook inserted between them (see "Key Workflow" in this plan).
  - Add a new **Personalization Enrichment** sub-section after Pipeline documenting:
    - The three columns written (`confirmed_dish_name`, `confirmed_portions`, `confirmed_tokens`).
    - The `confirmed_portions = sum(c.number_of_servings)` calculation.
    - The tokenization step (`personalized_food_index.tokenize`).
    - The swallow-log failure policy and its rationale (Phase 1.2 is fire-and-forget correctness for future uploads).
    - A forward-link to [Personalized Food Index](./personalized_food_index.md) and a back-link from its Component Checklist.
  - Extend the Component Checklist at the bottom with:
    - `[x] Stage 4 — confirm_step1_and_trigger_step2 calls crud_personalized_food.update_confirmed_fields with swallow-log policy`
- **Update** `docs/technical/dish_analysis/personalized_food_index.md`:
  - Flip `- [ ] Stage 4 (Phase 1.2): update_confirmed_fields called from confirm_step1_and_trigger_step2` to `- [x]` with a one-line link back to `user_customization.md`.

#### API Documentation (`docs/api_doc/`)

No changes needed — Stage 4 does not change the request / response contract of any endpoint. The project does not yet ship a `docs/api_doc/` tree.

#### To Delete

None.

#### To Update

- `docs/abstract/dish_analysis/user_customization.md` — one-sentence personalization note.
- `docs/technical/dish_analysis/user_customization.md` — pipeline diagram extension, new Personalization Enrichment sub-section, Component Checklist row.
- `docs/technical/dish_analysis/personalized_food_index.md` — flip Stage 4 checklist row.

#### To Add New

None.

---

### Chrome Claude Extension Execution

**Included this stage.** Spec at `docs/chrome_test/260418_2337_stage4_phase1_2_confirm_enriches_personalization.md` (10 tests, 5 desktop + 5 mobile). Covers:

1. Happy path — confirm enriches the row (DB assertion).
2. Row missing (graceful degrade) — confirm returns 200, no implicit insert, WARN logged.
3. Subsequent upload retrieves the enriched row as its reference.
4. Double-confirm → 409, no re-invocation of `update_confirmed_fields`.
5. Cross-user isolation — beta's confirm does not touch alpha's row.

Scope caveats:
- The API response doesn't surface `confirmed_tokens` / `confirmed_portions`, so authoritative checks rely on direct SQL. A dev-only debug field on `GET /api/item/{id}` is suggested in the spec's "good to have" proposals.
- Test 2 requires the operator to DELETE the personalization row between upload and confirm — timing-sensitive.
- Placeholder usernames (no `docs/technical/testing_context.md` in repo).

Execution flow: `feature-implement-full` invokes `chrome-test-execute` after Stage 4 lands.

#### To Delete

None.

#### To Update

None.

#### To Add New

- `docs/chrome_test/260418_2337_stage4_phase1_2_confirm_enriches_personalization.md` (already written by `chrome-test-generate` in Step 1.6).

---

## Dependencies

- **Stage 0** — `personalized_food_descriptions` schema; `crud_personalized_food.update_confirmed_fields`; `personalized_food_index.tokenize`. All consumed verbatim.
- **Stage 2** — the producer of the row this stage updates. When Stage 2 graceful-degrades and no row exists, Stage 4 logs and moves on (does not create one implicitly).
- **Existing confirm pipeline** — `confirm_step1_atomic`, `trigger_step2_analysis_background`. Unchanged; Stage 4 inserts between them.
- **No new external libraries.**

---

## Resolved Decisions

- **Enrichment failure policy — swallow + log WARN; still schedule Phase 2 and return 200** (confirmed with user 2026-04-18). Applies to both `None` returns (row missing) and exceptions (DB error). Rationale: the user's primary intent (confirm + Phase 2) has already succeeded at the atomic-CRUD layer; a peripheral table error should not bounce them to an error card. Stage 6 (Phase 2.2) unions `tokens` + `confirmed_tokens` at the query side, so missing `confirmed_tokens` degrades retrieval signal rather than breaking it.
- **Call ordering — after `confirm_step1_atomic` returns `"confirmed"`, before `background_tasks.add_task(...)`** (confirmed with user 2026-04-18). Keeps all state mutations on the synchronous path before background dispatch. Functionally equivalent to placing after the `add_task` call (FastAPI background tasks don't start until after the response), but the read-rule "all mutations before dispatch" makes ordering audits trivial.
- **Row-missing behavior — do NOT create an implicit row** (decision recorded by the planner). A row inserted here would have null `description` / `tokens` (Stage 2 is the sole producer of those), only the confirmed columns populated. That partial state violates the Stage 0 invariant that `tokens` is the BM25 corpus document — Stage 0's `search_for_user` filters out rows with empty tokens anyway, so the implicit row buys nothing. Reopening this decision would require Stage 2 and Stage 4 to share a row-creation path; out of scope.
- **`confirmed_portions` formula — `sum(c.number_of_servings for c in components)`** (per issue spec). The dish-level "portion count" in this project is defined as the sum of per-component serving counts; e.g. "1.0 burger + 1.5 cups of fries" → `2.5`. Stage 6 uses this as a rough total-portion signal; semantic interpretation is Stage 6's concern.
- **`confirmed_tokens` source — `tokenize(selected_dish_name)`, NOT the components** (per issue spec). The confirmed tokens are the dish-name-level identity string ("Hainanese Chicken Rice" → `["hainanese", "chicken", "rice"]`). Component-name tokens could in theory add recall, but they conflate dish-name identity with component-level ingredients — a design question deferred to future stages.

## Open Questions

None — all decisions resolved 2026-04-18. Ready for implementation.
