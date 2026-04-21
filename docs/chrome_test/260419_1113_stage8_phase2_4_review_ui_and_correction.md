# Chrome E2E Test Spec — Stage 8: Phase 2.4 (Enhanced Review UI + Correction Endpoint)

**Feature:** Step 2 results view gains a single top-level **Edit** toggle that flips healthiness_score + rationale + five macros + micronutrient chips into inputs. Save posts to a new `POST /api/item/{record_id}/correction` endpoint that writes `result_gemini.step2_corrected` (preserving `step2_data` for audit) AND calls `crud_personalized_food.update_corrected_step2_data(query_id, payload)` so future Phase 2.2 retrieval surfaces user-verified nutrients. Three new read-only panels sit below the editable card: **ReasoningPanel** (expandable, all seven `reasoning_*` fields), **Top5DbMatches** (chip row with confidence_score badges), **PersonalizationMatches** (one card per match with thumbnail + description + similarity_score + prior nutrients).

**Spec generated:** 2026-04-19 11:13
**Plan target:** `docs/plan/260419_stage8_phase2_4_review_ui_and_correction.md`
**Screenshots directory:** `data/chrome_test_images/260419_1113_stage8_phase2_4_review_ui_and_correction/`

---

## Remarks

### Context

- **Frontend base URL:** `http://localhost:2512` (from `start_app.sh`).
- **Backend base URL:** `http://localhost:2612` (from `start_app.sh`).
- **Login page:** `http://localhost:2512/login`.
- **Test users:** placeholders (no `docs/technical/testing_context.md`):
  - `TEST_USER_ALPHA`
  - `TEST_USER_BETA`
- **Display precedence:** when `result_gemini.step2_corrected` is non-null, the frontend renders it over `step2_data` (user override wins).
- **Cleanup between runs:** standard personalization + dish-query delete for both users.

### Key assertion surface

Stage 8 is frontend-heavy. Assertions run via a mix of:

1. **DOM screenshots** — the Edit toggle, each editable input, the three new panels, and the correction-applied state.
2. **API fetch** (`javascript_tool`) against `GET /api/item/{id}` — inspect `result_gemini.step2_corrected` and `result_gemini.step2_data` coexistence.
3. **SQL** (operator terminal) — `SELECT corrected_step2_data FROM personalized_food_descriptions WHERE query_id = ?` to verify the personalization-row dual write.
4. **POST /correction via fetch** — 401 / 422 validation paths.

### Screenshot convention

> **Screenshot convention:**
> - Capture **one screenshot per Chrome action** — not one per "test step". A checklist bullet like *"Click Approve"* expands into:
>   1. Screenshot the Approve button highlighted/scrolled into view (before click) — `..._XX_approve_button.png`
>   2. Click it.
>   3. Screenshot the confirmation modal that appears (after click, if any) — `..._XX_approve_modal.png` or `..._XXb_approve_modal.png`
>   4. Click the modal's confirm button.
>   5. Screenshot the resulting state (status badge / workflow stage updated) — `..._XX_status_xxx.png`
> - Treat each of these as a distinct Chrome action. If an action yields a new visual state (modal opens, page navigates, status changes, form field appears), that state gets its own file.
> - Filename format: `test{id}_{HMMSS}_{NN}_{name}.png` where:
>   - `id` is the test number (`1`, `2`, `3`, …)
>   - `HMMSS` is the last 5 digits of the system clock `HHMMSS` at the moment of capture (so files sort in chronological order)
>   - `NN` is a two-digit action sequence number within the test (`01`, `02`, …); sub-actions may use a letter suffix (`06b`, `06c`) or the next sequential number — either is fine as long as the order is preserved
>   - `name` is a short kebab-snake label describing the visible state (`list_empty`, `approve_button`, `modal_confirm`, `status_paid`)
> - Before each `screencapture -R …` call, bring the target application tab to the front of its Chrome window via AppleScript (lookup by URL substring, set active tab index, set window index to 1, `activate`). This guards against the user browsing another tab/window while the test runs.

---

## Database Pre-Interaction

### Cleanup (run before AND after every execution)

```sql
DELETE FROM personalized_food_descriptions
WHERE user_id IN (SELECT id FROM users WHERE username IN ('test_user_alpha', 'test_user_beta'));

DELETE FROM dish_image_query_prod_dev
WHERE user_id IN (SELECT id FROM users WHERE username IN ('test_user_alpha', 'test_user_beta'));
```

### Test image assets

- `chicken_rice_1.jpg`, `chicken_rice_2.jpg` — similar chicken-rice plates; first for Test 1's baseline correction, second for Test 3's subsequent-upload retrieval assertion.

---

## Pre-requisite

Run Cleanup SQL, `localStorage.clear()`, confirm `nutrition_foods` is populated.

---

## Tests

### Test 1 — Happy path: Edit → change → Save writes both stores (desktop, 1080 × 1280)

**User(s):** `test_user_alpha`

**Goal:** Upload + confirm a dish; on Step 2 page, click Edit, change calories_kcal + healthiness_score_rationale, add a micronutrient chip, click Save. Assert: 200 response; DOM re-renders with the overridden values; `GET /api/item/{id}` shows `result_gemini.step2_corrected` populated; `SELECT corrected_step2_data FROM personalized_food_descriptions WHERE query_id = ?` returns the same payload.

- [ ] **Action 01 — set desktop viewport:** `resize_window` 1080 × 1280. **Screenshot:** `test1_{HMMSS}_01_viewport.png`
- [ ] **Action 02 — sign in as alpha:** **Screenshot:** `test1_{HMMSS}_02_dashboard.png`
- [ ] **Action 03 — upload chicken_rice_1.jpg:** **Screenshot:** `test1_{HMMSS}_03_upload.png`
- [ ] **Action 04 — Confirm Step 1:** **Screenshot:** `test1_{HMMSS}_04_confirm.png`
- [ ] **Action 05 — Step 2 view loads with AI values:** wait for `step2_data` to land; Edit button visible. **Screenshot:** `test1_{HMMSS}_05_step2_view.png`
- [ ] **Action 06 — click Edit:** all editable fields flip to inputs (healthiness score slider/input, rationale textarea, five macro number inputs, micronutrient chips with + / −). Save + Cancel buttons visible. **Screenshot:** `test1_{HMMSS}_06_edit_mode.png`
- [ ] **Action 07 — change calories input to 450:** **Screenshot:** `test1_{HMMSS}_07_cal_edit.png`
- [ ] **Action 08 — change rationale to a custom string:** e.g. `"Corrected by user — over-estimated fat."` **Screenshot:** `test1_{HMMSS}_08_rationale_edit.png`
- [ ] **Action 09 — add a micronutrient chip 'Magnesium':** type + Enter/Add. **Screenshot:** `test1_{HMMSS}_09_chip_added.png`
- [ ] **Action 10 — click Save:** button disables while in flight. **Screenshot:** `test1_{HMMSS}_10_save_in_flight.png`
- [ ] **Action 11 — Step 2 view re-renders with corrected values:** calories shows 450; rationale shows the user's text; Magnesium chip in the list. Edit button visible again (not in edit mode). **Screenshot:** `test1_{HMMSS}_11_corrected_rendered.png`
- [ ] **Action 12 — API: step2_corrected + step2_data coexist:**
  ```js
  const j = await (await fetch(`/api/item/${window.location.pathname.split('/').pop()}`, { credentials: 'include' })).json();
  const g = j.result_gemini || {};
  ({
    has_corrected: !!g.step2_corrected,
    has_original: !!g.step2_data,
    corrected_cal: g.step2_corrected?.calories_kcal,
    original_cal: g.step2_data?.calories_kcal,
    micronutrients: g.step2_corrected?.micronutrients,
  });
  ```
  Expect `has_corrected: true, has_original: true, corrected_cal: 450, original_cal !== 450, micronutrients contains "Magnesium"`. **Screenshot:** `test1_{HMMSS}_12_api_coexist.png`
- [ ] **Action 13 — SQL: personalization row also has corrected_step2_data:** run
  ```sql
  SELECT corrected_step2_data FROM personalized_food_descriptions
   WHERE query_id = <record_id>;
  ```
  Expect a non-null JSONB payload carrying the same calories_kcal + rationale + micronutrients. **Screenshot:** `test1_{HMMSS}_13_db_corrected.png` (terminal)

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time; record the DB payload verbatim)_
- **Improvement Proposals:**
  + good to have - On Save response, include the updated `step2_corrected` payload in the JSON body so the frontend can trust it without a follow-up GET.

---

### Test 2 — Cancel mid-edit reverts to server state; no endpoint call (desktop)

**User(s):** `test_user_alpha`

**Goal:** Open Edit, change fields, click Cancel. Verify no POST /correction was issued and the DOM reverts to the original AI values.

- [ ] **Action 01 — upload + confirm fresh dish:** **Screenshot:** `test2_{HMMSS}_01_fresh_step2.png`
- [ ] **Action 02 — capture POST /correction call count via fetch wrapper:**
  ```js
  window.__postCount = 0;
  const _origFetch = window.fetch;
  window.fetch = (...args) => {
    if (typeof args[0] === "string" && args[0].includes("/correction") &&
        (args[1]?.method || "GET").toUpperCase() === "POST") {
      window.__postCount += 1;
    }
    return _origFetch.apply(window, args);
  };
  ```
  **Screenshot:** `test2_{HMMSS}_02_fetch_wrapped.png`
- [ ] **Action 03 — click Edit:** inputs render. **Screenshot:** `test2_{HMMSS}_03_edit_mode.png`
- [ ] **Action 04 — change calories to 9999:** **Screenshot:** `test2_{HMMSS}_04_cal_changed.png`
- [ ] **Action 05 — click Cancel:** **Screenshot:** `test2_{HMMSS}_05_cancel_clicked.png`
- [ ] **Action 06 — DOM reverted, no POST fired:** verify calories shows the original value AND `window.__postCount === 0`. **Screenshot:** `test2_{HMMSS}_06_reverted.png`
- [ ] **Action 07 — API: step2_corrected is still null:**
  ```js
  const j = await (await fetch(`/api/item/${...}`, { credentials: 'include' })).json();
  ({ corrected: j.result_gemini?.step2_corrected });
  ```
  Expect `corrected: undefined` or `null`. **Screenshot:** `test2_{HMMSS}_07_api_no_corrected.png`

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time)_
- **Improvement Proposals:** _(empty baseline)_

---

### Test 3 — Subsequent upload: PersonalizationMatches card surfaces corrected nutrients (desktop)

**User(s):** `test_user_alpha`

**Goal:** After Test 1 wrote `corrected_step2_data` to the personalization row, a new similar-dish upload's Phase 2.2 retrieval should surface the corrected value in the PersonalizationMatches panel card (NOT the original prior_step2_data).

- [ ] **Action 01 — upload chicken_rice_2.jpg on a fresh slot:** **Screenshot:** `test3_{HMMSS}_01_upload.png`
- [ ] **Action 02 — Confirm Step 1:** **Screenshot:** `test3_{HMMSS}_02_confirm.png`
- [ ] **Action 03 — Step 2 view loads; PersonalizationMatches panel visible with one card:** **Screenshot:** `test3_{HMMSS}_03_panel_visible.png`
- [ ] **Action 04 — card shows corrected nutrients, not original:**
  ```js
  const j = await (await fetch(`/api/item/${...}`, { credentials: 'include' })).json();
  const m = (j.result_gemini?.personalized_matches || [])[0];
  ({
    similarity: m?.similarity_score,
    has_corrected: !!m?.corrected_step2_data,
    corrected_cal: m?.corrected_step2_data?.calories_kcal,
    prior_cal: m?.prior_step2_data?.calories_kcal,
  });
  ```
  Expect `has_corrected: true, corrected_cal: 450` (from Test 1 override), `prior_cal !== corrected_cal`. **Screenshot:** `test3_{HMMSS}_04_api_corrected_match.png`
- [ ] **Action 05 — DOM: card shows the 450 value (corrected) with a visual "User-verified" badge:** scroll the PersonalizationMatches card into view. **Screenshot:** `test3_{HMMSS}_05_card_user_verified.png`

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time)_
- **Improvement Proposals:**
  + must have - Add a "User-verified" badge (or equivalent visual) on PersonalizationMatches cards whose `corrected_step2_data` is non-null so users can see at a glance which matches carry their own prior overrides.

---

### Test 4 — Validation: calories < 0 and healthiness_score > 100 return 422 (desktop)

**User(s):** `test_user_alpha`

**Goal:** The Step2CorrectionRequest Pydantic schema enforces macro ≥ 0 and healthiness_score in [0, 100]. Client shouldn't submit out-of-range values, but if it does the endpoint returns 422.

- [ ] **Action 01 — use an existing record:** Test 1's record works. **Screenshot:** `test4_{HMMSS}_01_item_page.png`
- [ ] **Action 02 — POST /correction with calories_kcal=-50:**
  ```js
  const r = await fetch(`/api/item/<record_id>/correction`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({
      healthiness_score: 70,
      healthiness_score_rationale: "x",
      calories_kcal: -50,
      fiber_g: 2,
      carbs_g: 40,
      protein_g: 30,
      fat_g: 15,
      micronutrients: [],
    }),
  });
  ({ status: r.status });
  ```
  Expect `status: 422`. **Screenshot:** `test4_{HMMSS}_02_api_neg_cal.png`
- [ ] **Action 03 — POST /correction with healthiness_score=150:** same call with score out of range. Expect `status: 422`. **Screenshot:** `test4_{HMMSS}_03_api_oor_score.png`
- [ ] **Action 04 — DB unchanged:** `SELECT result_gemini->'step2_corrected' FROM dish_image_query_prod_dev WHERE id = <record_id>`. Unchanged from Test 1's value. **Screenshot:** `test4_{HMMSS}_04_db_unchanged.png` (terminal)

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time)_
- **Improvement Proposals:**
  + good to have - Client-side validation: disable Save when calories_kcal < 0 or healthiness_score is outside [0, 100] so 422s never reach the user.

---

### Test 5 — Permission guard + three new panels' empty-state rendering (desktop)

**User(s):** `test_user_beta` (cold-start for beta)

**Goal:** Two invariants in one test — auth guard on POST /correction, plus empty-state rendering for the three new panels when the user has no DB matches / no personalization / minimal reasoning.

- [ ] **Action 01 — sign out alpha, sign in beta:** **Screenshot:** `test5_{HMMSS}_01_beta_dashboard.png`
- [ ] **Action 02 — beta uploads a dish and confirms:** full happy-path cycle. **Screenshot:** `test5_{HMMSS}_02_confirmed.png`
- [ ] **Action 03 — Step 2 view loads:** **Screenshot:** `test5_{HMMSS}_03_step2_view.png`
- [ ] **Action 04 — ReasoningPanel renders (always visible); click to expand:** **Screenshot:** `test5_{HMMSS}_04_reasoning_expanded.png`
- [ ] **Action 05 — Top5DbMatches panel: either hidden OR shows empty state:** if no DB match cleared its display threshold, the panel should either be absent or render an empty-state message. **Screenshot:** `test5_{HMMSS}_05_db_panel_state.png`
- [ ] **Action 06 — PersonalizationMatches panel: hidden (beta is cold-start):** cold-start user; personalized_matches is []; panel should not render. **Screenshot:** `test5_{HMMSS}_06_persona_hidden.png`
- [ ] **Action 07 — sign out; POST /correction without token → 401:**
  ```js
  localStorage.clear();
  const r = await fetch(`/api/item/<beta_record>/correction`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ healthiness_score: 50, healthiness_score_rationale: "x",
      calories_kcal: 100, fiber_g: 1, carbs_g: 10, protein_g: 5, fat_g: 2,
      micronutrients: [] }),
  });
  ({ status: r.status });
  ```
  Expect `status: 401`. **Screenshot:** `test5_{HMMSS}_07_api_401.png`

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time; flag any panel that renders incorrectly on empty state)_
- **Improvement Proposals:** _(empty baseline)_

---

### Test 6 — Mobile: happy-path Edit → Save (mirrors Test 1)

**User(s):** `test_user_alpha`

**Goal:** Replay Test 1's Edit → change → Save at mobile viewport. Verify the Edit button, input fields, and micronutrient chip UI all usable on 375 px.

- [ ] **Action 01 — set mobile viewport:** `resize_window` 375 × 1080. **Screenshot:** `test6_{HMMSS}_01_viewport.png`
- [ ] **Action 02 — upload + confirm fresh dish (alpha mobile):** **Screenshot:** `test6_{HMMSS}_02_confirmed.png`
- [ ] **Action 03 — Step 2 view on mobile:** **Screenshot:** `test6_{HMMSS}_03_step2_mobile.png`
- [ ] **Action 03b — overflow check on Step 2 view:** horizontal overflow JS; `hasOverflow === false`. **Screenshot:** `test6_{HMMSS}_03b_overflow.png`
- [ ] **Action 04 — tap Edit (tap-target check):** verify button height ≥ 44 px. **Screenshot:** `test6_{HMMSS}_04_edit_tap.png`
- [ ] **Action 05 — inputs render on mobile:** **Screenshot:** `test6_{HMMSS}_05_inputs_mobile.png`
- [ ] **Action 06 — change calories + add chip + Save:** **Screenshot:** `test6_{HMMSS}_06_save.png`
- [ ] **Action 07 — corrected state renders on mobile:** **Screenshot:** `test6_{HMMSS}_07_corrected_mobile.png`
- [ ] **Action 08 — API: step2_corrected populated:** **Screenshot:** `test6_{HMMSS}_08_api.png`

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time)_
- **Improvement Proposals:** _(empty baseline)_

---

### Test 7 — Mobile: Cancel reverts (mirrors Test 2)

**User(s):** `test_user_alpha`

**Goal:** Cancel mid-edit at mobile viewport; no POST fired; DOM reverts cleanly.

- [ ] **Action 01 — upload + confirm fresh dish:** **Screenshot:** `test7_{HMMSS}_01_confirmed.png`
- [ ] **Action 02 — wrap fetch to count POSTs:** same snippet as Test 2 Action 02. **Screenshot:** `test7_{HMMSS}_02_wrapped.png`
- [ ] **Action 03 — Edit → change → Cancel:** **Screenshot:** `test7_{HMMSS}_03_cancel.png`
- [ ] **Action 04 — DOM reverted; postCount === 0:** **Screenshot:** `test7_{HMMSS}_04_reverted.png`
- [ ] **Action 05 — readability check on the Step 2 card:** body text ≥ 12 px. **Screenshot:** `test7_{HMMSS}_05_readability.png`

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time)_
- **Improvement Proposals:** _(empty baseline)_

---

### Test 8 — Mobile: PersonalizationMatches card on subsequent upload (mirrors Test 3)

**User(s):** `test_user_alpha`

**Goal:** Subsequent upload's Phase 2.2 → card surfaces corrected nutrients on mobile; scroll-reachability on the Step 2 page.

- [ ] **Action 01 — upload chicken_rice_2.jpg on fresh slot (alpha, mobile):** **Screenshot:** `test8_{HMMSS}_01_upload.png`
- [ ] **Action 02 — Step 2 view + panel visible:** **Screenshot:** `test8_{HMMSS}_02_panel.png`
- [ ] **Action 03 — card shows corrected nutrients:** **Screenshot:** `test8_{HMMSS}_03_card.png`
- [ ] **Action 04 — scroll-reachability to bottom of Step 2:** **Screenshot:** `test8_{HMMSS}_04_scroll.png`

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time)_
- **Improvement Proposals:** _(empty baseline)_

---

### Test 9 — Mobile validation (mirrors Test 4)

**User(s):** `test_user_alpha`

**Goal:** 422 on out-of-range values, same as desktop Test 4.

- [ ] **Action 01 — POST /correction with calories=-5 via fetch:** expect 422. **Screenshot:** `test9_{HMMSS}_01_api_422.png`
- [ ] **Action 02 — POST /correction with healthiness_score=200:** expect 422. **Screenshot:** `test9_{HMMSS}_02_api_422b.png`

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time)_
- **Improvement Proposals:** _(empty baseline)_

---

### Test 10 — Mobile permission guard (mirrors Test 5)

**User(s):** _(unauthenticated)_

**Goal:** POST /correction without token returns 401 at mobile viewport.

- [ ] **Action 01 — clear tokens:** `localStorage.clear()`. **Screenshot:** `test10_{HMMSS}_01_logged_out.png`
- [ ] **Action 02 — POST /correction → 401:** **Screenshot:** `test10_{HMMSS}_02_api_401.png`
- [ ] **Action 03 — login page overflow check at 375 px:** **Screenshot:** `test10_{HMMSS}_03_login_overflow.png`

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time)_
- **Improvement Proposals:** _(empty baseline)_

---

## Summary for the Caller

- **Output file:** `docs/chrome_test/260419_1113_stage8_phase2_4_review_ui_and_correction.md`
- **Screenshots directory:** `data/chrome_test_images/260419_1113_stage8_phase2_4_review_ui_and_correction/`
- **Number of tests:** 10 total — 5 desktop + 5 mobile.
- **Users involved:** placeholders `test_user_alpha`, `test_user_beta` (replace with seeded usernames).
- **Rough screenshot budget:** ~55 PNGs + ~4 terminal captures.
- **Viewport notes:** Test 1 Action 01 sets 1080 × 1280; Test 6 Action 01 sets 375 × 1080.
- **Critical caveats:**
  - Frontend-heavy: DOM screenshots need stable selectors for the Edit button, each macro input, and the three new panels. The plan should ship deterministic `data-testid` attributes (e.g. `data-testid="step2-edit-toggle"`, `"step2-calories-input"`, `"persona-card-${query_id}"`) to avoid XPath brittleness.
  - Placeholder usernames (no `docs/technical/testing_context.md`).
  - Runtime cost: each test triggers a real Phase 1 + Phase 2 Gemini Pro cycle on upload (~15 s wall-clock). 10 tests ≈ 3 min + Pro pricing.
- **Next step:** spec stays `IN QUEUE`. `feature-implement-full` will invoke `chrome-test-execute` after Stage 8 lands.
