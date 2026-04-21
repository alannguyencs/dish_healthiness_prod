# Discussion — Dish Recognition and Quantity Estimation (4 checkboxes)

**Question:** For each of the 4 items under "Dish Recognition and Quantity Estimation", decide Done / Not Done and list missing pieces:

1. Dish name recognition (≤5 names with likelihood)
2. Individual-dish breakdown (≤10 components)
3. Portion size suggestions (3-5 per component)
4. Predicted number of portions (per component)

**Verdict:** **All 4 are Done.** Every item is a property of the `Step1ComponentIdentification` schema, enforced by the Phase 1 Gemini call and consumed by `Step1ComponentEditor.jsx` / `DishNameSelector.jsx` / `ComponentListItem.jsx`.

These items overlap with the earlier "Photo-Based Dish Analysis" / "Automatic Dish Identification" checkboxes — same code path, different slice of the response.

---

## Where it lives in the docs

- **Abstract:** [`docs/abstract/dish_analysis/component_identification.md`](../abstract/dish_analysis/component_identification.md) — `Status: Done`. Scope explicitly lists "Up to 5 dish name predictions", "Detection of individual components in the photo (up to 10)", "3-5 serving size options per component", and "Predicted servings count per component".
- **Technical:** [`docs/technical/dish_analysis/component_identification.md`](../technical/dish_analysis/component_identification.md) — Component Checklist for `Step1ComponentIdentification`, `DishNamePrediction`, `ComponentServingPrediction` is all `[x]`.

## Per-item verdict

### 1. Dish name recognition → Done

- `backend/src/service/llm/models.py:78-` — `Step1ComponentIdentification.dish_predictions: List[DishNamePrediction]` with `min_length=1, max_length=5`.
- `backend/src/service/llm/models.py:16-26` — `DishNamePrediction(name: str, confidence: float ∈ [0.0, 1.0])`.
- Prompt instruction (`backend/resources/step1_component_identification.md`, Task 1): "Generate the top 1-5 most likely meal names based on visual analysis, ranked by confidence."
- Frontend: `DishNameSelector.jsx:40-46` shows the top prediction with its confidence as a percentage; `:92-112` lists the rest behind a toggle.

### 2. Individual-dish breakdown → Done

- `backend/src/service/llm/models.py:78-` — `Step1ComponentIdentification.components: List[ComponentServingPrediction]` with `min_length=1, max_length=10`.
- Prompt (Task 2): instructs Gemini to identify individual dishes (1-10 per plate), explicitly NOT ingredient-level.
- Frontend: `Step1ComponentEditor.jsx:194-` iterates `components.map(...)` to render one `ComponentListItem` per detected dish.

### 3. Portion size suggestions → Done (with one schema/prompt mismatch worth noting)

- Schema: `ComponentServingPrediction.serving_sizes: List[str] = Field(..., min_length=1, max_length=5)`.
- Prompt (Task 3): "Provide **3-5 realistic serving size options** for each individual dish."
- Frontend: `ComponentListItem.jsx:74-92` populates the dropdown from `servingSizeOptions` (`step1_data.components[].serving_sizes`).
- **Mismatch (does not block check-off):** the Pydantic floor is `min_length=1`, but the prompt asks for 3-5. In practice Gemini follows the prompt; a malformed response with only 1 option would still validate. If strict 3-option minimum is a hard requirement, tighten `min_length=3` in `models.py`.

### 4. Predicted number of portions → Done

- Schema: `ComponentServingPrediction.predicted_servings: float = Field(default=1.0, ge=0.01, le=10.0)`.
- Prompt (Task 3): "estimate the number of servings visible" with explicit decimal precision guidance (0.5, 0.75, 1.0, 1.5, 2.0…).
- Frontend: `Step1ComponentEditor.jsx:30-44` seeds each component's `number_of_servings` from `comp.predicted_servings || 1.0`; `ComponentListItem.jsx:138-149` shows it in an editable number input.

## Pipeline (Current State)

### Current State

```
[User] Uploads photo via Meal Upload
   │
   ▼
[Backend] analyze_step1_component_identification_async(image, prompt)
   │
   │   Gemini 2.5 Pro, response_schema=Step1ComponentIdentification
   │
   ▼
[Gemini] Returns single JSON blob:
   ├── dish_predictions[1..5]
   │     ├── name (str)
   │     └── confidence (0.0-1.0)
   └── components[1..10]
         ├── component_name (str)
         ├── serving_sizes[1..5]    (prompt asks 3-5)
         └── predicted_servings (0.01-10.0, default 1.0)
   │
   ▼
[Backend] Persist to result_gemini.step1_data
   │
   ▼
[Frontend] Step1ComponentEditor renders
   ├── DishNameSelector (consumes dish_predictions)
   └── ComponentListItem × N (consumes components, serving_sizes,
                              predicted_servings)
```

### New State

_Pending comments._

## Recommendation

Tick all 4 boxes in `docs/issues/260414.md`.

(Optional follow-up — not blocking — if the "3-5 serving sizes" guarantee needs to be enforced server-side, change `min_length=1` → `min_length=3` for `ComponentServingPrediction.serving_sizes` in `backend/src/service/llm/models.py`. Today the bound is 1-5; the 3-5 rule is prompt-only.)

## Next Steps

- Mark all 4 items `[x]`.
- Continue with "Dishes history calendar and Logging dishes" — calendar dashboard + meal upload features.
