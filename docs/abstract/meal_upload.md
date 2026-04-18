# Meal Upload

[< Prev: Calendar Dashboard](./calendar_dashboard.md) | [Parent](./index.md) | [Next: Dish Analysis >](./dish_analysis/index.md)

**Status:** Done

## Related Docs
- Technical: [technical/meal_upload.md](../technical/meal_upload.md)

## Problem

Most people eat a handful of distinct meals on a given day (breakfast, lunch, snacks, dinner, an evening treat). Users need a predictable place to add a photo for each meal without worrying about ordering, naming, or complicated forms.

## Solution

Every day has five meal slots. The user picks a day from the calendar, then taps any empty slot to upload a dish photo. Once uploaded, the slot shows the photo and becomes a tappable entry that leads to the analysis for that dish. Filled slots are clearly distinguished from empty ones.

## User Flow

```
Click a day on the Calendar Dashboard
  |
  v
Meal Upload page for that date (5 slots)
  |
  +--> Empty slot: shows an "Upload" button
  |     |
  |     v
  |   Pick a photo from device
  |     |
  |     v
  |   Photo uploads (progress indicator shown)
  |     |
  |     v
  |   Go to Dish Analysis page for that slot
  |
  +--> Filled slot: shows the dish photo
  |     |
  |     v
  |   Tap the photo --> Go to Dish Analysis page for that slot
  |
  +--> Click "Back" --> Return to Calendar Dashboard
```

## Scope

- **Included:**
  - Exactly five meal slots per day (positions 1 through 5)
  - Upload a dish photo to any empty slot
  - See the uploaded photo in each filled slot
  - Tap a filled slot to open its Dish Analysis page
  - Back navigation to the Calendar Dashboard
  - Visible upload progress while a photo is being sent
- **Not included:**
  - More than five meals per day
  - Reordering or moving a meal between slots
  - Deleting an uploaded meal
  - Re-uploading or replacing the photo in an existing slot
  - Capturing a photo with the device camera directly from the page (user picks an existing file)
  - Bulk upload of multiple photos at once

## Acceptance Criteria

- [x] Each date view shows five clearly labelled slots
- [x] Uploading a photo to an empty slot fills that slot with the photo and opens the analysis page
- [x] Filled slots display the uploaded photo and remain tappable to return to the analysis
- [x] Empty slots always show an upload control
- [x] The back button returns the user to the Calendar Dashboard on the same month they came from
- [x] While an upload is in progress, the user sees a loading indicator and cannot submit the same slot twice

---

[< Prev: Calendar Dashboard](./calendar_dashboard.md) | [Parent](./index.md) | [Next: Dish Analysis >](./dish_analysis/index.md)
