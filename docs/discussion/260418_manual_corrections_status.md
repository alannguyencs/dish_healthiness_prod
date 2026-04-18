# Discussion — Manual Corrections Section (6 checkboxes)

**Question:** For each of the 6 items under "Refining the results with manual corrections for difficult cases", decide Done / Not Done and list missing pieces.

**Verdict:** **All 6 are Done.** They are implemented by `Step1ComponentEditor.jsx` plus its three children (`DishNameSelector`, `ComponentListItem`, `AddComponentForm`) and the standalone `ServingSizeReference` page mounted at `/reference/serving-size`.

---

## Where it lives in the docs

- **Abstract:** [`docs/abstract/dish_analysis/user_customization.md`](../abstract/dish_analysis/user_customization.md) — `Status: Done`. All 6 acceptance criteria are checked off (dish-name override, per-component checkbox + dropdown + count input, adding manual components, validation, custom-vs-prediction non-destructiveness, payload to Phase 2).
- **Technical:** [`docs/technical/dish_analysis/user_customization.md`](../technical/dish_analysis/user_customization.md) — every UI/state component related to these 6 items is `[x]` in the Component Checklist.
- The serving-size reference page is referenced from `Step1ComponentEditor.jsx:184-190` (`<Link to="/reference/serving-size" target="_blank">ⓘ Serving Size Guide</Link>`) and routed in `App.js:60-63`.

## Per-item verdict

### 1. Set the dish name → Done

- `frontend/src/components/item/DishNameSelector.jsx:26-46` — radio for the top prediction.
- `:49-88` — toggle that expands the rest of the predictions list.
- `:114-136` — "Custom Dish Name" radio + text input.
- `Step1ComponentEditor.jsx:20-28` — `selectedDishName`, `customDishName`, `useCustomDish` state; both buffers persist across the toggle so the user can flip back without losing work.
- `:130-136` — submit picks `useCustomDish ? customDishName : selectedDishName`, validates non-empty.

### 2. Include or exclude detected components → Done

- `ComponentListItem.jsx:30-37` — checkbox rendered when `!isManual` (AI-detected components).
- `Step1ComponentEditor.jsx:30-44` — `componentSelections[name].enabled` defaults to `true` on first load, persisted across re-entry.
- `Step1ComponentEditor.jsx:56-64` — `handleComponentToggle` flips the flag.
- `:138-144` — only `enabled` components are sent to Phase 2.
- `:147-150` — submit alerts and aborts if the user unticks every component.

### 3. Change the portion size (dropdown) → Done

- `ComponentListItem.jsx:74-92` — `<select>` populated from `servingSizeOptions` (the AI's 3-5 suggestions for that component).
- `Step1ComponentEditor.jsx:65-73` — `handleComponentServingSizeChange` writes the chosen value into per-component state.

### 4. Adjust portions (custom serving size + number of servings) → Done

Two sub-features, both implemented:

- **Custom portion description** — `ComponentListItem.jsx:91, 94-122` adds a `Custom...` option to the dropdown; selecting it swaps the `<select>` for a text input bound to `customValue`, which writes through `onServingSizeChange` so it round-trips into `componentSelections`.
- **Change number of portions** — `ComponentListItem.jsx:138-149` `<input type="number" min=0.1 max=10 step=0.1>` bound to `number_of_servings`. Handler at `Step1ComponentEditor.jsx:74-82` clamps via `parseFloat || 0.1`. Backend Pydantic re-validates `[0.01, 10.0]`.

### 5. Add a missed component → Done

- `AddComponentForm.jsx` — full form (component name, serving size, number of servings, Add/Cancel buttons).
- `Step1ComponentEditor.jsx:84-102` — `handleAddManualComponent` validates non-empty name + size, appends a row with synthetic `id = Date.now()`.
- Manual rows render through the same `ComponentListItem` with `isManual=true`, gaining a "Remove" button (`ComponentListItem.jsx:54-62`) and skipping the include/exclude checkbox.
- Backend `Step1ConfirmationRequest` accepts manual and AI components in a single uniform `components[]` array — no special casing on the server.

### 6. Serving Size Helpful Reference Guide → Done

- `frontend/src/pages/ServingSizeReference.jsx` — standalone page exists.
- `frontend/src/App.js:14, 60-63` — imported and routed at `/reference/serving-size`.
- `Step1ComponentEditor.jsx:184-190` — accessible from the editor as "ⓘ Serving Size Guide" link that opens in a new tab.

## Pipeline (Current State)

### Current State

```
[User] Lands on Step 1 results
   │
   ▼
[Frontend] Step1ComponentEditor reads dish_predictions + components
   │
   ├──> [User] DishNameSelector
   │     │
   │     ├── pick top prediction (radio)
   │     ├── expand "Show more" → pick another prediction
   │     └── flip to "Custom Dish Name" → type free-text
   │
   ├──> [User] ComponentListItem × N (AI components)
   │     │
   │     ├── checkbox: include / exclude
   │     ├── dropdown: pick serving size (or "Custom..." → text input)
   │     └── number input: number of servings (min 0.1, max 10)
   │
   ├──> [User] AddComponentForm (optional)
   │     │
   │     └── add manual row with name + size + count
   │
   ├──> [User] (optional) "ⓘ Serving Size Guide" → opens
   │     /reference/serving-size in a new tab
   │
   ▼
[User] Click "Confirm and Analyze Nutrition"
   │
   │   guards: dish name non-empty, ≥1 component selected
   │
   ▼
[Frontend] POST /api/item/{id}/confirm-step1
   │
   ▼
[Backend] confirm_step1_and_trigger_step2 → optimistic write +
          schedule Phase 2 background task
```

### New State

_Pending comments._

## Recommendation

Tick all 6 boxes in `docs/issues/260414.md`.

## Next Steps

- Mark all 6 items `[x]`.
- Move on to "Dish Recognition and Quantity Estimation" — most of those items are also covered by the existing Step 1 pipeline.
