# System Pipelines

[Parent](./index.md) | [Next: Authentication >](./authentication.md)

Cross-cutting data-flow diagrams for each distinct user entry point into the system. Each pipeline heading links to the feature page that covers that flow in full.

---

## Login Pipeline — [details](./authentication.md)

```
User submits username + password on Login page
  │
  ▼
React: apiService.login() --POST /api/login/--> FastAPI
  │
  ▼
authenticate_user(username, password)
  │
  ▼
crud_user.get_user_by_username() ──> Postgres `users` table
  │
  ▼
bcrypt_context.verify(password, user.hashed_password)
  │
  ▼
create_access_token({username}) ──> JWT (HS256, 90-day expire)
  │
  ▼
Set-Cookie: access_token=<jwt>; HttpOnly; SameSite=Lax; Max-Age=7776000
  │
  ▼
React AuthProvider sets authenticated=true ──> Navigate to /dashboard
```

---

## Calendar Dashboard Pipeline — [details](./calendar_dashboard.md)

```
User lands on /dashboard (or clicks prev/next month)
  │
  ▼
React: apiService.getDashboardData(year, month)
  │
  ▼
GET /api/dashboard/?year=Y&month=M (cookie: access_token)
  │
  ▼
authenticate_user_from_request() ──> Users
  │
  ▼
get_calendar_data(user_id, year, month)
  │
  ▼
SELECT COUNT(id), extract(day, target_date) FROM dish_image_query_prod_dev
  WHERE user_id = :uid
    AND extract(year, target_date) = :Y
    AND extract(month, target_date) = :M
  GROUP BY day
  │
  ▼
Backend builds calendar grid (week-by-week) with per-day counts + today flag
  │
  ▼
JSON response ──> React renders CalendarGrid / CalendarDay
```

---

## Meal Upload Pipeline — [details](./meal_upload.md)

```
User picks file on DateView, or opens existing slot
  │
  ▼
React: apiService.uploadDishImage(year, month, day, dish_position, file)
  │
  ▼
POST /api/date/{year}/{month}/{day}/upload  (multipart/form-data)
  │
  ▼
authenticate_user_from_request()  +  validate dish_position ∈ [1, 5]
  │
  ▼
PIL: open(file) ──> thumbnail(max=384) ──> convert RGB ──> save as JPEG
  │     saved at backend/data/images/{yyMMdd_HHmmss}_dish{N}.jpg
  │
  ▼
create_dish_image_query(user_id, image_url, target_date, dish_position, created_at)
  │
  ▼
BackgroundTasks.add_task(analyze_image_background, query.id, file_path)
  │                                                     │
  │                                                     └──> Step 1 Pipeline (below)
  ▼
JSON response {query.id, image_url} ──> React navigate(`/item/{id}`)
```

---

## Dish Analysis — Phase 1 Pipeline — [details](./dish_analysis/component_identification.md)

```
Background task: analyze_image_background(query_id, file_path)
  │
  ▼
get_step1_component_identification_prompt()
  ──> read backend/resources/step1_component_identification.md
  │
  ▼
analyze_step1_component_identification_async(
    image_path, prompt,
    model="gemini-2.5-pro", thinking_budget=-1)
  │
  ▼
google.genai Client.models.generate_content(
    contents=[prompt, image_part],
    config={response_mime_type: application/json,
            response_schema: Step1ComponentIdentification,
            temperature: 0, thinking_budget: -1})
  │
  ▼
Parse response ──> {dish_predictions[1..5], components[1..10]}
  │
  ▼
Enrich with input_token / output_token / price_usd / analysis_time
  │
  ▼
update_dish_image_query_results(
    result_gemini={step:1, step1_data, step2_data:null,
                   step1_confirmed:false, iterations:[{...}],
                   current_iteration:1})
  │
  ▼
Frontend polls GET /api/item/{id} every 3s until step==1 && !step1_confirmed
```

---

## User Customization + Step 2 Trigger Pipeline — [details](./dish_analysis/user_customization.md)

```
ItemV2 renders Step1ComponentEditor with step1_data
  │
  ▼
User edits dish name, toggles components, picks serving sizes,
  adjusts counts, adds custom components
  │
  ▼
Click "Confirm and Analyze Nutrition"
  │
  ▼
apiService.confirmStep1(record_id, {selected_dish_name, components[]})
  │
  ▼
POST /api/item/{record_id}/confirm-step1
  │
  ▼
Validate auth + record ownership + step1 complete + image exists
  │
  ▼
Optimistic DB write:
  result_gemini.step1_confirmed = true
  result_gemini.confirmed_dish_name = <name>
  result_gemini.confirmed_components = <array>
  │
  ▼
BackgroundTasks.add_task(trigger_step2_analysis_background,
                         record_id, image_path, dish_name, components)
  │                                                    │
  │                                                    └──> Step 2 Pipeline (below)
  ▼
JSON response {success, step2_in_progress:true}
  │
  ▼
Frontend begins polling for step2_data
```

---

## Dish Analysis — Phase 2 Pipeline — [details](./dish_analysis/nutritional_analysis.md)

```
Background task: trigger_step2_analysis_background(
    query_id, image_path, dish_name, components)
  │
  ▼
get_step2_nutritional_analysis_prompt(dish_name, components)
  ──> read backend/resources/step2_nutritional_analysis.md
  ──> append "USER-CONFIRMED DATA FROM STEP 1" block
  │
  ▼
analyze_step2_nutritional_analysis_async(
    image_path, prompt,
    model="gemini-2.5-pro", thinking_budget=-1)
  │
  ▼
google.genai Client.models.generate_content(
    contents=[prompt, image_part],
    config={response_mime_type: application/json,
            response_schema: Step2NutritionalAnalysis,
            temperature: 0, thinking_budget: -1})
  │
  ▼
Parse response ──> {dish_name, healthiness_score, rationale,
                    calories_kcal, fiber_g, carbs_g, protein_g, fat_g,
                    micronutrients[]}
  │
  ▼
Enrich with tokens / price_usd / analysis_time
  │
  ▼
update_dish_image_query_results(
    result_gemini.step = 2
    result_gemini.step2_data = <payload>
    iterations[cur].step2_data = <payload>)
  │
  ▼
Frontend polling (every 3s) sees step==2 && step2_data
  ──> render Step2Results component
```

---

[Parent](./index.md) | [Next: Authentication >](./authentication.md)
