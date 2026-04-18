# Dish Healthiness — Technical

Feature-level architectural reference. Each page describes how a feature works in terms of components, data flow, and layer responsibilities. Abstract-layer counterparts live under `docs/abstract/` with the same filenames.

| # | Page | Description |
|---|------|-------------|
| 1 | [System Pipelines](./system_pipelines.md) | Cross-cutting overview — one ASCII data-flow diagram per user entry point |
| 2 | [Authentication](./authentication.md) | JWT-over-cookie session, bcrypt password hashing, FastAPI request auth helper |
| 3 | [Calendar Dashboard](./calendar_dashboard.md) | Month grid built from per-day `DishImageQuery` counts |
| 4 | [Meal Upload](./meal_upload.md) | Multipart image upload, PIL resize/convert, background Step 1 kickoff |
| 5 | [Dish Analysis](./dish_analysis/index.md) | Two-phase Gemini workflow with user-confirmed component editing between phases |
