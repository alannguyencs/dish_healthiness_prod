# Stage 10 — Phase 2.4 "AI Assistant Edit" — Prompt-Driven Step 2 Correction

**Feature**: Add a second button on the Step 2 results card that lets the user type a natural-language hint (e.g. *"Portions are smaller than the AI estimated — about 200 kcal per serving"*). The backend loads the current effective Step 2 payload as baseline, calls Gemini 2.5 Pro with the query image + trimmed baseline JSON + user hint, and commits the revised payload **directly** (no preview / Accept-Cancel) via the same `/correction` persistence path used by Stage 8.
**Plan Created:** 2026-04-19
**Status:** Plan
**Reference**:
- [Discussion — DB-backed nutrition analysis](../discussion/260418_food_db.md) (§ End-to-end workflow diagram, Phase 2.4 block)
- [Issues — 260415](../issues/260415.md) (§ Stage 10)
- [Abstract — User Customization](../abstract/dish_analysis/user_customization.md)
- [Abstract — Nutritional Analysis](../abstract/dish_analysis/nutritional_analysis.md)
- [Abstract — End-to-End Workflow](../abstract/dish_analysis/end_to_end_workflow.md)
- [Technical — User Customization](../technical/dish_analysis/user_customization.md)
- [Technical — Nutritional Analysis](../technical/dish_analysis/nutritional_analysis.md)
- [Testing Context](../technical/testing_context.md)

---

## Problem Statement

1. Today, the only way to correct the Step 2 results is **Manual Edit** (Stage 8) — flip every field into an input and type new numbers by hand. That is precise but slow, and it forces the user to own the arithmetic themselves (e.g. "this is actually 3 portions — I need to triple every macro").
2. Users regularly know *contextual* things that should change the estimate ("I used high-quality oil", "portions are smaller than the AI estimated", "this has organic ingredients") but have to translate that knowledge into concrete numbers before Stage 8 can accept it.
3. The AI has already done most of the work in Phase 2.3 — re-running Phase 2.3 against the user's hint is cheap (one Gemini 2.5 Pro call, same response schema) and produces a coherent revision that keeps `healthiness_score_rationale` and the macros internally consistent.

The gap: we need a second correction path that accepts free-text guidance, revises the payload via LLM, and lands in the same `step2_corrected` + `personalized_food_descriptions.corrected_step2_data` shape so the downstream personalization pipeline benefits from the user's context on future uploads.

---

## Proposed Solution

Add **Button B: "AI Assistant Edit"** beside the existing **Manual Edit** button on the Step 2 card. Clicking it expands an inline textarea + Submit control. On submit:

1. Frontend POSTs `{ prompt: <hint> }` to a new endpoint `POST /api/item/{record_id}/ai-assistant-correction`.
2. Backend loads the current effective Step 2 payload — `step2_corrected` if present, else `step2_data` — as the baseline.
3. Backend calls a new revision service (`step2_assistant.py::revise_step2_with_hint`) which:
   - Reads the new prompt template `backend/resources/step2_assistant_correction.md`.
   - Substitutes the trimmed baseline JSON + user hint into the template.
   - Calls Gemini 2.5 Pro with `response_schema=Step2NutritionalAnalysis` and the **query image** attached (multi-modal — lets the LLM cross-check hints against what is actually visible on the plate).
   - Returns the revised payload.
4. Backend commits the revised payload **directly** via the same `/correction` write path — writes `result_gemini.step2_corrected` (preserving `step2_data` for audit), stashes `ai_assistant_prompt = <latest user hint>` on the corrected payload, and mirrors onto `personalized_food_descriptions.corrected_step2_data`.
5. Frontend re-renders the Step 2 card with the new numbers. No preview, no Accept/Cancel step.

### Key design decisions (from Step 1.5 clarifications)

| Decision | Choice | Rationale |
|---|---|---|
| Image input to revision call | **Include query image (multi-modal)** | Lets Gemini visually cross-check user hints (e.g. "portions are smaller" claimed against a plate that clearly shows a large portion). |
| Baseline source when `step2_corrected` already exists | **Use current effective payload** (`step2_corrected` if present, else `step2_data`) | Supports stacked edits: user can manually tweak calories then ask AI to recompute macros, or iterate with multiple AI prompts. |
| Audit log shape | **Single `ai_assistant_prompt: str` field, latest wins** | Matches the Stage 10 spec in `docs/issues/260415.md`. Simpler schema. `step2_data` is preserved separately for audit of the AI's original baseline. |

### User flow sketch

```
Step 2 card renders with AI baseline
  │
  ├── Click "Manual Edit"    ─────► flip fields, Save → POST /correction
  │                                (Stage 8, unchanged)
  │
  └── Click "AI Assistant Edit"
         │
         ▼
     Inline textarea + Submit expands below button row
         │
         │  user types hint, clicks Submit
         ▼
     Both buttons disable; AI button shows "Revising…"
         │
         │  POST /api/item/{id}/ai-assistant-correction
         │    body: { prompt: <hint> }
         │
         ▼
     Backend: load effective baseline → Gemini 2.5 Pro (image + baseline JSON + hint)
         │
         ▼
     Backend: write result_gemini.step2_corrected (with ai_assistant_prompt)
              + personalized_food_descriptions.corrected_step2_data
         │
         ▼
     Response: { success, step2_corrected }
         │
         ▼
     Frontend: buttons re-enable; card re-renders with revised numbers
              (no Accept/Cancel modal)
```

---

## Current Implementation Analysis

### What Exists (keep as-is)

| Component | File | Status |
|-----------|------|--------|
| `POST /api/item/{id}/correction` endpoint (Manual Edit write path) | `backend/src/api/item_correction.py` | Keep — reused as the persistence layer; no changes to its body |
| `_enrich_personalization_corrected_data` (dual-write helper) | `backend/src/api/item_correction.py` | Keep — reused verbatim from the new endpoint |
| `Step2CorrectionRequest` Pydantic schema | `backend/src/api/item_schemas.py` | Keep — used by Manual Edit; AI path has its own request schema |
| `Step2NutritionalAnalysis` response model | `backend/src/service/llm/models.py` | Keep — the revision call reuses the exact same output schema |
| `analyze_step2_nutritional_analysis_async` (Gemini call wrapper) | `backend/src/service/llm/gemini_analyzer.py` | Keep — the new revision service builds on the same Gemini SDK wrapper |
| `Step2ResultsEditForm` (Manual Edit form) | `frontend/src/components/item/Step2ResultsEditForm.jsx` | Keep — only invoked by Manual Edit |
| `Step2Results.jsx` dish-name heading / macros / micronutrients rendering | `frontend/src/components/item/Step2Results.jsx` | Keep read-only rendering; extend header to two buttons |
| `saveStep2Correction` API service method | `frontend/src/services/api.js` | Keep — Manual Edit still uses it |
| `crud_personalized_food.update_corrected_step2_data` | `backend/src/crud/crud_personalized_food.py` | Keep — reused by the AI path dual-write |

### What Changes

| Component | Current | Proposed |
|-----------|---------|----------|
| Step 2 card header (Edit toggle) | Single **Edit** button | Two buttons side-by-side: **Manual Edit** + **AI Assistant Edit**; AI button expands inline textarea on click |
| Step 2 card body in edit mode | Full form with all fields editable (Manual path only) | Manual path unchanged; AI path renders a textarea + Submit below the button row while keeping the read-only card visible |
| `Step2Corrected` JSONB payload | Contains macros + rationale + micronutrients only | Optional new field `ai_assistant_prompt: str` (set only when the AI path wrote the payload) |
| Correction endpoints | One: `POST /correction` | Two: `POST /correction` (manual, unchanged) + `POST /ai-assistant-correction` (new) |
| Persistence path | Manual Edit → direct write | Manual Edit → direct write; AI Assistant Edit → Gemini call → same direct write |
| Prompt templates | `step2_nutritional_analysis.md` only | Adds `step2_assistant_correction.md` for the revision call |

---

## Implementation Plan

### Key Workflow

```
Frontend (Step2Results.jsx)                         Backend                                Gemini 2.5 Pro
───────────────────────────                         ───────                                ──────────────
[button row: Manual Edit | AI Assistant Edit]
       │
       │ click "AI Assistant Edit"
       ▼
[textarea + Submit expands]
       │
       │ user types hint, clicks Submit
       │ (both buttons disabled; AI btn → "Revising…")
       ▼
POST /api/item/{id}/ai-assistant-correction
  body: { prompt: <hint> }                 ─────►   save_ai_assistant_correction()
                                                        │
                                                        ├─ authenticate + ownership check
                                                        ├─ load record → result_gemini
                                                        ├─ require step2_data present (422 if not)
                                                        ├─ require non-empty prompt (422 if empty)
                                                        ▼
                                                    revise_step2_with_hint(
                                                        record_id, user_hint,
                                                    )
                                                        │
                                                        ├─ baseline = step2_corrected or step2_data
                                                        ├─ prompt = render_assistant_prompt(
                                                        │              baseline, hint)
                                                        ├─ analyze_step2_nutritional_analysis_async(
                                                        │     image_path, prompt, "gemini-2.5-pro")
                                                        │                                    ─────►   generate_content
                                                        │                                    ◄─────   Step2NutritionalAnalysis
                                                        ◄─ revised: Step2NutritionalAnalysis
                                                        │
                                                        ├─ payload = revised + {ai_assistant_prompt: hint}
                                                        ├─ result_gemini["step2_corrected"] = payload
                                                        ├─ update_dish_image_query_results(...)
                                                        ├─ _enrich_personalization_corrected_data(
                                                        │     record_id, payload)
                                                        ▼
                                                    200 { success, record_id, step2_corrected }
       ◄─────────────────────────────────────────── JSON
       │
       │ buttons re-enable; close textarea;
       │ setStep2Corrected(payload) via reload()
       ▼
[Step 2 card re-renders with revised macros]
[Corrected by you badge visible]
```

**To Delete:** None.

**To Update:**
- `Step2Results.jsx` — split the single Edit button into `Manual Edit` + `AI Assistant Edit`; add the textarea/submit panel for Button B.
- `ItemV2.jsx` — add `handleAiAssistantCorrection(prompt)` handler that calls the new API method and reloads (mirrors `handleStep2Correction`).

**To Add New:**
- Backend endpoint `POST /api/item/{id}/ai-assistant-correction` in `backend/src/api/item_correction.py`.
- Backend service `revise_step2_with_hint` in `backend/src/service/llm/step2_assistant.py`.
- Prompt template `backend/resources/step2_assistant_correction.md`.
- Frontend API method `apiService.saveAiAssistantCorrection(recordId, prompt)`.
- Frontend inline "hint textarea" markup inside `Step2Results.jsx`.

---

### Database Schema

No new tables, no new columns. `result_gemini` is a JSONB blob so adding `ai_assistant_prompt` inside `step2_corrected` needs no DDL. `personalized_food_descriptions.corrected_step2_data` is also JSONB and will transparently carry the new key.

**To Delete:** None.
**To Update:** None.
**To Add New:** None.

---

### CRUD

No new CRUD functions. The AI path reuses:
- `get_dish_image_query_by_id(record_id)` — ownership check + baseline load.
- `update_dish_image_query_results(query_id, result_openai=None, result_gemini=new_blob)` — writes the revised `step2_corrected` into the JSONB blob.
- `crud_personalized_food.update_corrected_step2_data(query_id, payload)` — mirrors onto the personalization row.

**To Delete:** None.
**To Update:** None.
**To Add New:** None.

---

### Services

**To Delete:** None.

**To Update:** None.

**To Add New:**

- **`backend/src/service/llm/step2_assistant.py` (NEW)**
  ```python
  async def revise_step2_with_hint(
      record_id: int,
      user_hint: str,
  ) -> Dict[str, Any]:
      """
      Phase 2.4 AI Assistant path. Loads the current effective Step 2 payload
      (step2_corrected if present, else step2_data) as baseline, renders the
      revision prompt against the user's hint, calls Gemini 2.5 Pro with the
      query image attached, and returns the revised Step2NutritionalAnalysis
      payload. Does not write — persistence is the endpoint's job.
      """
  ```

  Internally:
  1. `record = get_dish_image_query_by_id(record_id)` — fetch for baseline + image path.
  2. `baseline = record.result_gemini.get("step2_corrected") or record.result_gemini["step2_data"]`.
  3. `trimmed_baseline = _trim_baseline_for_prompt(baseline)` — drop `model`, `price_usd`, `analysis_time`, `input_token`, `output_token`, `ai_assistant_prompt` (if present); keep macros + rationale + micronutrients.
  4. `prompt = render_assistant_prompt(trimmed_baseline, user_hint)` — load template, substitute `{{BASELINE_JSON}}` and `{{USER_HINT}}` placeholders.
  5. `image_path = resolve_image_path(record.image_url)`.
  6. `result = await analyze_step2_nutritional_analysis_async(image_path, prompt, gemini_model="gemini-2.5-pro")`.
  7. Return `result`.

- **`backend/resources/step2_assistant_correction.md` (NEW)**

  Prompt template. Instructs Gemini to:
  - Keep the same JSON shape as the baseline (the response schema is enforced server-side).
  - Change only fields the user's hint justifies (don't invent numbers).
  - Explain each change inline in `healthiness_score_rationale` + `reasoning_*` using phrases like *"revised per user hint: portions smaller than AI estimate"*.
  - Preserve the user's `micronutrients` list when the hint does not contradict it (e.g. don't remove Vitamin D just because the hint talks about portions).
  - Cross-check the hint against the attached query image — if the hint claims "small portions" but the image clearly shows a large portion, the model may reject the hint and preserve the baseline numbers (explain this in the rationale).

  Template sketch:
  ```markdown
  # Step 2 Revision — User Hint Driven

  You previously produced the nutritional analysis below for the attached dish image.
  The user now provides a natural-language hint about the dish. Your task: revise the
  analysis to reflect what the hint adds, **while still grounded in the attached image**.

  ## Baseline (your previous output, JSON)
  ```json
  {{BASELINE_JSON}}
  ```

  ## User hint
  > {{USER_HINT}}

  ## Revision rules
  1. Keep the same JSON shape as the baseline. Do not invent new top-level fields.
  2. Change only the numeric fields the hint justifies. Leave the rest identical.
  3. Preserve the baseline's `micronutrients` list unless the hint explicitly contradicts it.
  4. Rewrite `healthiness_score_rationale` so the reader can see what changed and why.
  5. Cite the user hint explicitly in the rationale (e.g. "revised per user hint: ...").
  6. If the attached image clearly contradicts the hint (e.g. hint says "small portion"
     but image shows a large plate), state that in the rationale and keep the baseline
     numbers close to their original values.
  ```

---

### API Endpoints

**To Delete:** None.

**To Update:** None.

**To Add New:**

- **`POST /api/item/{record_id}/ai-assistant-correction`** (`backend/src/api/item_correction.py`)

  Request body:
  ```json
  { "prompt": "Portions are smaller than the AI estimated — about 200 kcal per serving of fried chicken." }
  ```

  Request schema (`backend/src/api/item_schemas.py`):
  ```python
  class AiAssistantCorrectionRequest(BaseModel):
      prompt: str = Field(
          ...,
          min_length=1,
          max_length=2000,
          description="User's natural-language hint to drive the Step 2 revision.",
      )
  ```

  Response (200):
  ```json
  {
    "success": true,
    "record_id": 42,
    "step2_corrected": {
      "dish_name": "Ayam Goreng",
      "healthiness_score": 55,
      "healthiness_score_rationale": "Revised per user hint: portions smaller than AI estimate. Calories per serving reduced from ~500 to ~200 kcal...",
      "calories_kcal": 600,
      "fiber_g": 3,
      "carbs_g": 35,
      "protein_g": 40,
      "fat_g": 25,
      "micronutrients": ["Iron", "Potassium"],
      "ai_assistant_prompt": "Portions are smaller than the AI estimated — about 200 kcal per serving of fried chicken."
    }
  }
  ```

  Error codes:
  - `401` — no/invalid auth cookie.
  - `404` — record not found or owned by another user.
  - `400` — Step 2 analysis has not completed (`step2_data` missing) — nothing to revise.
  - `422` — empty / whitespace-only prompt (Pydantic validation).
  - `502` — Gemini call failed (bubble up as "AI revision failed; please try again").

  Endpoint body (sketch):
  ```python
  @router.post("/{record_id}/ai-assistant-correction")
  async def save_ai_assistant_correction(
      record_id: int,
      request: Request,
      body: AiAssistantCorrectionRequest,
  ) -> JSONResponse:
      user = authenticate_user_from_request(request)
      if not user:
          raise HTTPException(status_code=401, detail="Not authenticated")

      record = get_dish_image_query_by_id(record_id)
      if not record or record.user_id != user.id:
          raise HTTPException(status_code=404, detail="Record not found")

      if not record.result_gemini or not record.result_gemini.get("step2_data"):
          raise HTTPException(
              status_code=400,
              detail="Step 2 analysis has not completed; nothing to revise.",
          )

      try:
          revised = await revise_step2_with_hint(record_id, body.prompt.strip())
      except Exception as exc:
          logger.exception("AI Assistant revision failed for record_id=%s", record_id)
          raise HTTPException(status_code=502, detail="AI revision failed") from exc

      payload = {
          "dish_name": revised.get("dish_name"),
          "healthiness_score": revised["healthiness_score"],
          "healthiness_score_rationale": revised["healthiness_score_rationale"],
          "calories_kcal": revised["calories_kcal"],
          "fiber_g": revised["fiber_g"],
          "carbs_g": revised["carbs_g"],
          "protein_g": revised["protein_g"],
          "fat_g": revised["fat_g"],
          "micronutrients": revised.get("micronutrients", []),
          "ai_assistant_prompt": body.prompt.strip(),
      }

      new_blob = dict(record.result_gemini)
      new_blob["step2_corrected"] = payload
      update_dish_image_query_results(
          query_id=record_id, result_openai=None, result_gemini=new_blob
      )
      _enrich_personalization_corrected_data(record_id, payload)

      return JSONResponse(
          content={
              "success": True,
              "record_id": record_id,
              "step2_corrected": payload,
          }
      )
  ```

  Router registration already covers the file (`api_router.include_router(item_correction.router)`) — no change to `api_router.py`.

---

### Testing

**To Delete:** None.

**To Update:**
- `frontend/src/components/item/__tests__/Step2Results.test.jsx` (if present) — add a case asserting that both `Manual Edit` and `AI Assistant Edit` render; the AI button expands a textarea; an empty textarea disables Submit.

**To Add New:**

Unit tests:
- `backend/tests/service/llm/test_step2_assistant.py` — mock `analyze_step2_nutritional_analysis_async`, pass a known baseline, assert the rendered prompt contains `{{BASELINE_JSON}}` substituted and the hint verbatim.
- `backend/tests/api/test_item_ai_assistant_correction.py` — FastAPI TestClient:
  - 401 without cookie.
  - 404 for other user's record.
  - 400 when `step2_data` absent.
  - 422 when prompt is empty / whitespace.
  - Happy path: mocked revise returns a payload; verify `step2_corrected.ai_assistant_prompt` persists and `step2_data` is preserved; verify `update_corrected_step2_data` is called with the same payload.
- `frontend/src/components/item/__tests__/Step2Results.aiAssistant.test.jsx` — renders two buttons; clicking AI button shows textarea; Submit is disabled on empty; Submit fires with non-empty value; buttons disabled while `aiAssisting=true`; "Revising…" label appears.

Integration test:
- `backend/tests/integration/test_stage10_e2e.py` — confirm a Step 1, wait for mocked Step 2 to land, POST `/ai-assistant-correction`, assert `result_gemini.step2_corrected.ai_assistant_prompt` is set and `personalized_food_descriptions.corrected_step2_data` mirror matches.

Validation & pre-commit loop:
1. `source venv/bin/activate && pre-commit run --all-files`.
2. Fix lint / line-count / black reformat issues.
3. Re-run until clean (Prettier can push frontend lines back over the 300-line cap; if `Step2Results.jsx` exceeds, extract the AI assistant panel into its own `Step2AiAssistantPanel.jsx`).
4. Repeat until pre-commit passes with no new failures.

---

### Frontend

**To Delete:** None.

**To Update:**

- **`frontend/src/components/item/Step2Results.jsx`**
  - Rename existing `Edit` button to `Manual Edit`; keep `data-testid="step2-edit-toggle"` on it (backwards compatible for Stage 8 tests).
  - Add second button `AI Assistant Edit` beside it, `data-testid="step2-ai-assistant-toggle"`.
  - Add local state `aiHintOpen: bool`, `aiHint: string`, `aiAssisting: bool`.
  - When `aiHintOpen=true`, render an inline panel below the button row:
    - `<textarea data-testid="step2-ai-assistant-textarea" placeholder="Describe any context the AI should consider (portion size, cooking method, ingredients)...">`
    - `Submit` button `data-testid="step2-ai-assistant-submit"` — disabled when `aiHint.trim() === ""` or `aiAssisting`.
    - `Cancel` button (close the panel, discard the draft).
  - On Submit: set `aiAssisting=true`, change the AI button label to `Revising…`, disable both edit buttons, call `onAiAssistSubmit(aiHint)` (new prop). When parent resolves, reset state and close the panel.
  - Keep dish-name heading styling (`text-2xl font-bold text-blue-600`) unchanged.

- **`frontend/src/pages/ItemV2.jsx`**
  - Add state `aiAssisting` and handler `handleAiAssistantCorrection(prompt)`:
    ```jsx
    const handleAiAssistantCorrection = async (prompt) => {
      try {
        setAiAssisting(true);
        await apiService.saveAiAssistantCorrection(recordId, prompt);
        await reload();
      } catch (err) {
        console.error("Failed to save AI assistant correction:", err);
        alert("AI revision failed. Please try again.");
      } finally {
        setAiAssisting(false);
      }
    };
    ```
  - Pass `onAiAssistSubmit={handleAiAssistantCorrection}` and `aiAssisting={aiAssisting}` to `<Step2Results …/>`.

- **`frontend/src/services/api.js`**
  - Append:
    ```js
    saveAiAssistantCorrection: async (recordId, prompt) => {
      const response = await api.post(
        `/api/item/${recordId}/ai-assistant-correction`,
        { prompt },
      );
      return response.data;
    },
    ```

**To Add New:**

- **`frontend/src/components/item/Step2AiAssistantPanel.jsx`** — extract the textarea/Submit/Cancel block if `Step2Results.jsx` exceeds 300 lines after Prettier pass. Props: `value`, `onChange`, `onSubmit`, `onCancel`, `assisting`.

Visual spec:
- Button row: `flex gap-2` right-aligned in the card header. `Manual Edit` unchanged (`bg-gray-100 hover:bg-gray-200`). `AI Assistant Edit` uses a violet accent (`bg-violet-100 hover:bg-violet-200 text-violet-900`) to visually distinguish it as the AI path.
- AI panel: `bg-violet-50 border border-violet-200 rounded-lg p-4 mt-3 space-y-2`. Textarea uses `rows={3}` and `resize-y`. Submit button uses `bg-violet-600 hover:bg-violet-700 text-white`.
- "Revising…" state replaces the Submit button text with a small inline spinner + the word `Revising…`.

---

### Documentation

#### Abstract (`docs/abstract/`)

**To Delete:** None.

**To Update:**

- **`docs/abstract/dish_analysis/end_to_end_workflow.md`** — Phase 2.4 block. Already contains the two-button layout (Manual Edit + AI Assistant Edit) from the earlier diagram-only edit pass; verify the acceptance criteria list mentions "AI Assistant Edit" as an additional correction path and that the Scope section's Included bullet covers it.
- **`docs/abstract/dish_analysis/user_customization.md`** — Solution section: add a short paragraph below the current `Reviewing and correcting the analysis` narrative noting the new AI-assisted path; Scope Included: add bullet *"Second correction path ('AI Assistant Edit') — user types a free-text hint and the AI revises the Step 2 numbers in one call, committing directly"*; Acceptance Criteria: add `[ ] AI Assistant Edit accepts a non-empty hint, disables both edit buttons while the revision is in flight, and re-renders the Step 2 card with revised numbers without a preview step`.
- **`docs/abstract/dish_analysis/nutritional_analysis.md`** — `Reviewing and correcting the analysis` subsection: append a sentence noting the AI Assistant Edit path exists as a parallel correction channel; no change to Scope.

**To Add New:** None.

#### Technical (`docs/technical/`)

**To Delete:** None.

**To Update:**

- **`docs/technical/dish_analysis/user_customization.md`** — add a new subsection `### Phase 2.4 — AI Assistant Edit (Stage 10)` under the existing Stage 8 note. Content:
  - New endpoint row in the Backend API Layer table: `POST /api/item/{record_id}/ai-assistant-correction` + request/response schemas.
  - New schema `AiAssistantCorrectionRequest` under Data Model.
  - Service layer: document `revise_step2_with_hint` and the new prompt template.
  - Pipeline: one ASCII diagram showing endpoint → revise service → Gemini → direct commit (mirrors the existing Stage 8 diagram).
  - Component Checklist: add items for the new endpoint, service, prompt template, Step2Results dual-button UI, API method.

- **`docs/technical/dish_analysis/nutritional_analysis.md`** — cross-reference the new AI path in a short note (*"Stage 10 adds a parallel correction path; see user_customization.md § Phase 2.4 — AI Assistant Edit"*).

**To Add New:** None.

#### API Documentation (`docs/api_doc/`)

No `docs/api_doc/` folder exists in the current workspace. Skip — "No changes needed — `docs/api_doc/` is not present in this project; API surfaces are documented in `docs/technical/` instead."

---

### Chrome Claude Extension Execution

**To Delete:** None.
**To Update:** None.
**To Add New:** The Chrome E2E test spec for this feature was generated in Step 1.6 at `docs/chrome_test/260419_1940_ai_assistant_edit.md`. After implementation is complete, invoke `/webapp-dev:chrome-test-execute docs/chrome_test/260419_1940_ai_assistant_edit.md`. `feature-implement-full` runs this automatically as part of its post-implementation flow.

Test coverage:
1. Happy path — AI Edit lowers calories per a portion-size hint; `ai_assistant_prompt` persists; personalization mirror updates.
2. Validation — empty prompt rejected (422 or client-side disabled Submit).
3. Stacked edits — Manual edit (calories = 9999) → AI Assistant edit → revised to realistic value.
4. Re-submit — second AI prompt overwrites `ai_assistant_prompt`.
5. Cross-stage invariant — `step1_data`, `confirmed_*`, `nutrition_db_matches`, `personalized_matches` unchanged after AI revise.
6. Mobile layout — 375 × 812 viewport, no horizontal overflow, tap-target ≥ 44 px.

---

## Dependencies

- **Stage 8** — `POST /api/item/{id}/correction` endpoint, `_enrich_personalization_corrected_data` helper, `Step2Results.jsx` edit-toggle pattern. Stage 10 reuses the persistence layer and the Manual Edit UX precedent.
- **Stage 6** — `personalized_food_descriptions.corrected_step2_data` column + `crud_personalized_food.update_corrected_step2_data`. The AI revision flows into the same row.
- **Phase 2.3 infrastructure** — `analyze_step2_nutritional_analysis_async` + `Step2NutritionalAnalysis` response schema. The revision call reuses the exact Gemini wrapper and output contract.
- **Gemini 2.5 Pro** — same model tier used by Phase 2.3; no new credentials or quota impact beyond per-revision cost (one Gemini 2.5 Pro call per AI Assistant Edit).

## Open Questions

None at plan time. Step 1.5 resolved:
- Image input → included (multi-modal).
- Baseline source → current effective payload (`step2_corrected` if present, else `step2_data`).
- Audit log → single `ai_assistant_prompt: str`, latest wins.

Potential future work (out of scope for Stage 10):
- Stream the Gemini response to give a faster perceived latency on the "Revising…" state.
- Append to `ai_assistant_history: List[{prompt, timestamp}]` if a richer audit trail becomes needed.
- Let the user compare before/after side-by-side (revert to baseline button).
