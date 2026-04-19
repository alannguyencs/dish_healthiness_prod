# Chrome E2E Test Spec — Stage 10: Phase 2.4 "AI Assistant Edit"

**Feature:** Step 2 results view gains a second button — **AI Assistant Edit** — beside the existing **Manual Edit**. Clicking it expands an inline textarea + `Submit` control; on submit, the frontend POSTs `{ prompt }` to `POST /api/item/{record_id}/ai-assistant-correction`. The backend loads the current effective Step 2 payload (`step2_corrected` if present, else `step2_data`), calls Gemini 2.5 Pro with the query image + trimmed baseline JSON + user hint, and commits the revised payload **directly** (no preview / Accept-Cancel step) via the same `/correction` persistence path. `result_gemini.step2_corrected.ai_assistant_prompt = <latest user hint>`, and `personalized_food_descriptions.corrected_step2_data` is mirrored so future Phase 2.2 lookups surface the AI-assisted nutrients.

**Spec generated:** 2026-04-19 19:40
**Plan target:** `docs/plan/260419_ai_assistant_edit.md`
**Screenshots directory:** `data/chrome_test_images/260419_1940_ai_assistant_edit/`

---

## Remarks

### Context

- **Frontend base URL:** `http://localhost:2512`
- **Backend base URL:** `http://localhost:2612`
- **Test user:** `Alan` (from `docs/technical/testing_context.md`; no sign-in required for local testing)
- **Baseline source:** the revise service reads the current effective Step 2 payload — `result_gemini.step2_corrected` if present, else `result_gemini.step2_data`. This lets successive AI prompts refine previous corrections.
- **Display precedence:** the frontend keeps its Stage 8 rule — `step2_corrected` over `step2_data` when present.
- **Audit field:** `step2_corrected.ai_assistant_prompt: str` is overwritten on every AI revision (latest wins); manual edits via Button A leave the field unset (or at its prior value — the spec tolerates either).
- **Disabled state:** while an AI revision is in flight, both buttons (Manual Edit, AI Assistant Edit) disable and the AI button shows "Revising…".
- **Cleanup between runs:** standard personalization + dish-query delete for `Alan`.

### Key assertion surface

Stage 10 is frontend-thin (one new button + inline textarea) and backend-thick (new endpoint + revision service + new prompt template). Assertions run via:

1. **DOM screenshots** — the new button beside Manual Edit, the expanded textarea, the "Revising…" in-flight state, the re-rendered Step 2 card with revised numbers, and the persisted audit badge.
2. **API fetch** (`javascript_tool`) against `GET /api/item/{id}` — inspect `result_gemini.step2_corrected.ai_assistant_prompt` and the coexistence of `step2_data` + `step2_corrected`.
3. **SQL** (operator terminal) — `SELECT corrected_step2_data FROM personalized_food_descriptions WHERE query_id = ?` to verify the personalization dual-write mirrors the AI-revised payload.
4. **POST via fetch** — 422 validation (empty prompt), 401 (no cookie), 404 (wrong record id).

### Screenshot convention

> **Screenshot convention:**
> - Capture **one screenshot per Chrome action** — not one per "test step".
> - Filename format: `test{id}_{HMMSS}_{NN}_{name}.png` where
>   - `id` is the test number (`1`, `2`, `3`, …)
>   - `HMMSS` is the last 5 digits of the system clock `HHMMSS` at the moment of capture
>   - `NN` is a two-digit action sequence number (`01`, `02`, …); sub-actions may use a letter suffix (`06b`, `06c`)
>   - `name` is a short kebab-snake label describing the visible state
> - Before each `screencapture -R …` call, bring the target application tab to the front of its Chrome window via AppleScript.

---

## Database Pre-Interaction

### Cleanup (run before AND after every execution)

```sql
DELETE FROM personalized_food_descriptions
WHERE user_id IN (SELECT id FROM users WHERE username = 'Alan');

DELETE FROM dish_image_query_prod_dev
WHERE user_id IN (SELECT id FROM users WHERE username = 'Alan');
```

### Test image assets

- **Primary canary:** `Ayam Goreng (Malaysian fried chicken)` — `https://www.marionskitchen.com/wp-content/uploads/2021/08/20201216_Malaysian-Fried-Chicken-Ayam-Goreng-11-Web-1024x1024-1.jpeg` (from `docs/technical/testing_context.md`).
- Reused across all tests — each test re-uploads from this URL to start with a clean `step2_data` baseline.

---

## Pre-requisite

Run Cleanup SQL, `localStorage.clear()`. No sign-in required.

---

## Tests

### Test 1 — Happy path: AI Assistant Edit lowers calories per a portion-size hint (desktop, 1280 × 900)

**User(s):** `Alan`

**Goal:** Upload the ayam goreng canary, confirm Step 1 with default proposals, wait for Step 2 to render. Click **AI Assistant Edit**, type *"Portions are smaller than the AI estimated — about 200 kcal per serving of fried chicken."*, submit. Assert: button shows "Revising…" while in flight; the Step 2 card re-renders with revised macros (typically lower `calories_kcal`); `GET /api/item/{id}` returns `result_gemini.step2_corrected.ai_assistant_prompt` equal to the hint; `SELECT corrected_step2_data FROM personalized_food_descriptions WHERE query_id = ?` returns the revised payload.

- [x] **Action 01 — set desktop viewport:** `resize_window` 1280 × 900. **Screenshot:** (implicit — viewport set before Action 02 capture)
- [x] **Action 02 — navigate to today's meal upload page:** **Screenshot:** `test1_11454_02_upload_page.png`
- [x] **Action 03 — upload ayam goreng via URL:** click "Or paste image URL", paste canary URL, click Load. **Screenshot:** `test1_11519_03_url_loaded.png`
- [x] **Action 04 — wait for Step 1 proposals, click Confirm and Analyze Nutrition:** **Screenshot:** `test1_11901_04_step1_confirmed.png`
- [x] **Action 05 — Step 2 view loads with AI baseline:** baseline `calories_kcal` = 1785, `dish_name` = "Fried Chicken". Two buttons visible: **✏️ Manual Edit**, **✨ AI Assistant Edit**. **Screenshot:** `test1_11935_05_step2_baseline.png`
- [x] **Action 06 — click AI Assistant Edit:** inline violet textarea panel + Submit/Cancel expand below the button row. Both edit buttons remain visible. **Screenshot:** `test1_11947_06_textarea_open.png`
- [x] **Action 07 — type hint into textarea:** *"Portions are smaller than the AI estimated — about 200 kcal per serving of fried chicken."* **Screenshot:** `test1_11955_07_hint_typed.png`
- [x] **Action 08 — click Submit:** buttons disable, AI Assistant Edit shows "Revising…". **Screenshot:** `test1_12000_08_revising.png`
- [x] **Action 09 — Step 2 card re-renders with revised payload:** revised `calories_kcal` = 1190 (down from 1785); rationale explains the portion-size correction. No Accept/Cancel modal appeared. **Screenshot:** `test1_12033_09_revised_rendered.png`
- [x] **Action 10 — API: ai_assistant_prompt persisted:** `fetch('/api/item/41')` returned `has_corrected: true, has_original: true, revised_cal: 1190, original_cal: 1785, ai_prompt` equals the submitted hint. **Screenshot:** `test1_12103_10_api_coexist.png`
- [x] **Action 11 — SQL: personalization row has corrected_step2_data with the revised macros:**
  ```
  query_id=41, cal=1190.0, prompt="Portions are smaller than the AI estimated — about 200 kcal per serving of fried chicken."
  ```
  Non-null JSONB payload whose `calories_kcal` = 1190 matches the revised value from Action 10. **Screenshot:** captured in terminal log (no PNG saved)

**Report:**

- **Status:** PASSED
- **Findings:**
  - Record ID 41 created for user Alan on 2026-04-19; Phase 1 completed (dish_predictions populated), user confirmed default proposals, Phase 2 landed with baseline `calories_kcal=1785`, `dish_name="Fried Chicken"`.
  - `POST /api/item/41/ai-assistant-correction` with body `{prompt: "Portions are smaller than the AI estimated — about 200 kcal per serving of fried chicken."}` completed in ~30s.
  - `result_gemini.step2_corrected.calories_kcal` = 1190 (down ~33% from baseline 1785) — LLM correctly applied the portion-size hint.
  - `result_gemini.step2_corrected.ai_assistant_prompt` persisted verbatim (latest-wins audit field working).
  - `result_gemini.step2_data.calories_kcal` preserved at 1785 (audit trail intact).
  - `personalized_food_descriptions.corrected_step2_data` dual-write succeeded: `query_id=41, calories_kcal=1190.0` — Phase 2.2 lookups on future similar uploads will now surface the user-assisted nutrients.
  - Button icons rendered correctly: `✏️ Manual Edit` and `✨ AI Assistant Edit` (violet accent). While revising, the AI button label flipped to `⏳ Revising…` and both buttons were disabled.
  - No Accept/Cancel preview step appeared — direct commit as specified.
  - Per-action screenshots saved to `data/chrome_test_images/260419_1940_ai_assistant_edit/`: `test1_11454_02_upload_page.png`, `test1_11519_03_url_loaded.png`, `test1_11901_04_step1_confirmed.png`, `test1_11935_05_step2_baseline.png`, `test1_11947_06_textarea_open.png`, `test1_11955_07_hint_typed.png`, `test1_12000_08_revising.png`, `test1_12033_09_revised_rendered.png`, `test1_12103_10_api_coexist.png` (9 PNGs total).
- **Improvement Proposals:**
  - _nice to have_ — The revise endpoint takes ~20–30s end-to-end (Gemini 2.5 Pro with image + thinking_budget=-1). Consider streaming the response or surfacing a progress indicator if users find the wait too long in practice.
  - _good to have_ — Surface the original `step2_data.calories_kcal` alongside the corrected value in the Step 2 card (small "was 1785 kcal" strikethrough) so the user sees what the AI changed. Currently only the "Corrected by you" badge signals a delta.

---

### Test 2 — Validation: empty prompt is rejected with 422 (desktop, 1280 × 900)

**User(s):** `Alan`

**Goal:** Confirm Step 1 on a fresh upload, open the AI Assistant textarea, leave it empty (or whitespace-only), click Submit. Assert: the request is either blocked client-side with a disabled Submit button OR the endpoint returns 422; in neither case does `step2_corrected` change.

- [ ] **Action 01 — upload + confirm a fresh ayam goreng record:** (compressed reuse of Test 1 Actions 02–05). **Screenshot:** `test2_{HMMSS}_01_step2_baseline.png`
- [ ] **Action 02 — click AI Assistant Edit:** **Screenshot:** `test2_{HMMSS}_02_textarea_open.png`
- [ ] **Action 03 — leave textarea empty; click Submit (or observe disabled Submit):** if client-side disabled, capture the disabled state. If enabled, click and capture the 422 toast / inline error. **Screenshot:** `test2_{HMMSS}_03_empty_rejected.png`
- [ ] **Action 04 — API: no corrected payload written:**
  ```js
  const recId = window.location.pathname.split('/').pop();
  const j = await (await fetch(`/api/item/${recId}`, { credentials: 'include' })).json();
  ({ has_corrected: !!j.result_gemini?.step2_corrected });
  ```
  Expect `has_corrected: false`. **Screenshot:** `test2_{HMMSS}_04_api_unchanged.png`

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time)_
- **Improvement Proposals:** _(populated at execution time)_

---

### Test 3 — Stacked edits: Manual edit → AI Assistant refines (desktop, 1280 × 900)

**User(s):** `Alan`

**Goal:** Exercise the "current effective payload as baseline" clarification. Upload + confirm a new ayam goreng record. Click **Manual Edit**, change `calories_kcal` to an obviously wrong value (e.g. 9999), Save. Now click **AI Assistant Edit**, submit *"Restore a realistic calorie count for ayam goreng — you had the right sense before."*. Assert: the AI's revised payload is **not** 9999 (it reconsidered from the manual baseline); `ai_assistant_prompt` is set to the restore-hint; the manual 9999 is still visible in `step2_data` coexistence (original) OR in prior `step2_corrected` if stored separately.

- [ ] **Action 01 — upload + confirm:** **Screenshot:** `test3_{HMMSS}_01_step2_baseline.png`
- [ ] **Action 02 — click Manual Edit, set calories to 9999, Save:** **Screenshot:** `test3_{HMMSS}_02_manual_saved.png`
- [ ] **Action 03 — verify manual correction rendered:** card shows calories 9999 + "Corrected by you" badge. **Screenshot:** `test3_{HMMSS}_03_manual_rendered.png`
- [ ] **Action 04 — click AI Assistant Edit, submit restore-hint:** **Screenshot:** `test3_{HMMSS}_04_ai_submitted.png`
- [ ] **Action 05 — card re-renders with realistic calories (≠ 9999):** **Screenshot:** `test3_{HMMSS}_05_ai_revised.png`
- [ ] **Action 06 — API: ai_assistant_prompt set, calories revised from the manual baseline:**
  ```js
  const recId = window.location.pathname.split('/').pop();
  const j = await (await fetch(`/api/item/${recId}`, { credentials: 'include' })).json();
  const g = j.result_gemini || {};
  ({
    original_cal: g.step2_data?.calories_kcal,
    corrected_cal: g.step2_corrected?.calories_kcal,
    ai_prompt: g.step2_corrected?.ai_assistant_prompt,
  });
  ```
  Expect `corrected_cal` is a realistic number (not 9999 and not necessarily equal to `original_cal`). Expect `ai_prompt` equals the restore-hint. **Screenshot:** `test3_{HMMSS}_06_api_stacked.png`

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time)_
- **Improvement Proposals:** _(populated at execution time)_

---

### Test 4 — Re-submit: second AI prompt overwrites ai_assistant_prompt (desktop, 1280 × 900)

**User(s):** `Alan`

**Goal:** After Test-1-style first AI submission, click AI Assistant Edit again with a different hint. Assert: the revised card changes; `ai_assistant_prompt` matches the **second** hint (not the first).

- [ ] **Action 01 — reach revised state via Test 1 actions 02–09 compressed:** **Screenshot:** `test4_{HMMSS}_01_first_revision.png`
- [ ] **Action 02 — click AI Assistant Edit; enter second hint:** e.g. *"Actually 3 portions were served; re-calculate total calories at full baseline per-portion size."* **Screenshot:** `test4_{HMMSS}_02_second_hint.png`
- [ ] **Action 03 — Submit:** **Screenshot:** `test4_{HMMSS}_03_second_revising.png`
- [ ] **Action 04 — card re-renders again:** **Screenshot:** `test4_{HMMSS}_04_second_revised.png`
- [ ] **Action 05 — API: ai_assistant_prompt overwritten to the second hint:**
  ```js
  const recId = window.location.pathname.split('/').pop();
  const j = await (await fetch(`/api/item/${recId}`, { credentials: 'include' })).json();
  ({ ai_prompt: j.result_gemini?.step2_corrected?.ai_assistant_prompt });
  ```
  Expect `ai_prompt` equals the second hint (not the first). **Screenshot:** `test4_{HMMSS}_05_api_overwritten.png`

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time)_
- **Improvement Proposals:** _(populated at execution time)_

---

### Test 5 — Cross-stage invariant: Phase 1 + 2.1/2.2 artifacts untouched (desktop, 1280 × 900)

**User(s):** `Alan`

**Goal:** Confirm the workflow diagram's invariant #7. After an AI Assistant Edit, `result_gemini.step1_data`, `step1_confirmed`, `confirmed_dish_name`, `confirmed_components`, `nutrition_db_matches`, and `personalized_matches` must all be byte-for-byte identical to their pre-revise values.

- [ ] **Action 01 — reach Step 2 baseline state (Test 1 actions 02–05):** **Screenshot:** `test5_{HMMSS}_01_step2_baseline.png`
- [ ] **Action 02 — capture baseline artifacts:**
  ```js
  const recId = window.location.pathname.split('/').pop();
  const j = await (await fetch(`/api/item/${recId}`, { credentials: 'include' })).json();
  const g = j.result_gemini || {};
  window.__baseline__ = {
    step1_data: JSON.stringify(g.step1_data),
    step1_confirmed: g.step1_confirmed,
    confirmed_dish_name: g.confirmed_dish_name,
    confirmed_components: JSON.stringify(g.confirmed_components),
    nutrition_db_matches: JSON.stringify(g.nutrition_db_matches),
    personalized_matches: JSON.stringify(g.personalized_matches),
  };
  ```
  Assert all fields present. **Screenshot:** `test5_{HMMSS}_02_baseline_captured.png`
- [ ] **Action 03 — click AI Assistant Edit and submit a hint:** **Screenshot:** `test5_{HMMSS}_03_ai_submitted.png`
- [ ] **Action 04 — card re-renders:** **Screenshot:** `test5_{HMMSS}_04_ai_revised.png`
- [ ] **Action 05 — compare artifacts:**
  ```js
  const recId = window.location.pathname.split('/').pop();
  const j = await (await fetch(`/api/item/${recId}`, { credentials: 'include' })).json();
  const g = j.result_gemini || {};
  const b = window.__baseline__;
  ({
    step1_data_match: JSON.stringify(g.step1_data) === b.step1_data,
    step1_confirmed_match: g.step1_confirmed === b.step1_confirmed,
    dish_name_match: g.confirmed_dish_name === b.confirmed_dish_name,
    components_match: JSON.stringify(g.confirmed_components) === b.confirmed_components,
    db_match: JSON.stringify(g.nutrition_db_matches) === b.nutrition_db_matches,
    personalized_match: JSON.stringify(g.personalized_matches) === b.personalized_matches,
  });
  ```
  Expect all six booleans `true`. **Screenshot:** `test5_{HMMSS}_05_invariant_verified.png`

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time)_
- **Improvement Proposals:** _(populated at execution time)_

---

### Test 6 — Mobile layout: AI Assistant textarea fits 375 × 812 (mobile)

**User(s):** `Alan`

**Goal:** On iPhone-13-sized viewport, verify the AI Assistant button fits beside Manual Edit without horizontal overflow, the textarea expands to full width, Submit is tappable (≥ 44 px tall), and the revised card stays readable.

- [ ] **Action 01 — resize to 375 × 812:** `resize_window` 375 × 812. **Screenshot:** `test6_{HMMSS}_01_viewport.png`
- [ ] **Action 02 — upload + confirm a fresh ayam goreng record:** **Screenshot:** `test6_{HMMSS}_02_step2_baseline.png`
- [ ] **Action 03 — horizontal overflow JS check:**
  ```js
  ({
    overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
    width: document.documentElement.scrollWidth,
  });
  ```
  Expect `overflow: false`. **Screenshot:** `test6_{HMMSS}_03_no_overflow.png`
- [ ] **Action 04 — tap AI Assistant Edit button; measure tap-target:**
  ```js
  const btn = document.querySelector('[data-testid="step2-ai-assistant-toggle"]');
  ({ h: btn.getBoundingClientRect().height, w: btn.getBoundingClientRect().width });
  ```
  Expect `h >= 44`. **Screenshot:** `test6_{HMMSS}_04_button_measured.png`
- [ ] **Action 05 — type hint + submit:** **Screenshot:** `test6_{HMMSS}_05_submitted_mobile.png`
- [ ] **Action 06 — revised card renders readably on mobile:** **Screenshot:** `test6_{HMMSS}_06_revised_mobile.png`

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time)_
- **Improvement Proposals:** _(populated at execution time)_

---
