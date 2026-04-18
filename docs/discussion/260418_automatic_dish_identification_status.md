# Discussion — Is "Automatic Dish Identification" Done?

**Question:** Check whether the feature item is implemented:
> **Automatic Dish Identification**: It determines the most likely **dish name** by combining image evidence with structured nutrition database matches.

**Verdict:** **Done — functionally**, with one caveat about the marketing wording (no structured nutrition database lookup is performed; identification is purely vision-based).

---

## Where it lives in the docs

- **Abstract:** [`docs/abstract/dish_analysis/component_identification.md`](../abstract/dish_analysis/component_identification.md) — `Status: Done`. Acceptance criterion "up to 5 dish name predictions with their confidence scores" is checked.
- **Technical:** [`docs/technical/dish_analysis/component_identification.md`](../technical/dish_analysis/component_identification.md) — Component Checklist for the `Step1ComponentIdentification` schema (which holds `dish_predictions`) is `[x]`.

This item is delivered by the same Phase 1 / Component Identification pipeline as the previous checkbox.

## What's actually implemented

### Backend

- `backend/src/service/llm/models.py:16-26` — `DishNamePrediction(name: str, confidence: float ∈ [0,1])`.
- `backend/src/service/llm/models.py:78-` — `Step1ComponentIdentification.dish_predictions: List[DishNamePrediction]` with `min_length=1, max_length=5`.
- `backend/resources/step1_component_identification.md` — Task 1 of the Gemini system prompt explicitly instructs the model to:
  - "Generate the top 1-5 most likely meal names based on visual analysis, ranked by confidence."
  - Each prediction returns `name` + `confidence ∈ [0.0, 1.0]`, ordered highest first.
- `backend/src/service/llm/gemini_analyzer.py` — `analyze_step1_component_identification_async(...)` runs the Gemini 2.5 Pro call with `response_schema=Step1ComponentIdentification`, so the dish-prediction list is contractually present in every successful response.

### Frontend

- `frontend/src/components/item/Step1ComponentEditor.jsx:13` — destructures `dish_predictions` from `step1Data`.
- `frontend/src/components/item/Step1ComponentEditor.jsx:21` — defaults the selected name to `dish_predictions[0]?.name` (the highest-confidence prediction).
- `frontend/src/components/item/Step1ComponentEditor.jsx:165-177` — passes the predictions into `<DishNameSelector>` with show-all toggle so the user can pick any of the up-to-5 candidates.
- The user can also override with a custom name (covered by the next checkbox, "Set the dish name").

## Pipeline (Current State)

### Current State

```
[Backend] Phase 1 Gemini call (image + step1 prompt)
   │
   │   response_schema=Step1ComponentIdentification
   │
   ▼
[Gemini] Returns up to 5 dish_predictions, ranked by confidence
   │
   ▼
[Backend] Persist to result_gemini.step1_data.dish_predictions
   │
   ▼
[Frontend] Step1ComponentEditor reads dish_predictions
   │
   ├──> Default selectedDishName = dish_predictions[0].name
   │
   ▼
[User] Sees ranked dish names in DishNameSelector
   │
   │   can keep top suggestion, pick another, or type a custom one
   │
   ▼
[User] Confirms → POST /confirm-step1 with selected_dish_name
```

### New State

_Pending comments._

## The wording caveat

The issue item phrases the feature as "combining image evidence **with structured nutrition database matches**." The current implementation does **not** consult a structured nutrition database during dish-name prediction:

- Phase 1 is a single Gemini multimodal call with the image + prompt. No DB lookup, no retrieval, no external food API.
- Searched for `nutrition.*database`, `food.*database`, `USDA`, `FDC`, `nutritionix`, `edamam` — none of those appear anywhere in `backend/src/`. The only hits are inside the `step2_nutritional_analysis.md` prompt (and a few docs referencing MyFitnessPal-style serving sizes), and even there the database is conceptual (the LLM is told to act as if it knows nutrition values), not a real lookup.

Two ways to reconcile this:

1. **Treat the wording as marketing-level shorthand for "the model has nutritional knowledge baked in."** Functionally, the user gets a ranked list of dish-name predictions automatically, which is what the line is selling. → Mark as Done.
2. **Take the wording literally.** Then this item is partially done — predictions are produced, but there is no DB-backed retrieval step. → Either add a retrieval stage, or reword the line in `260414.md` to drop the DB phrase. → Leave unchecked until that decision is made.

The technical doc's own description of Phase 1 explicitly says it's vision-only, so the docs are internally consistent — the discrepancy is between the marketing PDF and the implementation.

## Recommendation

Mark this item as `[x]` since the functional outcome (automatic dish identification with up-to-5 ranked candidates and confidence scores) is fully implemented and exposed in the UI. If you want to honor the literal "structured nutrition database matches" wording later, that becomes a separate enhancement (RAG / nutrition DB retrieval) — track it under a new item rather than blocking this checkbox.

## Next Steps

- Tick `Automatic Dish Identification` in `docs/issues/260414.md`.
- (Optional) If the literal "DB-backed match" wording matters for client deliverables, add a follow-up item like "Add nutrition DB retrieval to dish-name prediction" and use `/feature-plan`.
- Continue down the checklist — Healthiness Category and Healthiness rationale are next, both produced in Phase 2.
