# Nutritional Analysis — Technical Design

[< Prev: User Customization](./user_customization.md) | [Parent](./index.md)

## Related Docs
- Abstract: [abstract/dish_analysis/nutritional_analysis.md](../../abstract/dish_analysis/nutritional_analysis.md)

## Architecture

Phase 2 is a second Gemini vision call scheduled as a `BackgroundTasks` coroutine the moment the confirm endpoint returns. The prompt is the Step 2 markdown file with the user's confirmed dish name and component list appended as a plain-text block. Output is enforced to `Step2NutritionalAnalysis` via the SDK `response_schema` parameter. The frontend continues polling the same item endpoint and renders the results when the payload arrives.

```
+---------------------+     +-----------------------+     +------------------+
|   React SPA         |     |   FastAPI backend     |     |   Google Gemini  |
|                     |     |                       |     |                  |
|  ItemV2.jsx         |     |  trigger_step2_       |     |  models.         |
|   (poll 3s)         |     |  analysis_background()|---->|  generate_       |
|  Step2Results.jsx   |<====|                       |     |  content()       |
|                     | JSON|  analyze_step2_...()  |     |                  |
+---------------------+     +-----------------------+     +------------------+
                                  │
                                  ▼
                            +----------------+
                            |  Postgres      |
                            |  result_gemini |
                            |  .step2_data   |
                            |  .step = 2     |
                            +----------------+
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
(Exceptions are caught and logged; task swallows them silently)

---- Frontend side ----

ItemV2.jsx poller (3 s)
  │
  ▼
GET /api/item/{id}
  │
  ▼
if result_gemini.step == 2 && result_gemini.step2_data:
    stopPolling(); render <Step2Results step2Data={step2_data} />
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

No dedicated Phase 2 HTTP endpoint. Observable API surface:

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/item/{record_id}` | Frontend polls; returns updated `result_gemini` once Phase 2 lands |

## Backend — Service Layer

- `api/item_tasks.py#trigger_step2_analysis_background(query_id, image_path, dish_name, components)` — the Phase 2 background coroutine. Catches and logs every exception.
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

- `components/item/AnalysisLoading.jsx` — shown while `pollingStep2 && !step2_data`.
- `components/item/Step2Results.jsx` — renders the confirmed dish name, the healthiness score with a category badge and rationale, the five core macros, the micronutrients list, and the model/cost/time footer.
- `components/item/ItemImage.jsx` / `ItemHeader.jsx` / `ItemNavigation.jsx` — chrome shared across the item page.

## Frontend — Services & Hooks

- `services/api.js#getItem(recordId)` — same polling call as Phase 1.
- Polling loop inside `ItemV2.jsx`: stops when `result_gemini.step === 2 && result_gemini.step2_data`.

## External Integrations

- **Google Gemini 2.5 Pro** — second call per record. Same SDK, same auth, same rate-limit and error handling story as Phase 1.

## Constraints & Edge Cases

- The background task catches every exception and logs it; a Gemini failure leaves `result_gemini.step = 1, step1_confirmed = true, step2_data = null`, and the frontend polls indefinitely. There is no retry, no surfaced error state.
- `record.result_gemini` is re-read before the write — if the record is deleted between confirm and Phase 2 the task returns early with a log.
- Image file deletion between Phase 1 and Phase 2: Phase 1's file is the one used; if it is gone, Gemini call fails and is logged (no explicit user-facing error).
- Pricing relies on the same `PRICING` table as Phase 1; unknown models fall back to `DEFAULT_PRICING` and report cost incorrectly.
- Gemini may exceed the thinking budget for complex plates, adding latency and cost; `thinking_budget=-1` does not cap this.
- No retries on transient 429 / 5xx from Gemini. A single failed call means the user sees a permanent "Calculating nutritional values..." state.
- Because there's no endpoint gating Phase 2 on top of Phase 1, a double-tap on Confirm can enqueue two Phase 2 tasks that both write the same key. Last writer wins.
- Healthiness-score category thresholds are UI-only (`Step2Results.jsx`) — changing them is a frontend edit; the API just returns the integer.

## Component Checklist

- [x] `trigger_step2_analysis_background()` — background task entry
- [x] `analyze_step2_nutritional_analysis_async()` — Gemini call with structured output
- [x] `get_step2_nutritional_analysis_prompt(dish_name, components)` — prompt loader + injection
- [x] `Step2NutritionalAnalysis` Pydantic schema
- [x] Required-field guard in analyzer
- [x] `enrich_result_with_metadata()` — model / price / time stamps
- [x] `update_dish_image_query_results()` — single DB write
- [x] Iteration bookkeeping in `trigger_step2_analysis_background`
- [x] `ItemV2.jsx` polling stop condition (`step==2 && step2_data`)
- [x] `AnalysisLoading.jsx` — Phase 2 loading UI
- [x] `Step2Results.jsx` — score badge, rationale, macros, micros, footer
- [x] `apiService.getItem()` — polling call
- [ ] Retry / error-state UI for Phase 2 failures
- [ ] Idempotency key or dedupe on Phase 2 background task scheduling

---

[< Prev: User Customization](./user_customization.md) | [Parent](./index.md)
