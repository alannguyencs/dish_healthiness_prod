# Calendar Dashboard — Technical Design

[< Prev: Authentication](./authentication.md) | [Parent](./index.md) | [Next: Meal Upload >](./meal_upload.md)

## Related Docs
- Abstract: [abstract/calendar_dashboard.md](../abstract/calendar_dashboard.md)

## Architecture

A single GET endpoint returns everything needed to paint a month grid: per-day record counts, navigation pointers for previous/next months, and a weekday header. The frontend does no aggregation of its own — the calendar matrix arrives pre-built.

```
+---------------------+        +---------------------+        +------------------+
|   React SPA         |        |   FastAPI           |        |   Postgres       |
|                     |        |                     |        |                  |
|  Dashboard.jsx      |        |  /api/dashboard/    |        |  dish_image_     |
|  MonthNavigation    |        |                     |        |  query_prod_dev  |
|  CalendarGrid       |<======>|  get_calendar_data()|<------>|  (target_date,   |
|  CalendarDay        |  JSON  |                     | ORM    |   user_id)       |
+---------------------+        +---------------------+        +------------------+
```

## Data Model

**`DishImageQuery`** (table `dish_image_query_prod_dev`) — only the fields used by this feature are listed here; the full model is documented in [Meal Upload](./meal_upload.md).

| Column | Type | Used by this feature |
|--------|------|-----------------------|
| `user_id` | Integer, FK → `users.id` | Scope queries to the signed-in user |
| `target_date` | DateTime, nullable | Day bucket for grouping |

## Pipeline

```
React: Dashboard mount / MonthNavigation click
  │
  ▼
apiService.getDashboardData(year, month)
  │
  ▼
GET /api/dashboard/?year=Y&month=M  (cookie: access_token)
  │
  ▼
api/dashboard.py: dashboard(request, year, month)
  │
  ├──> authenticate_user_from_request() → Users
  │
  ├──> clamp year to [2020, current_year+1], month to [1, 12]
  │
  ▼
crud/dish_query_filters.get_calendar_data(user_id, year, month)
  │
  ▼
SQL:
  SELECT COUNT(id), extract(day, target_date)
  FROM dish_image_query_prod_dev
  WHERE user_id = :uid
    AND extract(year, target_date) = :Y
    AND extract(month, target_date) = :M
  GROUP BY extract(day, target_date)
  │
  ▼
Dict{YYYY-MM-DD : count}
  │
  ▼
Python calendar.Calendar(firstweekday=0).monthdayscalendar(Y, M)
  │
  ▼
Build calendar_data = [[ {day, count, is_current_month, is_today}, ... ], ...]
  │
  ▼
Compute prev_month/prev_year, next_month/next_year (with year rollover)
  │
  ▼
JSON response
  │
  ▼
React: CalendarGrid → CalendarDay renders day + badge, onClick → /date/Y/M/D
```

## Algorithms

### Day bucketing

- Uses PostgreSQL `extract(year|month|day, target_date)` for grouping.
- Rows with `target_date = NULL` are **not** counted (the `extract` returns NULL and is excluded from `GROUP BY`). In practice uploads always set `target_date` from the URL path, so this is rarely observable.
- The `or_(target_date IS NOT NULL …, target_date IS NULL AND created_at …)` fallback used elsewhere in the codebase (see `get_dish_image_queries_by_user_and_date`) is **not** applied here — calendar counts are `target_date`-only.

### Month navigation calculation

- Previous: if `month == 1`, go to `(12, year-1)`; otherwise `(month-1, year)`.
- Next: if `month == 12`, go to `(1, year+1)`; otherwise `(month+1, year)`.

### Grid construction

- `calendar.Calendar(firstweekday=0).monthdayscalendar(year, month)` returns a list of weeks, each week a list of seven day numbers with `0` for out-of-month cells.
- Each non-zero day is enriched with `is_today` (matched against `datetime.now().date()`) and `count` from the CRUD dict.

## Backend — API Layer

| Method | Path | Auth | Request | Response | Status |
|--------|------|------|---------|----------|--------|
| GET | `/api/dashboard/` | Cookie | Query: `year?`, `month?` | `{calendar_data, month_name, display_year, display_month, prev_year, prev_month, next_year, next_month, weekdays}` | 200 / 401 |

`year` and `month` are optional and default to the server's current date. Out-of-range values are silently clamped to the current month/year.

## Backend — Service Layer

The handler in `api/dashboard.py` builds the response directly — there is no separate service module. Its responsibilities are:

- Validate auth, clamp month/year.
- Delegate the aggregation to `get_calendar_data`.
- Assemble the calendar matrix and navigation fields.

## Backend — CRUD Layer

- `crud/dish_query_filters.get_calendar_data(user_id, year, month)` — returns `Dict[str, int]` keyed by `YYYY-MM-DD` for every day with at least one record.

## Frontend — Pages & Routes

- `/dashboard` → `pages/Dashboard.jsx`

## Frontend — Components

All live under `components/dashboard/` and are re-exported via `components/dashboard/index.js`:

- `DashboardHeader.jsx` — page title, username from `useAuth()`, logout button.
- `MonthNavigation.jsx` — prev / next month arrows, month + year label.
- `CalendarGrid.jsx` — renders the weekday row and walks the `calendar_data` matrix.
- `CalendarDay.jsx` — single day cell; shows the day number, count badge (if `count > 0`), and `onClick → navigate('/date/Y/M/D')`.
- `EmptyState.jsx` — fallback UI when there are no records for the month at all.

## Frontend — Services & Hooks

- `services/api.js#getDashboardData(year, month)` — axios GET; the axios instance adds the cookie via `withCredentials: true`.

## External Integrations

None.

## Constraints & Edge Cases

- A user viewing the dashboard in a timezone far from UTC may see a record land on a different calendar day than they expect, because `target_date` is stored as a UTC `DateTime`. The upload endpoint sets `target_date = datetime.combine(meal_date, min.time()).replace(tzinfo=UTC)` based on the URL path, which matches the displayed day as long as the user stays within the same calendar navigation.
- Months out of range `[2020, current_year+1]` silently reset to the current year; no error is surfaced to the client.
- Records with `target_date = NULL` are invisible on the calendar; only `created_at`-only rows created by legacy paths would have this property.
- The grid is built with `firstweekday=0` (Monday first) — the frontend's weekday header must match.
- There is no pagination or caching; every month click issues a fresh query.

## Component Checklist

- [x] `GET /api/dashboard/` endpoint — year/month clamping, auth, month navigation pointers
- [x] `get_calendar_data(user_id, year, month)` — grouped count query
- [x] `Dashboard.jsx` — orchestrator page
- [x] `DashboardHeader.jsx` — username + logout
- [x] `MonthNavigation.jsx` — prev/next buttons
- [x] `CalendarGrid.jsx` — weekday row + day cells
- [x] `CalendarDay.jsx` — single cell with count badge + navigation on click
- [x] `EmptyState.jsx` — no-records fallback
- [x] `apiService.getDashboardData()` — frontend fetch

---

[< Prev: Authentication](./authentication.md) | [Parent](./index.md) | [Next: Meal Upload >](./meal_upload.md)
