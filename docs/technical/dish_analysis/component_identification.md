# Component Identification — Technical Design

[Parent](./index.md) | [Next: User Customization >](./user_customization.md)

## Related Docs
- Abstract: [abstract/dish_analysis/component_identification.md](../../abstract/dish_analysis/component_identification.md)

## Architecture

Phase 1 is a single Gemini vision call triggered as a FastAPI `BackgroundTasks` coroutine immediately after `Meal Upload` creates the row. The task lives in `backend/src/api/item_step1_tasks.py` (relocated from `date.py` to keep that file under the 300-line cap). On success it writes the structured output into `result_gemini.step1_data` and leaves `step1_confirmed=false` so the frontend poller can pick it up and route the user into the editor. On failure it classifies the exception and persists `result_gemini.step1_error` via the shared `persist_phase_error` helper in `src.api._phase_errors`; the frontend stops polling and renders `<PhaseErrorCard>` with a retry button.

```
+---------------------+     +-----------------------+     +------------------+
|   React SPA         |     |   FastAPI backend     |     |   Google Gemini  |
|                     |     |                       |     |                  |
|  ItemV2.jsx         |     |  analyze_image_       |     |  models.         |
|   (poll 3s)         |     |  background()         |---->|  generate_       |
|                     |<====|                       |     |  content()       |
|                     | JSON|  analyze_step1_...()  |     |                  |
+---------------------+     +-----------------------+     +------------------+
                                  │
                                  ▼
                            +----------------+
                            |  Postgres      |
                            |  result_gemini |
                            |  .step1_data   |
                            +----------------+
```

## Data Model

### Personalization Store (foundation, not yet consumed)

A separate per-user BM25 corpus lives in `personalized_food_descriptions` (see [Personalized Food Index](./personalized_food_index.md)). Phase 1.1.1 — when it lands in a later stage — will read from this table before the Gemini call and insert a new row after it. Today the table exists but nothing in this pipeline writes to or reads from it; the forward reference is here so reviewers of later stages can locate the shared foundation.

**`DishImageQuery.result_gemini`** — JSON blob. After Phase 1:

```json
{
  "step": 1,
  "step1_data": {
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
  "step2_data": null,
  "step1_confirmed": false,
  "iterations": [
    {
      "iteration_number": 1,
      "created_at": "2026-04-13T12:34:56.789Z",
      "step": 1,
      "step1_data": { ... same as above ... },
      "step2_data": null,
      "metadata": {}
    }
  ],
  "current_iteration": 1
}
```

The Pydantic schema enforced on the Gemini response is `Step1ComponentIdentification` (`backend/src/service/llm/models.py`):

| Field | Type | Constraints |
|-------|------|-------------|
| `dish_predictions[]` | `List[DishNamePrediction]` | min 1, max 5 |
| `dish_predictions[].name` | str | required |
| `dish_predictions[].confidence` | float | 0.0 ≤ x ≤ 1.0 |
| `components[]` | `List[ComponentServingPrediction]` | min 1, max 10 |
| `components[].component_name` | str | "individual dish" (not ingredient) |
| `components[].serving_sizes[]` | `List[str]` | min 1, max 5 |
| `components[].predicted_servings` | float | 0.01 ≤ x ≤ 10.0, default 1.0 |

### `step1_error` (failure path)

Written to `result_gemini.step1_error` by `persist_phase_error` when the background task catches an exception. Cleared on the next successful Phase 1 completion or by the retry-step1 endpoint dispatch.

| Field | Type | Description |
|-------|------|-------------|
| `error_type` | `str` | One of `config_error \| image_missing \| parse_error \| api_error \| unknown` |
| `message` | `str` | Pre-canned, user-facing string from `ERROR_USER_MESSAGE` |
| `occurred_at` | `str` | ISO-8601 UTC timestamp |
| `retry_count` | `int` | 0 on first failure; incremented by retry-step1 each manual retry |

If `result_gemini` was `NULL` at the time of failure, the helper initializes it as `{"step": 0, "step1_data": null, "step1_error": {...}}`.

## Pipeline

```
api/date.py: upload_dish() → BackgroundTasks.add_task(
  analyze_image_background, query.id, str(file_path))
  │
  ▼
analyze_image_background(query_id, file_path)
  │
  ▼
get_step1_component_identification_prompt()
  ──> read backend/resources/step1_component_identification.md
  │
  ▼
analyze_step1_component_identification_async(
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
        response_schema=Step1ComponentIdentification,
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
    result_gemini={step:1, step1_data, step2_data:null,
                   step1_confirmed:false,
                   iterations:[{iteration_number:1, step:1, step1_data, ...}],
                   current_iteration:1})
  │
  ▼
(On exception → persist_phase_error(query_id, exc, retry_count, "step1_error"):
   classify → write result_gemini.step1_error)

---- Retry path ----

POST /api/item/{record_id}/retry-step1   (item_retry.py)
  │
  ├── auth + ownership checks
  ├── guard: result_gemini.step1_data is null   (Phase 1 not yet succeeded)
  ├── guard: result_gemini.step1_error present  (else 400 — "nothing to retry")
  ├── guard: image file still on disk
  ├── clear result_gemini.step1_error
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
if result_gemini == null:                        → keep polling
if result_gemini.step1_error:                    → stop polling, render PhaseErrorCard
if result_gemini.step == 1 && !step1_confirmed:  → stop polling, render Step1ComponentEditor
```

## Algorithms

### Gemini call settings

- `model = "gemini-2.5-pro"` (hardcoded at the call site).
- `temperature = 0` for deterministic output.
- `thinking_budget = -1` enables unbounded thinking tokens (billed under `thoughts_token_count`).
- `response_mime_type = "application/json"` + `response_schema = Step1ComponentIdentification` forces structured JSON — `response.parsed` gives a typed Pydantic instance.
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
| POST | `/api/item/{record_id}/retry-step1` | Clears `step1_error`, increments `retry_count`, re-schedules `analyze_image_background`. 400 if Step 1 already complete or no prior error to retry. 404 if record not found or image file missing on disk. |

## Backend — Service Layer

- `api/item_step1_tasks.py`
  - `analyze_image_background(query_id, file_path, retry_count=0)` — Phase 1 background coroutine. Imported by `date.py`'s upload endpoints and by `item_retry.py`'s `retry_step1_analysis`.
- `api/_phase_errors.py` — shared with Phase 2:
  - `classify_phase_error(exc)` — buckets exceptions into `config_error | image_missing | parse_error | api_error | unknown`.
  - `persist_phase_error(query_id, exc, retry_count, error_key)` — writes `error_key` (e.g. `step1_error`) into `result_gemini`; initializes the blob if it was `NULL`.
  - `ERROR_USER_MESSAGE` dict — single source of user-facing strings for each `error_type`.
- `api/item_retry.py#retry_step1_analysis` — POST endpoint handler that clears `step1_error`, increments `retry_count`, and re-schedules the background task.
- `service/llm/gemini_analyzer.py`
  - `analyze_step1_component_identification_async(image_path, analysis_prompt, gemini_model, thinking_budget)` — the Phase 1 entry point.
  - `enrich_result_with_metadata(result, model, start_time)` — appends `model`, `price_usd`, `analysis_time`.
- `service/llm/prompts.py`
  - `get_step1_component_identification_prompt()` — reads `backend/resources/step1_component_identification.md`, raises `FileNotFoundError` if missing.
- `service/llm/pricing.py`
  - `compute_price_usd(model, vendor="gemini", input_tokens, output_tokens)` — applies `PRICING["gemini-2.5-pro"] = {input: 1.25, output: 10.00}` per 1 M tokens.
  - `extract_token_usage(response, "gemini")` — reads `usage_metadata.prompt_token_count` and `candidates_token_count + thoughts_token_count`.

## Backend — LLM Requests Layer

### Step 1 Component Identification

Prompt structure (ASCII diagram):

```
+----------------------------------------------------------+
|  SYSTEM PROMPT                                           |
|  (backend/resources/step1_component_identification.md)   |
|  - Instruct Gemini to identify individual dishes         |
|    (not ingredient-level), return top 1-5 meal-name      |
|    predictions with confidence, and 1-10 components      |
|    with 3-5 serving-size options + predicted servings.   |
+----------------------------------------------------------+
|                                                          |
+----------------------------------------------------------+
|  USER PROMPT  (built by analyze_step1_...)               |
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

**`Step1ComponentIdentification`** — model `gemini-2.5-pro`, temperature 0, structured JSON (`response_mime_type=application/json`):

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

- `crud/dish_query_basic.update_dish_image_query_results(query_id, result_openai, result_gemini)` — the only write made by Phase 1. Replaces `result_gemini` wholesale.

## Frontend — Pages & Routes

- `/item/:recordId` → `pages/ItemV2.jsx` (shared with Phase 2; this page owns the polling loop).

## Frontend — Components

- `components/item/AnalysisLoading.jsx` — loading spinner shown while `pollingStep1 === true`.
- `components/item/PhaseErrorCard.jsx` — generic error card shared with Phase 2 (`headline` prop differentiates). Rendered when `result_gemini.step1_error` is present and `step1_data` is null. Hides the retry button for `error_type === "config_error"` and shows a "Try Anyway" warning at `retry_count >= 5` (soft cap).
- `components/item/Step1ComponentEditor.jsx` — rendered once `step1_data` is present; the editor proper is documented on [User Customization](./user_customization.md). The "proposals view" portion (dish predictions list, per-component name/serving/count) is part of the same component.

## Frontend — Services & Hooks

- `services/api.js#getItem(recordId)` — GET `/api/item/{id}`; returns the whole record including `result_gemini`.
- `services/api.js#retryStep1(recordId)` — POST `/api/item/{id}/retry-step1`; called by `ItemV2.handleStep1Retry` from the error card.
- `hooks/useItemPolling.js` — owns the GET + 3-second polling lifecycle. Stops polling when any of: `step1_data`, `step1_error`, `step2_data`, `step2_error` lands, or when `step === 1 && !step1_confirmed`.

## External Integrations

- **Google Gemini 2.5 Pro** via `google.genai.Client`. Requires `GEMINI_API_KEY` env var. Structured output is enforced at the SDK level via `response_schema=Step1ComponentIdentification`. Errors are wrapped as `ValueError("Error calling Gemini API (Step 1): ...")` and caught one level up by `analyze_image_background`, which logs and returns silently.

## Constraints & Edge Cases

- `GEMINI_API_KEY` missing → `ValueError` inside the background task; classified as `config_error` and persisted to `result_gemini.step1_error`. The frontend renders `PhaseErrorCard`; the retry button is hidden because retrying a missing API key won't fix anything.
- Prompt file missing → `FileNotFoundError`; classified as `image_missing` (or `unknown` depending on the error message). Same failure UI flow.
- Gemini returns a response the Pydantic schema can't parse → `response.parsed` is `None`, falls back to `json.loads(response.text)`. If that still fails → `ValueError`.
- Schema guard: the analyzer explicitly checks that `dish_predictions` and `components` keys exist in the parsed dict and raises if not — guards against the fallback path returning an unrelated JSON shape.
- `thinking_budget=-1` means Gemini can use unbounded thinking tokens. Cost per call is therefore unbounded in theory; in practice it's dominated by the `output` rate ($10/M tokens for pro).
- Gemini SDK is sync; `run_in_executor(None, ...)` uses the default thread pool. Burst uploads can exhaust the pool and serialize Phase 1 calls.
- Pricing table entries for `gemini-2.5-pro` are hardcoded in `pricing.py`. If the model is changed without updating the table, `normalize_model_key` falls back to `"gemini-2.5"` which returns `DEFAULT_PRICING` ($0.075 / $0.30 per M) — cost numbers will be silently wrong.

## Component Checklist

- [x] `analyze_image_background(query_id, file_path, retry_count=0)` — background task entry (lives in `item_step1_tasks.py`)
- [x] `_phase_errors.py` — `classify_phase_error`, `persist_phase_error`, `ERROR_USER_MESSAGE` (shared with Phase 2)
- [x] `POST /api/item/{record_id}/retry-step1` — `item_retry.py#retry_step1_analysis`
- [x] `PhaseErrorCard.jsx` — error UI with retry button + soft-cap warning (shared with Phase 2)
- [x] `useItemPolling.js` — polling hook with stop conditions for all four terminal states
- [x] `apiService.retryStep1()` — retry call
- [x] `analyze_step1_component_identification_async()` — Gemini call with structured output
- [x] `get_step1_component_identification_prompt()` — prompt loader
- [x] `Step1ComponentIdentification` Pydantic schema
- [x] `DishNamePrediction`, `ComponentServingPrediction` Pydantic sub-schemas
- [x] `enrich_result_with_metadata()` — model / price / time stamps
- [x] `extract_token_usage()` + `compute_price_usd()` for Gemini
- [x] `update_dish_image_query_results()` CRUD write
- [x] `ItemV2.jsx` polling loop (3 s interval, stops on step==1 unconfirmed)
- [x] `AnalysisLoading.jsx` — loading UI
- [x] `Step1ComponentEditor.jsx` — renders AI proposals (editing covered in User Customization)
- [x] `apiService.getItem()` — frontend polling call

---

[Parent](./index.md) | [Next: User Customization >](./user_customization.md)
