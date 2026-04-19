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

If the AI call fails, the user sees a clear error message with a one-click **Try Again** button instead of an indefinite loading spinner. The user can toggle between the results view and the earlier component editor to recheck what was confirmed.

### Curated nutrition database (consulted silently)

Starting this phase, the system also consults a curated database of ~4,500 foods across four international sources (Malaysian, MyFCD, Anuvaad, CIQUAL) to find close matches for the confirmed dish and each of its components. The matches are recorded on the record but not yet shown to the user and not yet fed into the AI — the measurable benefit arrives when a later release lets the AI cite them for more consistent nutrition numbers. Dev environments that have not seeded the database, or dishes with no database coverage, continue to run exactly as before — the AI is never blocked on database coverage.

### Personalization history (consulted silently)

In parallel with the nutrition database lookup, the system also compares the user's confirmed dish and its short caption against the user's own prior uploads. Close historical matches are recorded on the record (but not yet shown to the user and not yet fed into the AI — the measurable benefit arrives when a later release lets the AI reuse the user's prior analyses for more consistent nutrition numbers on repeat dishes). Strictly per-account: one user's history never influences another user's analyses.

## User Flow

```
Confirm components on Component Identification page
  |
  v
Nutritional Analysis loading indicator
  |
  +--> AI returns results
  |        |
  |        v
  |    Results page shows:
  |       +-- Confirmed dish name
  |       +-- Healthiness score (0-100) with colour-coded badge
  |       +-- Short rationale for the score
  |       +-- Macro nutrients: calories, fibre, carbs, protein, fat
  |       +-- Notable micronutrients (labelled badges)
  |       +-- Phase metadata (AI model, time, cost)
  |        |
  |        +--> Toggle back to Component Identification view
  |        +--> Back button --> Return to Meal Upload page for the date
  |
  +--> AI call fails
           |
           v
       Error card with reason + "Try Again" button
           |
           +--> Click Try Again --> Loading indicator --> AI re-runs
           +--> "Try Anyway" warning appears after 5 failed attempts
           +--> Back button --> Return to Meal Upload page for the date
```

## Scope

- **Included:**
  - Healthiness score (0-100) with a colour-coded category badge
  - Plain-language rationale for the score
  - Display of calories (kcal), fibre (g), carbohydrates (g), protein (g), fat (g)
  - List of notable micronutrients
  - Loading indicator while the AI is working
  - Visible error state with a one-click retry when the AI call fails (no auto-retry)
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
- [x] If the AI call fails, the user sees an error card explaining what went wrong instead of an indefinite loading spinner
- [x] The user can retry from the error card; on success the results view appears as normal

---

[< Prev: User Customization](./user_customization.md) | [Parent](./index.md)
