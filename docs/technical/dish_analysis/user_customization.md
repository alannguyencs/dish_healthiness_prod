# User Customization — Technical Design

[< Prev: Component Identification](./component_identification.md) | [Parent](./index.md) | [Next: Nutritional Analysis >](./nutritional_analysis.md)

> **Note:** Stage 8 (Phase 2.4) adds a symmetric "one Edit toggle" pattern on the Step 2 results view via `POST /api/item/{record_id}/correction`. The UX mirrors this Step 1 editor's single-Confirm flow. See [nutritional_analysis.md § Phase 2.4](./nutritional_analysis.md#phase-24--user-review--correction-stage-8). Stage 10 extends the Step 2 card with a second, parallel correction path — see [§ Phase 2.4 — AI Assistant Edit (Stage 10)](#phase-24--ai-assistant-edit-stage-10) below.

## Related Docs
- Abstract: [abstract/dish_analysis/user_customization.md](../../abstract/dish_analysis/user_customization.md)

## Architecture

Customization is a fully client-side edit over the Phase 1 JSON. `Step1ComponentEditor.jsx` owns local state for the user's working copy; nothing is written to the server until the user clicks **Confirm**, which sends a single `POST /api/item/{id}/confirm-step1` call. That endpoint does an optimistic DB write of the user's corrections and then hands off to Phase 2 via a background task.

```
+-------------------------------------------------------+
|   React SPA                                           |
|                                                       |
|  Step1ComponentEditor.jsx                             |
|   ├── DishNameSelector.jsx                            |
|   ├── ComponentListItem.jsx (× AI components)         |
|   ├── ComponentListItem.jsx (× manual components)     |
|   └── AddComponentForm.jsx                            |
|                                                       |
|  local state (see "Data Model" below)                 |
+-------------------------------------------------------+
              │  click "Confirm and Analyze Nutrition"
              ▼
+-------------------------------------------------------+
|   FastAPI — /api/item/{id}/confirm-step1              |
|                                                       |
|   confirm_step1_and_trigger_step2()                   |
|    ├── auth + ownership checks                        |
|    ├── validate result_gemini.step == 1               |
|    ├── optimistic write: step1_confirmed=true,        |
|    │     confirmed_dish_name, confirmed_components    |
|    └── BackgroundTasks → trigger_step2_analysis...    |
+-------------------------------------------------------+
              │
              ▼
        Step 2 pipeline (see Nutritional Analysis)
```

## Data Model

### `Step1ConfirmationRequest` — request body

Defined in `backend/src/api/item_schemas.py`:

| Field | Type | Constraints |
|-------|------|-------------|
| `selected_dish_name` | `str` | non-empty |
| `components` | `List[ComponentConfirmation]` | min_length=1 |

### `ComponentConfirmation`

| Field | Type | Constraints |
|-------|------|-------------|
| `component_name` | `str` | required |
| `selected_serving_size` | `str` | required |
| `number_of_servings` | `float` | 0.01 ≤ x ≤ 10.0 |

### Local React state (inside `Step1ComponentEditor`)

| State | Shape | Purpose |
|-------|-------|---------|
| `selectedDishName` | `str` | Highlighted AI prediction |
| `customDishName` | `str` | Free-text override buffer |
| `useCustomDish` | `bool` | Toggle — when `true`, `customDishName` wins |
| `showAllDishPredictions` | `bool` | Expand/collapse predictions past top 1 |
| `componentSelections` | `Dict[component_name, {enabled, selected_serving_size, number_of_servings, serving_size_options}]` | Per-AI-component edit state |
| `manualComponents` | `List[{id, component_name, selected_serving_size, number_of_servings}]` | User-added components not in `step1_data.components` |
| `showAddComponent` + `newComponent*` | form state | "Add Custom Component" drawer |

### `result_gemini` after confirm (server-side)

The endpoint **mutates** `result_gemini` in place, adding three fields (no schema change to the JSON blob's structural shape):

```json
{
  "step": 1,
  "step1_data": { ... unchanged ... },
  "step1_confirmed": true,
  "confirmed_dish_name": "<user value>",
  "confirmed_components": [ { component_name, selected_serving_size, number_of_servings }, ... ],
  "step2_data": null,
  "iterations": [ ... unchanged ... ],
  "current_iteration": 1
}
```

The Phase 2 background task will later overwrite the same blob with `step = 2`, `step2_data`, and the iteration's metadata fields. See [Nutritional Analysis](./nutritional_analysis.md).

## Pipeline

```
ItemV2.jsx renders <Step1ComponentEditor step1Data={...}
                                         confirmedData={null on first load}
                                         onConfirm={handleStep1Confirmation}/>
  │
  ▼
useState initializers seed working state from step1_data (+ confirmedData on re-entry)
  │
  ├── selectedDishName = confirmedData?.selected_dish_name or dish_predictions[0].name
  │
  ├── componentSelections[name] = {
  │     enabled: true if confirmedData has this name (else: !confirmedData),
  │     selected_serving_size: confirmed value || step1_data.serving_sizes[0],
  │     number_of_servings:    confirmed value || step1_data.predicted_servings,
  │     serving_size_options:  step1_data.serving_sizes }
  │
  └── manualComponents = confirmedData.components \ step1_data.components
  │
  ▼
User interactions mutate state via handlers:
  handleComponentToggle(name)
  handleComponentServingSizeChange(name, size)
  handleComponentServingsChange(name, count) → parseFloat, fallback 0.1
  handleAddManualComponent()       → validate non-empty name + size
  handleManualServingSizeChange / handleManualServingsChange / handleRemoveManualComponent
  setSelectedDishName / setCustomDishName / setUseCustomDish
  │
  ▼
click "Confirm and Analyze Nutrition"
  │
  ▼
handleConfirm()
  ├── finalDishName = useCustomDish ? customDishName : selectedDishName
  ├── guard: finalDishName non-empty else alert()
  ├── enabled = Object.entries(componentSelections).filter(d.enabled)
  ├── payload.components = [...enabled, ...manualComponents]
  ├── guard: payload.components.length > 0 else alert()
  └── onConfirm({ selected_dish_name, components })
  │
  ▼
ItemV2.handleStep1Confirmation(confirmationData)
  ├── setConfirmedStep1Data(confirmationData)         ← optimistic UI
  ├── apiService.confirmStep1(recordId, confirmationData)
  ├── setPollingStep2(true); startPolling()
  └── loadItem()                                      ← refresh state
  │
  ▼
POST /api/item/{record_id}/confirm-step1
  │
  ▼
api/item.py: confirm_step1_and_trigger_step2()
  │
  ├── authenticate_user_from_request()              → 401
  ├── get_dish_image_query_by_id(record_id)         → 404 if missing / wrong user
  ├── require result_gemini && step == 1            → 400 "Step 1 not complete"
  ├── require image_url && file exists on disk      → 400 / 404
  │
  ▼
Optimistic update:
  result_gemini = result_gemini.copy()
  result_gemini.step1_confirmed = True
  result_gemini.confirmed_dish_name = confirmation.selected_dish_name
  result_gemini.confirmed_components = [c.model_dump() for c in confirmation.components]
update_dish_image_query_results(record_id, None, result_gemini)
  │
  ▼
Stage 4 enrichment (fire-and-forget; swallow-log on None/exception):
  confirmed_portions = sum(c.number_of_servings for c in confirmation.components)
  confirmed_tokens   = personalized_food_index.tokenize(selected_dish_name)
  crud_personalized_food.update_confirmed_fields(
      query_id=record_id,
      confirmed_dish_name=selected_dish_name,
      confirmed_portions=confirmed_portions,
      confirmed_tokens=confirmed_tokens)
  │
  ▼
BackgroundTasks.add_task(trigger_step2_analysis_background,
                         record_id, image_path,
                         confirmation.selected_dish_name,
                         components_data)
  │                                                  │
  │                                                  └──> Nutritional Analysis
  ▼
JSON {success, record_id, confirmed_dish_name, step2_in_progress:true}
  │
  ▼
Frontend continues polling for step2_data (see Phase 2 page)
```

## Algorithms

### Dish-name override

- `selectedDishName` holds the predicted choice; the custom path is kept in `customDishName` without overwriting the prediction.
- `useCustomDish` toggles which value wins at submit time. Both buffers persist when toggling so the user can flip between modes without losing work.

### Component state reconciliation on re-entry

When the editor is reopened after a prior confirmation (e.g. the user toggled from Step 2 view back to Step 1 via the step tabs on `ItemV2`), `confirmedData` is non-null. The initializer:

1. For every AI component, sets `enabled=true` iff that name exists in `confirmedData.components`; otherwise keeps it unchecked (the user previously unchecked it).
2. For every `confirmedData.components` entry whose name does **not** exist in `step1_data.components`, emits a `manualComponents` entry with a synthetic `id = Date.now() + i`.

### Validation on confirm

- `finalDishName.trim() === ""` → `alert("Please select or enter a dish name")`, abort.
- `allComponents.length === 0` → `alert("Please select at least one component")`, abort.
- `number_of_servings`: `parseFloat(input) || 0.1` inside the change handler clamps to a non-negative floor. Backend Pydantic re-validates to `[0.01, 10.0]` and rejects out-of-range values as 422.

### Ownership & state guards on the backend

The confirm endpoint does four independent checks before the optimistic write; any failure aborts without modifying the DB:

1. Auth present.
2. Record exists and `user_id == current_user.id` (returns 404 for other users' records to avoid existence leak).
3. `result_gemini` non-null and `result_gemini.step == 1`.
4. `image_url` non-null and the file resolves on disk under `IMAGE_DIR`.

### Personalization Enrichment (Stage 4)

After `confirm_step1_atomic` returns `"confirmed"`, the endpoint enriches the per-user personalization row by calling `crud_personalized_food.update_confirmed_fields` with three derived values:

- `confirmed_dish_name` — the user's selected dish name (same string committed onto `DishImageQuery.result_gemini.confirmed_dish_name`).
- `confirmed_portions` — `sum(c.number_of_servings for c in confirmation.components)`. A dish-level total-portion scalar for Stage 6 (Phase 2.2) retrieval; its semantic interpretation is that stage's concern.
- `confirmed_tokens` — `personalized_food_index.tokenize(confirmed_dish_name)`. Stage 6 unions this with the caption-side `tokens` at the query side, so user-verified dish names influence retrieval going forward.

**Failure policy: swallow + log WARN.** The call is wrapped in a broad `try/except` with two WARN paths:

- `update_confirmed_fields` returns `None` (no row for `query_id`) — Phase 1.1.1 graceful-degraded or the row was manually removed. Logged with the `query_id` so operators can correlate.
- Any exception (DB error, etc.) — caught and logged. Phase 2 scheduling proceeds.

Rationale: the atomic `confirm_step1_atomic` commit onto `DishImageQuery` has already succeeded by this point — the user's primary intent landed. Enrichment is fire-and-forget correctness for future uploads. Stage 6 retrieval degrades cleanly without `confirmed_tokens` (it still has `tokens`), so a transient enrichment failure weakens the signal rather than breaking retrieval. See [Personalized Food Index](./personalized_food_index.md) for the downstream consumer.

**Ordering.** The enrichment block runs **after** `confirm_step1_atomic(...) == "confirmed"` and **before** `background_tasks.add_task(trigger_step2_analysis_background, ...)`. FastAPI defers the background task until after the response, so the ordering is not semantically strict; it keeps the invariant "all state mutations happen before dispatch" as a clean read-rule for future maintainers.

**Not called** on `"not_found"` / `"no_step1"` / `"duplicate"` outcomes — the duplicate case in particular would otherwise stomp on the first-winner's committed values.

## Backend — API Layer

| Method | Path | Auth | Request | Response | Status |
|--------|------|------|---------|----------|--------|
| POST | `/api/item/{record_id}/confirm-step1` | Cookie | `Step1ConfirmationRequest` | `{success, message, record_id, confirmed_dish_name, step2_in_progress:true}` | 200 / 400 / 401 / 404 |

The legacy `PATCH /api/item/{record_id}/metadata` endpoint is defined in the same router and writes `selected_dish / selected_serving_size / number_of_servings` into the current iteration's `metadata` dict. No frontend call site renders a UI that triggers it; it is kept for backwards compatibility only.

## Backend — Service Layer

- `api/item.py#confirm_step1_and_trigger_step2` — orchestrator. Performs the guards, optimistic write, and background-task scheduling.
- `api/item_tasks.py#trigger_step2_analysis_background` — documented on [Nutritional Analysis](./nutritional_analysis.md).

## Backend — CRUD Layer

- `get_dish_image_query_by_id(record_id)` — read-before-write.
- `update_dish_image_query_results(query_id, result_openai, result_gemini)` — persists the optimistic `step1_confirmed=true` + confirmed fields. Replaces `result_gemini` wholesale.
- `update_metadata(query_id, dish, serving, count)` — legacy, only reachable via the legacy PATCH route.
- `crud_personalized_food.update_confirmed_fields(query_id, *, confirmed_dish_name, confirmed_portions, confirmed_tokens)` — Stage 4 enrichment. Returns the updated row on success, `None` if the row does not exist for this `query_id`. Raises on DB errors (caught and logged at the endpoint).
- `personalized_food_index.tokenize(text) -> List[str]` — NFKD-fold + casefold + strip + split. Deterministic; same string always produces the same token list, so `confirmed_tokens` can be compared directly against the fast-caption `tokens`.

## Frontend — Pages & Routes

- `/item/:recordId` → `pages/ItemV2.jsx` — owns `confirmedStep1Data`, polling, and the Step1 ↔ Step2 tab toggle.

## Frontend — Components

All under `components/item/`:

- `Step1ComponentEditor.jsx` — the top-level editor. Composes the children below and owns the working state listed under **Data Model**.
- `DishNameSelector.jsx` — dropdown + "use custom" toggle + custom-name input. Consumes `dishPredictions`, `selectedDishName`, `customDishName`, `useCustomDish`, `showAllPredictions`.
- `ComponentListItem.jsx` — one row per component: checkbox, name, serving-size dropdown, servings `+/-` input, and a remove button when `isManual=true`.
- `AddComponentForm.jsx` — inline form for creating a manual component (name + serving size + count).
- `ItemHeader.jsx`, `ItemImage.jsx`, `ItemNavigation.jsx` — chrome around the editor.
- A "Serving Size Guide" link (`<Link to="/reference/serving-size">`) opens the public reference page in a new tab for users who need disambiguation.

## Frontend — Services & Hooks

- `services/api.js#confirmStep1(recordId, confirmationData)` — POST to `/api/item/{id}/confirm-step1`. The request shape matches `Step1ConfirmationRequest` exactly.
- `services/api.js#updateItemMetadata(recordId, metadata)` — exists but not wired to any UI in the current codebase.
- `services/api.js#reanalyzeItem(recordId)` — explicitly commented as legacy; no caller.

## External Integrations

None. This feature is entirely DB + React state.

## Constraints & Edge Cases

- Phase 1 must complete before confirm is allowed — the editor is not rendered otherwise, and the endpoint rejects requests where `step != 1`.
- Submitting twice in rapid succession is possible (no debounce on the server); the second call re-applies the optimistic write and schedules a second Phase 2 background task, which will race. In practice the frontend disables the button via `isConfirming`.
- `confirmation.components` must have `min_length=1`; an empty list is rejected by Pydantic as 422, matching the client-side alert.
- Number validation: client-side floor is `0.1`; server-side `[0.01, 10.0]`. A pathological client that skips the React UI could send `0.01` (valid) — but nothing below `0.1` can be produced by the editor.
- The confirm endpoint does **not** persist the user's edited serving-size options for AI components back into `step1_data` — only `confirmed_components` is stored. Re-entering the editor rebuilds state from `step1_data.serving_sizes` and overlays the user's prior choices from `confirmed_components`.
- `iterations[]` array is preserved but not grown by the confirm call — iteration bookkeeping is a legacy hook; in the current flow there is always exactly one iteration per record.
- If the image file referenced by `image_url` has been deleted off disk, confirm returns 404 and no background task is scheduled.
- `ItemV2.jsx` does not handle a failed `confirmStep1` transition cleanly — it `alert`s and un-sets `isConfirming`, but `confirmedStep1Data` has already been set optimistically, which can leave the UI in an inconsistent state until the next `loadItem()` succeeds.

## Component Checklist

- [x] `Step1ConfirmationRequest` + `ComponentConfirmation` Pydantic schemas
- [x] `POST /api/item/{record_id}/confirm-step1` — auth, ownership, state guards, optimistic write, background task schedule
- [x] `update_dish_image_query_results()` reused for the optimistic write
- [x] `Step1ComponentEditor.jsx` — local working state + confirm handler
- [x] `DishNameSelector.jsx`
- [x] `ComponentListItem.jsx`
- [x] `AddComponentForm.jsx`
- [x] `apiService.confirmStep1()`
- [x] `ItemV2.handleStep1Confirmation()` — optimistic UI + poll start + loadItem
- [x] Stage 4 — `confirm_step1_and_trigger_step2` calls `crud_personalized_food.update_confirmed_fields` with swallow-log failure policy
- [ ] Error-recovery path on `confirmStep1` failure (currently just `alert`)
- [ ] Server-side idempotency / debounce on repeated confirm submissions

## Phase 2.4 — AI Assistant Edit (Stage 10)

Stage 10 adds a second correction path on the Step 2 card beside Stage 8's Manual Edit: the user types a natural-language hint, the backend calls Gemini 2.5 Pro to revise the current Step 2 payload, and the revised numbers commit directly (no preview / Accept-Cancel). Persistence reuses the Stage 8 write path — `result_gemini.step2_corrected` on the query row + `personalized_food_descriptions.corrected_step2_data` via the dual-write helper.

### Data Model — `AiAssistantCorrectionRequest`

Defined in `backend/src/api/item_schemas.py`:

| Field | Type | Constraints |
|-------|------|-------------|
| `prompt` | `str` | `min_length=1`, `max_length=2000` |

### `result_gemini.step2_corrected` (AI-authored variant)

Identical to the Stage 8 Manual payload but adds one audit field:

| Field | Type | Description |
|-------|------|-------------|
| `ai_assistant_prompt` | `str` | The latest user hint that produced this revision. Overwritten on every AI revision (latest wins). Absent from Manual Edit payloads. |

### Pipeline

```
Step2Results.jsx button row (Manual Edit | AI Assistant Edit)
  │
  │ click "AI Assistant Edit"
  ▼
Step2AiAssistantPanel expands (textarea + Submit/Cancel)
  │
  │ user types hint, clicks Submit
  │ (both edit buttons disable; AI button shows "Revising…")
  ▼
ItemV2.handleAiAssistantCorrection(prompt)
  │
  │ apiService.saveAiAssistantCorrection(recordId, prompt)
  ▼
POST /api/item/{record_id}/ai-assistant-correction
  │
  ▼
api/item_correction.py#save_ai_assistant_correction
  ├── authenticate + ownership (404 on mismatch)
  ├── require result_gemini.step2_data (400 otherwise)
  ├── trim prompt; 422 if empty
  ├── revise_step2_with_hint(record_id, prompt) — Gemini 2.5 Pro
  ├── compose payload (macros + rationale + micronutrients + ai_assistant_prompt)
  ├── new_blob = dict(result_gemini); new_blob.step2_corrected = payload
  ├── update_dish_image_query_results(query_id, None, new_blob)
  └── _enrich_personalization_corrected_data(record_id, payload)   # dual-write
  │
  ▼
200 { success, record_id, step2_corrected }
  │
  ▼
Frontend reload() → card re-renders with revised numbers + "Corrected by you" badge
```

`revise_step2_with_hint` (in `backend/src/service/llm/step2_assistant.py`):

1. Load the record; read `result_gemini.step2_corrected` if present, else `step2_data` (current-effective-payload baseline).
2. Trim the baseline to prompt-relevant fields only (drops `model`, `price_usd`, `analysis_time`, `input_token`, `output_token`, `ai_assistant_prompt`).
3. Render `backend/resources/step2_assistant_correction.md` with `{{BASELINE_JSON}}` and `{{USER_HINT}}` substituted.
4. Call `analyze_step2_nutritional_analysis_async(image_path, prompt, "gemini-2.5-pro")` with the query image attached (single-image, no reference-image B).
5. Return the raw `Step2NutritionalAnalysis` dict; the endpoint composes the `step2_corrected` payload.

### Backend — API Layer (Stage 10 addition)

| Method | Path | Auth | Request | Response | Status |
|--------|------|------|---------|----------|--------|
| POST | `/api/item/{record_id}/ai-assistant-correction` | Cookie | `AiAssistantCorrectionRequest` | `{success, record_id, step2_corrected}` | 200 / 400 / 401 / 404 / 422 / 502 |

### Frontend — Components (Stage 10 additions)

- `Step2Results.jsx` — header now renders two buttons (`Manual Edit`, `AI Assistant Edit`). Manages `aiHintOpen` / `aiHint` local state and passes them to the new panel.
- `Step2AiAssistantPanel.jsx` (NEW) — inline textarea + Submit/Cancel inside a violet-accented card. Disabled while `assisting=true`; Submit guard: `value.trim().length > 0`.
- `ItemV2.jsx` — owns `aiAssisting` state and `handleAiAssistantCorrection(prompt)`; passes both through to `<Step2Results/>`.
- `services/api.js#saveAiAssistantCorrection(recordId, prompt)` — mirrors `saveStep2Correction`.

### Constraints & Edge Cases (Stage 10)

- **Stacked edits.** Baseline is the current effective payload (`step2_corrected` → `step2_data`), so a Manual edit followed by an AI Assistant edit refines the manual numbers rather than reverting to the original AI proposal.
- **Image required.** `revise_step2_with_hint` raises `FileNotFoundError` if the query image is no longer on disk; the endpoint catches and bubbles a 502.
- **Audit trail.** Only the latest `ai_assistant_prompt` is stored. Earlier hints are lost — if a richer history is later needed, extend the payload with `ai_assistant_history: List[str]`.
- **Latency.** A single Gemini 2.5 Pro call with image + prompt typically completes in 6–10s; the UI shows "Revising…" the whole time and both edit buttons are disabled to prevent double-submit.
- **Cross-stage invariant #7.** Phase 1 state (`step1_data`, `confirmed_*`) and the Phase 2.1 / 2.2 retrieval artifacts (`nutrition_db_matches`, `personalized_matches`) are **not** touched — only `step2_corrected` changes.

### Component Checklist (Stage 10)

- [x] `AiAssistantCorrectionRequest` Pydantic schema
- [x] `POST /api/item/{record_id}/ai-assistant-correction` — auth, ownership, state guard (`step2_data` required), empty-prompt guard, Gemini call, dual-write persistence
- [x] `backend/src/service/llm/step2_assistant.py#revise_step2_with_hint` — baseline selection + prompt render + Gemini call
- [x] `backend/resources/step2_assistant_correction.md` — revision prompt template
- [x] `Step2Results.jsx` — dual-button header + AI hint panel integration
- [x] `Step2AiAssistantPanel.jsx` — textarea + Submit/Cancel
- [x] `apiService.saveAiAssistantCorrection()`
- [x] `ItemV2.handleAiAssistantCorrection()` — error alert + reload on success

---

[< Prev: Component Identification](./component_identification.md) | [Parent](./index.md) | [Next: Nutritional Analysis >](./nutritional_analysis.md)
