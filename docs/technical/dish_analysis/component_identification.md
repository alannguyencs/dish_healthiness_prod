# Component Identification — Technical Design

[Parent](./index.md) | [Next: User Customization >](./user_customization.md)

## Related Docs
- Abstract: [abstract/dish_analysis/component_identification.md](../../abstract/dish_analysis/component_identification.md)

## Architecture

Phase 1 is a single Gemini vision call triggered as a FastAPI `BackgroundTasks` coroutine immediately after `Meal Upload` creates the row. It writes the structured output into `result_gemini.step1_data` and leaves `step1_confirmed=false` so the frontend poller can pick it up and route the user into the editor.

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
(Any exception here is caught in analyze_image_background → log only)

---- Frontend side ----

ItemV2.jsx on mount
  │
  ▼
apiService.getItem(recordId) every 3 s (setInterval)
  │
  ▼
if result_gemini == null:                        → keep polling
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
| GET | `/api/item/{record_id}` | Frontend polls this to detect Phase 1 completion; returns the full record including `result_gemini` |

## Backend — Service Layer

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
- `components/item/Step1ComponentEditor.jsx` — rendered once `step1_data` is present; the editor proper is documented on [User Customization](./user_customization.md). The "proposals view" portion (dish predictions list, per-component name/serving/count) is part of the same component.

## Frontend — Services & Hooks

- `services/api.js#getItem(recordId)` — GET `/api/item/{id}`; returns the whole record including `result_gemini`.
- Polling is inline inside `ItemV2.jsx`: `setInterval(loadItem, 3000)` that clears itself when `result_gemini.step === 1 && !step1_confirmed` (or `step === 2 && step2_data`).

## External Integrations

- **Google Gemini 2.5 Pro** via `google.genai.Client`. Requires `GEMINI_API_KEY` env var. Structured output is enforced at the SDK level via `response_schema=Step1ComponentIdentification`. Errors are wrapped as `ValueError("Error calling Gemini API (Step 1): ...")` and caught one level up by `analyze_image_background`, which logs and returns silently.

## Constraints & Edge Cases

- `GEMINI_API_KEY` missing → `ValueError` inside the background task; the record stays at `result_gemini = NULL`, the frontend polls forever. **Same gap exists today on Phase 1 that Phase 2 already fixed via `step2_error` + retry endpoint** (see `nutritional_analysis.md`). A follow-up will mirror that pattern with `step1_error` + `POST /retry-step1`; tracked in `docs/issues/260414.md`.
- Prompt file missing → `FileNotFoundError`; same failure mode as above.
- Gemini returns a response the Pydantic schema can't parse → `response.parsed` is `None`, falls back to `json.loads(response.text)`. If that still fails → `ValueError`.
- Schema guard: the analyzer explicitly checks that `dish_predictions` and `components` keys exist in the parsed dict and raises if not — guards against the fallback path returning an unrelated JSON shape.
- `thinking_budget=-1` means Gemini can use unbounded thinking tokens. Cost per call is therefore unbounded in theory; in practice it's dominated by the `output` rate ($10/M tokens for pro).
- Gemini SDK is sync; `run_in_executor(None, ...)` uses the default thread pool. Burst uploads can exhaust the pool and serialize Phase 1 calls.
- Pricing table entries for `gemini-2.5-pro` are hardcoded in `pricing.py`. If the model is changed without updating the table, `normalize_model_key` falls back to `"gemini-2.5"` which returns `DEFAULT_PRICING` ($0.075 / $0.30 per M) — cost numbers will be silently wrong.

## Component Checklist

- [x] `analyze_image_background(query_id, file_path)` — background task entry
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
