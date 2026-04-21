# Stage 8 — Phase 2.4: Enhanced Review UI + Correction Endpoint

**Feature**: Turn the Step 2 results view into an editable review surface. A single top-level **Edit** toggle on `Step2Results.jsx` flips healthiness score + rationale + five macros + micronutrient chips into inputs; Save posts to a new `POST /api/item/{record_id}/correction` endpoint that writes `result_gemini.step2_corrected` (preserving `step2_data` for audit) AND calls `crud_personalized_food.update_corrected_step2_data(query_id, payload)` so future Phase 2.2 retrieval surfaces user-verified nutrients. Three new read-only panels sit below the editable card: **ReasoningPanel** (expandable, renders the seven `reasoning_*` fields), **Top5DbMatches** (chip row with confidence badges), **PersonalizationMatches** (one card per match with thumbnail + description + similarity score + prior nutrients). Closes out the end-to-end workflow by making the pipeline's evidence visible to the user and letting their corrections feed back into the personalization corpus.
**Plan Created:** 2026-04-19
**Status:** Plan
**Reference**:
- [Issues — 260415, Stage 8](../issues/260415.md)
- [Discussion — Food DB investigation & end-to-end redesign](../discussion/260418_food_db.md)
- [Plan — Stage 0 Personalized Food Index](./260418_stage0_personalized_food_index.md) (foundation; `corrected_step2_data` column + `update_corrected_step2_data` CRUD)
- [Plan — Stage 5 Phase 2.1](./260419_stage5_phase2_1_nutrition_db_lookup.md) (writes `nutrition_db_matches` that Top5DbMatches reads)
- [Plan — Stage 6 Phase 2.2](./260419_stage6_phase2_2_personalization_lookup.md) (writes `personalized_matches` that PersonalizationMatches reads)
- [Plan — Stage 7 Phase 2.3](./260419_stage7_phase2_3_gemini_threshold_gated_blocks.md) (adds `reasoning_*` that ReasoningPanel renders)
- [Plan — Stage 4 Phase 1.2](./260418_stage4_phase1_2_confirm_enriches_personalization.md) (swallow-log dual-write pattern; reused here)
- [Abstract — Nutritional Analysis](../abstract/dish_analysis/nutritional_analysis.md)
- [Technical — Nutritional Analysis](../technical/dish_analysis/nutritional_analysis.md)
- [Technical — Personalized Food Index](../technical/dish_analysis/personalized_food_index.md)
- [Technical — User Customization](../technical/dish_analysis/user_customization.md) (precedent for "one Edit toggle" UX)
- [Chrome Test Spec — 260419_1113](../chrome_test/260419_1113_stage8_phase2_4_review_ui_and_correction.md)

---

## Problem Statement

1. Today the Step 2 view is read-only. When the AI gets a dish wrong (over-estimated fat, missed a micronutrient, picked the wrong healthiness tier) the user has no way to fix it without re-uploading. The personalization corpus (Stage 0's `personalized_food_descriptions`) has a `corrected_step2_data` JSONB column waiting for a writer — Stage 4 populated the dish-name-level fields, but no stage writes the macro corrections.
2. Stage 7 persists seven `reasoning_*` strings and two threshold-gated reference blocks (`nutrition_db_matches`, `personalized_matches`) but none of those are visible to the user. The evidence the AI cited is opaque — users can't tell whether calories came from the database, a prior upload, or "LLM-only".
3. The end-to-end discussion specifies the user-facing Step 2 view has three read-only panels below an editable core card. Stage 6's `personalized_matches` entries carry both `prior_step2_data` and `corrected_step2_data`; the UI should show the corrected value when the user has previously corrected that row — making the personalization loop closed: user correction → next similar upload surfaces the correction → AI gets user-verified numbers as Phase 2.3 evidence.
4. The correction endpoint is the dual-write: `result_gemini.step2_corrected` on the main record + `personalized_food_descriptions.corrected_step2_data` via the existing Stage 0 CRUD. Stage 4's swallow-log pattern is the precedent — the user's primary intent (save correction) succeeds even if the personalization-row enrichment fails.
5. Frontend line-count cap (300 lines per file) constrains component composition. Today's `Step2Results.jsx` is ~170 lines; Stage 8 adds an Edit toggle + edit-mode renderer that pushes it well over the cap. Split is required.

---

## Proposed Solution

### Backend

- **`POST /api/item/{record_id}/correction`** — new endpoint on `backend/src/api/item.py`. Owns:
  - Auth + ownership check (same as the existing item endpoints).
  - Validate against `Step2CorrectionRequest` Pydantic schema (field shape below).
  - Re-read `DishImageQuery.result_gemini`, set `step2_corrected = payload.model_dump()`, preserve `step2_data` untouched, write back via `update_dish_image_query_results`.
  - Try/except wrap around `crud_personalized_food.update_corrected_step2_data(query_id, payload.model_dump())`. Swallow + log WARN if the row is missing or the DB errors — return 200 regardless.
  - Return `{ success: True, record_id, step2_corrected: <payload> }`.

- **`Step2CorrectionRequest` schema** in `backend/src/api/item_schemas.py`:
  ```python
  class Step2CorrectionRequest(BaseModel):
      healthiness_score: int = Field(..., ge=0, le=100)
      healthiness_score_rationale: str = Field(..., description="User-corrected rationale")
      calories_kcal: float = Field(..., ge=0)
      fiber_g: float = Field(..., ge=0)
      carbs_g: float = Field(..., ge=0)
      protein_g: float = Field(..., ge=0)
      fat_g: float = Field(..., ge=0)
      micronutrients: List[str] = Field(default_factory=list)
  ```
  Field names align with the existing `Step2NutritionalAnalysis` schema (confirmed with user 2026-04-19) — minimum drift on the frontend side.

- **CRUD** — no new CRUD. Stage 0 already shipped `crud_personalized_food.update_corrected_step2_data(query_id, payload)`; Stage 8 is the first caller.

### Frontend

- **`Step2Results.jsx`** — add a single top-level Edit toggle. When in edit mode, flip the fields to inputs; Save + Cancel buttons visible. Save calls a new `apiService.saveStep2Correction`; Cancel resets local state to server state. Component file is already near the 300-line cap; extract the edit-mode renderer into a sibling `Step2ResultsEditForm.jsx` and the view-mode renderer stays in `Step2Results.jsx`.

- **`Step2ResultsEditForm.jsx`** (new) — owns the controlled inputs. Props: `initialValues, onSave, onCancel`. Local state mirrors the seven editable fields. On Save: call `onSave(payload)` with the user's values; the parent manages the in-flight flag + server round-trip.

- **`ReasoningPanel.jsx`** (new) — always-visible, expandable panel below the edit card. Renders the seven `reasoning_*` strings with labels (Sources / Calories / Fiber / Carbs / Protein / Fat / Micronutrients). Empty-string entries render as "No rationale provided." — not hidden entirely; the user should see every metric has been accounted for.

- **`Top5DbMatches.jsx`** (new) — reads `result_gemini.nutrition_db_matches.nutrition_matches[0..4]`. Renders a chip row: `{matched_food_name}` + `{confidence_score}%` badge. Color-coded by confidence band (≥ 85 green, 70-84 yellow, < 70 gray). Hidden when `nutrition_matches` is empty (no DB coverage at all) — this preserves the "always-visible reasoning, optionally-visible evidence" split.

- **`PersonalizationMatches.jsx`** (new) — reads `result_gemini.personalized_matches[0..K]`. One card per match: thumbnail (from `image_url`) + description + similarity badge (`{similarity_score × 100}%`) + macros table (prefers `corrected_step2_data` over `prior_step2_data` when present, with a "User-verified" badge). Hidden when `personalized_matches` is empty.

- **`ItemV2.jsx`** — compose the three new panels below `Step2Results`. Refresh `result_gemini.step2_corrected` after save (in-place state update + background `loadItem()` for belt-and-suspenders).

- **`services/api.js::saveStep2Correction(recordId, payload)`** — POST to `/api/item/{record_id}/correction`. Standard pattern, matches the existing `confirmStep1` helper.

### Display precedence

When both `step2_data` and `step2_corrected` are present on `result_gemini`, the view-mode renderer on `Step2Results.jsx` shows **`step2_corrected`** values. The original `step2_data` is preserved on the record but not rendered — it's audit-only. A "Corrected by you" badge on the view-mode card signals the override visually.

A key design call: `reasoning_*` fields stay sourced from `step2_data` (the AI's rationale for its original numbers), not re-derived from the user's correction. The user's override replaces the numeric fields but the audit trail for the AI's reasoning stays intact. If the user's corrected values diverge noticeably from the AI's values, the ReasoningPanel still shows what the AI thought — which is useful for UX: "here's why the AI got 687 kcal, you overrode to 450".

### Dual-write failure policy (confirmed with user 2026-04-19)

```
save_step2_correction(record_id, body):
  - guard auth + ownership + request body (422 on invalid)
  - re-read record.result_gemini
  - write step2_corrected onto result_gemini, preserve step2_data
  - update_dish_image_query_results(record_id, None, result_gemini)
  - try:
        crud_personalized_food.update_corrected_step2_data(record_id, body.model_dump())
        if updated is None:
            logger.warning("Stage 8 enrichment skipped: no personalization row for query_id=%s", record_id)
    except Exception as exc:
        logger.warning("Stage 8 enrichment failed for query_id=%s: %s", record_id, exc)
  - return 200 with {success, record_id, step2_corrected: body.model_dump()}
```

Same shape as Stage 4's `_enrich_personalization_row` helper. Extract a sibling helper `_enrich_personalization_corrected_data(record_id, payload)` for symmetry + cyclomatic-complexity headroom.

---

## Current Implementation Analysis

### What Exists (keep as-is)

| Component | File | Status |
|-----------|------|--------|
| `crud_personalized_food.update_corrected_step2_data(query_id, payload)` | `backend/src/crud/crud_personalized_food.py` | Keep — Stage 0 CRUD; Stage 8 is the first caller. |
| `Step2NutritionalAnalysis` schema | `backend/src/service/llm/models.py` | Keep — the correction request does NOT re-use it (schema has `default_factory=list` for micronutrients which conflicts with the strict user-override shape). Stage 8's `Step2CorrectionRequest` is a sibling. |
| `result_gemini.step2_data` / `.step2_corrected` on `DishImageQuery` | JSON blob | Keep — Stage 8 writes `step2_corrected` alongside the existing key. |
| `result_gemini.nutrition_db_matches` (Stage 5) | JSON blob | Keep — Top5DbMatches reads. |
| `result_gemini.personalized_matches` (Stage 6) | JSON blob | Keep — PersonalizationMatches reads. |
| `result_gemini.step2_data.reasoning_*` (Stage 7) | JSON blob | Keep — ReasoningPanel reads. |
| Auth + ownership guards on `item.py` routes | `authenticate_user_from_request`, ownership check | Keep — Stage 8 follows the same pattern. |
| `ItemV2.jsx` polling + loadItem | frontend | Keep — Stage 8 adds a post-save refresh via the existing `loadItem()`. |
| `Step1ComponentEditor.jsx`'s "one Confirm" UX pattern | frontend | Keep — the "one Edit toggle" pattern on Stage 8 is symmetric. |

### What Changes

| Component | Current | Proposed |
|-----------|---------|----------|
| `backend/src/api/item.py` | No correction endpoint. | Add `POST /{record_id}/correction` → `save_step2_correction` + `_enrich_personalization_corrected_data` private helper. |
| `backend/src/api/item_schemas.py` | Only `Step1ConfirmationRequest` + `ComponentConfirmation`. | Add `Step2CorrectionRequest` with the 8 editable fields. |
| `frontend/src/components/item/Step2Results.jsx` | ~170-line read-only view. | Compose a new `Step2ResultsEditForm.jsx` when in edit mode; view mode renders `step2_corrected` over `step2_data` when present; shows a "Corrected by you" badge when overriding. |
| `frontend/src/components/item/Step2ResultsEditForm.jsx` | Does not exist. | New; owns controlled inputs + Save/Cancel. Parent passes `initialValues, onSave, onCancel, saving`. |
| `frontend/src/components/item/ReasoningPanel.jsx` | Does not exist. | New; expandable panel below the edit card; renders 7 `reasoning_*` fields with section labels. |
| `frontend/src/components/item/Top5DbMatches.jsx` | Does not exist. | New; chip row showing top-5 DB matches with confidence badges. Hidden on empty. |
| `frontend/src/components/item/PersonalizationMatches.jsx` | Does not exist. | New; one card per match; prefers `corrected_step2_data` over `prior_step2_data`. Hidden on empty. |
| `frontend/src/pages/ItemV2.jsx` | Composes `Step2Results`. | Adds the three new panels below; wires `handleStep2Correction` to `saveStep2Correction` + in-place state update + background `loadItem()`. |
| `frontend/src/services/api.js` | Has `confirmStep1`, `retryStep1`, `retryStep2`, `getItem`. | Adds `saveStep2Correction(recordId, payload)`. |
| `docs/abstract/dish_analysis/nutritional_analysis.md` | Abstract describes read-only results + the silent DB/personalization paragraphs (Stage 7 flipped to active). | Adds a new "Reviewing and correcting the analysis" sub-section. |
| `docs/technical/dish_analysis/nutritional_analysis.md` | Has Phase 2.1 / 2.2 / 2.3 sub-sections. | Adds "Phase 2.4 — User Review & Correction (Stage 8)" sub-section; extends Data Model with `step2_corrected` + `Step2CorrectionRequest`. |
| `docs/technical/dish_analysis/personalized_food_index.md` | Stage 8 checklist row is `[ ]`. | Flip to `[x]`; note `corrected_step2_data` is now actively populated. |

---

## Implementation Plan

### Key Workflow

```
ItemV2.jsx renders:
  <Step2Results step2Data={activeData} onEditSave={handleStep2Correction} saving={saving} />
  <ReasoningPanel step2Data={step2Data} />   # reasoning_* from the AI's original analysis
  <Top5DbMatches matches={nutrition_db_matches?.nutrition_matches} />
  <PersonalizationMatches matches={personalized_matches} />

Where:
  activeData = step2_corrected || step2_data (corrected wins)
  step2Data  = step2_data                      (reasoning_* always from the AI)

User clicks Edit:
  Step2Results flips to edit mode (Step2ResultsEditForm.jsx)
  local state seeded from activeData

User clicks Save:
  handleStep2Correction(payload)
    ├── setSaving(true)
    ├── await apiService.saveStep2Correction(recordId, payload)
    ├── optimistic: setItemData(prev => ({ ...prev, result_gemini: { ..., step2_corrected: payload } }))
    ├── loadItem()  # background refresh for belt-and-suspenders
    └── setSaving(false)

Backend POST /api/item/{record_id}/correction:
  save_step2_correction(record_id, request, confirmation):
    ├── auth + ownership (401 / 404)
    ├── Pydantic validates Step2CorrectionRequest (422 on out-of-range)
    ├── record = get_dish_image_query_by_id(record_id)
    ├── if not record or not record.result_gemini: 400 or 404
    ├── new_blob = record.result_gemini.copy()
    ├── new_blob["step2_corrected"] = request.model_dump()
    ├── update_dish_image_query_results(record_id, None, new_blob)
    ├── _enrich_personalization_corrected_data(record_id, request.model_dump())
    │     └── try: update_corrected_step2_data; except: log WARN
    └── return 200 { success, record_id, step2_corrected }
```

#### To Delete

None.

#### To Update

- `backend/src/api/item.py` — add route handler + module-private `_enrich_personalization_corrected_data` helper.
- `backend/src/api/item_schemas.py` — add `Step2CorrectionRequest`.
- `frontend/src/components/item/Step2Results.jsx` — add Edit toggle + compose edit-form component + render `step2_corrected` over `step2_data` when present.
- `frontend/src/pages/ItemV2.jsx` — compose the three new panels; wire `handleStep2Correction`.
- `frontend/src/services/api.js` — `saveStep2Correction` helper.

#### To Add New

- `frontend/src/components/item/Step2ResultsEditForm.jsx` — edit-mode renderer.
- `frontend/src/components/item/ReasoningPanel.jsx` — reasoning panel.
- `frontend/src/components/item/Top5DbMatches.jsx` — DB chip row.
- `frontend/src/components/item/PersonalizationMatches.jsx` — personalization cards.

---

### Database Schema

**No changes.** Stage 0 shipped the `personalized_food_descriptions.corrected_step2_data` JSONB column + the `update_corrected_step2_data` CRUD call; Stage 8 is the first caller. The main record's `step2_corrected` rides inside the existing `DishImageQuery.result_gemini` JSONB blob — no schema change.

#### To Delete

None.

#### To Update

None.

#### To Add New

None.

---

### CRUD

**No new CRUD.** Stage 8 re-uses:

- `update_dish_image_query_results(query_id, result_openai, result_gemini)` — writes `step2_corrected` to the main record.
- `crud_personalized_food.update_corrected_step2_data(query_id, payload)` — dual-write for the personalization row. Returns the updated ORM row on success, `None` if no row exists (Stage 8 logs and continues). Raises on DB errors (Stage 8 catches and logs).

#### To Delete

None.

#### To Update

None.

#### To Add New

None.

---

### Services

Stage 8 is a thin plumbing layer; no new service modules. The correction endpoint's logic lives inside `item.py` (parallel to `confirm_step1_and_trigger_step2`'s `_enrich_personalization_row` helper from Stage 4).

#### To Delete

None.

#### To Update

None.

#### To Add New

None.

---

### API Endpoints

#### `POST /api/item/{record_id}/correction`

| Field | Current | Proposed |
|---|---|---|
| Method | N/A | POST |
| Path | N/A | `/api/item/{record_id}/correction` |
| Auth | N/A | Cookie (authenticate_user_from_request) |
| Body | N/A | `Step2CorrectionRequest` — 8 fields, Pydantic-validated |
| Response | N/A | `{ success: bool, record_id: int, step2_corrected: Dict }` |
| Status | N/A | 200 / 401 / 404 / 422 |

**Side effects**:
1. `DishImageQuery.result_gemini.step2_corrected` is written (preserving `step2_data` and all other keys).
2. `personalized_food_descriptions.corrected_step2_data` is best-effort updated (swallow-log on failure).

#### To Delete

None.

#### To Update

None.

#### To Add New

- `POST /api/item/{record_id}/correction` on the existing `item` router.

---

### Frontend

**New components** (all under `frontend/src/components/item/`):

- **`Step2ResultsEditForm.jsx`** — ~150 lines. Props: `initialValues: { healthiness_score, healthiness_score_rationale, calories_kcal, fiber_g, carbs_g, protein_g, fat_g, micronutrients: [] }`, `onSave(payload)`, `onCancel()`, `saving: bool`. Local state per field. Micronutrient chip add/remove: input + Enter or "+Add" button; each chip has a × to remove. Save disabled while `saving===true`; Cancel always enabled; both reset local state via the parent. Uses `data-testid="step2-edit-form"` + `data-testid="step2-{field}-input"` for Chrome test stability.

- **`ReasoningPanel.jsx`** — ~80 lines. Always visible below the edit card. `<details>` / `<summary>` collapsible by default (open on first load? the spec is silent — recommend closed, matches progressive-disclosure convention). Section per `reasoning_*` field with short title + wrapped body text. Empty `""` renders as muted placeholder "No rationale provided".

- **`Top5DbMatches.jsx`** — ~80 lines. Reads `nutrition_db_matches.nutrition_matches`. Renders nothing when the list is empty or absent. Otherwise: section heading + chip row (up to 5 chips). Each chip: `{matched_food_name}` + confidence badge. Color bands: green ≥ 85, yellow 70-84, gray < 70. Optional: hover tooltip with `source` + `confidence_score`. `data-testid="top5-db-matches"`.

- **`PersonalizationMatches.jsx`** — ~120 lines. Reads `personalized_matches` (list). Renders nothing when empty. Otherwise: section heading + one card per match (up to 5). Card shape:
  - Thumbnail: `<img src={image_url}>` (use the same `/images/...` URL pattern the frontend already consumes for dish photos).
  - Description: `match.description` (one line, truncated).
  - Similarity badge: `{similarity_score × 100}%`.
  - Nutrients: prefer `corrected_step2_data` over `prior_step2_data`. When `corrected_step2_data` is present, add a "User-verified" badge (different color from the similarity badge).
  - Macro table: one row per macro (calories / fiber / carbs / protein / fat).

**Updated components:**

- **`Step2Results.jsx`** — ~180 lines after refactor. Split into:
  - Top bar: dish name + "Corrected by you" badge when `step2_corrected` present.
  - View mode (current read-only layout; reads from `activeData`).
  - Edit mode (delegates to `Step2ResultsEditForm`).
  - Edit toggle button in the top-right; only shown when not in edit mode.
  - `activeData = step2_corrected || step2_data` at the top of the component.
  - `data-testid="step2-edit-toggle"` on the toggle button.

- **`ItemV2.jsx`** — add three new panel imports + `handleStep2Correction` async handler. After panel composition:
  ```jsx
  <Step2Results step2Data={...} onEditSave={handleStep2Correction} saving={saving} />
  <ReasoningPanel step2Data={step2Data} />
  <Top5DbMatches matches={result_gemini?.nutrition_db_matches?.nutrition_matches} />
  <PersonalizationMatches matches={result_gemini?.personalized_matches} />
  ```
  Handler:
  ```js
  const handleStep2Correction = async (payload) => {
    setSaving(true);
    try {
      await apiService.saveStep2Correction(recordId, payload);
      setItemData(prev => ({
        ...prev,
        result_gemini: { ...prev.result_gemini, step2_corrected: payload },
      }));
      loadItem();  // belt-and-suspenders refresh
    } finally {
      setSaving(false);
    }
  };
  ```

- **`services/api.js`** — append `saveStep2Correction(recordId, payload)` calling `POST /api/item/{recordId}/correction`.

#### Line-count management

`Step2Results.jsx` (~170 today + Edit toggle + top bar) lands at ~200 lines post-refactor — under the cap. Edit form extracts to `Step2ResultsEditForm.jsx` (~150 lines). `ItemV2.jsx` is at the cap today; Stage 8 adds ~20 lines — flag during pre-commit and extract a `Step2ReviewPanels.jsx` wrapper if `ItemV2.jsx` crosses 300.

#### To Delete

None.

#### To Update

- `frontend/src/components/item/Step2Results.jsx` — add Edit toggle + render `step2_corrected` over `step2_data` when present; delegate edit mode to `Step2ResultsEditForm`.
- `frontend/src/pages/ItemV2.jsx` — compose the three new panels; wire `handleStep2Correction`.
- `frontend/src/services/api.js` — `saveStep2Correction`.

#### To Add New

- `frontend/src/components/item/Step2ResultsEditForm.jsx`
- `frontend/src/components/item/ReasoningPanel.jsx`
- `frontend/src/components/item/Top5DbMatches.jsx`
- `frontend/src/components/item/PersonalizationMatches.jsx`

---

### Testing

Test location: `backend/tests/` + `frontend/src/components/item/__tests__/`.

**Backend unit tests — correction endpoint (`backend/tests/test_item_correction.py` — NEW):**

- `test_returns_401_when_not_authenticated`.
- `test_returns_404_for_other_users_record`.
- `test_returns_404_when_record_missing`.
- `test_returns_422_when_calories_negative`.
- `test_returns_422_when_healthiness_score_out_of_range`.
- `test_happy_path_writes_step2_corrected_preserving_step2_data` — POST with valid payload; assert `result_gemini.step2_corrected` equals payload AND `result_gemini.step2_data` is unchanged.
- `test_happy_path_calls_update_corrected_step2_data` — assert `crud_personalized_food.update_corrected_step2_data` called with `(query_id, payload_dict)`.
- `test_personalization_row_missing_swallow_and_log_WARN` — `update_corrected_step2_data` returns None; endpoint still returns 200; `result_gemini.step2_corrected` landed; WARN log line emitted.
- `test_personalization_crud_exception_swallow_and_log_WARN` — `update_corrected_step2_data` raises; endpoint still returns 200; WARN log.
- `test_response_body_carries_step2_corrected_payload` — response JSON echoes the payload back.
- `test_saves_correction_does_not_destroy_other_result_gemini_keys` — pre-populate `nutrition_db_matches` + `personalized_matches`; after save, both keys still present on the record alongside `step2_corrected`.

**Frontend unit tests — new components (`frontend/src/components/item/__tests__/*.test.jsx`):**

- `Step2ResultsEditForm.test.jsx` — renders all 8 inputs; saving → Save disabled; Cancel calls `onCancel`; micronutrient chip add/remove; Save button packages the current values into a payload and calls `onSave`.
- `ReasoningPanel.test.jsx` — all 7 reasoning fields rendered; empty string → muted "No rationale provided"; click toggles expand/collapse.
- `Top5DbMatches.test.jsx` — empty matches → returns null; populated → chip row with confidence-band colors.
- `PersonalizationMatches.test.jsx` — empty → null; populated → one card per match; `corrected_step2_data` present → "User-verified" badge + corrected macros; `corrected_step2_data` null → prior macros + no badge.
- `Step2Results.test.jsx` — `step2_corrected` present → corrected values render + "Corrected by you" badge; Edit toggle → edit mode; Cancel returns to view with original state.

**Pre-commit loop** (mandatory):

1. `source venv/bin/activate && pre-commit run --all-files`.
2. Fix lint / line-count issues. Jest tests are a larger set this stage; expect ~30-60 s runtime.
3. Watch `Step2Results.jsx` + `ItemV2.jsx` line counts; extract if near 300.
4. Repeat until clean.

**Acceptance check from the issue's "done when":**

- Editing the Step 2 view writes both to `result_gemini.step2_corrected` AND to `personalized_food_descriptions.corrected_step2_data`. Chrome Test 1 Action 12-13 verifies both.
- A subsequent upload whose Phase 2.2 retrieves this row surfaces the corrected nutrients in the new PersonalizationMatches panel. Chrome Test 3 verifies.

#### To Delete

None.

#### To Update

None (existing backend tests are untouched).

#### To Add New

- `backend/tests/test_item_correction.py` — 10 endpoint tests.
- `frontend/src/components/item/__tests__/Step2ResultsEditForm.test.jsx`
- `frontend/src/components/item/__tests__/ReasoningPanel.test.jsx`
- `frontend/src/components/item/__tests__/Top5DbMatches.test.jsx`
- `frontend/src/components/item/__tests__/PersonalizationMatches.test.jsx`
- Extend `frontend/src/components/item/__tests__/Step2Results.test.jsx` — add corrected-values + Edit-toggle + Cancel tests.

---

### Documentation

#### Abstract (`docs/abstract/`)

- **Update** `docs/abstract/dish_analysis/nutritional_analysis.md` — add a new "Reviewing and correcting the analysis" sub-section:
  - User can click **Edit** on the Step 2 view and override the healthiness score, rationale, five macros, and micronutrients list.
  - Save persists both on the record (for this meal) and into the user's personalization history (so future similar dishes pick up the correction).
  - Cancel reverts without saving.
  - Three read-only reference panels are always visible: a short rationale per metric, the top-5 database matches the AI considered, and the user's prior similar dishes — so it's clear which sources drove the numbers.

- **Update** `docs/abstract/dish_analysis/index.md` — no structural change needed; the existing index row for Nutritional Analysis already implies this surface. Flag for review during implementation.

#### Technical (`docs/technical/`)

- **Update** `docs/technical/dish_analysis/nutritional_analysis.md`:
  - Add a **Phase 2.4 — User Review & Correction (Stage 8)** sub-section documenting:
    - The `Step2CorrectionRequest` schema.
    - The endpoint route + response shape.
    - The dual-write (`result_gemini.step2_corrected` + `personalized_food_descriptions.corrected_step2_data`).
    - The swallow-log failure policy for the personalization half.
    - Display precedence: `step2_corrected` wins over `step2_data`; `reasoning_*` stays sourced from `step2_data`.
  - Extend the Data Model section with the `step2_corrected` key shape (8 fields) and a note that it rides alongside `step2_data` on the same blob.
  - Extend the Pipeline diagram with the correction-path loop (user click → POST → dual write → future upload's PersonalizationMatches card carries the override).
  - Component Checklist additions — 1 new backend endpoint, 1 new backend schema, 4 new frontend components, 2 updated frontend files, 1 new frontend service method.

- **Update** `docs/technical/dish_analysis/personalized_food_index.md`:
  - Flip `[ ] Stage 8 (Phase 2.4)` row to `[x]` with a back-link to `nutritional_analysis.md § Phase 2.4`.
  - Note that `corrected_step2_data` is now actively populated by `save_step2_correction`; Stage 6's `lookup_personalization` surfaces it on the match shape already (no change).

- **Update** `docs/technical/dish_analysis/user_customization.md`:
  - One-sentence cross-reference: the "one Edit toggle" UX on Step 2 is symmetric with the Step 1 editor's "one Confirm" pattern.

#### API Documentation (`docs/api_doc/`)

No project-wide `docs/api_doc/` tree exists today. If one is added before Stage 8 lands, document `POST /api/item/{record_id}/correction` following whatever convention the tree adopts. For now, the technical doc update is the authoritative reference.

#### To Delete

None.

#### To Update

- `docs/abstract/dish_analysis/nutritional_analysis.md` — add the "Reviewing and correcting the analysis" sub-section.
- `docs/technical/dish_analysis/nutritional_analysis.md` — Phase 2.4 sub-section, Data Model extension, Pipeline extension, Component Checklist.
- `docs/technical/dish_analysis/personalized_food_index.md` — flip Stage 8 checklist row.
- `docs/technical/dish_analysis/user_customization.md` — one-line cross-reference.

#### To Add New

None (all updates are appendages to existing docs).

---

### Chrome Claude Extension Execution

**Included this stage.** Spec at `docs/chrome_test/260419_1113_stage8_phase2_4_review_ui_and_correction.md`. 10 tests, 5 desktop + 5 mobile:

1. Happy path — Edit → change → Save → both stores updated.
2. Cancel reverts; no POST fired.
3. Subsequent upload surfaces corrected nutrients in PersonalizationMatches.
4. Validation 422s on out-of-range values.
5. Empty states + permission guard.

Scope caveats:
- Frontend-heavy: tests rely on stable `data-testid` attributes. Plan ships those attributes (see Frontend section above).
- Placeholder usernames (no `docs/technical/testing_context.md`).
- Each test triggers a real Phase 1 + Phase 2 Gemini call on fresh upload (~15 s). 10 tests ≈ 3 min wall-clock + Pro pricing.

Execution flow: `feature-implement-full` invokes `chrome-test-execute` after Stage 8 lands.

#### To Delete

None.

#### To Update

None.

#### To Add New

- `docs/chrome_test/260419_1113_stage8_phase2_4_review_ui_and_correction.md` (already written).

---

## Dependencies

- **Stage 0** — `corrected_step2_data` column + `update_corrected_step2_data` CRUD. Stage 8 is the first caller.
- **Stage 4** — dual-write swallow-log pattern; Stage 8 reuses it verbatim for the personalization half of `save_step2_correction`.
- **Stage 5** — `nutrition_db_matches` on `result_gemini`; Top5DbMatches reads.
- **Stage 6** — `personalized_matches` on `result_gemini` + `corrected_step2_data` on each match; PersonalizationMatches reads.
- **Stage 7** — `reasoning_*` fields on `step2_data`; ReasoningPanel reads.
- **Existing item pipeline** — `item.py`, `item_schemas.py`, `ItemV2.jsx`, `Step2Results.jsx`, `services/api.js`.
- **No new external libraries.**
- **No schema changes.**

---

## Resolved Decisions

- **`Step2CorrectionRequest` field names mirror the existing schema** (confirmed with user 2026-04-19). `healthiness_score` (int 0-100) + `healthiness_score_rationale` (str). Minimum drift; the Step 2 view's numeric badge recomputes from the score.
- **Dual-write failure is swallow + log + return 200** (confirmed with user 2026-04-19). Matches Stage 4's enrichment pattern. The user's primary intent (save correction) succeeds; personalization-row update is fire-and-forget for future uploads.
- **Display precedence: `step2_corrected` wins over `step2_data`** (decision recorded by the planner). Frontend derives `activeData = step2_corrected || step2_data` in `Step2Results.jsx`. A "Corrected by you" badge signals the override.
- **`reasoning_*` stays sourced from `step2_data` even when the user has overridden** (decision recorded by the planner). The AI's original rationale is preserved as audit — it explains *why the AI picked its number*, not *why the user's number is right*. If the two diverge, the user reading the ReasoningPanel can see the AI's case for the original value.
- **`Top5DbMatches` and `PersonalizationMatches` hide on empty** (decision recorded by the planner). Progressive disclosure — users shouldn't see two panels claiming "no data" when the cold-start / no-match state already means there's nothing to see. The always-visible `ReasoningPanel` is enough baseline signal.
- **Optimistic UI on Save, plus background `loadItem()`** (decision recorded by the planner). Same pattern as Step 1 confirmation. The optimistic update makes the UX responsive; `loadItem()` catches the `personalized_matches` refresh if any concurrent retry/write landed between Save and the response. No spinner on `loadItem()`.
- **Edit form splits into sibling `Step2ResultsEditForm.jsx`** (decision recorded by the planner). Keeps `Step2Results.jsx` under the 300-line cap and makes the view-vs-edit state boundary cleaner to test.
- **Micronutrients as `List[str]` (plain strings, no mg quantities)** (decision recorded by the planner). The existing schema tolerates both `List[Micronutrient | str]`; the correction endpoint sends simple strings only. If Stage 8 UX adds quantity capture later, extend the schema to `List[Micronutrient]`.

## Open Questions

None — all decisions resolved 2026-04-19. Ready for implementation.
