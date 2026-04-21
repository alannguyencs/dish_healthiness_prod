# Discussion — Dishes History Calendar & Logging (3 checkboxes)

**Question:** For each of the 3 items under "Dishes history calendar and Logging dishes", decide Done / Not Done.

1. Monthly calendar view
2. Up to five dishes per day
3. Photo upload (file or URL paste)

**Verdict:** **All 3 are Done.**

---

## Where it lives in the docs

- **Calendar Dashboard:** abstract [`docs/abstract/calendar_dashboard.md`](../abstract/calendar_dashboard.md) (`Status: Done`, all 5 acceptance criteria checked) + technical [`docs/technical/calendar_dashboard.md`](../technical/calendar_dashboard.md) (Component Checklist all `[x]`).
- **Meal Upload:** abstract [`docs/abstract/meal_upload.md`](../abstract/meal_upload.md) (`Status: Done`, all 6 acceptance criteria checked) + technical [`docs/technical/meal_upload.md`](../technical/meal_upload.md) (Component Checklist all `[x]`, including the URL upload variant).

## Per-item verdict

### 1. Monthly calendar view → Done

- **Backend:** `GET /api/dashboard/` returns the month's day-by-day record counts with year/month clamping and prev/next month pointers (technical doc).
- **Frontend components (all `[x]` in Component Checklist):**
  - `Dashboard.jsx` — page orchestrator.
  - `DashboardHeader.jsx` — signed-in username + logout.
  - `MonthNavigation.jsx` — prev/next month arrows.
  - `CalendarGrid.jsx` — weekday row + day cells.
  - `CalendarDay.jsx` — single cell rendering the day number plus a count badge if there are logged meals; click → navigate to `/date/Y/M/D`.
  - `EmptyState.jsx` — no-records fallback.
- All 5 acceptance criteria in the abstract doc are checked: opens on the current month, count badges where applicable, prev/next nav, click-day navigation, header username + logout.

### 2. Up to five dishes per day → Done

- **Constant:** `MAX_DISHES_PER_DATE = 5` declared at `backend/src/api/date.py:35`.
- **Server enforcement:**
  - `backend/src/api/date.py:125` — date GET walks positions `1..MAX_DISHES_PER_DATE` to build the response slot map.
  - `backend/src/api/date.py:162, 232` — file upload and URL upload both reject `dish_position < 1 or > MAX_DISHES_PER_DATE` with HTTP 400.
- **Response field:** the GET payload exposes `max_dishes: 5` (`date.py:138`) so the frontend renders exactly five `MealUploadSlot` components.
- **Frontend:** `MealUploadGrid.jsx` renders five `MealUploadSlot` instances; each empty slot shows an upload control, each filled slot shows the dish photo + tap-through to analysis.
- **Caveat (already noted in tech doc):** the cap is API-layer only, not enforced at the database level — a malicious client bypassing the API could insert more rows. Acceptable for this product surface.

### 3. Photo upload (file pick OR URL paste) → Done

Both modes are implemented end-to-end:

- **File pick:**
  - UI: `MealUploadSlot.jsx` — `<input type="file">` change handler.
  - API: `apiService.uploadDishImage(year, month, day, dishPosition, file)` → multipart POST.
  - Backend: `POST /api/date/{Y}/{M}/{D}/upload` (`backend/src/api/date.py`) with PIL normalization (`_process_and_save_image` — 384px cap, RGBA→RGB, JPEG re-encode) and background Step 1 trigger.

- **URL paste:**
  - UI: `MealUploadSlot.jsx:96-128` — "Or paste image URL" button toggles a `<form>` with `<input type="url">` and Submit/Cancel.
  - API: `apiService.uploadDishImageFromUrl(year, month, day, dishPosition, imageUrl)` (`services/api.js:64`) → JSON POST.
  - Backend: `POST /api/date/{Y}/{M}/{D}/upload-url` — fetches the URL with `httpx.AsyncClient` (30 s timeout), then funnels into the same `_process_and_save_image` pipeline (technical doc).

The PDF wording — "picking an image file from the device or by pasting the web address of a photo" — maps exactly to these two paths.

(Note: the abstract `meal_upload.md` calls out "Capturing a photo with the device camera directly from the page" as **not included**, which is consistent with the PDF — the PDF doesn't claim camera capture either.)

## Pipeline (Current State)

### Current State

```
[User] Signs in → Calendar Dashboard (current month)
   │
   │   GET /api/dashboard/  →  per-day record counts
   │
   ▼
[Frontend] CalendarGrid → CalendarDay × N
   │   each day shows day number + count badge if any meals
   │
   │   [User] click prev/next month  →  re-fetch
   │   [User] click a day            →  navigate /date/Y/M/D
   │
   ▼
[Frontend] DateView → MealUploadGrid → MealUploadSlot × 5
   │
   │   each empty slot:
   │     ┌─ "Upload Image" file picker  ─┐
   │     └─ "Or paste image URL" toggle  ─┘
   │
   ├──> [User] File pick
   │      │
   │      ▼
   │   POST /api/date/Y/M/D/upload (multipart)
   │
   ├──> [User] Paste URL + submit
   │      │
   │      ▼
   │   POST /api/date/Y/M/D/upload-url (JSON)
   │      │
   │      ▼
   │   Backend httpx.AsyncClient fetches bytes (30 s timeout)
   │
   ▼
[Backend] _process_and_save_image (384 px cap, RGB JPEG)
   │   create_dish_image_query row (dish_position 1-5)
   │   BackgroundTasks → analyze_image_background → Step 1 pipeline
   │
   ▼
[Frontend] navigate /item/{id} with optimistic preview
```

### New State

_Pending comments._

## Recommendation

Tick all 3 boxes in `docs/issues/260414.md`.

## Next Steps

- Mark all 3 items `[x]`.
- Last group remaining: "Key In-Depth Technical Features" — these are the trickier ones (curated nutrition DB lookup, multi-stage search, multi-source evidence fusion). Some may need pushback similar to the "Automatic Dish Identification" caveat.
