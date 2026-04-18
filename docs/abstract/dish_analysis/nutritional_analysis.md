# Nutritional Analysis

[< Prev: User Customization](./user_customization.md) | [Parent](./index.md)

**Status:** Done

## Related Docs
- Technical: [technical/dish_analysis/nutritional_analysis.md](../../technical/dish_analysis/nutritional_analysis.md)

## Problem

Once the user has confirmed what is in their meal, they want a clear, trustworthy answer to two questions: "How healthy is this meal?" and "What am I actually eating, in nutrition terms?" A raw dump of numbers is not useful — the user needs a summary score with a short explanation, plus the key macro and micro nutrients at a glance.

## Solution

After the user confirms the component list in the previous phase, the system runs a second AI pass that returns:

- A healthiness score from 0 to 100 with a colour-coded badge (Very Healthy, Healthy, Moderate, Unhealthy, Very Unhealthy).
- A short plain-language rationale explaining why the meal got that score.
- Core nutrition numbers: calories, fibre, carbohydrates, protein, and fat.
- A list of notable micronutrients worth calling out.

The user can toggle between this results view and the earlier component editor to recheck what was confirmed.

## User Flow

```
Confirm components on Component Identification page
  |
  v
Nutritional Analysis loading indicator
  |
  v
AI returns results
  |
  v
Results page shows:
   +-- Confirmed dish name
   +-- Healthiness score (0-100) with colour-coded badge
   +-- Short rationale for the score
   +-- Macro nutrients: calories, fibre, carbs, protein, fat
   +-- Notable micronutrients (labelled badges)
   +-- Phase metadata (AI model, time, cost)
  |
  +--> Toggle back to Component Identification view
  +--> Back button --> Return to Meal Upload page for the date
```

## Scope

- **Included:**
  - Healthiness score (0-100) with a colour-coded category badge
  - Plain-language rationale for the score
  - Display of calories (kcal), fibre (g), carbohydrates (g), protein (g), fat (g)
  - List of notable micronutrients
  - Loading indicator while the AI is working
  - Toggle between the results view and the component editor view once both phases are complete
  - Visibility into the AI model used, time taken, and cost for this phase
- **Not included:**
  - Daily or weekly nutrition totals
  - Goal setting or comparing to recommended daily intake
  - Allergen warnings or dietary preference filtering
  - Editing nutrition numbers after they are returned
  - Re-running the analysis from the results page (to change inputs, the user goes back to Component Identification)

## Acceptance Criteria

- [x] A loading indicator is shown continuously until the results arrive
- [x] The healthiness score is shown with a colour-coded category label
- [x] A rationale sentence explains the score in plain language
- [x] Calories, fibre, carbs, protein, and fat are all visible on the results view
- [x] Notable micronutrients appear as labelled badges
- [x] Once both phases are complete, the user can switch between the results view and the component editor view

---

[< Prev: User Customization](./user_customization.md) | [Parent](./index.md)
