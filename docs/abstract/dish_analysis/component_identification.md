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
  v
AI returns:
   - Overall meal name predictions (up to 5, each with confidence)
   - Per-component suggestions:
       * component name
       * 3-5 serving size options
       * predicted servings count
  |
  v
Proposals are shown on the Component Identification screen
  |
  v
User proceeds to review and customize the proposals --> see User Customization
```

## Scope

- **Included:**
  - Up to 5 dish name predictions, each with a confidence score
  - Detection of individual components in the photo (up to 10)
  - 3-5 serving size options per component
  - Predicted servings count per component
  - Loading indicator until the first pass completes
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

---

[Parent](./index.md) | [Next: User Customization >](./user_customization.md)
