# User Customization

[< Prev: Component Identification](./component_identification.md) | [Parent](./index.md) | [Next: Nutritional Analysis >](./nutritional_analysis.md)

**Status:** Done

## Related Docs
- Technical: [technical/dish_analysis/user_customization.md](../../technical/dish_analysis/user_customization.md)

## Problem

The AI's first pass is a best guess — it may mis-name the dish, miss a component, include a component the user did not eat, or suggest a serving size that does not match what is actually on the plate. If the user cannot correct these details before nutrition is calculated, the final healthiness score is built on the wrong inputs and loses its value. Users need the last word on what they actually ate.

## Solution

On the Component Identification screen, every piece of AI output is editable by the user. The user can:

- Override the dish name by picking a different prediction or typing a custom one.
- Include or exclude individual components with a checkbox.
- Swap the serving size for any component using a per-component dropdown.
- Change how many servings of each component they ate.
- Add a completely new component the AI did not detect, with its own serving size and count.

Only when the user clicks **Confirm** is their corrected version saved and passed into the Nutritional Analysis phase.

## User Flow

```
Component Identification screen is showing AI proposals
  |
  v
User reviews the overall dish name
  |
  +--> Pick a different prediction from the list, OR
  +--> Type a custom name in the "custom dish name" field
  |
  v
User reviews each component
  |
  +--> Untick components they did not eat
  +--> Tick components that should be included
  +--> For each ticked component:
  |      - Open the serving size dropdown and pick a different option, or type a custom size
  |      - Adjust the servings count (+ / - buttons, or type a number)
  |
  +--> Add a custom component the AI missed:
         - Type the component name
         - Pick or type a serving size
         - Set a servings count
  |
  v
At least one component is ticked? 
  |
  Yes --> "Confirm" becomes active
  |
  v
Click Confirm
  |
  v
Edited version is saved --> Nutritional Analysis runs on user's confirmed data
```

## Scope

- **Included:**
  - Dish name override (pick from predictions or enter custom)
  - Per-component checkbox to include or exclude
  - Per-component serving size dropdown with custom entry
  - Per-component servings count (numeric input with +/- controls)
  - Adding a manual component not detected by AI
  - Validation that at least one component is ticked before Confirm is allowed
  - Editing remains available until the user clicks Confirm
- **Not included:**
  - Editing or overriding nutrition numbers after the Nutritional Analysis has run
  - Re-opening the editor and re-running analysis after confirmation (the current flow is one-shot)
  - Saving a customized meal as a reusable template for future uploads
  - Sharing or exporting the customized component list
  - Suggesting replacements ("swap fries for salad") or recipe variants

## Acceptance Criteria

- [x] The user can pick any of the predicted dish names, or type a custom name that is accepted as-is
- [x] Every AI-detected component has a checkbox, a serving size dropdown, and a servings count input that all work independently
- [x] Unticking every component disables the Confirm button and shows a hint that at least one component is required
- [x] The user can add at least one custom component with its own name, serving size, and count, and it is treated equivalently to AI-detected components
- [x] Custom entries for dish name and serving size do not overwrite the AI's predictions — both remain visible if the user changes their mind
- [x] After Confirm is clicked, the Nutritional Analysis phase receives the user's edited list, not the raw AI proposals

---

[< Prev: Component Identification](./component_identification.md) | [Parent](./index.md) | [Next: Nutritional Analysis >](./nutritional_analysis.md)
