# Component Identification

[Parent](./index.md) | [Next: User Customization >](./user_customization.md)

**Status:** Done

## Related Docs
- Technical: [technical/dish_analysis/component_identification.md](../../technical/dish_analysis/component_identification.md)

## Problem

A single photo often shows a dish made of multiple components (rice, protein, vegetables, sauce), and the user needs a starting point that is close enough to what is actually on the plate that they only have to make small corrections. We need a first pass that reliably proposes the overall dish and lists the individual components, with enough structure that the user can review it quickly.

## Solution

Right after the user uploads a photo, the system runs a first-pass AI analysis that returns:

- A short ranked list of possible names for the overall meal, each with a confidence score.
- A list of individual components visible in the photo. For every component, the AI suggests a small set of plausible serving size options and a predicted number of servings.

The proposals are displayed on the Component Identification screen, where the user then edits and confirms them (see [User Customization](./user_customization.md) for the editing capability).

If the AI call fails, the user sees a clear error message with a one-click **Try Again** button instead of an indefinite loading spinner.

### Personalization (silent in this stage)

Starting with this phase, the system quietly remembers every dish each user has uploaded. Before the first-pass AI call runs, a short description of the new photo is compared against the user's own upload history, and the closest prior dish — if any — is set aside as an invisible reference. The reference is not shown to the user and does not change what the user sees today. The measurable benefit arrives when a later release starts feeding that reference into the first-pass AI call so the model can borrow portion / preparation hints from similar dishes the same user has seen before. The user's history is strictly per-account: one user's uploads never influence another user's analyses.

## User Flow

```
Upload photo on Meal Upload page
  |
  v
Dish Analysis page opens with a loading indicator
  |
  v
AI first pass runs in the background
  |
  +--> AI returns:
  |       - Overall meal name predictions (up to 5, each with confidence)
  |       - Per-component suggestions:
  |           * component name
  |           * 3-5 serving size options
  |           * predicted servings count
  |       |
  |       v
  |   Proposals are shown on the Component Identification screen
  |       |
  |       v
  |   User proceeds to review and customize the proposals --> see User Customization
  |
  +--> AI call fails
         |
         v
       Error card with reason + "Try Again" button
         |
         +--> Click Try Again --> Loading indicator --> AI re-runs
         +--> "Try Anyway" warning appears after 5 failed attempts
```

## Scope

- **Included:**
  - Up to 5 dish name predictions, each with a confidence score
  - Detection of individual components in the photo (up to 10)
  - 3-5 serving size options per component
  - Predicted servings count per component
  - Loading indicator until the first pass completes
  - Visible error state with a one-click retry when the AI call fails (no auto-retry)
  - Visibility into the AI model used, time taken, and cost for this phase
- **Not included:**
  - Any editing of the proposals (see [User Customization](./user_customization.md))
  - The nutritional calculation itself (see [Nutritional Analysis](./nutritional_analysis.md))
  - Cropping the photo to a specific region
  - Multi-language dish name predictions
  - Confidence scores on individual components or serving size suggestions

## Acceptance Criteria

- [x] A loading indicator is visible from the moment the user lands on the page until the first-pass results arrive
- [x] When the results arrive, the screen shows up to 5 dish name predictions with their confidence scores
- [x] Every detected component appears with its name, a list of serving size options, and a predicted servings count
- [x] The phase's model, elapsed time, and cost are visible on the same screen
- [x] If the first pass fails, an error state is shown instead of hanging on the loading indicator
- [x] The user can retry from the error card; on success the component proposals appear as normal

---

[Parent](./index.md) | [Next: User Customization >](./user_customization.md)
