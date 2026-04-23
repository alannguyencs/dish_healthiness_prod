# End-to-End Workflow

[Parent](./index.md) | [Next: Component Identification >](./component_identification.md)

**Status:** Done

## Related Docs

- Technical pipelines overview: [technical/system_pipelines.md](../../technical/system_pipelines.md)
- Discussion (source of this diagram): [discussion/260418_food_db.md](../../discussion/260418_food_db.md)
- Technical feature pages:
  [Component Identification](../../technical/dish_analysis/component_identification.md) ·
  [User Customization](../../technical/dish_analysis/user_customization.md) ·
  [Nutritional Analysis](../../technical/dish_analysis/nutritional_analysis.md) ·
  [Personalized Food Index](../../technical/dish_analysis/personalized_food_index.md) ·
  [Nutrition DB](../../technical/dish_analysis/nutrition_db.md)

## Problem

Dish analysis is a multi-stage AI workflow: a fast caption, a reference retrieval against the user's own history, a component-identification pass, a user verification step, two parallel nutrition-lookup queries, the final Gemini analysis, and an optional user correction. Each stage is documented in its own feature page, but a reader who has not built the pipeline cannot easily picture how the pieces fit together or when each AI call fires.

## Solution

Provide a single cross-feature overview that traces one meal photo from the moment the user uploads it to the point where the user sees (and optionally edits) the final nutrition numbers. The diagram below names every phase, the service module that owns it, the JSONB key it writes on the `result_gemini` payload, and the hand-off contract between phases. It is the canonical "one picture of the whole flow" that every feature doc below links back to.

## User Flow

What the user experiences, top to bottom:

1. **Upload a meal photo.** The user picks a date on the calendar, picks a slot, and uploads (or pastes an image URL). The request returns immediately; the analysis runs in the background.
2. **Watch the Component Identification editor render.** Within a few seconds the Dish Analysis page shows an AI-proposed dish name, component list, and per-component serving-size options. If the user has uploaded a similar dish before, a small "Personalized Data (Research only)" card above the editor exposes the AI's short caption of the image and the prior match it retrieved.
3. **Confirm or edit the proposals.** The user accepts the AI name/components or types their own (custom dish name, different component count, adjusted servings). Clicking **Confirm and Analyze Nutrition** hands off to Phase 2.
4. **Watch the Nutritional Analysis card render.** After another few seconds the page shows the dish name, calories, fiber, carbs, protein, fat, micronutrients, and a healthiness label + rationale. A collapsed "Research only" panel below reveals the reasoning, top nutrition-DB matches, and the user's similar prior dishes when expanded.
5. **Optionally correct Nutritional Analysis.** The user clicks **Edit**, adjusts any macro, adds or removes micronutrients, rewrites the rationale, and saves. The corrected payload is both written back to the record and stored on the user's personalization row, so the next similar upload inherits the user-verified numbers.

## Diagram — one dish from upload to final result

The following ASCII diagram is the canonical end-to-end trace. **Phase 1** handles food identification and portion estimation. Its LLM Component Identification step (Phase 1.1) is itself a two-stage, reference-assisted pipeline: **Phase 1.1.1** sends the image to a fast LLM (Gemini 2.5 Flash) to produce a short description, BM25-retrieves the most similar past dish from this user's history, and stores the new image+description pair for future lookups; **Phase 1.1.2** then runs the main Gemini 2.5 Pro component ID with both the query image and the retrieved reference image, using the reference dish's prior result as a hint (not ground truth). **Phase 1.2** is user verification. **Phase 2** then handles dish nutrient analysis given the confirmed dish name and portion count, composed of three sub-steps: DB lookup, personalization lookup, and the Gemini image analysis that optionally integrates the first two when their confidence exceeds a threshold.

```
  ┌────────────────────────────────────────────────────────────────────────┐
  │                            USER (browser)                              │
  └──┬────────────────────────────────────────────────────────────▲────────┘
     │ POST /date/upload                                          │ HTTP 200
     │    (dish image, target_date, dish_position)                │ result_gemini JSONB
     ▼                                                            │
  ┌────────────────────────────────────────────────────────────────────────┐
  │                 FastAPI — upload + read endpoints                       │
  │        backend/src/api/date.py  ·  backend/src/api/item.py              │
  │  • persist image + DishImageQuery row  (result_gemini = NULL)           │
  │  • kick off Phase 1.1.1  (asyncio.create_task, not awaited)             │
  └──┬─────────────────────────────────────────────────────────────────────┘
     │
     ▼
  ──────────────────────────────────────────────────────────────────────────
   PHASE 1 — Food Identification & Portion Estimation
  ──────────────────────────────────────────────────────────────────────────

   ┄┄ PHASE 1.1 — LLM Component Identification  (reference-assisted) ┄┄

  ╔══════════════════════════════════════════════════════════════════════╗
  ║  PHASE 1.1.1 — Fast Captioning + Personalized Reference Retrieval     ║
  ║  backend/src/service/personalized_reference.py     (orchestrator)     ║
  ║  backend/src/service/llm/fast_caption.py           (LLM call)         ║
  ║  backend/src/service/personalized_food_index.py    (BM25 retrieval)   ║
  ║                                                                       ║
  ║  (a) fast LLM caption                                                 ║
  ║      • Model   : Gemini 2.5 Flash  (fast, cheap)                      ║
  ║      • Input   : user query image                                     ║
  ║      • Prompt  : backend/resources/prompts/fast_caption.md            ║
  ║      • Output  : short free-text food description                     ║
  ║                                                                       ║
  ║  (b) BM25 retrieval over THIS USER's history                          ║
  ║      • Pre-process description: NFKD normalize, lowercase,            ║
  ║        strip punctuation, tokenize                                    ║
  ║      • Query the per-user BM25 index built from rows of the           ║
  ║        personalized_food_descriptions table (scope = user_id)         ║
  ║      • Pick top-1 match with similarity ≥ threshold, else none        ║
  ║                                                                       ║
  ║  (c) persist for future lookups                                       ║
  ║      • INSERT (user_id, query_id, image_url, description, tokens)     ║
  ║        into personalized_food_descriptions  (one row per upload)      ║
  ║                                                                       ║
  ║  Writes result_gemini.reference_image =                               ║
  ║    { query_id, image_url, description, similarity_score,              ║
  ║      prior_identification_data } | null                               ║
  ║      (null on cold-start / below thresh)                              ║
  ╚══╤═══════════════════════════════════════════════════════════════════╝
     │ reference_image may be null
     ▼
  ╔══════════════════════════════════════════════════════════════════════╗
  ║  PHASE 1.1.2 — LLM Component Identification  (two-image, referenced)  ║
  ║  backend/src/api/item_identification_tasks.py      (orchestrator)     ║
  ║  backend/src/service/llm/identification_analyzer.py (LLM call)        ║
  ║  backend/src/service/llm/prompts.py                (prompt builder)   ║
  ║  • Model   : Gemini 2.5 Pro Dynamic Thinking                          ║
  ║  • Prompt  : backend/resources/prompts/component_identification.md    ║
  ║  • Input   :                                                          ║
  ║      – image A : user query image                                     ║
  ║      – image B : reference image from Phase 1.1.1  (if present)       ║
  ║      – text    : existing component_identification.md prompt          ║
  ║                  + a "Reference results" block carrying the reference ║
  ║                    dish's prior identification_data (dish_name,       ║
  ║                    components, servings) — framed as a HINT only,     ║
  ║                    since the two dishes may differ                    ║
  ║  • Output  : dish_name guess, component list, per-component serving   ║
  ║  • Writes  : result_gemini.identification_data ; phase = 1            ║
  ╚══╤═══════════════════════════════════════════════════════════════════╝
     │ frontend polls result_gemini.identification_data
     ▼
  ┌──────────────────────────────────────────────────────────────────────┐
  │  PHASE 1.2 — User Verification & Editing                               │
  │  frontend/src/pages/ItemV2.jsx   (component-confirmation UI)          │
  │  • User reviews LLM's dish_name guess + components + portion count    │
  │  • Edits dish name / components / serving sizes as needed             │
  │  • Submits  →  POST /item/{id}/confirm                                │
  │  • Endpoint writes result_gemini.identification_confirmed = true      │
  │       + confirmed dish_name and portion count into the iteration      │
  │  • UPDATE personalized_food_descriptions  (row inserted in 1.1.1c)    │
  │       SET confirmed_dish_name   = <user-confirmed dish name>,         │
  │           confirmed_portions    = <user-confirmed portion count>,     │
  │           confirmed_tokens      = BM25-tokenize(confirmed_dish_name)  │
  │       WHERE query_id = <this query_id>                                │
  │    → enriches the per-user BM25 corpus used by future 1.1.1(b)        │
  │      searches, so later uploads match against human-verified names    │
  │      rather than only the Flash-generated caption                     │
  └──┬───────────────────────────────────────────────────────────────────┘
     │ confirm endpoint schedules Phase 2 as a background task
     │ Phase-2 handoff contract: { confirmed dish_name, confirmed portions }
     ▼
  ──────────────────────────────────────────────────────────────────────────
   PHASE 2 — Dish Nutrient Analysis
   input contract: confirmed dish_name + confirmed portion count
  ──────────────────────────────────────────────────────────────────────────

  ╔══════════════════════════════════════════════════════════════════════╗      ╔══════════════════════════════════════════════════════════════════════╗
  ║  PHASE 2.1 — Nutrition DB Lookup                                       ║      ║  PHASE 2.2 — Personalization Lookup  (same BM25 path as 1.1.1b)       ║
  ║  backend/src/service/nutrition_db.py                                  ║      ║  backend/src/service/personalized_food_index.py   (reused)            ║
  ║                                                                       ║      ║                                                                       ║
  ║   ┌────────────────────────────────────────────┐                       ║      ║  • Query corpus : personalized_food_descriptions  (scope = user_id)  ║
  ║   │ Four BM25 indices held in memory (init-time)│                      ║      ║       — same per-user BM25 index that 1.1.1(b) searches              ║
  ║   │   ├ Anuvaad_INDB_2024.csv    (1,014 rows)   │                      ║      ║  • Query tokens : BM25-tokenize(image description from 1.1.1a)       ║
  ║   │   ├ ciqual_2020.csv          (3,186 rows)   │                      ║      ║                   unioned with the confirmed_dish_name from 1.2       ║
  ║   │   ├ malaysian_food_calories.csv (60 rows)   │                      ║      ║  • Retrieval    : top-K historical rows with similarity_score (0–1)  ║
  ║   │   └ myfcd_basic + myfcd_nutrients (233)     │                      ║      ║       — self-exclude the current query_id                            ║
  ║   │  source: backend/resources/database/        │                      ║      ║  • Join each hit back to its DishImageQuery row to pull prior        ║
  ║   └────────────────────────────────────────────┘                       ║      ║    nutrition_data (nutrient values + user manual corrections)        ║
  ║                                                                       ║      ║  • Empty result is a valid outcome (cold-start, no history)          ║
  ║  Combined weighted retrieval:                                         ║      ║  • Writes result_gemini.personalized_matches = [                      ║
  ║    dish_name + all component tokens in one query @ min_confidence=60  ║      ║      { query_id, image_url, description, similarity_score,           ║
  ║    dish_name tokens weighted 0.85; component tokens weighted 0.15    ║      ║        prior_nutrition_data }, ... ]                                  ║
  ║  Per-candidate confidence scoring  →  top-K with confidence_score     ║      ╚══╤═══════════════════════════════════════════════════════════════════╝
  ║  Writes result_gemini.nutrition_db_matches                            ║         │
  ╚══╤═══════════════════════════════════════════════════════════════════╝         │
     │                                                                              │
     └──────────────────────────────┐    ┌──────────────────────────────────────────┘
                                    ▼    ▼
                 (Phase 2.1 and Phase 2.2 run in parallel; both finish before Phase 2.3)
                                    │
                                    ▼
  ╔══════════════════════════════════════════════════════════════════════╗
  ║  PHASE 2.3 — Gemini Image Analysis  (final nutrient estimation)        ║
  ║  backend/src/api/item_tasks.py                     (orchestrator)     ║
  ║  backend/src/service/llm/nutrition_analyzer.py     (LLM call)         ║
  ║  backend/src/service/llm/prompts.py                (prompt builder)   ║
  ║  • Model   : Gemini 2.5 Pro Dynamic Thinking                          ║
  ║  • Prompt  : backend/resources/prompts/nutritional_analysis.md        ║
  ║  • System dish prompt explicitly instructs the LLM to take into       ║
  ║    account — when inferring nutrients — the dish's:                   ║
  ║      – cooking style     (e.g. deep-fried vs steamed vs grilled)      ║
  ║      – preparation method (e.g. battered, breaded, tempered, raw)     ║
  ║      – regional variant   (e.g. North-Indian vs South-Indian curry,   ║
  ║                              Hainanese vs Hakka chicken rice)         ║
  ║    and to reflect these in reasoning_* when they shift the estimate.  ║
  ║  • Input images:                                                      ║
  ║      – image A : user query image  (always)                           ║
  ║      – image B : reference image from the top-1 Phase 2.2 match,      ║
  ║                  attached only if its similarity_score ≥ threshold    ║
  ║                  (same pattern as Phase 1.1.2; dish may still differ, ║
  ║                   so the prompt frames image B as a HINT only)        ║
  ║  • Input text : confirmed dish_name + confirmed portion count         ║
  ║           + OPTIONAL reference blocks:                                ║
  ║               – Phase 2.1 top-K DB matches, included only if the top   ║
  ║                 confidence_score ≥ threshold  (e.g. 80%)              ║
  ║               – Phase 2.2 personalization matches, included only if   ║
  ║                 a historical similarity_score ≥ threshold             ║
  ║                 (when included, carry prior_nutrition_data per match) ║
  ║             When a block (or image B) is below threshold, it is       ║
  ║             omitted; the LLM falls back to image-only analysis and    ║
  ║             the reasoning_* fields explain which sources applied.     ║
  ║  • Output: dish_name, calories_kcal, carbs_g, protein_g, fat_g,       ║
  ║            fiber_g, micronutrients, healthiness_score + rationale,    ║
  ║            reasoning_* (which sources drove each number)              ║
  ║  • Writes result_gemini.nutrition_data ; phase = 2                    ║
  ╚══╤═══════════════════════════════════════════════════════════════════╝
     │
     │ frontend poll / websocket refresh (ItemV2.jsx)
     ▼
  ──────────────────────────────────────────────────────────────────────────
   PHASE 2.4 — User Review & Correction
   frontend/src/pages/ItemV2.jsx   (Nutritional Analysis item-detail view)
   Two side-by-side buttons drive two parallel paths; both converge on
   the Persistence box below.
  ──────────────────────────────────────────────────────────────────────────

  ┌──────────────────────────────────────────────────────────────────────┐      ┌──────────────────────────────────────────────────────────────────────┐
  │  Button A: "Manual Edit"                                              │      │  Button B: "AI Assistant Edit"  (prompt-driven correction, NEW)       │
  │  (direct field-by-field correction)                                   │      │                                                                       │
  │                                                                       │      │  Expands an inline text box where the user types a natural-language   │
  │  Flips every editable field into an input at once:                    │      │  context / preference hint, e.g.                                      │
  │     – Healthiness label + healthiness_rationale                       │      │     "I used high-quality oil and organic ingredients,                 │
  │     – Calories / Fiber / Carbs / Protein / Fat (g)                    │      │      so this should be healthier than the baseline."                  │
  │     – Micronutrients chips (add / remove, e.g. Iron, Folate, …)       │      │     "Portions are smaller than the AI estimated — about               │
  │                                                                       │      │      200 kcal per serving of fried chicken."                          │
  │  Save  →  POST /item/{id}/correction  with edited payload             │      │                                                                       │
  │           (no LLM call; direct write-through to Persistence below).   │      │  Submit  →  POST /item/{id}/ai-assistant-correction                   │
  │                                                                       │      │             body: { prompt: <user hint> }                             │
  │                                                                       │      │  • Backend loads result_gemini.nutrition_data (current baseline).     │
  │                                                                       │      │  • Gemini call: "revise baseline given user context"                  │
  │                                                                       │      │      – Model  : Gemini 2.5 Pro Dynamic Thinking                       │
  │                                                                       │      │      – Prompt : prompts/nutrition_assistant_correction.md             │
  │                                                                       │      │      – Input  : query image + trimmed baseline JSON + user hint       │
  │                                                                       │      │      – Output : revised NutritionalAnalysis JSON (same shape as       │
  │                                                                       │      │                 nutrition_data; changes explained in reasoning_*)     │
  │                                                                       │      │  • The revised payload is committed DIRECTLY (no preview, no          │
  │                                                                       │      │    Accept/Cancel step) via the same /correction persistence path,     │
  │                                                                       │      │    with ai_assistant_prompt = <user hint> stashed on the corrected    │
  │                                                                       │      │    payload for audit.                                                 │
  │                                                                       │      │  • UI re-renders with the new numbers as soon as the POST returns;    │
  │                                                                       │      │    user can re-submit a new hint or fall back to Button A.            │
  └──┬───────────────────────────────────────────────────────────────────┘      └──┬───────────────────────────────────────────────────────────────────┘
     │ save (manual path)                                                            │ submit (AI-assistant path)
     │                                                                               │
     │                (Button A and Button B are parallel                            │
     │                 user actions; either one commits                              │
     │                 via the same /correction endpoint)                            │
     │                                                                               │
     └──────────────────────────────────────┐    ┌───────────────────────────────────┘
                                            ▼    ▼
  ┌──────────────────────────────────────────────────────────────────────┐
  │  Persistence + read-only references  (both paths converge here)       │
  │                                                                       │
  │  • Endpoint writes result_gemini.nutrition_corrected = { healthiness, │
  │       healthiness_rationale, calories_kcal, fiber_g, carbs_g,         │
  │       protein_g, fat_g, micronutrients (, ai_assistant_prompt for     │
  │       Button B) } while preserving original nutrition_data for audit; │
  │       phase = 2                                                       │
  │  • UPDATE personalized_food_descriptions  (row inserted in 1.1.1c)    │
  │       SET corrected_nutrition_data = <final payload>                  │
  │       WHERE query_id = <this query_id>                                │
  │    → enriches future Phase 2.2 lookups: historical matches now carry  │
  │      user-verified nutrients rather than LLM-only estimates.          │
  │                                                                       │
  │  Read-only references (visible under either path, NOT editable):      │
  │     – Reasoning panel (which sources drove each number)               │
  │     – Top-5 Nutrition DB matches with confidence badges               │
  │     – Top personalization matches (past similar dishes)               │
  └──────────────────────────────────────────────────────────────────────┘

Legend:
   ┌── ──┐   FastAPI endpoint / frontend surface
   ╔══ ══╗   Background task (asyncio-scheduled, not awaited by HTTP caller)
   ──▶       Control / data flow
   phase counter on result_gemini JSONB advances 0 → 1 → 2, retried per phase
```

## Key invariants the diagram encodes

1. **Clean phase split.** Phase 1 is strictly about *what is this and how much of it?* (identification + portion count). Phase 2 is strictly about *given the confirmed dish and portion, what are the nutrients?* — the user never re-confirms anything between 2.1 / 2.2 / 2.3.
2. **Reference is a hint, not ground truth.** Phase 1.1.1's retrieved reference image + its prior `identification_data` are passed to Phase 1.1.2 as a second image + an explicit "Reference results" block. The prompt frames them as hints because the two dishes may differ; the LLM is expected to disagree when the query image doesn't match. Cold-start users simply have `reference_image = null` and Phase 1.1.2 runs single-image.
3. **Write-after-read for the personalized index.** Phase 1.1.1 reads the per-user BM25 index *before* it inserts the current image+description, so the current upload never matches itself. Inserting at the end also guarantees the next upload by the same user benefits from this one.
4. **Phase 2.1 and Phase 2.2 run in parallel** and both complete before Phase 2.3 fires. They write to independent JSONB keys (`nutrition_db_matches`, `personalized_matches`) so neither blocks the other, and either can be empty without breaking the pipeline.
5. **Threshold-gated integration.** Phase 2.3 is the single LLM call that produces the final numbers. DB matches and personalization are *references*, not *overrides* — each is only injected into the prompt if its top-confidence / top-similarity crosses a configurable threshold. Below threshold, the block is omitted so low-quality retrievals can't drag the estimate around.
6. **Phase independence.** Each phase reads from and writes to `result_gemini JSONB` and can be retried alone. A Phase 2.3 failure leaves `nutrition_db_matches` and `personalized_matches` intact, so a retry only re-runs the Gemini call.
7. **User corrections never replay Phase 1 or the retrievals.** Two correction paths exist on the Item view — **Manual Edit** writes the user's typed values straight through with no LLM call, while **AI Assistant Edit** re-runs a short Phase 2.3-lite Gemini call that revises the current `nutrition_data` against a free-text user hint and commits the revised payload directly (no preview / Accept-Cancel step). Both land in the same `nutrition_corrected` + `corrected_nutrition_data` shape and leave Phase 1 and the 2.1 / 2.2 retrieval artifacts untouched.

## Scope

- **Included:** every phase that fires between upload and the rendered Nutritional Analysis card (Phase 1.1.1, 1.1.2, 1.2, 2.1, 2.2, 2.3, 2.4), named with the module that owns it and the JSONB key it writes.
- **Not included:** the server lifecycle (login, calendar dashboard, meal upload date routing) — those live in their own abstract pages. The page also does not cover non-dish flows (re-analysis of legacy records, bulk ingestion).

## Acceptance Criteria

- [x] Every phase in the diagram has a corresponding technical doc or subsection under `docs/technical/dish_analysis/`.
- [x] Every JSONB key named in the diagram (`reference_image`, `identification_data`, `identification_confirmed`, `nutrition_db_matches`, `personalized_matches`, `nutrition_data`, `nutrition_corrected`) is produced by the running pipeline.
- [x] Every phase can be retried independently without corrupting the outputs of the others.

---

[Parent](./index.md) | [Next: Component Identification >](./component_identification.md)
