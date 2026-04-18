# Discussion — Phase 2 Nutrition Items (8 checkboxes)

**Question:** For each item below, decide Done / Not Done and list missing pieces:

1. Healthiness Category
2. Healthiness rationale
3. Calorie estimation
4. Fiber estimation
5. Carbohydrate estimation
6. Protein estimation
7. Fat estimation
8. Notable micronutrients

**Verdict:** **All 8 are Done.** Each is a field in the `Step2NutritionalAnalysis` Pydantic schema, returned by the Phase 2 Gemini call, persisted under `result_gemini.step2_data`, and rendered by `Step2Results.jsx`.

---

## Where it lives in the docs

- **Abstract:** [`docs/abstract/dish_analysis/nutritional_analysis.md`](../abstract/dish_analysis/nutritional_analysis.md) — `Status: Done`. All 6 acceptance criteria checked, including: "Calories, fibre, carbs, protein, and fat are all visible on the results view" and "Notable micronutrients appear as labelled badges".
- **Technical:** [`docs/technical/dish_analysis/nutritional_analysis.md`](../technical/dish_analysis/nutritional_analysis.md) — every component related to these 8 items is `[x]` in the Component Checklist. (The two unchecked items in that doc — "Retry / error-state UI" and "Idempotency key on Phase 2 task" — are operational hardening, not features in this list.)

## Code grounding

### Backend schema — `backend/src/service/llm/models.py:104-134`

```python
class Step2NutritionalAnalysis(BaseModel):
    dish_name: str
    healthiness_score: int = Field(..., ge=0, le=100)
    healthiness_score_rationale: str
    calories_kcal: int = Field(..., ge=0)
    fiber_g: int = Field(..., ge=0)
    carbs_g: int = Field(..., ge=0)
    protein_g: int = Field(..., ge=0)
    fat_g: int = Field(..., ge=0)
    micronutrients: List[str] = Field(default_factory=list)
```

The Gemini call enforces this schema via `response_schema=Step2NutritionalAnalysis` (see `analyze_step2_nutritional_analysis_async` in `gemini_analyzer.py`), so each field is contractually present in every successful Phase 2 response.

### Frontend rendering — `frontend/src/components/item/Step2Results.jsx`

| Item | Schema field | Rendered at |
|------|--------------|-------------|
| Healthiness Category | derived from `healthiness_score` via `getScoreLabel()` | `Step2Results.jsx:39-43, 62` (5 buckets: Very Healthy / Healthy / Moderate / Unhealthy / Very Unhealthy) |
| Healthiness rationale | `healthiness_score_rationale` | `Step2Results.jsx:67` |
| Calorie estimation | `calories_kcal` | `Step2Results.jsx:86` |
| Fiber estimation | `fiber_g` | `Step2Results.jsx:92` |
| Carbohydrate estimation | `carbs_g` | `Step2Results.jsx:103` |
| Protein estimation | `protein_g` | `Step2Results.jsx:108` |
| Fat estimation | `fat_g` | `Step2Results.jsx:113` |
| Notable micronutrients | `micronutrients[]` | `Step2Results.jsx:121-129` (badges, conditional on `length > 0`) |

## Pipeline (Current State)

### Current State

```
[User] Confirms Step 1 → POST /confirm-step1
   │
   ▼
[Backend] BackgroundTasks.add_task(trigger_step2_analysis_background, ...)
   │
   ▼
[Backend] get_step2_nutritional_analysis_prompt(dish_name, components)
   │
   │   loads backend/resources/step2_nutritional_analysis.md
   │   appends confirmed dish + components block
   │
   ▼
[Backend] analyze_step2_nutritional_analysis_async(image_path, prompt)
   │
   │   Gemini 2.5 Pro, response_schema=Step2NutritionalAnalysis
   │
   ▼
[Gemini] Returns: dish_name, healthiness_score, rationale,
                  calories_kcal, fiber_g, carbs_g, protein_g, fat_g,
                  micronutrients[]
   │
   ▼
[Backend] update_dish_image_query_results → result_gemini.step2_data
   │
   ▼
[Frontend] ItemV2.jsx polling stops on (step==2 && step2_data)
   │
   ▼
[Frontend] Step2Results.jsx renders:
             - score badge with category label (Healthiness Category)
             - rationale paragraph (Healthiness rationale)
             - 5 macro tiles (Calories / Fiber / Carbs / Protein / Fat)
             - micronutrient badges
```

### New State

_Pending comments._

## Per-item verdict

- **Healthiness Category** → Done. Score → category bucket lives in `Step2Results.jsx:38-44`. Backend returns the integer; the 5-band label is computed client-side and shown as a colored badge.
- **Healthiness rationale** → Done. Field is required (`...` in Pydantic), rendered as plain text at `Step2Results.jsx:67`.
- **Calorie estimation** → Done. `calories_kcal: int ≥ 0`. Rendered as the headline tile (`Step2Results.jsx:86`).
- **Fiber estimation** → Done. `fiber_g: int ≥ 0`. Rendered at `Step2Results.jsx:92`.
- **Carbohydrate estimation** → Done. `carbs_g: int ≥ 0`. Rendered at `Step2Results.jsx:103`.
- **Protein estimation** → Done. `protein_g: int ≥ 0`. Rendered at `Step2Results.jsx:108`.
- **Fat estimation** → Done. `fat_g: int ≥ 0`. Rendered at `Step2Results.jsx:113`.
- **Notable micronutrients** → Done. `micronutrients: List[str]` (defaults to `[]`). Rendered as badges at `Step2Results.jsx:121-129` (the section is hidden when the list is empty).

## Caveats (don't block check-off)

- All values are integers (no decimals on macros). Acceptable for a healthiness display; flag if precision matters.
- Micronutrients are free-form strings — no canonical list, no mg quantities. The PDF says "list of noteworthy vitamins and minerals", which matches.
- Healthiness category thresholds are hardcoded UI-side (≥81, ≥61, ≥41, ≥21). Changing them is a frontend edit, not an API change.
- No retry / error UI if Phase 2 fails (tracked as unchecked item in the technical doc's checklist) — orthogonal to whether the features themselves exist.

## Recommendation

Tick all 8 boxes in `docs/issues/260414.md`.

## Next Steps

- Mark all 8 items `[x]` in the issues file.
- Move on to the "Refining the results with manual corrections" section next.
