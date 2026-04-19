# Personalized Data Card (Research only)

**Feature**: Add a collapsible "Personalized Data (Research only)" card on the Dish Analysis Details page, placed between the Step 1/Step 2 tab strip and the "Overall Meal Name" card, showing the Phase 1.1.1(a) flash caption for the current upload and the top-1 personalization-lookup hit.

**Plan Created:** 2026-04-19
**Status:** Plan
**Reference**:
- [Discussion — Food DB end-to-end workflow](../discussion/260418_food_db.md)
- [Abstract — Component Identification](../abstract/dish_analysis/component_identification.md)
- [Technical — Component Identification](../technical/dish_analysis/component_identification.md)
- [Technical — Personalized Food Index](../technical/dish_analysis/personalized_food_index.md)
- [Testing Context](../technical/testing_context.md)

---

## Problem Statement

1. The Phase 1.1.1(a) fast caption (the Gemini 2.0 Flash plain-text description of the current upload) and the Phase 1.1.1(b) BM25 retrieval result are **invisible** in the UI today — they live on the backend row and are readable only via direct DB queries or API inspection. Nutrition researchers and PMs reviewing dish analyses cannot see whether Phase 1.1.1 fired at all, what caption the Flash model produced, or whether a prior upload was matched and with what similarity score.
2. The current `result_gemini` JSON exposes `reference_image` (the matched prior row) but **not** the current upload's own flash caption. Surfacing the caption requires one additional backend write at Phase 1.1.1 time — it is already computed in `resolve_reference_for_upload` but discarded after being persisted to the `personalized_food_descriptions` row.
3. This information is **not user-facing**: end users shouldn't have to read a Gemini Flash caption or see BM25 mechanics. It needs to live behind an explicit "Research only" surface that is collapsed by default and clearly labeled as a debug panel.

---

## Proposed Solution

Add a new `<PersonalizedDataCard>` component on the Dish Analysis Details page that is rendered **only in the Step 1 view** (the same conditional that renders `<Step1ComponentEditor>`), between `<ItemStepTabs>` and `<Step1ComponentEditor>`. The card is collapsed by default; a chevron toggle on the right edge of the header expands/collapses the body. The body has two sections:

1. **Flash Caption (Phase 1.1.1(a))** — renders `result_gemini.flash_caption` verbatim. Falls back to "No caption generated (Flash call unavailable)" when the field is `null` (graceful-degrade cases from the orchestrator).
2. **Most Relevant Prior Item (Phase 1.1.1(b))** — renders `result_gemini.reference_image` as a compact card with the prior thumbnail, description, similarity-score badge, and a link to `/item/{reference.query_id}`. Falls back to "No prior match — cold-start upload or below 0.25 threshold" when the field is `null`.

The only backend change is exposing the **current** upload's flash caption on `result_gemini.flash_caption`. The `reference_image` field is already populated. Both values are produced inside `resolve_reference_for_upload`; the refactor returns them as a dict `{ "flash_caption": str | None, "reference_image": dict | None }` instead of just the reference. `analyze_image_background` merges both onto the pre-Pro blob.

The header label reads **"Personalized Data (Research only)"** — the parenthetical explicitly communicates that this is not a product feature, only an engineering/research surface.

```
+------------------------------------------------------------+
|  Personalized Data (Research only)                   [ ▼ ] |
+------------------------------------------------------------+
           (expanded state below, collapsed state hides body)
+------------------------------------------------------------+
|  Flash Caption (Phase 1.1.1(a))                            |
|    The image shows a plate of golden-brown fried           |
|    chicken pieces sprinkled with salt.                     |
|                                                            |
|  Most Relevant Prior Item (Phase 1.1.1(b))                 |
|    [thumb]  Query #25                       [0.72 sim]     |
|             Grilled chicken rice with…                     |
|             → /item/25                                     |
+------------------------------------------------------------+
```

---

## Current Implementation Analysis

### What Exists (keep as-is)

| Component | File | Status |
|-----------|------|--------|
| `generate_fast_caption_async` | `backend/src/service/llm/fast_caption.py` | Keep — produces the Flash caption unchanged. |
| `personalized_food_index.search_for_user` | `backend/src/service/personalized_food_index.py` | Keep — post-Jaccard-fix, already returns absolute-scale similarity. |
| `crud_personalized_food.insert_description_row` | `backend/src/crud/crud_personalized_food.py` | Keep — still inserts the caption into the corpus. |
| `result_gemini.reference_image` persistence | `backend/src/api/item_step1_tasks.py` | Keep — already writes the matched-prior-row blob to `reference_image`. |
| `<ItemStepTabs>` | `frontend/src/components/item/ItemStepTabs.jsx` | Keep — the Step 1 / Step 2 tab strip visible above the new card. |
| `<Step1ComponentEditor>` | `frontend/src/components/item/Step1ComponentEditor.jsx` | Keep — the Overall Meal Name / Individual Dishes / Confirm card below the new card. |
| `<PersonalizationMatches>` (Phase 2.2 panel) | `frontend/src/components/item/PersonalizationMatches.jsx` | Keep — different feature; renders post-confirm under Step 2. |

### What Changes

| Component | Current | Proposed |
|-----------|---------|----------|
| `resolve_reference_for_upload` return shape | `Optional[Dict[str, Any]]` — the matched-prior-row dict or `None` | `Optional[Dict[str, Any]]` — `{ "flash_caption": str \| None, "reference_image": dict \| None }` or `None` on retry short-circuit |
| `analyze_image_background` pre-blob merge | writes `pre_blob["reference_image"] = reference` only | also writes `pre_blob["flash_caption"] = reference_out["flash_caption"]` |
| `result_gemini` JSON contract | has `reference_image` | also has `flash_caption` (string or null) |
| `<ItemV2>` Step 1 conditional render | `<Step1ComponentEditor>` alone | `<PersonalizedDataCard>` above `<Step1ComponentEditor>` |
| Docs | `technical/dish_analysis/component_identification.md` doesn't mention `flash_caption` | add the new JSON key + the frontend `<PersonalizedDataCard>` component to the checklist |

---

## Implementation Plan

### Key Workflow

```
URL / file upload arrives
  │
  ▼
analyze_image_background (Phase 1.1.1 + 1.1.2 background task)
  │
  ├── resolve_reference_for_upload(user_id, query_id, image_path)
  │     │
  │     ├── generate_fast_caption_async(image_path) → caption
  │     ├── tokenize(caption) → tokens
  │     ├── search_for_user(user_id, tokens, …) → top_1 or None
  │     ├── insert_description_row(…)            [corpus seed]
  │     └── return { flash_caption: caption, reference_image: {…} | None }
  │
  ├── pre_blob["flash_caption"] = reference_out["flash_caption"]      [NEW]
  ├── pre_blob["reference_image"] = reference_out["reference_image"]
  └── update_dish_image_query_results(query_id, result_gemini=pre_blob)
  │
  ▼
Phase 1.1.2 (Gemini Pro component ID) — unchanged
  │
  ▼
Frontend polls /api/item/{id} and reads:
    result_gemini.flash_caption         (new — surfaced in the card)
    result_gemini.reference_image       (already there)
  │
  ▼
<ItemV2> renders <PersonalizedDataCard>, collapsed by default.
User clicks the chevron → body reveals Flash Caption + Most Relevant Prior Item.
```

**To Delete**: None.
**To Update**: `resolve_reference_for_upload` return shape; `analyze_image_background` pre-blob merge.
**To Add New**: `flash_caption` key on `result_gemini`; `<PersonalizedDataCard>` component and its conditional render in `<ItemV2>`.

### Database Schema

**To Delete:**

One-time pre-deploy cleanup — **purge every pre-feature record** so no row exists without `result_gemini.flash_caption`. Operator runs the following DELETE statements manually (they cannot live in `scripts/sql/` because migration files are DDL-only — `DELETE` would be stripped):

```sql
-- Purge every existing dish upload + personalization row across all users.
DELETE FROM personalized_food_descriptions;
DELETE FROM dish_image_query_prod_dev;
```

Image files on disk become orphaned after the DELETE. Operator runs:

```bash
rm -f data/images/*_u*_dish*.jpg
```

File this under `scripts/cleanup/260419_personalized_data_card_purge.sql` + `scripts/cleanup/260419_personalized_data_card_purge.sh` (new directory; mirrors the `scripts/` layout the one-off migration script `s251107_1530_migrate_to_dish_position.py` already sets the precedent for).

**To Update / To Add New:** No schema change, no new migration file. The feature uses data already being written by Phase 1.1.1 (the caption is in `personalized_food_descriptions.description` and the matched-prior blob is in `result_gemini.reference_image`).

### CRUD

**To Delete / To Update / To Add New:** None. The feature does not require any new CRUD helper. `crud_personalized_food.insert_description_row` and `get_row_by_query_id` are reused unchanged.

### Services

**To Delete**: None.

**To Update**:
- `backend/src/service/personalized_reference.py::resolve_reference_for_upload`
  - **Change the return shape** from `Optional[Dict[str, Any]]` (the reference dict) to `Optional[Dict[str, Any]]` with explicit keys:
    ```python
    Optional[{
        "flash_caption": str | None,     # Current upload's Flash description, None on Flash failure.
        "reference_image": dict | None,  # Matched prior row, None on cold-start / below-threshold.
    }]
    ```
  - Retry short-circuit still returns `None` (no change).
  - Graceful-degrade Flash-failure branch returns `{"flash_caption": None, "reference_image": None}` (not `None`, so the caller can still stash `flash_caption: null` on the blob).
  - Empty-query-tokens branch returns `{"flash_caption": description, "reference_image": None}` (we did caption the image, we just couldn't search).
- Update the module docstring + function docstring accordingly.

**To Add New**: None.

### API Endpoints

**To Delete / To Update**: None at the HTTP layer.

**To Add New**: None. `GET /api/item/{id}` already returns the full `result_gemini` JSON; adding a new key is backward-compatible and requires zero router code changes. Frontend reads defensively with optional chaining.

### Testing

**To Delete**: None.

**To Update**:
- `backend/tests/test_personalized_reference.py` — all 10 existing call sites. Update assertions from `reference is None / reference == {...}` to the new dict shape: `{"flash_caption": ..., "reference_image": ...}`. Add a test for the Flash-failure branch asserting `flash_caption is None`.
- `backend/tests/test_item_step1_tasks.py` — the five `fake_resolve` / `_noop` doubles. Adjust their stubbed return values to the new dict shape. Add one assertion that `pre_blob["flash_caption"]` is written alongside `pre_blob["reference_image"]`.

**To Add New**:
- **Frontend unit tests** — `frontend/src/components/item/__tests__/PersonalizedDataCard.test.jsx`:
  - Collapsed by default (body not in DOM).
  - Click the chevron → body renders.
  - Flash caption text visible in expanded state.
  - Reference block with thumbnail + similarity badge visible in expanded state when `reference_image` is non-null.
  - Fallback text visible in expanded state when `flash_caption: null` or `reference_image: null`.
- **Backend integration test** — extend `backend/tests/test_item_step1_tasks.py` with a happy-path test asserting `result_gemini["flash_caption"]` is written to DB on a fresh upload.
- **Chrome E2E spec** — `docs/chrome_test/260419_1540_personalized_data_card.md` (see Chrome Claude Extension Execution sub-section below).

**Pre-commit loop (required):**

1. `source venv/bin/activate && pre-commit run --all-files`
2. Fix lint / line-count / type errors. The new `PersonalizedDataCard.jsx` file must stay under 300 lines.
3. Re-run until clean.

### Frontend

**To Delete**: None.

**To Update**:
- `frontend/src/pages/ItemV2.jsx`:
  - Destructure `flashCaption = resultGemini?.flash_caption` and `referenceImage = resultGemini?.reference_image` alongside the existing `step1Data`, `step2Data`, etc.
  - Render `<PersonalizedDataCard flashCaption={flashCaption} referenceImage={referenceImage} />` **immediately before** `<Step1ComponentEditor>` under the same conditional (`viewStep === 1 && step1Data` OR default-view with `currentStep === 1`).
  - Do NOT render the card in Step 2 view (Phase 2.2's `<PersonalizationMatches>` already covers the personalization surface there).
- `frontend/src/components/item/index.js`:
  - Add `export { default as PersonalizedDataCard } from "./PersonalizedDataCard";`.

**To Add New**:
- `frontend/src/components/item/PersonalizedDataCard.jsx` (target ~120 lines):
  - Props: `{ flashCaption: string | null, referenceImage: object | null }`.
  - Internal state: `const [expanded, setExpanded] = useState(false)`.
  - Header row: title text `"Personalized Data (Research only)"` on the left, a `<button>` on the right containing a chevron SVG (down/up based on `expanded`). The button toggles `expanded`. `aria-expanded={expanded}`, `aria-controls="personalized-data-body"`, `data-testid="personalized-data-toggle"`.
  - Body section (rendered only when `expanded`):
    - `<section data-testid="personalized-data-flash-caption">`:
      - Subheader: `"Flash Caption (Phase 1.1.1(a))"`.
      - Content: `flashCaption` inside an italicized paragraph, or the fallback `"No caption generated (Flash call unavailable)."` when `flashCaption == null`.
    - `<section data-testid="personalized-data-reference">`:
      - Subheader: `"Most Relevant Prior Item (Phase 1.1.1(b))"`.
      - If `referenceImage` is non-null: a compact card with:
        - `<img src={referenceImage.image_url}>` 64×64 thumbnail, lazy-loaded.
        - `referenceImage.description` truncated with CSS line-clamp.
        - A badge `"{similarity_score.toFixed(2)} sim"` (e.g. `0.72 sim`) in the same blue palette as existing "confidence" badges.
        - `<Link to={"/item/" + referenceImage.query_id}>` wrapping the row so the whole block navigates to the prior item page.
      - If `referenceImage` is null: fallback text `"No prior match — cold-start upload or below 0.25 threshold."`.
  - Styling: follow the existing card pattern (`bg-white rounded-lg shadow-md p-4 space-y-3`). Muted header color (e.g. `text-gray-500`) to signal it's a research-only surface, not a primary user action.

### Documentation

#### Abstract (`docs/abstract/`)

**To Delete**: None.

**To Update**:
- `docs/abstract/dish_analysis/component_identification.md`:
  - Under the existing `### Personalization (active)` block, append one sentence: `"For research review, a collapsed 'Personalized Data (Research only)' card on the Component Identification screen exposes the Flash caption and the top-1 retrieval result. It is hidden by default and does not affect the user flow."`
  - Under `## Scope`, add to `**Not included:**`: `"Editable or user-facing Personalization surface on this screen — the 'Personalized Data (Research only)' card is a non-editable debug panel aimed at engineers and PMs."`

**To Add New**: None — this feature piggybacks on the existing Component Identification abstract page.

#### Technical (`docs/technical/`)

**To Delete**: None.

**To Update**:
- `docs/technical/dish_analysis/component_identification.md`:
  - **`reference_image` JSON shape** sub-section: also document the adjacent `flash_caption` key. Example JSON:
    ```json
    {
      "flash_caption": "grilled chicken rice with cucumber",
      "reference_image": { "query_id": 1234, ... } 
    }
    ```
  - **Failure-mode table** row "Gemini Flash errors": change `reference_image: null` → `reference_image: null, flash_caption: null`.
  - **Frontend — Components** section: add a bullet for `<PersonalizedDataCard>` with its data sources (`result_gemini.flash_caption`, `result_gemini.reference_image`) and placement (between `<ItemStepTabs>` and `<Step1ComponentEditor>` in the Step 1 view).
  - **Component Checklist** at the bottom of the doc: append `- [ ] Frontend — <PersonalizedDataCard> research panel on the Step 1 view`.

**To Add New**: None.

#### API Documentation (`docs/api_doc/`)

No changes needed — `docs/api_doc/` does not exist in this project. The `GET /api/item/{id}` response is documented only via the technical doc + plan files. The new `result_gemini.flash_caption` key is mentioned in the technical-doc update above.

### Chrome Claude Extension Execution

**To Add New**: `docs/chrome_test/260419_1540_personalized_data_card.md` (5 desktop tests, ~30 actions total) covering:

1. **Card visible in Step 1 view, collapsed by default** — upload Ayam Goreng, navigate to `/item/{id}`, assert the header is rendered and the body (`[data-testid="personalized-data-flash-caption"]`) is NOT in the DOM.
2. **Expand → flash caption renders (cold start)** — click `[data-testid="personalized-data-toggle"]`, assert the Flash-caption body renders with text matching the DB `description`, and the Reference section shows the "cold-start" fallback.
3. **Expand → reference renders (warm start)** — upload Ayam Goreng a second time, expand the card on the new record, assert the reference section shows the prior thumbnail + similarity badge + link to the prior item page.
4. **Card hidden in Step 2 view** — click Confirm, wait for Step 2 to render, assert `<PersonalizedDataCard>` is no longer in the DOM.
5. **API contract** — assert `result_gemini.flash_caption` is a non-empty string on any successful Phase 1.1.1 run and `null` on a Flash-failure simulation (if a test hook is available; otherwise skip with note).

After implementation, run `/webapp-dev:chrome-test-execute docs/chrome_test/260419_1540_personalized_data_card.md` to execute.

---

## Dependencies

- **Phase 1.1.1(a)** (Stage 2) — already shipped (`backend/src/service/llm/fast_caption.py`, `resolve_reference_for_upload`).
- **Phase 1.1.1(b)** (Stage 2) — already shipped. Post-Jaccard-fix `similarity_score` is an absolute-scale measure, so the badge displays a meaningful `0.72 sim` rather than always 1.0.
- **`react-router-dom::Link`** — already imported elsewhere in `frontend/src/pages/ItemV2.jsx` for the back-to-dashboard link.

## Open Questions

All four questions **resolved** by the requester on 2026-04-19:

1. **Card scope — Step 1 only, or both Step 1 and Step 2 views?** → **Step 1 only.** `<PersonalizedDataCard>` renders under the same conditional as `<Step1ComponentEditor>` and is removed from the DOM when the view switches to Step 2.
2. **Thumbnail link behavior** — **Same tab.** `<Link to={`/item/${reference.query_id}`}>` (no `target="_blank"`).
3. **Similarity-score badge precision** — **`.toFixed(2)`** (e.g. `0.72 sim`).
4. **Caption persistence for older records** — **Purge every pre-feature record** before deploy. See the Database Schema → To Delete sub-section for the exact DELETE statements. After the purge, every row that exists in the DB has been analyzed with the new `flash_caption` field populated, so the frontend never needs to render a "missing field" fallback on historical data.
