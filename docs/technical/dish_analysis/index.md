# Dish Analysis — Technical

[< Prev: Meal Upload](../meal_upload.md) | [Parent](../index.md)

Two-phase Gemini pipeline that turns an uploaded photo into a nutritional readout. Phase 1 runs automatically after upload and stops awaiting user input. User Customization is the React-side editor that mutates the Phase 1 output before confirmation. Phase 2 runs in the background after confirmation and produces the final payload. All three pages share the same record row (`DishImageQuery`) and the same JSON blob (`result_gemini`); each page documents the subset it owns.

| # | Page | Description |
|---|------|-------------|
| 1 | [Component Identification](./component_identification.md) | Phase 1 — Gemini Step 1 call, `Step1ComponentIdentification` schema, background task wiring, polling contract |
| 2 | [User Customization](./user_customization.md) | React editor component, local state shape, `POST /confirm-step1` contract, DB optimistic write |
| 3 | [Nutritional Analysis](./nutritional_analysis.md) | Phase 2 — Gemini Step 2 call, prompt injection of confirmed components, `Step2NutritionalAnalysis` schema |
| 4 | [Personalized Food Index](./personalized_food_index.md) | Shared per-user BM25 foundation — `personalized_food_descriptions` table, CRUD, and index service that Stages 2/4/6/8 consume |
| 5 | [Nutrition DB](./nutrition_db.md) | Curated four-source nutrition corpus (`nutrition_foods` + MyFCD child) plus the BM25-backed `NutritionCollectionService` library that Stages 5/7/9 consume |

---

[< Prev: Meal Upload](../meal_upload.md) | [Parent](../index.md)
