# Component Identification — Technical Design

[Parent](./index.md) | [Next: User Customization >](./user_customization.md)

## Related Docs
- Abstract: [abstract/dish_analysis/component_identification.md](../../abstract/dish_analysis/component_identification.md)

## Architecture

Phase 1 is a two-step Gemini pipeline triggered as a FastAPI `BackgroundTasks` coroutine immediately after `Meal Upload` creates the row. The task lives in `backend/src/api/item_identification_tasks.py` (relocated from `date.py` to keep that file under the 300-line cap). The two steps are:

- **Phase 1.1.1 — Fast caption + personalized reference retrieval.** A fast Gemini 2.0 Flash call produces a plain-text caption; the caption is BM25-searched against the user's prior personalization corpus (`personalized_food_descriptions`, Stage 0 foundation); the top-1 hit (or `null`) is stashed on `result_gemini.reference_image` before the component-ID call runs. The upload's own row is inserted into the corpus **after** the search so it cannot self-match. See [Phase 1.1.1 — Fast Caption + Reference Retrieval](#phase-111--fast-caption--reference-retrieval) below for the full flow.
- **Phase 1.1.2 — Gemini 2.5 Pro structured-output component identification.** On success it writes the structured output into `result_gemini.identification_data` and leaves `identification_confirmed=false` so the frontend poller can pick it up and route the user into the editor. On failure it classifies the exception and persists `result_gemini.identification_error` via the shared `persist_phase_error` helper in `src.api._phase_errors`; the frontend stops polling and renders `<PhaseErrorCard>` with a retry button.

The two phases persist independently on `result_gemini`: Phase 1.1.1 writes `reference_image` before Phase 1.1.2 runs, so a Phase 1.1.2 failure does not destroy the retrieval output and a `/retry-identification` that re-runs only Phase 1.1.2 keeps the original reference intact.

### Phase 1.1.1 — Fast Caption + Reference Retrieval

Pipeline (runs first inside `analyze_image_background`):

```
analyze_image_background(query_id, file_path, retry_count=0)
  │
  ▼
record_pre = get_dish_image_query_by_id(query_id)
  │
  ├── is_retry_short_circuit?
  │     (crud_personalized_food.get_row_by_query_id(query_id) is not None)
  │     → skip Phase 1.1.1 entirely; preserve prior reference_image
  │
  ▼ (first run only)
resolve_reference_for_upload(user_id, query_id, file_path)
  │
  ├── generate_fast_caption_async(file_path)          gemini-2.0-flash, temp=0, plain text
  │     (on ValueError / FileNotFoundError → log WARN, return None — graceful degrade)
  │
  ├── query_tokens = personalized_food_index.tokenize(description)
  │
  ├── if query_tokens:
  │     matches = personalized_food_index.search_for_user(
  │         user_id, query_tokens, top_k=1,
  │         min_similarity=THRESHOLD_PHASE_1_1_1_SIMILARITY (0.25),
  │         exclude_query_id=query_id)
  │   else:
  │     matches = []
  │
  ├── if matches:
  │     prior = get_dish_image_query_by_id(top.query_id)
  │     reference = { query_id, image_url, description,
  │                   similarity_score,
  │                   prior_identification_data = prior.result_gemini.identification_data or None }
  │   else:
  │     reference = None
  │
  └── crud_personalized_food.insert_description_row(
          user_id, query_id,
          image_url=record_pre.image_url,
          description=description, tokens=query_tokens,
          similarity_score_on_insert=(top.similarity_score if matches else None))
  │
  ▼
pre_blob = (result_gemini or { phase:0, identification_data:None }).copy()
pre_blob["reference_image"] = reference
update_dish_image_query_results(query_id, result_openai=None, result_gemini=pre_blob)
  │
  ▼ (Phase 1.1.2 starts — sees reference_image already persisted)
```

Failure-mode table:

| Failure                              | Behavior                                   | `flash_caption` | `reference_image` | Personalization row |
|---                                   |---                                         |---              |---                |---                  |
| Gemini Flash errors (rate, net, parse) | Log WARN; orchestrator returns `{flash_caption: None, reference_image: None}`. | `null` | `null`            | Not inserted         |
| User has zero prior rows             | BM25 returns `[]`.                        | caption string  | `null`            | Inserted (seeds future searches) |
| Top-1 below `THRESHOLD_PHASE_1_1_1_SIMILARITY` | `[]` after threshold filter.    | caption string  | `null`            | Inserted             |
| Caption tokenizes to `[]`            | Skip search; still insert corpus row.     | caption string  | `null`            | Inserted with `tokens=[]` |
| Retry and row already exists          | Caller short-circuits; orchestrator returns `None`. | Unchanged | Unchanged (prior attempt's value preserved) | Unchanged            |
| Retry and no row                      | Normal path.                              | caption string  | New value          | Inserted             |

`flash_caption` + `reference_image` JSON shape (both stashed on `result_gemini`):

```json
{
  "flash_caption": "grilled chicken rice with cucumber",
  "reference_image": {
    "query_id": 1234,
    "image_url": "/images/260418_200123_u7_dish1.jpg",
    "description": "grilled chicken rice with cucumber",
    "similarity_score": 0.87,
    "prior_identification_data": { ...the referenced DishImageQuery's result_gemini.identification_data... }
  }
}
```

…either key can be `null` per the failure-mode table. `flash_caption` is the **current** upload's Flash output; `reference_image.description` is the matched prior row's caption.

**Thresholds and scoring.** `similarity_score` is the per-user BM25 top-1 normalized by max-in-batch (see [Personalized Food Index — Algorithms](./personalized_food_index.md#algorithms)); the top hit is always `1.0`. `THRESHOLD_PHASE_1_1_1_SIMILARITY = 0.25` mainly rejects corpora with zero lexical overlap — the prompt framing in Phase 1.1.2 is the real quality control. Re-tune after real retrieval-quality data lands.

### Phase 1.1.2 — Reference-Assisted Component ID

Consumes the `result_gemini.reference_image` key Phase 1.1.1 just persisted (or, on retry, the one the prior attempt persisted). When a full reference is available, the Gemini 2.5 Pro call runs with **two image parts** (query image at index 1, reference image at index 2) and the prompt substitutes a `__REFERENCE_BLOCK__` placeholder with a rendered "Reference results (HINT ONLY)" block. When any degrade condition applies, the Pro call falls back to today's single-image path with the placeholder stripped.

Decision matrix:

| Path                                              | `reference_image` persisted | File on disk | `prior_identification_data` | Image parts | Prompt block |
|---------------------------------------------------|----------|----------|----------|----|----|
| Cold-start / below-threshold / caption failed     | `null`   | —        | —        | 1  | stripped |
| Warm-start, full reference                        | populated | present  | present  | **2** | **substituted** |
| Warm-start, `prior_identification_data` null (Option B)    | populated | present  | `null`   | 1  | stripped |
| Warm-start, image file missing                    | populated | missing  | any      | 1  | stripped + WARN log |
| Retry-identification after Phase 1.1.2 failure             | preserved from prior attempt | present | present | 2  | substituted |

All branching lives in `_resolve_reference_inputs(reference) -> (Optional[bytes], Optional[Dict])` inside `backend/src/api/item_identification_tasks.py`. Call site re-reads `DishImageQuery.result_gemini.reference_image` before the Pro call so both the first-attempt and retry-short-circuit paths share a single resolution point.

Rendered reference block (from `_render_reference_block(prior_identification_data)` in `prompts.py`):

```
## Reference results (HINT ONLY — may or may not match)

The user has uploaded a similar dish before. The **image attached after the query image is the prior dish**, and the analysis below is what we produced for it last time. Use this ONLY as a hint — the two dishes may differ in cuisine, preparation, or portion. If the query image disagrees, trust the query image.

**Prior dish name:** {top dish_predictions[0].name}

**Prior components (name · serving sizes · predicted servings):**
- {c.component_name} · {serving_sizes comma-joined} · {c.predicted_servings}
- …
```

Only non-empty sections render — missing `dish_predictions` drops the dish-name line, missing `components` drops the list. Empty `prior_identification_data` is treated as "strip the placeholder" at the builder level.

```
+---------------------+     +-----------------------+     +------------------+
|   React SPA         |     |   FastAPI backend     |     |   Google Gemini  |
|                     |     |                       |     |                  |
|  ItemV2.jsx         |     |  analyze_image_       |     |  models.         |
|   (poll 3s)         |     |  background()         |---->|  generate_       |
|                     |<====|                       |     |  content()       |
|                     | JSON| analyze_comp_id_...() |     |                  |
+---------------------+     +-----------------------+     +------------------+
                                  │
                                  ▼
                            +-------------------+
                            |  Postgres         |
                            |  result_gemini    |
                            |  .identification_ |
                            |  data             |
                            +-------------------+
```

## Data Model

### Personalization Store

A per-user BM25 corpus lives in `personalized_food_descriptions` (see [Personalized Food Index](./personalized_food_index.md)). Phase 1.1.1 reads from this table before the Gemini component-ID call and inserts a new row after the search (see the [Phase 1.1.1](#phase-111--fast-caption--reference-retrieval) sub-section above). The `reference_image` key on `result_gemini` is the link from this pipeline to the foundation table; Stage 3 (Phase 1.1.2) will start consuming that key to attach a second image + reference block to the Pro call.

**`DishImageQuery.result_gemini`** — JSON blob. After Phase 1:

```json
{
  "phase": 1,
  "identification_data": {
    "dish_predictions": [
      {"name": "Burger with Fries", "confidence": 0.92},
      {"name": "Cheeseburger Plate", "confidence": 0.71}
    ],
    "components": [
      {
        "component_name": "Beef Burger",
        "serving_sizes": ["1 burger", "200 g", "1 small burger"],
        "predicted_servings": 1.0
      },
      {
        "component_name": "French Fries",
        "serving_sizes": ["1 small serving (80 g)", "1 medium serving (120 g)"],
        "predicted_servings": 1.0
      }
    ],
    "input_token": 1840,
    "output_token": 612,
    "model": "gemini-2.5-pro",
    "price_usd": 0.0084,
    "analysis_time": 6.213
  },
  "nutrition_data": null,
  "identification_confirmed": false,
  "iterations": [
    {
      "iteration_number": 1,
      "created_at": "2026-04-13T12:34:56.789Z",
      "phase": 1,
      "identification_data": { ... same as above ... },
      "nutrition_data": null,
      "metadata": {}
    }
  ],
  "current_iteration": 1
}
```

The Pydantic schema enforced on the Gemini response is `ComponentIdentification` (`backend/src/service/llm/models/component_identification.py`):

| Field | Type | Constraints |
|-------|------|-------------|
| `dish_predictions[]` | `List[DishNamePrediction]` | min 1, max 5 |
| `dish_predictions[].name` | str | required |
| `dish_predictions[].confidence` | float | 0.0 ≤ x ≤ 1.0 |
| `components[]` | `List[ComponentServingPrediction]` | min 1, max 10 |
| `components[].component_name` | str | "individual dish" (not ingredient) |
| `components[].serving_sizes[]` | `List[str]` | min 1, max 5 |
| `components[].predicted_servings` | float | 0.01 ≤ x ≤ 10.0, default 1.0 |

### `identification_error` (failure path)

Written to `result_gemini.identification_error` by `persist_phase_error` when the background task catches an exception. Cleared on the next successful Phase 1 completion or by the retry-identification endpoint dispatch.

| Field | Type | Description |
|-------|------|-------------|
| `error_type` | `str` | One of `config_error \| image_missing \| parse_error \| api_error \| unknown` |
| `message` | `str` | Pre-canned, user-facing string from `ERROR_USER_MESSAGE` |
| `occurred_at` | `str` | ISO-8601 UTC timestamp |
| `retry_count` | `int` | 0 on first failure; incremented by retry-identification each manual retry |

If `result_gemini` was `NULL` at the time of failure, the helper initializes it as `{"phase": 0, "identification_data": null, "identification_error": {...}}`.

## Pipeline

```
api/date.py: upload_dish() → BackgroundTasks.add_task(
  analyze_image_background, query.id, str(file_path))
  │
  ▼
analyze_image_background(query_id, file_path)
  │
  ▼
[Phase 1.1.1] resolve_reference_for_upload(user_id, query_id, file_path)
  │                                    (see Architecture → Phase 1.1.1 above)
  ▼ writes result_gemini.reference_image BEFORE the Pro call
  │
  ▼
get_component_identification_prompt()
  ──> read backend/resources/prompts/component_identification.md
  │
  ▼
analyze_component_identification_async(
    image_path, prompt,
    gemini_model="gemini-2.5-pro",
    thinking_budget=-1)
  │
  ├──> os.environ["GEMINI_API_KEY"] (ValueError if unset)
  ├──> open(image_path, "rb")  →  types.Part.from_bytes(..., mime="image/jpeg")
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
        response_schema=ComponentIdentification,
        temperature=0,
        thinking_config=ThinkingConfig(thinking_budget=-1)))
  │
  ▼
response.parsed.model_dump()  (fallback: json.loads(response.text))
  │
  ▼
Validate dish_predictions + components keys present
  │
  ▼
extract_token_usage(response, "gemini") → (input_tok, output_tok)
  │
  ▼
enrich_result_with_metadata(result, model, start_time)
  ├──> result["model"] = "gemini-2.5-pro"
  ├──> result["price_usd"] = compute_price_usd(...)
  └──> result["analysis_time"] = round(now - start, 3)
  │
  ▼
update_dish_image_query_results(
    query_id,
    result_openai=None,
    result_gemini={phase:1, identification_data, nutrition_data:null,
                   identification_confirmed:false,
                   iterations:[{iteration_number:1, phase:1, identification_data, ...}],
                   current_iteration:1})
  │
  ▼
(On exception → persist_phase_error(query_id, exc, retry_count, "identification_error"):
   classify → write result_gemini.identification_error)

---- Retry path ----

POST /api/item/{record_id}/retry-identification   (item_retry.py)
  │
  ├── auth + ownership checks
  ├── guard: result_gemini.identification_data is null   (Phase 1 not yet succeeded)
  ├── guard: result_gemini.identification_error present  (else 400 — "nothing to retry")
  ├── guard: image file still on disk
  ├── clear result_gemini.identification_error
  ├── persist cleared blob
  └── BackgroundTasks.add_task(
        analyze_image_background, record_id, str(image_path), retry_count + 1)

---- Frontend side ----

ItemV2.jsx (via useItemPolling hook)
  │
  ▼
apiService.getItem(recordId) every 3 s (setInterval)
  │
  ▼
if result_gemini == null:                                    → keep polling
if result_gemini.identification_error:                       → stop polling, render PhaseErrorCard
if result_gemini.phase == 1 && !identification_confirmed:    → stop polling, render IdentificationComponentEditor
```

## Algorithms

### Gemini call settings

- `model = "gemini-2.5-pro"` (hardcoded at the call site).
- `temperature = 0` for deterministic output.
- `thinking_budget = -1` enables unbounded thinking tokens (billed under `thoughts_token_count`).
- `response_mime_type = "application/json"` + `response_schema = ComponentIdentification` forces structured JSON — `response.parsed` gives a typed Pydantic instance.
- `json.loads(response.text)` is a fallback path if `response.parsed` is unexpectedly empty.

### Token accounting

- `extract_token_usage(response, "gemini")` reads `response.usage_metadata` (the Google SDK's container) and returns `(prompt_token_count, candidates_token_count + thoughts_token_count)`.
- Output tokens therefore include the hidden thinking budget — cost is charged on the sum.

### Async execution

- The Gemini SDK is synchronous. The analyzer wraps the call in `loop.run_in_executor(None, _sync_gemini_call)` so the FastAPI event loop stays responsive while the model runs.

## Backend — API Layer

Phase 1 has **no dedicated HTTP endpoint** — it runs inside the `/api/date/{Y}/{M}/{D}/upload` handler via `BackgroundTasks`. The observable API surface for Phase 1 is:

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/item/{record_id}` | Frontend polls this to detect Phase 1 completion (success or error); returns the full record including `result_gemini` |
| POST | `/api/item/{record_id}/retry-identification` | Clears `identification_error`, increments `retry_count`, re-schedules `analyze_image_background`. 400 if Component Identification already complete or no prior error to retry. 404 if record not found or image file missing on disk. |

## Backend — Service Layer

- `api/item_identification_tasks.py`
  - `analyze_image_background(query_id, file_path, retry_count=0)` — Phase 1 background coroutine. Runs Phase 1.1.1 first (unless retry short-circuits on an existing personalization row), persists `result_gemini.reference_image`, then runs Phase 1.1.2. Imported by `date.py`'s upload endpoints and by `item_retry.py`'s `retry_identification_analysis`.
- `service/llm/fast_caption.py`
  - `generate_fast_caption_async(image_path) -> str` — Gemini 2.0 Flash plain-text wrapper. Temperature 0, no structured schema, no thinking budget. Raises `ValueError` on API failure or empty text; propagates `FileNotFoundError`.
- `service/personalized_reference.py`
  - `resolve_reference_for_upload(user_id, query_id, image_path) -> Optional[Dict]` — Phase 1.1.1 orchestrator. Composes `fast_caption + tokenize + search_for_user + insert_description_row` with graceful-degrade on caption failure and retry-idempotency short-circuit when a row already exists for this `query_id`.
- `service/llm/prompts.py`
  - `get_component_identification_prompt(reference=None) -> str` — loads `prompts/component_identification.md` and either substitutes the `__REFERENCE_BLOCK__` placeholder with a rendered block (when `reference['prior_identification_data']` is non-empty) or strips the placeholder line entirely.
  - `_render_reference_block(prior_identification_data) -> str` — module-private renderer; only emits sections for populated fields.
- `service/llm/gemini_analyzer.py`
  - `analyze_component_identification_async(..., reference_image_bytes=None)` — builds a two-image Gemini request when reference bytes are provided; identical to today when `None`.
- `api/item_identification_tasks.py`
  - `_resolve_reference_inputs(reference) -> (Optional[bytes], Optional[Dict])` — reads the reference image off disk (`IMAGE_DIR` + basename), enforces the four degrade paths in the Phase 1.1.2 decision matrix, logs WARN on missing file.
- `configs.py`
  - `THRESHOLD_PHASE_1_1_1_SIMILARITY = 0.25` — per-user BM25 top-1 floor. Rejects zero-overlap cases; the top hit is always 1.0 under max-in-batch normalization.
- `api/_phase_errors.py` — shared with Phase 2:
  - `classify_phase_error(exc)` — buckets exceptions into `config_error | image_missing | parse_error | api_error | unknown`.
  - `persist_phase_error(query_id, exc, retry_count, error_key)` — writes `error_key` (e.g. `identification_error`) into `result_gemini`; initializes the blob if it was `NULL`.
  - `ERROR_USER_MESSAGE` dict — single source of user-facing strings for each `error_type`.
- `api/item_retry.py#retry_identification_analysis` — POST endpoint handler that clears `identification_error`, increments `retry_count`, and re-schedules the background task.
- `service/llm/gemini_analyzer.py`
  - `analyze_component_identification_async(image_path, analysis_prompt, gemini_model, thinking_budget)` — the Phase 1 entry point.
  - `enrich_result_with_metadata(result, model, start_time)` — appends `model`, `price_usd`, `analysis_time`.
- `service/llm/prompts.py`
  - `get_component_identification_prompt()` — reads `backend/resources/prompts/component_identification.md`, raises `FileNotFoundError` if missing.
- `service/llm/pricing.py`
  - `compute_price_usd(model, vendor="gemini", input_tokens, output_tokens)` — applies `PRICING["gemini-2.5-pro"] = {input: 1.25, output: 10.00}` per 1 M tokens.
  - `extract_token_usage(response, "gemini")` — reads `usage_metadata.prompt_token_count` and `candidates_token_count + thoughts_token_count`.

## Backend — LLM Requests Layer

### Component Identification

Prompt structure (ASCII diagram):

```
+----------------------------------------------------------+
|  SYSTEM PROMPT                                           |
|  (backend/resources/prompts/component_identification.md) |
|  - Instruct Gemini to identify individual dishes         |
|    (not ingredient-level), return top 1-5 meal-name      |
|    predictions with confidence, and 1-10 components      |
|    with 3-5 serving-size options + predicted servings.   |
+----------------------------------------------------------+
|                                                          |
+----------------------------------------------------------+
|  USER PROMPT  (built by analyze_component_id_...)        |
|                                                          |
|  +----------------------------------------------------+  |
|  | Component 1 — full system prompt text              |  |
|  +----------------------------------------------------+  |
|  | Component 2 — image_part                           |  |
|  |   types.Part.from_bytes(                           |  |
|  |     data=<jpeg bytes>, mime="image/jpeg")          |  |
|  |   (≤384 px, RGB, JPEG — see Meal Upload)           |  |
|  +----------------------------------------------------+  |
+----------------------------------------------------------+
```

Output schema table:

**`ComponentIdentification`** — model `gemini-2.5-pro`, temperature 0, structured JSON (`response_mime_type=application/json`):

| Field | Type | Description |
|-------|------|-------------|
| `dish_predictions` | `List[DishNamePrediction]` | 1-5 overall meal-name candidates |
| `dish_predictions[].name` | `str` | Predicted meal name |
| `dish_predictions[].confidence` | `float` | 0.0-1.0 |
| `components` | `List[ComponentServingPrediction]` | 1-10 individual dishes detected in the image |
| `components[].component_name` | `str` | Name of the individual dish (not ingredient-level) |
| `components[].serving_sizes` | `List[str]` | 1-5 serving size candidates for this dish |
| `components[].predicted_servings` | `float` | 0.01-10.0, default 1.0 |

After receipt the analyzer appends these engineering fields to the same dict before persisting:

| Field | Type | Description |
|-------|------|-------------|
| `input_token` | `int` | `usage_metadata.prompt_token_count` |
| `output_token` | `int` | `candidates_token_count + thoughts_token_count` |
| `model` | `str` | e.g. `"gemini-2.5-pro"` |
| `price_usd` | `float` | `compute_price_usd(...)` rounded to 4 decimals |
| `analysis_time` | `float` | wall-clock seconds (3-decimal) |

## Backend — CRUD Layer

- `crud/dish_query_basic.update_dish_image_query_results(query_id, result_openai, result_gemini)` — Phase 1 writes this twice per run (once after Phase 1.1.1 to persist `reference_image`, once after Phase 1.1.2 success to merge `identification_data`). The error path writes via `persist_phase_error`. All three writes replace `result_gemini` wholesale by merging onto the current DB value.
- `crud/crud_personalized_food.get_row_by_query_id(query_id)` — retry-idempotency probe. Returns the row if one exists for this dish, `None` otherwise. Uses the existing `uq_personalized_food_descriptions_query_id` unique index.
- `crud/crud_personalized_food.insert_description_row(user_id, query_id, *, image_url, description, tokens, similarity_score_on_insert)` — Phase 1.1.1's write-after-read insert. Stage 0 CRUD; Stage 2 is the first caller.

## Frontend — Pages & Routes

- `/item/:recordId` → `pages/ItemV2.jsx` (shared with Phase 2; this page owns the polling loop).

## Frontend — Components

- `components/item/AnalysisLoading.jsx` — loading spinner shown while `pollingIdentification === true`.
- `components/item/PhaseErrorCard.jsx` — generic error card shared with Phase 2 (`headline` prop differentiates). Rendered when `result_gemini.identification_error` is present and `identification_data` is null. Hides the retry button for `error_type === "config_error"` and shows a "Try Anyway" warning at `retry_count >= 5` (soft cap).
- `components/item/IdentificationComponentEditor.jsx` — rendered once `identification_data` is present; the editor proper is documented on [User Customization](./user_customization.md). The "proposals view" portion (dish predictions list, per-component name/serving/count) is part of the same component.
- `components/item/PersonalizedDataCard.jsx` — research-only collapsible card rendered above `<IdentificationComponentEditor>` in the Component Identification view only. Reads `result_gemini.flash_caption` and `result_gemini.reference_image`. Collapsed by default; the chevron toggle reveals the flash caption and a link-wrapped reference row (thumbnail + description + `.toFixed(2)` similarity badge → `/item/{reference.query_id}`).

## Frontend — Services & Hooks

- `services/api.js#getItem(recordId)` — GET `/api/item/{id}`; returns the whole record including `result_gemini`.
- `services/api.js#retryIdentification(recordId)` — POST `/api/item/{id}/retry-identification`; called by `ItemV2.handleIdentificationRetry` from the error card.
- `hooks/useItemPolling.js` — owns the GET + 3-second polling lifecycle. Stops polling when any of: `identification_data`, `identification_error`, `nutrition_data`, `nutrition_error` lands, or when `phase === 1 && !identification_confirmed`.

## External Integrations

- **Google Gemini 2.5 Pro** via `google.genai.Client`. Requires `GEMINI_API_KEY` env var. Structured output is enforced at the SDK level via `response_schema=ComponentIdentification`. Errors are wrapped as `ValueError("Error calling Gemini API (Component Identification): ...")` and caught one level up by `analyze_image_background`, which logs and returns silently.

## Constraints & Edge Cases

- `GEMINI_API_KEY` missing → `ValueError` inside the background task; classified as `config_error` and persisted to `result_gemini.identification_error`. The frontend renders `PhaseErrorCard`; the retry button is hidden because retrying a missing API key won't fix anything.
- Prompt file missing → `FileNotFoundError`; classified as `image_missing` (or `unknown` depending on the error message). Same failure UI flow.
- Gemini returns a response the Pydantic schema can't parse → `response.parsed` is `None`, falls back to `json.loads(response.text)`. If that still fails → `ValueError`.
- Schema guard: the analyzer explicitly checks that `dish_predictions` and `components` keys exist in the parsed dict and raises if not — guards against the fallback path returning an unrelated JSON shape.
- `thinking_budget=-1` means Gemini can use unbounded thinking tokens. Cost per call is therefore unbounded in theory; in practice it's dominated by the `output` rate ($10/M tokens for pro).
- Gemini SDK is sync; `run_in_executor(None, ...)` uses the default thread pool. Burst uploads can exhaust the pool and serialize Phase 1 calls.
- Pricing table entries for `gemini-2.5-pro` are hardcoded in `pricing.py`. If the model is changed without updating the table, `normalize_model_key` falls back to `"gemini-2.5"` which returns `DEFAULT_PRICING` ($0.075 / $0.30 per M) — cost numbers will be silently wrong.

## Component Checklist

- [x] `generate_fast_caption_async()` — Gemini 2.0 Flash plain-text wrapper (`backend/src/service/llm/fast_caption.py`)
- [x] `resolve_reference_for_upload()` — Phase 1.1.1 orchestrator (`backend/src/service/personalized_reference.py`)
- [x] `analyze_image_background()` extended — Phase 1.1.1 call + `reference_image` persistence before the Pro call
- [x] `THRESHOLD_PHASE_1_1_1_SIMILARITY = 0.25` config constant (`backend/src/configs.py`)
- [x] `crud_personalized_food.get_row_by_query_id()` — retry-idempotency probe
- [x] Stage 3 (Phase 1.1.2): `reference_image` + `prior_identification_data` injected into the Component Identification Pro call
- [x] `get_component_identification_prompt(reference=None)` — `__REFERENCE_BLOCK__` substitute / strip
- [x] `analyze_component_identification_async(reference_image_bytes=None)` — optional second image part
- [x] `_resolve_reference_inputs()` — four-path degrade arbiter (`item_identification_tasks.py`)
- [x] `prompts/component_identification.md` — `__REFERENCE_BLOCK__` placeholder line
- [x] `analyze_image_background(query_id, file_path, retry_count=0)` — background task entry (lives in `item_identification_tasks.py`)
- [x] `_phase_errors.py` — `classify_phase_error`, `persist_phase_error`, `ERROR_USER_MESSAGE` (shared with Phase 2)
- [x] `POST /api/item/{record_id}/retry-identification` — `item_retry.py#retry_identification_analysis`
- [x] `PhaseErrorCard.jsx` — error UI with retry button + soft-cap warning (shared with Phase 2)
- [x] `useItemPolling.js` — polling hook with stop conditions for all four terminal states
- [x] `result_gemini.flash_caption` — current upload's Flash caption, written in the same pre-Pro write as `reference_image`
- [x] `PersonalizedDataCard.jsx` — research-only collapsible card on the Component Identification view
- [x] `apiService.retryIdentification()` — retry call
- [x] `analyze_component_identification_async()` — Gemini call with structured output
- [x] `get_component_identification_prompt()` — prompt loader
- [x] `ComponentIdentification` Pydantic schema
- [x] `DishNamePrediction`, `ComponentServingPrediction` Pydantic sub-schemas
- [x] `enrich_result_with_metadata()` — model / price / time stamps
- [x] `extract_token_usage()` + `compute_price_usd()` for Gemini
- [x] `update_dish_image_query_results()` CRUD write
- [x] `ItemV2.jsx` polling loop (3 s interval, stops on phase==1 unconfirmed)
- [x] `AnalysisLoading.jsx` — loading UI
- [x] `IdentificationComponentEditor.jsx` — renders AI proposals (editing covered in User Customization)
- [x] `apiService.getItem()` — frontend polling call

---

[Parent](./index.md) | [Next: User Customization >](./user_customization.md)
