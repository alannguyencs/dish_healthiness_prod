# Discussion — Is "Photo-Based Dish Analysis" Done?

**Question:** Check whether the feature item is implemented:
> **Photo-Based Dish Analysis**: The AI agent analyzes an uploaded **dish image** directly, using multimodal vision to assess what food is present.

**Verdict:** **Yes — Done.**

This feature item describes the very first stage of the existing two-phase dish analysis pipeline. It is fully documented at both abstract and technical levels, and the source files cited in the technical doc all exist on disk.

---

## Where it lives in the docs

- **Abstract:** [`docs/abstract/dish_analysis/component_identification.md`](../abstract/dish_analysis/component_identification.md) — `Status: Done`. All 5 acceptance criteria are checked off.
- **Technical:** [`docs/technical/dish_analysis/component_identification.md`](../technical/dish_analysis/component_identification.md) — every item in the Component Checklist is `[x]`.

The "Photo-Based Dish Analysis" line in `docs/issues/260414.md` maps cleanly onto **Phase 1 / Component Identification** of the dish analysis workflow. The same code path also feeds the other Phase-1 items in the checklist (Automatic Dish Identification, Dish name recognition, Individual-dish breakdown, Portion size suggestions, Predicted number of portions).

## Pipeline (Current State)

### Current State

```
[User] Upload meal photo
   │
   │   Meal Upload page POSTs multipart image
   │
   ▼
[Backend] api/date.py:upload_dish()
   │
   │   creates DishImageQuery row, adds BackgroundTasks
   │
   ▼
[Backend] analyze_image_background(query_id, file_path)
   │
   ▼
[Backend] analyze_step1_component_identification_async(...)
   │
   │   - reads backend/resources/step1_component_identification.md
   │   - sends prompt + image bytes to Gemini 2.5 Pro
   │     (response_schema = Step1ComponentIdentification, temperature=0)
   │
   ▼
[Gemini] Multimodal vision call returns structured JSON
   │
   ▼
[Backend] enrich_result_with_metadata() → model, price, time
   │
   ▼
[Backend] update_dish_image_query_results(...)
   │
   │   writes result_gemini.step1_data, leaves step1_confirmed=false
   │
   ▼
[Frontend] ItemV2.jsx polls GET /api/item/{id} every 3 s
   │
   │   stops polling when step==1 && !step1_confirmed
   │
   ▼
[Frontend] Step1ComponentEditor.jsx renders dish predictions + components
```

### New State

_Pending comments._

## Code grounding

Cross-checked the technical doc against the repo:

- `backend/src/api/date.py:38` — `analyze_image_background(query_id, file_path)` exists.
- `backend/src/api/date.py:198, 288` — `background_tasks.add_task(analyze_image_background, ...)` is wired on both upload paths.
- `backend/src/service/llm/gemini_analyzer.py` — contains `analyze_step1_component_identification_async`.
- `backend/src/service/llm/models.py` — `Step1ComponentIdentification` schema (1–5 dish predictions, 1–10 components).
- `backend/src/service/llm/prompts.py` — `get_step1_component_identification_prompt()` reads `backend/resources/step1_component_identification.md` (file present).
- `frontend/src/pages/ItemV2.jsx` — polling loop and Step 1 editor mount.

No gaps found between docs and code for this specific item.

## What "Photo-Based Dish Analysis" actually delivers today

Per the technical doc and source:

- Direct multimodal vision call: image bytes (`types.Part.from_bytes(..., mime="image/jpeg")`) sent alongside the system prompt to `gemini-2.5-pro`.
- Structured output enforced by Pydantic `Step1ComponentIdentification` (no free-text parsing).
- `temperature=0`, `thinking_budget=-1` (unbounded thinking tokens).
- Cost + token usage tracked per call (`compute_price_usd`, `extract_token_usage`).
- Runs as a FastAPI `BackgroundTasks` coroutine — non-blocking for the upload response.
- Frontend reflects completion via 3 s polling on `GET /api/item/{id}`.

## Caveats worth noting

These are real but they don't invalidate "Done" status; they're operational concerns documented in the tech doc's Constraints & Edge Cases:

- If `GEMINI_API_KEY` is unset, the background task raises and the frontend polls forever.
- If `gemini-2.5-pro` is swapped to an unknown key, `pricing.py` silently falls back to a default rate — cost numbers may be wrong.
- Gemini SDK is sync, wrapped in `run_in_executor`; burst uploads can serialize on the default thread pool.

## Suggestion for the checklist

Since this single line in `docs/issues/260414.md` is satisfied by the existing Phase 1 implementation, you can tick it:

```markdown
- [x] **Photo-Based Dish Analysis**: ...
```

Several other unchecked items in the same file are also covered by Phase 1 / 2 already (e.g. Automatic Dish Identification, Dish name recognition, Individual-dish breakdown, Portion size suggestions, Predicted number of portions, the macro/micronutrient estimations, the manual correction items, and the calendar / meal upload items). If you'd like, I can do the same per-item grounding and tick off everything that is already shipped.

## Next Steps

- Tick `Photo-Based Dish Analysis` in `docs/issues/260414.md`.
- (Optional) Ask me to run the same check for the rest of the items in `260414.md` and update their checkboxes in one pass.
- Use `/feature-update` only if you want to change Phase 1 behavior (e.g., swap models, add language support, expose confidence on components).
