# Calendar Dashboard

[< Prev: Authentication](./authentication.md) | [Parent](./index.md) | [Next: Meal Upload >](./meal_upload.md)

**Status:** Done

## Related Docs
- Technical: [technical/calendar_dashboard.md](../technical/calendar_dashboard.md)

## Problem

Users want a simple way to look back at their meal history and see at a glance which days they have logged dishes. Scrolling through a long list of entries makes it hard to pick a specific day or notice gaps in logging.

## Solution

After signing in, the user lands on a monthly calendar. Each day cell shows the number of meals logged on that day. The user can move forward or backward one month at a time, and tap any day to open its detailed meal view.

## User Flow

```
Sign in
  |
  v
Calendar Dashboard (current month)
  |
  v
Each day shows:
   - day number
   - number of meals logged (if any)
  |
  +--> Click "<" or ">" --> Switch to previous / next month
  |
  +--> Click a day ----------> Open Meal Upload page for that date
  |
  +--> Click "Logout" -------> Sign out
```

## Scope

- **Included:**
  - Monthly calendar grid showing every day of the selected month
  - Count badge on each day that has at least one logged meal
  - Previous / next month navigation
  - Click a day to open the meal view for that date
  - Header showing the signed-in username and a logout button
- **Not included:**
  - Week or day-level calendar views
  - Summary statistics (total calories, healthiness averages, streaks)
  - Filtering or searching by dish name
  - Sharing or exporting the calendar

## Acceptance Criteria

- [x] The dashboard opens on the current month when the user signs in
- [x] Days with logged meals display a count badge; days without meals show no badge
- [x] Clicking the previous / next month arrows updates the grid to that month
- [x] Clicking a day opens that date's meal upload page
- [x] The header shows the current user's name and a working logout button

---

[< Prev: Authentication](./authentication.md) | [Parent](./index.md) | [Next: Meal Upload >](./meal_upload.md)
