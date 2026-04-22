# Meal Upload — Technical Design

[< Prev: Calendar Dashboard](./calendar_dashboard.md) | [Parent](./index.md) | [Next: Dish Analysis >](./dish_analysis/index.md)

## Related Docs
- Abstract: [abstract/meal_upload.md](../abstract/meal_upload.md)

## Architecture

The date view renders five fixed slots keyed by `dish_position` (1-5). A slot is filled by uploading an image (multipart form) or supplying an image URL. The backend resizes and re-encodes the image, persists a `DishImageQuery` row, and schedules the Component Identification analysis via FastAPI `BackgroundTasks` before returning.

```
+---------------------+      +-----------------------+      +-------------------+
|   React SPA         |      |   FastAPI             |      |   Filesystem      |
|                     |      |                       |      |                   |
|  DateView.jsx       |      |  /api/date/Y/M/D      |      |  backend/data/    |
|  MealUploadGrid     |<====>|  /api/date/Y/M/D/     |----->|  images/*.jpg     |
|  MealUploadSlot     | JSON |   upload (multipart)  |      |                   |
|                     |      |  /api/date/Y/M/D/     |      +-------------------+
|                     |      |   upload-url          |                │
+---------------------+      +-----------------------+                │
                                   │                                  │
                                   ▼                                  │
                             +--------------+                         │
                             |  Postgres    |                         │
                             |  dish_image_ |<------------------------┘
                             |  query_prod  |   image_url points to
                             |  _dev        |   /images/<file>.jpg
                             +--------------+
                                   │
                                   ▼
                             BackgroundTasks →
                             analyze_image_background() → Component Identification pipeline
```

## Data Model

**`DishImageQuery`** (table `dish_image_query_prod_dev`) — full schema.

| Column | Type | Constraints | Purpose |
|--------|------|-------------|---------|
| `id` | Integer | PK | Record identity |
| `user_id` | Integer | FK → `users.id`, NOT NULL | Ownership |
| `image_url` | String | nullable | Publicly servable path (`/images/<file>.jpg`) |
| `result_openai` | JSON | nullable | Reserved for a second vendor; unused today |
| `result_gemini` | JSON | nullable | Full analysis payload (see Dish Analysis pages) |
| `dish_position` | Integer | nullable | Slot index 1-5 |
| `created_at` | DateTime | NOT NULL | UTC insert timestamp |
| `target_date` | DateTime | nullable | UTC midnight of the meal date |

`MAX_DISHES_PER_DATE = 5` is enforced at the API layer, not the database — the schema permits any integer in `dish_position`.

## Pipeline

```
DateView mounts for /date/Y/M/D
  │
  ▼
GET /api/date/{year}/{month}/{day}
  │
  ├──> authenticate_user_from_request()
  ├──> validate date via datetime(Y, M, D).date()  (400 on ValueError)
  │
  ▼
crud.get_dish_image_queries_by_user_and_date(user_id, target_date)
  │    └── OR(target_date::date = d, target_date IS NULL AND created_at::date = d)
  │
  ▼
Build dish_data = {dish_1 … dish_5:
  {has_data, record_id, image_url}} for every position 1..MAX
  │
  ▼
JSON → React renders 5 MealUploadSlot components

---- User uploads a file into an empty slot ----

MealUploadSlot: <input type="file"> change
  │
  ▼
DateView.handleFileUpload(dishPosition, file)
  │
  ▼
apiService.uploadDishImage(year, month, day, dishPosition, file)
  │   FormData: dish_position=<N>, file=<binary>
  │
  ▼
POST /api/date/{year}/{month}/{day}/upload
  │
  ├──> authenticate_user_from_request()
  ├──> validate 1 <= dish_position <= 5
  ├──> validate date
  │
  ▼
_process_and_save_image(content, file_path)
  │   ├──> PIL Image.open(BytesIO(content))
  │   ├──> thumbnail((384, 384), LANCZOS) if larger
  │   ├──> RGBA → paste onto white RGB / non-RGB → convert("RGB")
  │   └──> save(file_path, "JPEG")
  │
  ▼
create_dish_image_query(user_id, image_url="/images/<file>.jpg",
                        result_openai=None, result_gemini=None,
                        created_at=utcnow, target_date=UTC midnight of day,
                        dish_position=N)
  │
  ▼
BackgroundTasks.add_task(analyze_image_background, query.id, str(file_path))
  │                                              │
  │                                              └──> see Dish Analysis / Phase 1
  ▼
JSON {success, message, query: _serialize_query(query)}
  │
  ▼
React: navigate(`/item/${query.id}`, {state:{uploadedImage, uploadedDishPosition}})
```

The URL-upload variant (`/upload-url`) is identical except it first downloads the image via `httpx.AsyncClient` (30 s timeout) and feeds the bytes into `_process_and_save_image`.

## Algorithms

### Image normalization

- Cap each dimension at 384 px via `Image.thumbnail((384, 384), LANCZOS)` — preserves aspect ratio.
- RGBA → paste onto a white RGB background using the alpha channel as the mask, to avoid dark transparent regions after JPEG encoding.
- Any other mode (`P`, `L`, `LA`, etc.) falls through to `img.convert("RGB")`.
- Encode as JPEG at PIL defaults to the deterministic filename `{yyMMdd_HHmmss UTC}_dish{N}.jpg`.

### Slot resolution

- `get_dish_image_queries_by_user_and_date` returns all records for the day, ordered `dish_position ASC NULLS LAST, created_at DESC`.
- `get_date` walks positions 1..5 and picks the first matching record per position via `next(... if q.dish_position == position ...)`. If two rows share the same position, the first in iteration order wins (SQL order is not re-sorted client-side).

### `target_date` semantics

- On upload, `target_date = datetime.combine(meal_date, time.min).replace(tzinfo=UTC)` — UTC midnight of the URL-path day.
- Legacy rows with `target_date = NULL` are reachable via the `created_at` fallback in the filter.

## Backend — API Layer

| Method | Path | Auth | Request | Response | Status |
|--------|------|------|---------|----------|--------|
| GET | `/api/date/{year}/{month}/{day}` | Cookie | — | `{target_date, formatted_date, dish_data: {dish_1..dish_5: {has_data, record_id, image_url}}, max_dishes, year, month, day}` | 200 / 400 / 401 |
| POST | `/api/date/{year}/{month}/{day}/upload` | Cookie | multipart: `dish_position`, `file` | `{success, message, query}` | 200 / 400 / 401 |
| POST | `/api/date/{year}/{month}/{day}/upload-url` | Cookie | JSON `{dish_position, image_url}` | `{success, message, query}` | 200 / 400 / 401 |

## Backend — Service Layer

- `api/date.py#_process_and_save_image(content, file_path)` — PIL-based normalization.
- `api/item_identification_tasks.py#analyze_image_background(query_id, file_path, retry_count=0)` — background entry point for Component Identification. Imported by `date.py`'s upload endpoints. On failure, classifies the exception and persists `result_gemini.identification_error` via the shared `persist_phase_error` helper (see [Component Identification](./dish_analysis/component_identification.md)).
- Static file mount in `main.py`: `app.mount("/images", StaticFiles(directory=IMAGE_DIR), name="images")` — the same path stored as `image_url`.

## Backend — CRUD Layer

- `crud/dish_query_basic.create_dish_image_query(...)` — inserts the row.
- `crud/dish_query_basic.get_dish_image_query_by_id(record_id)` — used by downstream endpoints.
- `crud/dish_query_basic.update_dish_image_query_results(query_id, result_openai, result_gemini)` — used by the background Component Identification task.
- `crud/dish_query_filters.get_dish_image_queries_by_user_and_date(user_id, query_date)` — ordered list for a day.

## Frontend — Pages & Routes

- `/date/:year/:month/:day` → `pages/DateView.jsx`.

## Frontend — Components

Live under `components/dateview/` and are re-exported via `components/dateview/index.js`:

- `DateViewNavigation.jsx` — back-to-calendar button.
- `MealUploadGrid.jsx` — grid container that renders five `MealUploadSlot`s and the formatted date header.
- `MealUploadSlot.jsx` — per-slot UI: file picker when empty, image thumbnail + tap-to-open when filled. Owns the `uploading` state for that slot while the POST is in flight.

## Frontend — Services & Hooks

- `services/api.js#getDateData(year, month, day)` — GET date view payload.
- `services/api.js#uploadDishImage(year, month, day, dishPosition, file)` — multipart POST.
- `services/api.js#uploadDishImageFromUrl(year, month, day, dishPosition, imageUrl)` — JSON POST for URL-sourced images.

`DateView.jsx` hard-navigates to `/item/{id}` on successful upload, passing `{uploadedImage, uploadedDishPosition}` via route state so the item page can show an optimistic preview before its own `GET /api/item/{id}` returns.

## External Integrations

- `httpx.AsyncClient` — used only by the URL-upload variant to fetch external image bytes with a 30 s timeout. Any `httpx.HTTPError` surfaces as HTTP 400.

## Constraints & Edge Cases

- `dish_position` outside `[1, 5]` → 400 "Invalid dish position".
- Invalid date tuple in the URL (e.g. `2025/02/30`) → 400 "Invalid date".
- Re-uploading the same slot is **not** deduplicated or rejected at the DB level — a second POST creates a second row with the same `dish_position`. The GET endpoint only shows one of them (the first returned by the ordered CRUD query), so the duplicate becomes orphaned. There is no delete endpoint exposed.
- `IMAGE_DIR` is a local path (`backend/data/images/`). The app assumes a single-server deployment for image serving; no cloud storage integration.
- Image filenames are generated with second-level UTC precision; two uploads in the same second would collide. Collisions are not currently guarded.
- Background task failures in `analyze_image_background` are now classified and persisted to `result_gemini.identification_error`. The frontend stops polling and renders `<PhaseErrorCard>` with a retry button. See [Component Identification](./dish_analysis/component_identification.md).
- `SessionMiddleware` and CORS are configured in `main.py`; see [Authentication](./authentication.md) for details that affect upload behaviour (cookies + `withCredentials`).

## Component Checklist

- [x] `GET /api/date/{Y}/{M}/{D}` — returns 5 slot descriptors
- [x] `POST /api/date/{Y}/{M}/{D}/upload` — multipart upload + background Component Identification trigger
- [x] `POST /api/date/{Y}/{M}/{D}/upload-url` — URL-sourced upload variant
- [x] `_process_and_save_image()` — 384 px cap, RGBA → RGB, JPEG encode
- [x] `create_dish_image_query()` CRUD insert
- [x] Static mount `/images → IMAGE_DIR`
- [x] `DateView.jsx` page
- [x] `MealUploadGrid.jsx` + `MealUploadSlot.jsx`
- [x] `apiService.uploadDishImage()` + `uploadDishImageFromUrl()`
- [x] Route navigation `/item/{id}` on successful upload

---

[< Prev: Calendar Dashboard](./calendar_dashboard.md) | [Parent](./index.md) | [Next: Dish Analysis >](./dish_analysis/index.md)
