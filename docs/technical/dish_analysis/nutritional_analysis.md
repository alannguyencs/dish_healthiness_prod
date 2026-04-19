# Nutritional Analysis — Technical Design

[< Prev: User Customization](./user_customization.md) | [Parent](./index.md) | [Next: Personalized Food Index >](./personalized_food_index.md)

## Related Docs
- Abstract: [abstract/dish_analysis/nutritional_analysis.md](../../abstract/dish_analysis/nutritional_analysis.md)

## Architecture

Phase 2 is a second Gemini vision call scheduled as a `BackgroundTasks` coroutine the moment the confirm endpoint returns. The prompt is the Step 2 markdown file with the user's confirmed dish name and component list appended as a plain-text block. Output is enforced to `Step2NutritionalAnalysis` via the SDK `response_schema` parameter. If the call fails, the background task classifies the exception and persists a `step2_error` block into `result_gemini` so the frontend can surface a retry-able error card. The frontend continues polling the same item endpoint and renders either the results or the error card when the payload arrives.

```
+---------------------+     +-----------------------+     +------------------+
|   React SPA         |     |   FastAPI backend     |     |   Google Gemini  |
|                     |     |                       |     |                  |
|  ItemV2.jsx         |     |  trigger_step2_       |     |  models.         |
|   (poll 3s)         |     |  analysis_background()|---->|  generate_       |
|  Step2Results.jsx   |<====|                       |     |  content()       |
|  Step2ErrorCard.jsx | JSON|  analyze_step2_...()  |     |                  |
|  ItemStepTabs.jsx   |     |                       |     |                  |
|                     |     |  item_retry.py:       |     |                  |
|                     |---->|  POST /retry-step2    |     |                  |
+---------------------+     +-----------------------+     +------------------+
                                  │
                                  ▼
                            +-----------------+
                            |  Postgres       |
                            |  result_gemini  |
                            |  .step2_data    |
                            |  .step2_error   |
                            |  .step = 2      |
                            +-----------------+
```

## Data Model

### `Step2NutritionalAnalysis` (response schema)

Defined in `backend/src/service/llm/models.py`:

| Field | Type | Constraints |
|-------|------|-------------|
| `dish_name` | `str` | Echoes the user-confirmed dish name |
| `healthiness_score` | `int` | 0 ≤ x ≤ 100 |
| `healthiness_score_rationale` | `str` | Short plain-language explanation |
| `calories_kcal` | `int` | ≥ 0 |
| `fiber_g` | `int` | ≥ 0 |
| `carbs_g` | `int` | ≥ 0 |
| `protein_g` | `int` | ≥ 0 |
| `fat_g` | `int` | ≥ 0 |
| `micronutrients` | `List[str]` | Default `[]` |

The analyzer appends the same engineering fields used by Phase 1 (`input_token`, `output_token`, `model`, `price_usd`, `analysis_time`).

### `step2_error` (failure path)

Written to `result_gemini.step2_error` by `_persist_step2_error` whenever the background task catches an exception. Cleared on successful Step 2 completion or on retry-endpoint dispatch.

| Field | Type | Description |
|-------|------|-------------|
| `error_type` | `str` | One of `config_error \| image_missing \| parse_error \| api_error \| unknown` |
| `message` | `str` | Pre-canned, user-facing string (`ERROR_USER_MESSAGE[error_type]`) |
| `occurred_at` | `str` | ISO-8601 UTC timestamp |
| `retry_count` | `int` | 0 on first failure; incremented by the retry endpoint each time the user re-runs |

### `result_gemini` after Phase 2

```json
{
  "step": 2,
  "step1_data":       { ... unchanged from Phase 1 ... },
  "step1_confirmed":  true,
  "confirmed_dish_name":    "User-confirmed name",
  "confirmed_components":   [ ... ],
  "step2_data": {
    "dish_name": "User-confirmed name",
    "healthiness_score": 72,
    "healthiness_score_rationale": "Balanced macros but high saturated fat from ...",
    "calories_kcal": 640,
    "fiber_g": 6,
    "carbs_g": 58,
    "protein_g": 30,
    "fat_g": 28,
    "micronutrients": ["Vitamin C", "Iron", "Calcium"],
    "input_token": 2412,
    "output_token": 704,
    "model": "gemini-2.5-pro",
    "price_usd": 0.0100,
    "analysis_time": 7.841
  },
  "iterations": [
    {
      "iteration_number": 1,
      "step": 2,
      "step1_data": { ... },
      "step2_data": { ... same as above ... },
      "metadata": {
        "confirmed_dish_name": "...",
        "confirmed_components": [ ... ]
      }
    }
  ],
  "current_iteration": 1
}
```

### Phase 2.1 — Nutrition DB Lookup (Stage 5)

Runs **before** the Gemini 2.5 Pro call inside `trigger_step2_analysis_background`. Consumes the Stage 1 `NutritionCollectionService` (four BM25 indices over `nutrition_foods` + `nutrition_myfcd_nutrients`). Persists the result on `result_gemini.nutrition_db_matches` immediately so Step 2 failure / retry cannot destroy the lookup.

Strategy:

1. Build candidate list `[dish_name, *components.component_name]`, order-preserved and deduplicated.
2. **Stage 1 — per-query search @ `min_confidence=70`.** Run `collect_from_nutrition_db(query, 70)` for each candidate. Track `best_confidence` (top match's confidence across all queries) and `search_attempts` (per-query record of query / success / matches / top_confidence).
3. **Stage 2 fallback — comma-joined @ `min_confidence=60`.** If `best_confidence < 0.75`, run one more lookup with `", ".join(candidates)` at the lower threshold. **Replace** the best_result only if the combined result scores higher. `search_attempts` records the combined attempt too.
4. Write the `best_result` dict on `result_gemini.nutrition_db_matches`, augmented with `search_attempts` and `dish_candidates=[dish_name]`.

Return shape (persisted on `nutrition_db_matches`):

```python
{
    "success": True,
    "method": "Direct BM25 Text Matching",
    "input_text": "<winning query>",
    "nutrition_matches": [ ... up to 10 rows ... ],
    "total_nutrition": { total_calories, total_protein_g, total_carbohydrates_g, total_fat_g, foods_included, disclaimer, aggregation_strategy, best_match_confidence, ... },
    "recommendations": [ ... ],
    "match_summary": { total_matched, avg_confidence, ... },
    "processing_info": { malaysian_foods_count, myfcd_foods_count, anuvaad_foods_count, ciqual_foods_count, min_confidence_threshold, ... },
    "search_strategy": "individual_dish_name: <query>" | "combined_terms: <csv>",
    "search_attempts": [ { query, success, matches, top_confidence, ... }, ... ],
    "dish_candidates": [dish_name],
}
```

Failure modes:

- `NutritionDBEmptyError` (DB not seeded) → log WARN, persist the empty-response shape with `match_summary.reason = "nutrition_db_empty"`. Phase 2.3 runs as today.
- Per-query exception → swallow, record `error` in the `search_attempts` entry, continue.
- No matches across any strategy → persist the empty-response shape with `match_summary.reason = "no_matches_across_strategies"`.

Written by:
- `service/nutrition_lookup.py::extract_and_lookup_nutrition(dish_name, components)` — orchestrator.
- `service/nutrition_db.py::NutritionCollectionService.collect_from_nutrition_db(text, min_confidence, deduplicate)` — the per-query wrapper.
- `service/_nutrition_aggregation.py` — `deduplicate_matches / aggregate_nutrition / calculate_optimal_nutrition / extract_single_match_nutrition / generate_recommendations` helpers.

Read by:
- Stage 7 (Phase 2.3 prompt) — not yet wired.
- Stage 8 (Phase 2.4 Top-5 DB Matches panel) — not yet wired.

### Phase 2.2 — Personalization Lookup (Stage 6)

Runs **in parallel** with Phase 2.1 inside `trigger_step2_analysis_background` via `asyncio.gather(..., return_exceptions=True)`. Consumes the Stage 0 per-user BM25 corpus (`personalized_food_descriptions`) populated by Stage 2 (caption + tokens) and Stage 4 (confirmed_dish_name + confirmed_tokens). Persists the raw list on `result_gemini.personalized_matches` in the same pre-Pro write as `nutrition_db_matches`.

Signature:

```python
def lookup_personalization(
    user_id: int,
    query_id: int,
    description: Optional[str],        # from result_gemini.reference_image.description
    confirmed_dish_name: str,          # from Stage 4 confirm endpoint
    top_k: int = 5,
    min_similarity: float = THRESHOLD_PHASE_2_2_SIMILARITY,  # 0.30
) -> List[Dict[str, Any]]:
```

Per-match shape:

```python
{
    "query_id": int,                         # referenced DishImageQuery id
    "image_url": str | None,                 # referenced dish's image URL
    "description": str | None,               # Phase 1.1.1 caption on the referenced row
    "similarity_score": float,               # 0..1 max-in-batch normalized
    "prior_step2_data": Dict | None,         # referenced DishImageQuery.result_gemini.step2_data
    "corrected_step2_data": Dict | None,     # personalization row's corrected_step2_data (Stage 8 writes)
}
```

Token source: **union** of `tokenize(description) ∪ tokenize(confirmed_dish_name)` — either side may be empty (cold-start Phase 1.1.1 or empty dish name) without breaking the lookup. Empty union returns `[]` without touching the DB.

Self-excluding: `search_for_user` is called with `exclude_query_id=query_id` so the current upload's own row never matches itself (double-belt with Stage 2's write-after-read insertion order).

Failure modes inside the gather:

- **Phase 2.2 raises** — `_safe_phase_2_2_result` logs WARN naming the query_id + exception; returns `[]`. Pro call still runs.
- **Phase 2.1 raises** — `_safe_phase_2_1_result` logs WARN; returns the Stage 5 empty-response shape with `match_summary.reason = "unexpected_exception"`. Pro call still runs.
- **`result_gemini` absent** — fall back to sequential Phase 2.1 only; `personalized_matches = []`.

Written by:
- `service/personalized_lookup.py::lookup_personalization` — orchestrator.
- `api/item_tasks.py::_gather_pre_pro_lookups` — the `asyncio.gather` scheduler.
- `api/item_tasks.py::_persist_pre_pro_state` — atomic two-key persist.
- `api/item_tasks.py::_safe_phase_2_1_result / _safe_phase_2_2_result` — gather exception converters.

Read by:
- Stage 7 (Phase 2.3 prompt) — `personalized_matches` drives the `__PERSONALIZED_BLOCK__` placeholder substitution and the optional image-B attach.
- Stage 8 (Phase 2.4 PersonalizationMatches panel) — not yet wired.

### Phase 2.3 — Reference-Assisted Prompt (Stage 7)

Consumes the two match keys persisted in Stages 5 and 6, plus the top-1 personalization image when `similarity_score ≥ 0.35`. Three thresholds gate the prompt and the image-B attach:

| Constant | Value | Compared against | Gate effect |
|---|---|---|---|
| `THRESHOLD_DB_INCLUDE` | `80` | `nutrition_db_matches.nutrition_matches[0].confidence_score` (0-100) | Include `__NUTRITION_DB_BLOCK__` in the prompt |
| `THRESHOLD_PERSONALIZATION_INCLUDE` | `0.30` | `personalized_matches[0].similarity_score` (0-1) | Include `__PERSONALIZED_BLOCK__` in the prompt |
| `THRESHOLD_PHASE_2_2_IMAGE` | `0.35` | same as above | Attach image B (second Gemini image part) |

Below threshold = placeholder line stripped cleanly via regex (same pattern as Stage 3's `__REFERENCE_BLOCK__`). The gap band `[0.30, 0.35)` lets the text block in but keeps image B off.

**Block order** in the prompt: DB block precedes personalization block. DB is the curated, consistent source; personalization is weaker evidence (the user's prior analysis may itself have been uncertain).

**Trimmed JSON payload.** Neither block dumps the full match dict verbatim. A module-private helper (`backend/src/service/llm/_step2_blocks.py`) narrows each match to the fields the prompt actually needs:

- DB match: `matched_food_name, source, confidence_score, calories_kcal, protein_g, carbs_g, fat_g, fiber_g` (macros come from the source-aware `extract_single_match_nutrition` in `_nutrition_aggregation.py`).
- Personalization match: `description, similarity_score, prior_step2_data` (5 macros) `, corrected_step2_data` (same 5 macros when Stage 8 has written them; otherwise `null`).

Drops `raw_bm25_score`, full `raw_data`, `image_url`, `query_id`, `nutrition_data`. Keeps outbound prompts readable in `backend.log` and reduces Gemini input tokens by ~2× compared to a full-dict dump.

**Image B**. When `personalized_matches[0].similarity_score >= 0.35`, `_resolve_phase_2_2_image_bytes` reads the bytes from `IMAGE_DIR / Path(image_url).name` and appends them to the Gemini `contents` list after the query image. Missing file → log WARN, single-image fallback (same pattern as Stage 3).

**Output schema additions.** `Step2NutritionalAnalysis` gains seven flat `reasoning_*: str = Field(default="")` fields:

| Field | Purpose |
|---|---|
| `reasoning_sources` | Top-level attribution for the analysis (DB match name, user-prior reference, or "LLM-only") |
| `reasoning_calories` | One-line rationale for `calories_kcal` |
| `reasoning_fiber` | One-line rationale for `fiber_g` |
| `reasoning_carbs` | One-line rationale for `carbs_g` |
| `reasoning_protein` | One-line rationale for `protein_g` |
| `reasoning_fat` | One-line rationale for `fat_g` |
| `reasoning_micronutrients` | One-line rationale for the micronutrients list (empty `""` acceptable) |

All seven default to `""` in the schema. The analyzer's required-field guard is **not** extended — Gemini structured-output emits empty strings when no citation is warranted, and a missing reasoning would otherwise raise and force the user into retry.

**Attribution contract** (enforced via prompt text, not schema). The .md prompt tells Gemini: "An omitted block is authoritatively absent — do NOT cite a Nutrition Database source that was not provided." This prevents the model from hallucinating citations for blocks that were gated out.

Written by:
- `backend/src/service/llm/_step2_blocks.py` — `render_nutrition_db_block`, `render_personalized_block`, `_trim_db_match`, `_trim_personalization_match`.
- `backend/src/service/llm/prompts.py::get_step2_nutritional_analysis_prompt(dish_name, components, nutrition_db_matches=None, personalized_matches=None)` — new signature; substitutes or strips both placeholders.
- `backend/src/service/llm/gemini_analyzer.py::analyze_step2_nutritional_analysis_async(..., reference_image_bytes=None)` — new kwarg; second Gemini image part when bytes provided.
- `backend/src/api/item_tasks.py::_resolve_phase_2_2_image_bytes` — optional image-B resolution; graceful degrade on missing file.
- `backend/src/api/item_tasks.py::trigger_step2_analysis_background` — re-read persisted matches, resolve bytes, plumb all three into prompt + analyzer.

Read by:
- Stage 8 (Phase 2.4 ReasoningPanel + Top-5 panels) — `reasoning_*` surfaces in the ReasoningPanel; `nutrition_db_matches` + `personalized_matches` surface in the Top5DbMatches + PersonalizationMatches panels respectively.

### Phase 2.4 — User Review & Correction (Stage 8)

Closes the loop: the Step 2 results view becomes an editable surface + three read-only reference panels, and a new `POST /api/item/{record_id}/correction` endpoint persists user corrections in two places so future similar uploads benefit from the user's verified numbers.

**Endpoint** — `POST /api/item/{record_id}/correction` in `backend/src/api/item_correction.py::save_step2_correction`. Body validated against `Step2CorrectionRequest`:

```python
class Step2CorrectionRequest(BaseModel):
    healthiness_score: int                  # 0..100
    healthiness_score_rationale: str
    calories_kcal: float                    # >= 0
    fiber_g: float                          # >= 0
    carbs_g: float                          # >= 0
    protein_g: float                        # >= 0
    fat_g: float                            # >= 0
    micronutrients: List[str]               # default []
```

Dual write on success:

1. `DishImageQuery.result_gemini.step2_corrected = payload` — the user override. `step2_data` is untouched (preserved for audit).
2. `personalized_food_descriptions.corrected_step2_data = payload` — via Stage 0's existing `crud_personalized_food.update_corrected_step2_data(query_id, payload)`. Stage 6's retrieval surfaces this field on matches, so future uploads carry the override.

The personalization half is wrapped in try/except-swallow-log (parallel to Stage 4's `_enrich_personalization_row`):

- Row missing for this `query_id` (Phase 1.1.1 graceful-degraded earlier) → log WARN, return 200.
- `update_corrected_step2_data` raises → log WARN, return 200.

Response:

```json
{ "success": true, "record_id": 1, "step2_corrected": { ...payload echo... } }
```

**Frontend** — four new components under `frontend/src/components/item/`:

- `Step2ResultsEditForm.jsx` — controlled inputs for all eight editable fields; micronutrient chip add/remove. Save passes a packaged payload to the parent via `onSave`; Cancel calls `onCancel`.
- `ReasoningPanel.jsx` — always-visible, `<details>`-style collapsible panel below the edit card. Renders the seven `reasoning_*` strings from `step2_data` (NOT from `step2_corrected` — the AI's rationale stays visible as audit even when the user overrides). Empty string → "No rationale provided." muted placeholder.
- `Top5DbMatches.jsx` — chip row showing up to 5 DB matches with color-coded confidence badges (≥ 85 green, 70–84 yellow, < 70 gray). Hidden when `nutrition_matches` is empty.
- `PersonalizationMatches.jsx` — one card per match: thumbnail, description, similarity badge, macro table. Prefers `corrected_step2_data` over `prior_step2_data` (with a "User-verified" badge when present). Hidden when `personalized_matches` is empty.

Plus updates:

- `Step2Results.jsx` — single top-level Edit toggle; `activeData = step2_corrected || step2_data`; "Corrected by you" badge when `step2_corrected` is present.
- `ItemV2.jsx` — composes the three panels below the results card; wires `handleStep2Correction` to `apiService.saveStep2Correction` + `reload()`.
- `services/api.js` — `saveStep2Correction(recordId, payload)` POST helper.

**Display precedence.** `Step2Results.jsx` derives `activeData = step2_corrected || step2_data`. Corrected wins for numeric fields and micronutrients; `reasoning_*` always reads from `step2_data` so the AI's case for its original numbers stays visible even after the user overrides.

**Retry / re-edit flow.** The endpoint overwrites `step2_corrected` on each save — re-editing is just another POST. No transactional ordering is required across the two writes; if the personalization half fails once, a subsequent successful edit re-syncs both stores.

Written by:
- `backend/src/api/item_correction.py::save_step2_correction` — the endpoint.
- `backend/src/api/item_correction.py::_enrich_personalization_corrected_data` — module-private swallow-log helper (parallel to Stage 4's `_enrich_personalization_row`).
- `backend/src/api/item_schemas.py::Step2CorrectionRequest` — validation schema.

Read by:
- The three new frontend panels; future stages (Stage 9 regression gate).

## Pipeline

```
api/item.py: confirm_step1_and_trigger_step2()
  │
  └──> BackgroundTasks.add_task(
         trigger_step2_analysis_background,
         record_id, image_path, dish_name, components)
  │
  ▼
api/item_tasks.py: trigger_step2_analysis_background(query_id, image_path, dish_name, components)
  │
  ▼ (Phase 2.1 + Phase 2.2, Stages 5 + 6 — parallel gather)
_gather_pre_pro_lookups(query_id, dish_name, components)
  ├── user_id, ref_description = record.user_id, result_gemini.reference_image.description
  ├── asyncio.gather(
  │     asyncio.to_thread(extract_and_lookup_nutrition, dish_name, components),
  │     asyncio.to_thread(lookup_personalization, user_id, query_id, ref_description, dish_name),
  │     return_exceptions=True)
  ├── exception-side converted to empty-shape fallbacks via _safe_phase_2_{1,2}_result
  └── returns (nutrition_db_matches, personalized_matches)
  │
  ▼
_persist_pre_pro_state(query_id, nutrition_db_matches, personalized_matches)
  └── writes BOTH result_gemini.nutrition_db_matches AND result_gemini.personalized_matches
     BEFORE the Pro call
  │
  ▼ (Phase 2.3, Stage 7 — prompt + image-B resolution)
reference_image_bytes = _resolve_phase_2_2_image_bytes(personalized_matches)
  └── None unless personalized_matches[0].similarity_score >= THRESHOLD_PHASE_2_2_IMAGE (0.35)
  │
step2_prompt = get_step2_nutritional_analysis_prompt(
    dish_name, components,
    nutrition_db_matches=nutrition_db_matches,
    personalized_matches=personalized_matches)
  ├── render_nutrition_db_block gated on confidence_score >= 80
  ├── render_personalized_block gated on similarity_score >= 0.30
  └── placeholder lines stripped via regex when gates fail
  │
step2_result = await analyze_step2_nutritional_analysis_async(
    image_path, step2_prompt,
    gemini_model="gemini-2.5-pro", thinking_budget=-1,
    reference_image_bytes=reference_image_bytes)
  │
  ▼
service/llm/prompts.py: get_step2_nutritional_analysis_prompt(dish_name, components)
  │
  ├──> read backend/resources/step2_nutritional_analysis.md
  │
  └──> append:
         "**USER-CONFIRMED DATA FROM STEP 1:**"
         "**Dish Name:** {dish_name}"
         "**Components with Serving Sizes:**"
         "- {name}: {size} × {count}"
         "**Calculate nutritional values for the entire dish based on the above confirmed data.**"
  │
  ▼
service/llm/gemini_analyzer.py: analyze_step2_nutritional_analysis_async(
    image_path, prompt,
    gemini_model="gemini-2.5-pro", thinking_budget=-1)
  │
  ├──> os.environ["GEMINI_API_KEY"]
  ├──> open(image_path, "rb") → types.Part.from_bytes(..., mime="image/jpeg")
  │
  ▼
loop.run_in_executor(None, _sync_gemini_call)
  │
  ▼
client.models.generate_content(
    model="gemini-2.5-pro",
    contents=[prompt, image_part],
    config=GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=Step2NutritionalAnalysis,
        temperature=0,
        thinking_config=ThinkingConfig(thinking_budget=-1)))
  │
  ▼
response.parsed.model_dump()  (fallback: json.loads(response.text))
  │
  ▼
Verify required fields: dish_name, healthiness_score, calories_kcal,
                        fiber_g, carbs_g, protein_g, fat_g
  │
  ▼
extract_token_usage + enrich_result_with_metadata
  │
  ▼
get_dish_image_query_by_id(query_id)  (re-read — tasks run out-of-session)
  │
  ▼
result_gemini = record.result_gemini.copy()
result_gemini["step"] = 2
result_gemini["step2_data"] = step2_result
result_gemini["step1_confirmed"] = True
if result_gemini.iterations:
    current = result_gemini.current_iteration - 1
    iterations[current].step = 2
    iterations[current].step2_data = step2_result
    iterations[current].metadata.confirmed_dish_name = dish_name
    iterations[current].metadata.confirmed_components = components
  │
  ▼
update_dish_image_query_results(query_id, None, result_gemini)
  │
  ▼
(On exception → _persist_step2_error(query_id, exc, retry_count):
   classify → write result_gemini.step2_error)

---- Retry path ----

POST /api/item/{record_id}/retry-step2  (item_retry.py)
  │
  ├──> auth + ownership checks
  ├──> guard: step1_confirmed && !step2_data && step2_error present
  ├──> guard: image file still on disk
  ├──> clear result_gemini.step2_error
  ├──> persist cleared blob
  └──> BackgroundTasks.add_task(
         trigger_step2_analysis_background,
         record_id, image_path,
         confirmed_dish_name, confirmed_components,
         retry_count + 1)

---- Frontend side ----

ItemV2.jsx poller (3 s)
  │
  ▼
GET /api/item/{id}
  │
  ▼
if result_gemini.step2_data:
    stopPolling(); render <Step2Results step2Data={step2_data} />
elif result_gemini.step2_error:
    stopPolling(); render <Step2ErrorCard error={step2_error}
                                          onRetry={handleStep2Retry} />
```

## Algorithms

### Prompt construction

- Base prompt: entire text of `backend/resources/step2_nutritional_analysis.md`.
- Appended block is a plain text Markdown snippet; Gemini reads both the structured schema (via `response_schema`) and the natural-language constraint to calculate values for the full dish at the supplied quantities.
- Component lines follow the template `- {component_name}: {selected_serving_size} × {number_of_servings}`.

### Healthiness score presentation

- Backend returns an integer 0-100. The frontend (`Step2Results.jsx`) buckets it into badge categories (Very Healthy, Healthy, Moderate, Unhealthy, Very Unhealthy) purely for UI — the thresholds are defined in the component, not the backend.

### Iteration bookkeeping

- The background task mutates both the top-level `result_gemini` fields (`step`, `step1_confirmed`, `step2_data`) and the entry in `iterations[current_iteration - 1]`.
- In the current flow there is always one iteration; this code is defensive against future iteration growth.

## Backend — API Layer

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/item/{record_id}` | Frontend polls; returns updated `result_gemini` once Phase 2 lands (success or `step2_error`) |
| POST | `/api/item/{record_id}/retry-step2` | Clears `step2_error`, increments `retry_count`, re-schedules the background task. 400 if Step 1 not confirmed, Step 2 already done, or no prior error to retry. 404 if record not found or image file missing on disk. |

## Backend — Service Layer

- `api/item_tasks.py#trigger_step2_analysis_background(query_id, image_path, dish_name, components, retry_count=0)` — the Phase 2 background coroutine. On success clears any prior `step2_error`; on exception delegates to the shared `persist_phase_error(query_id, exc, retry_count, "step2_error")` helper.
- `api/_phase_errors.py` — shared with Phase 1. Owns `classify_phase_error`, `persist_phase_error`, and the `ERROR_USER_MESSAGE` table. Single source of truth for error classification + persistence across both phases.
- `api/item_retry.py#retry_step2_analysis(...)` — POST endpoint handler that clears `step2_error`, increments retry count, and re-schedules the background task.
- `service/llm/gemini_analyzer.py#analyze_step2_nutritional_analysis_async(...)` — Gemini call.
- `service/llm/prompts.py#get_step2_nutritional_analysis_prompt(dish_name, components)` — prompt loader + confirmed-data injection.
- `service/llm/pricing.py#compute_price_usd(..., vendor="gemini")` — reused Phase 1 pricing logic.

## Backend — LLM Requests Layer

### Step 2 Nutritional Analysis

Prompt structure (ASCII diagram):

```
+----------------------------------------------------------+
|  SYSTEM PROMPT                                           |
|  (backend/resources/step2_nutritional_analysis.md)       |
|  - Instruct Gemini to return a healthiness score 0-100,  |
|    short rationale, macronutrients (calories, fiber,     |
|    carbs, protein, fat), and notable micronutrients,     |
|    calculated for the entire dish at user-confirmed      |
|    quantities.                                           |
+----------------------------------------------------------+
|                                                          |
+----------------------------------------------------------+
|  USER PROMPT  (built by prompts.get_step2_...)           |
|                                                          |
|  +----------------------------------------------------+  |
|  | Component 1 — base system prompt text              |  |
|  +----------------------------------------------------+  |
|  | Component 2 — Appended confirmed-data block:       |  |
|  |    **USER-CONFIRMED DATA FROM STEP 1:**            |  |
|  |    **Dish Name:** {dish_name}                      |  |
|  |    **Components with Serving Sizes:**              |  |
|  |    - {component_name}: {serving_size} × {count}    |  |
|  |    ...                                             |  |
|  |    **Calculate nutritional values for the entire   |  |
|  |    dish based on the above confirmed data.**       |  |
|  +----------------------------------------------------+  |
|  | Component 3 — image_part                           |  |
|  |   types.Part.from_bytes(data=<jpeg>, mime=         |  |
|  |     "image/jpeg") — same 384px JPEG as Phase 1     |  |
|  +----------------------------------------------------+  |
+----------------------------------------------------------+
```

Output schema table:

**`Step2NutritionalAnalysis`** — model `gemini-2.5-pro`, temperature 0, structured JSON:

| Field | Type | Description |
|-------|------|-------------|
| `dish_name` | `str` | Confirmed dish name (echo) |
| `healthiness_score` | `int` | 0-100 overall healthiness score |
| `healthiness_score_rationale` | `str` | Short plain-language explanation |
| `calories_kcal` | `int` | Total calories |
| `fiber_g` | `int` | Fiber in grams |
| `carbs_g` | `int` | Carbohydrates in grams |
| `protein_g` | `int` | Protein in grams |
| `fat_g` | `int` | Fat in grams |
| `micronutrients` | `List[str]` | Notable micronutrients / vitamins |

Engineering metadata appended on receipt (same as Phase 1): `input_token`, `output_token`, `model`, `price_usd`, `analysis_time`.

## Backend — CRUD Layer

- `get_dish_image_query_by_id(query_id)` — re-read inside the task; necessary because the task runs on a fresh session.
- `update_dish_image_query_results(query_id, result_openai, result_gemini)` — single write that replaces `result_gemini` with the Phase 2-augmented blob.

## Frontend — Pages & Routes

- `/item/:recordId` → `pages/ItemV2.jsx`. The page's step-tab row lets the user toggle between `step1_data` (via `Step1ComponentEditor`) and `step2_data` (via `Step2Results`) once both are present.

## Frontend — Components

- `components/item/AnalysisLoading.jsx` — shown while `pollingStep2 && !step2_data && !step2_error`.
- `components/item/Step2Results.jsx` — renders the confirmed dish name, the healthiness score with a category badge and rationale, the five core macros, the micronutrients list, and the model/cost/time footer.
- `components/item/PhaseErrorCard.jsx` — generic red-tinted card shared with Phase 1 (`headline` prop differentiates). Rendered when `result_gemini.step2_error` is present. Shows the user-facing message, hides the **Try Again** button for `error_type === "config_error"`, and swaps the button label to **Try Anyway** with a warning paragraph once `retry_count >= 5` (soft cap).
- `components/item/ItemStepTabs.jsx` — Step 1 ↔ Step 2 progress tab row. Extracted from `ItemV2.jsx` to keep the page under the 300-line cap.
- `components/item/ItemImage.jsx` / `ItemHeader.jsx` / `ItemNavigation.jsx` — chrome shared across the item page.

## Frontend — Services & Hooks

- `services/api.js#getItem(recordId)` — same polling call as Phase 1.
- `services/api.js#retryStep2(recordId)` — `POST /api/item/{id}/retry-step2`; called by `ItemV2.handleStep2Retry` when the user clicks the error card's button.
- Polling loop inside `ItemV2.jsx`: stops when `result_gemini.step2_data || result_gemini.step2_error` is truthy.

## External Integrations

- **Google Gemini 2.5 Pro** — second call per record. Same SDK, same auth, same rate-limit and error handling story as Phase 1.

## Constraints & Edge Cases

- On Gemini failure the background task classifies the exception and persists `result_gemini.step2_error`; the frontend stops polling and renders `Step2ErrorCard`. The user can click **Try Again** to invoke `POST /retry-step2`. `error_type === "config_error"` hides the retry button because retrying a missing API key won't fix anything.
- Soft retry cap: at `retry_count >= 5` the frontend swaps the button label to **Try Anyway** and shows a warning. The backend does not block — it relies on the UX nudge to discourage runaway retries while preserving user agency.
- No auto-retry on transient errors (`api_error`). The user explicitly opts in via the retry button so cost is never silently doubled during regional outages.
- `record.result_gemini` is re-read before the write — if the record is deleted between confirm and Phase 2 the task returns early with a log.
- Image file deletion between Phase 1 and Phase 2: Phase 1's file is the one used; if it is gone, Gemini call fails and is logged (no explicit user-facing error).
- Pricing relies on the same `PRICING` table as Phase 1; unknown models fall back to `DEFAULT_PRICING` and report cost incorrectly.
- Gemini may exceed the thinking budget for complex plates, adding latency and cost; `thinking_budget=-1` does not cap this.
- No retries on transient 429 / 5xx from Gemini. A single failed call means the user sees a permanent "Calculating nutritional values..." state.
- Because there's no endpoint gating Phase 2 on top of Phase 1, a double-tap on Confirm can enqueue two Phase 2 tasks that both write the same key. Last writer wins.
- Healthiness-score category thresholds are UI-only (`Step2Results.jsx`) — changing them is a frontend edit; the API just returns the integer.

## Component Checklist

- [x] `trigger_step2_analysis_background()` — background task entry (now accepts `retry_count`)
- [x] Shared `_phase_errors.py` (`classify_phase_error`, `persist_phase_error`, `ERROR_USER_MESSAGE`) — used by both Phase 1 and Phase 2
- [x] `analyze_step2_nutritional_analysis_async()` — Gemini call with structured output
- [x] `get_step2_nutritional_analysis_prompt(dish_name, components)` — prompt loader + injection
- [x] `Step2NutritionalAnalysis` Pydantic schema
- [x] Required-field guard in analyzer
- [x] `enrich_result_with_metadata()` — model / price / time stamps
- [x] `update_dish_image_query_results()` — single DB write
- [x] Iteration bookkeeping in `trigger_step2_analysis_background`
- [x] `POST /api/item/{record_id}/retry-step2` — `item_retry.py#retry_step2_analysis`
- [x] `ItemV2.jsx` polling stop condition (`step2_data || step2_error`)
- [x] `AnalysisLoading.jsx` — Phase 2 loading UI
- [x] `Step2Results.jsx` — score badge, rationale, macros, micros, footer
- [x] `PhaseErrorCard.jsx` — error UI with retry button + soft-cap warning (shared with Phase 1)
- [x] `ItemStepTabs.jsx` — extracted Step 1 / Step 2 progress tabs
- [x] `apiService.getItem()` — polling call
- [x] `apiService.retryStep2()` — retry call
- [x] Stage 5 — `extract_and_lookup_nutrition()` + pre-Pro persist in `item_tasks.py`
- [x] Stage 5 — `_nutrition_aggregation.py` helpers (`deduplicate_matches / aggregate_nutrition / calculate_optimal_nutrition / extract_single_match_nutrition / generate_recommendations`)
- [x] Stage 5 — `NutritionCollectionService.collect_from_nutrition_db(text, min_confidence, deduplicate)` method
- [x] Stage 6 — `lookup_personalization()` in `service/personalized_lookup.py`
- [x] Stage 6 — `_gather_pre_pro_lookups`, `_persist_pre_pro_state`, `_safe_phase_2_{1,2}_result` in `item_tasks.py`
- [x] Stage 6 — `THRESHOLD_PHASE_2_2_SIMILARITY = 0.30` config constant
- [x] Stage 7 — Phase 2.3 prompt consumes `nutrition_db_matches` + `personalized_matches` with threshold gating
- [x] Stage 7 — `Step2NutritionalAnalysis` schema adds seven flat `reasoning_*` fields (default `""`)
- [x] Stage 7 — `analyze_step2_nutritional_analysis_async(reference_image_bytes=None)` two-image path
- [x] Stage 7 — `_resolve_phase_2_2_image_bytes` in `item_tasks.py` + `trigger_step2_analysis_background` plumb-through
- [x] Stage 7 — `THRESHOLD_DB_INCLUDE=80`, `THRESHOLD_PERSONALIZATION_INCLUDE=0.30`, `THRESHOLD_PHASE_2_2_IMAGE=0.35`
- [x] Stage 7 — `_step2_blocks.py` render/trim helpers (JSON-dump trimmed subsets; keep outbound prompt under log-budget)
- [x] Stage 8 — `POST /api/item/{record_id}/correction` endpoint in `item_correction.py`
- [x] Stage 8 — `Step2CorrectionRequest` schema in `item_schemas.py`
- [x] Stage 8 — `Step2ResultsEditForm.jsx` controlled edit form
- [x] Stage 8 — `ReasoningPanel.jsx` expandable rationale panel
- [x] Stage 8 — `Top5DbMatches.jsx` chip row
- [x] Stage 8 — `PersonalizationMatches.jsx` card list with "User-verified" badge
- [x] Stage 8 — `Step2Results.jsx` Edit toggle + corrected-over-original precedence
- [x] Stage 8 — `ItemV2.jsx` panel composition + `handleStep2Correction`
- [x] Stage 8 — `apiService.saveStep2Correction`
- [ ] Idempotency key or dedupe on Phase 2 background task scheduling

---

[< Prev: User Customization](./user_customization.md) | [Parent](./index.md) | [Next: Personalized Food Index >](./personalized_food_index.md)
