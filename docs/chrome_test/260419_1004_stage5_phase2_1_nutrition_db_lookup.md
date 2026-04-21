# Chrome E2E Test Spec — Stage 5: Phase 2.1 (Nutrition DB Lookup Integration)

**Feature:** Every Phase 2 background task now calls the Stage 1 nutrition service (per-component + dish_name search with min_confidence=70; comma-joined fallback at min_confidence=60 when best_confidence < 0.75) and stashes the structured result on `result_gemini.nutrition_db_matches` **BEFORE** the Gemini 2.5 Pro Step 2 call runs. The data survives Step 2 failure / retry because it is persisted synchronously before the Pro call. Stage 5 is backend-only — Phase 2's prompt is unchanged this stage (Stage 7 will consume the matches later).

**Spec generated:** 2026-04-19 10:04
**Plan target:** `docs/plan/260419_stage5_phase2_1_nutrition_db_lookup.md`
**Screenshots directory:** `data/chrome_test_images/260419_1004_stage5_phase2_1_nutrition_db_lookup/`

---

## Remarks

### Context

- **Frontend base URL:** `http://localhost:2512` (from `start_app.sh`).
- **Backend base URL:** `http://localhost:2612` (from `start_app.sh`).
- **Login page:** `http://localhost:2512/login`. Username + password auth.
- **Test users:** placeholders (no `docs/technical/testing_context.md` yet) — operator replaces with real seeded usernames before running:
  - `TEST_USER_ALPHA`
- **Nutrition DB state:** tests assume `nutrition_foods` has been seeded via `python -m scripts.seed.load_nutrition_db` (run from `backend/`). Tests 2 and 7 deliberately truncate and re-seed between steps.
- **Cleanup between runs:** standard personalization + dish-query delete from prior stages; **do NOT** drop `nutrition_foods` in the happy-path cleanup — it is shared reference data.

### Key assertion channel

Stage 5 ships no DOM change. Assertions run via:

1. **API fetch** (`javascript_tool`) on `GET /api/item/{id}`; inspect `result_gemini.nutrition_db_matches`.
2. **Backend log tail** (`backend.log | grep ...`) for the "empty DB" WARN branch and for the per-query attempt INFO lines.
3. **SQL DB inspection** where useful (mainly Test 2 for the truncate / re-seed setup).

### Timing note

The issue pins Phase 2.1 as "fast; <50 ms". The first call per process builds the four BM25 indices (~1 s). Subsequent calls in the same process reuse the lazy singleton. Tests that assert on timing should run Test 1 twice: once to warm the singleton (implicitly done during happy-path setup) then a second measurement call.

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

### Seed

- `nutrition_foods` + `nutrition_myfcd_nutrients` pre-populated via the standard Stage 1 seed script.
- `users` seeded with `test_user_alpha` (the operator creates once if missing).

### Cleanup (run before AND after every execution)

```sql
DELETE FROM personalized_food_descriptions
WHERE user_id IN (SELECT id FROM users WHERE username IN ('test_user_alpha'));

DELETE FROM dish_image_query_prod_dev
WHERE user_id IN (SELECT id FROM users WHERE username IN ('test_user_alpha'));
```

**Do NOT** `DELETE FROM nutrition_foods` here — shared reference data. Tests 2 and 7 handle their own targeted truncate + re-seed.

### Test image assets

- `chicken_rice_1.jpg` — recognizable dish with high-confidence matches in the seeded DB.
- `obscure_dish.jpg` — a photo of a made-up / low-coverage dish whose per-component searches will all land below 0.75 confidence, forcing the Stage 2 fallback path.

---

## Pre-requisite

Before Test 1, run Cleanup SQL, clear `localStorage`, and confirm `nutrition_foods` is populated:

```sql
SELECT COUNT(*) FROM nutrition_foods;  -- expect ~4,493 rows
```

If 0, the operator runs `python -m scripts.seed.load_nutrition_db` first.

---

## Tests

### Test 1 — Happy path: nutrition_db_matches populated after Phase 2 (desktop, 1080 × 1280)

**User(s):** `test_user_alpha`

**Goal:** After Step 1 confirm, `result_gemini.nutrition_db_matches.nutrition_matches[]` is non-empty. The lookup runs BEFORE the Gemini Pro call, so the key is present even while `step2_data` is still null (briefly, during the task).

- [ ] **Action 01 — set desktop viewport:** `resize_window` 1080 × 1280. **Screenshot:** `test1_{HMMSS}_01_desktop_viewport_set.png`
- [ ] **Action 02 — sign in as alpha:** **Screenshot:** `test1_{HMMSS}_02_alpha_dashboard.png`
- [ ] **Action 03 — upload chicken_rice_1.jpg on slot 1:** **Screenshot:** `test1_{HMMSS}_03_upload.png`
- [ ] **Action 04 — Step 1 editor loads:** **Screenshot:** `test1_{HMMSS}_04_step1_editor.png`
- [ ] **Action 05 — click Confirm:** **Screenshot:** `test1_{HMMSS}_05_confirm_clicked.png`
- [ ] **Action 06 — (within ~1s of confirm) API: nutrition_db_matches already populated, step2_data still null:** poll
  ```js
  const r = await fetch(`/api/item/${window.location.pathname.split('/').pop()}`, { credentials: 'include' });
  const j = await r.json();
  ({
    has_nutrition: !!j.result_gemini?.nutrition_db_matches,
    n_matches: j.result_gemini?.nutrition_db_matches?.nutrition_matches?.length,
    step2_data: j.result_gemini?.step2_data,
    search_strategy: j.result_gemini?.nutrition_db_matches?.search_strategy,
  });
  ```
  Expect `has_nutrition: true, n_matches > 0, step2_data: null` (Phase 2.1 landed; Phase 2.3 still running). **Screenshot:** `test1_{HMMSS}_06_api_matches_pre_step2.png`
- [ ] **Action 07 — wait for step2_data:** re-fetch until `step2_data != null`. Confirm `nutrition_db_matches` is unchanged across the transition. **Screenshot:** `test1_{HMMSS}_07_api_matches_post_step2.png`
- [ ] **Action 08 — match shape sanity:** top match has the documented keys — `matched_food_name`, `source`, `confidence` (0..1), `confidence_score` (0..100), `search_method: "Direct BM25"`, `raw_bm25_score`, `matched_keywords`, `total_keywords`. **Screenshot:** `test1_{HMMSS}_08_api_match_shape.png`
- [ ] **Action 09 — Step 2 view renders as today:** UI regression guard — the healthiness card, macros, and rationale render (Stage 5 does not change the Step 2 prompt, so values should look like today). **Screenshot:** `test1_{HMMSS}_09_step2_view.png`

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time — include the top-3 matched_food_name + confidence for audit)_
- **Improvement Proposals:**
  + good to have - Surface `nutrition_db_matches.match_summary.avg_confidence` on the Step 2 debug panel (dev-only) so operators can eyeball retrieval quality.

---

### Test 2 — Empty-DB graceful degrade: Phase 2 still succeeds with empty matches

**User(s):** `test_user_alpha`

**Goal:** If `nutrition_foods` is empty at request time, Phase 2.1 must swallow, log a WARN, stash the empty-response shape on `result_gemini.nutrition_db_matches`, and let Phase 2.3 run exactly as today.

**Pre-step (destructive; restore after!):** temporarily move all rows out of `nutrition_foods`:

```sql
CREATE TABLE IF NOT EXISTS _nutrition_foods_backup AS TABLE nutrition_foods WITH NO DATA;
INSERT INTO _nutrition_foods_backup SELECT * FROM nutrition_foods;
DELETE FROM nutrition_foods;
```

Also restart the backend so the `_INSTANCE` singleton is discarded (it caches the indices).

- [ ] **Action 01 — truncate nutrition_foods + restart backend:** operator runs the SQL + `bash start_app.sh` restart cycle. **Screenshot:** `test2_{HMMSS}_01_db_truncated.png` (terminal)
- [ ] **Action 02 — upload chicken_rice_1.jpg on a fresh slot:** **Screenshot:** `test2_{HMMSS}_02_upload.png`
- [ ] **Action 03 — Step 1 editor → Confirm:** **Screenshot:** `test2_{HMMSS}_03_confirmed.png`
- [ ] **Action 04 — API: nutrition_db_matches present, nutrition_matches empty:**
  ```js
  const r = await fetch(`/api/item/${window.location.pathname.split('/').pop()}`, { credentials: 'include' });
  const j = await r.json();
  ({
    has_key: 'nutrition_db_matches' in (j.result_gemini || {}),
    n_matches: j.result_gemini?.nutrition_db_matches?.nutrition_matches?.length,
    success: j.result_gemini?.nutrition_db_matches?.success,
  });
  ```
  Expect `has_key: true, n_matches: 0, success: true` (empty-response shape, not a failure shape). **Screenshot:** `test2_{HMMSS}_04_api_empty_matches.png`
- [ ] **Action 05 — backend log: WARN line with seed command:** `backend.log | grep "nutrition_foods is empty"` or `grep "NutritionDBEmptyError"`. **Screenshot:** `test2_{HMMSS}_05_log_warn.png` (terminal)
- [ ] **Action 06 — step2_data still renders as today:** wait for step2_data; Step 2 UI is unchanged from today's baseline. **Screenshot:** `test2_{HMMSS}_06_step2_view.png`
- [ ] **Action 07 — RESTORE nutrition_foods:** `INSERT INTO nutrition_foods SELECT * FROM _nutrition_foods_backup; DROP TABLE _nutrition_foods_backup;` then restart backend. **Screenshot:** `test2_{HMMSS}_07_db_restored.png` (terminal)

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time)_
- **Improvement Proposals:**
  + must have - The empty-DB branch depends on the singleton being re-initialised after truncate — document the restart step in the ops runbook. A future improvement is a one-hour TTL on the singleton so it picks up a fresh seed without a restart.

---

### Test 3 — Survives Step 2 failure: nutrition_db_matches persists across retry

**User(s):** `test_user_alpha`

**Goal:** The whole point of persisting `nutrition_db_matches` BEFORE the Pro call is that Step 2 failure must not destroy it. Retry-step2 re-uses the stored lookup result.

**Pre-step:** invalidate `GEMINI_API_KEY` to force the Step 2 Pro call to fail (the nutrition lookup does NOT touch Gemini, so only Step 2.3 is broken).

- [ ] **Action 01 — unset GEMINI_API_KEY + restart backend:** operator. **Screenshot:** `test3_{HMMSS}_01_key_unset.png` (terminal)
- [ ] **Action 02 — upload + confirm:** standard happy-path up to confirm. **Screenshot:** `test3_{HMMSS}_02_confirmed.png`
- [ ] **Action 03 — Step 2 error surfaces in PhaseErrorCard:** wait for `step2_error`; error card renders. **Screenshot:** `test3_{HMMSS}_03_step2_error_card.png`
- [ ] **Action 04 — API: nutrition_db_matches is already persisted despite step2_error:**
  ```js
  const j = await (await fetch(`/api/item/${...}`, { credentials: 'include' })).json();
  ({
    has_nutrition: !!j.result_gemini?.nutrition_db_matches,
    n_matches: j.result_gemini?.nutrition_db_matches?.nutrition_matches?.length,
    has_step2_error: !!j.result_gemini?.step2_error,
    has_step2_data: !!j.result_gemini?.step2_data,
  });
  ```
  Expect `has_nutrition: true, n_matches > 0, has_step2_error: true, has_step2_data: false`. Record the top match's `matched_food_name` + `confidence_score` for comparison after retry. **Screenshot:** `test3_{HMMSS}_04_api_pre_retry.png`
- [ ] **Action 05 — restore GEMINI_API_KEY + restart backend:** **Screenshot:** `test3_{HMMSS}_05_key_restored.png` (terminal)
- [ ] **Action 06 — click Retry on the error card:** **Screenshot:** `test3_{HMMSS}_06_retry_clicked.png`
- [ ] **Action 07 — API post-retry: nutrition_db_matches unchanged:** compare `nutrition_matches[0].matched_food_name` + `confidence_score` against the snapshot from Action 04. Must be identical (the retry pathway does NOT re-run Phase 2.1 by default). **Screenshot:** `test3_{HMMSS}_07_api_post_retry_unchanged.png`
- [ ] **Action 08 — step2_data now populated:** Step 2 UI renders. **Screenshot:** `test3_{HMMSS}_08_step2_view.png`

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time; attach the before/after match snapshots)_
- **Improvement Proposals:**
  + good to have - Consider re-running Phase 2.1 on retry if `nutrition_db_matches` is missing or stale, once the DB is observed to change (e.g. seed re-ran between attempts). Probably out of scope here.

---

### Test 4 — Low-confidence dish triggers Stage 2 fallback (combined search)

**User(s):** `test_user_alpha`

**Goal:** When per-component + dish_name searches all score below 0.75 best_confidence, Phase 2.1 runs the comma-joined combined search and replaces the best result only if it scores higher. `search_attempts` records both strategies.

- [ ] **Action 01 — upload obscure_dish.jpg:** a dish whose component names don't overlap the seeded DB's vocabulary. **Screenshot:** `test4_{HMMSS}_01_upload.png`
- [ ] **Action 02 — edit dish name to something contrived (optional):** in the Step 1 editor, override the dish name to something like `"Fusion Platter"` with components `["Mystery Meat", "Odd Grain"]`. This maximises the chance of low per-component confidence. **Screenshot:** `test4_{HMMSS}_02_editor.png`
- [ ] **Action 03 — confirm:** **Screenshot:** `test4_{HMMSS}_03_confirmed.png`
- [ ] **Action 04 — API: search_attempts shows the fallback path:**
  ```js
  const j = await (await fetch(`/api/item/${...}`, { credentials: 'include' })).json();
  const m = j.result_gemini?.nutrition_db_matches;
  ({
    attempts: m?.search_attempts?.map(a => ({ query: a.query, top: a.top_confidence })),
    best_strategy: m?.search_strategy,
    dish_candidates: m?.dish_candidates,
  });
  ```
  Expect: multiple entries in `search_attempts`, at least one of which has the comma-joined dish_name + components as its `query`. If the combined result scored higher, `best_strategy` contains `"combined_terms:"`. **Screenshot:** `test4_{HMMSS}_04_api_fallback.png`
- [ ] **Action 05 — backend log: INFO lines for both strategies:** `backend.log | grep -E "Searching nutrition database|Combined search"`. **Screenshot:** `test4_{HMMSS}_05_log_strategies.png` (terminal)

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time)_
- **Improvement Proposals:**
  + good to have - Surface `best_strategy` (individual / combined / empty) on the item's debug panel, gated behind a dev flag.

---

### Test 5 — Permission guard: unauthenticated user cannot confirm, Phase 2.1 never runs

**User(s):** _(unauthenticated)_

**Goal:** Auth guard on the confirm endpoint; no row is mutated, no Phase 2.1 lookup runs.

- [ ] **Action 01 — sign out, clear tokens:** `localStorage.clear(); location.href = '/login'`. **Screenshot:** `test5_{HMMSS}_01_logged_out.png`
- [ ] **Action 02 — fetch POST /confirm-step1 without token:**
  ```js
  const r = await fetch(`/api/item/<alpha_last_record>/confirm-step1`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ selected_dish_name: "X", components: [] }),
  });
  ({ status: r.status });
  ```
  Expect `status: 401`. **Screenshot:** `test5_{HMMSS}_02_api_401.png`
- [ ] **Action 03 — DB: record unchanged:** `SELECT result_gemini->'nutrition_db_matches' FROM dish_image_query_prod_dev WHERE id = <alpha_last_record>`. Expect value identical to before the 401 attempt. **Screenshot:** `test5_{HMMSS}_03_db_unchanged.png` (terminal)

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time)_
- **Improvement Proposals:** _(empty baseline)_

---

### Test 6 — Mobile: happy-path nutrition lookup (mirrors Test 1)

**User(s):** `test_user_alpha`

**Goal:** Replay Test 1 at 375 × 1080. Verify `nutrition_db_matches` populates on mobile upload + confirm. Standard mobile assertions on the Step 2 view.

- [ ] **Action 01 — set mobile viewport:** `resize_window` 375 × 1080. **Screenshot:** `test6_{HMMSS}_01_mobile_viewport_set.png`
- [ ] **Action 02 — upload chicken_rice_1.jpg on new slot:** **Screenshot:** `test6_{HMMSS}_02_upload_mobile.png`
- [ ] **Action 02b — overflow check on Step 1 editor:** **Screenshot:** `test6_{HMMSS}_02b_overflow.png`
- [ ] **Action 03 — Step 1 editor → Confirm:** **Screenshot:** `test6_{HMMSS}_03_confirm.png`
- [ ] **Action 04 — API: nutrition_db_matches populated:** same fetch as Test 1 Action 06. **Screenshot:** `test6_{HMMSS}_04_api_matches.png`
- [ ] **Action 05 — tap-target + readability on Step 2 view:** Confirm/Retry buttons ≥ 44 px; body text ≥ 12 px. **Screenshot:** `test6_{HMMSS}_05_mobile_assertions.png`
- [ ] **Action 06 — scroll-reachability at the bottom of Step 2:** no content hidden. **Screenshot:** `test6_{HMMSS}_06_scroll_bottom.png`

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time)_
- **Improvement Proposals:** _(empty baseline)_

---

### Test 7 — Mobile: empty-DB graceful degrade (mirrors Test 2)

**User(s):** `test_user_alpha`

**Goal:** Same truncate-and-degrade flow at mobile viewport. Ensures the absence of `nutrition_matches` doesn't regress the mobile Step 2 layout (which today renders without DB context).

- [ ] **Action 01 — truncate + restart:** as Test 2 pre-step. **Screenshot:** `test7_{HMMSS}_01_db_truncated.png` (terminal)
- [ ] **Action 02 — upload + confirm at mobile:** **Screenshot:** `test7_{HMMSS}_02_confirmed.png`
- [ ] **Action 03 — API: empty matches:** **Screenshot:** `test7_{HMMSS}_03_api_empty.png`
- [ ] **Action 04 — Step 2 view renders cleanly at mobile (no empty-state regressions):** **Screenshot:** `test7_{HMMSS}_04_step2_mobile.png`
- [ ] **Action 05 — restore nutrition_foods:** **Screenshot:** `test7_{HMMSS}_05_db_restored.png` (terminal)

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time)_
- **Improvement Proposals:** _(empty baseline)_

---

### Test 8 — Mobile: retry preserves nutrition_db_matches (mirrors Test 3)

**User(s):** `test_user_alpha`

**Goal:** Same retry flow at mobile viewport. The user's primary assertion is identical; the mobile pass verifies the PhaseErrorCard + Retry button are ≥ 44 px tap-target and render without overflow.

- [ ] **Action 01 — break GEMINI_API_KEY + restart:** **Screenshot:** `test8_{HMMSS}_01_key_broken.png` (terminal)
- [ ] **Action 02 — upload + confirm at mobile:** **Screenshot:** `test8_{HMMSS}_02_confirmed.png`
- [ ] **Action 03 — error card renders on mobile:** **Screenshot:** `test8_{HMMSS}_03_error_card_mobile.png`
- [ ] **Action 03b — tap-target check on Retry:** ≥ 44 px. **Screenshot:** `test8_{HMMSS}_03b_retry_tap_target.png`
- [ ] **Action 04 — restore key + restart:** **Screenshot:** `test8_{HMMSS}_04_key_restored.png` (terminal)
- [ ] **Action 05 — click Retry; nutrition_db_matches unchanged:** **Screenshot:** `test8_{HMMSS}_05_api_post_retry.png`

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time)_
- **Improvement Proposals:** _(empty baseline)_

---

### Test 9 — Mobile: fallback path visible via search_attempts (mirrors Test 4)

**User(s):** `test_user_alpha`

**Goal:** Same low-confidence-dish exercise on mobile. Checks that the JSON surface is identical; mobile viewport adds overflow + readability checks.

- [ ] **Action 01 — upload obscure_dish.jpg + custom dish name in Step 1 editor:** **Screenshot:** `test9_{HMMSS}_01_editor.png`
- [ ] **Action 01b — readability check on the Step 1 editor:** **Screenshot:** `test9_{HMMSS}_01b_readability.png`
- [ ] **Action 02 — Confirm:** **Screenshot:** `test9_{HMMSS}_02_confirm.png`
- [ ] **Action 03 — API: search_attempts shows fallback:** **Screenshot:** `test9_{HMMSS}_03_api_fallback.png`
- [ ] **Action 04 — scroll-reachability on Step 2:** **Screenshot:** `test9_{HMMSS}_04_scroll.png`

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time)_
- **Improvement Proposals:** _(empty baseline)_

---

### Test 10 — Mobile permission guard (mirrors Test 5)

**User(s):** _(unauthenticated)_

**Goal:** Auth guard on confirm at mobile viewport. No DOM or state change should leak.

- [ ] **Action 01 — sign out, clear tokens:** **Screenshot:** `test10_{HMMSS}_01_logged_out_mobile.png`
- [ ] **Action 02 — POST /confirm-step1 without token → 401:** **Screenshot:** `test10_{HMMSS}_02_api_401.png`
- [ ] **Action 03 — login page overflow check at 375 px:** **Screenshot:** `test10_{HMMSS}_03_login_overflow.png`

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time)_
- **Improvement Proposals:** _(empty baseline)_

---

## Summary for the Caller

- **Output file:** `docs/chrome_test/260419_1004_stage5_phase2_1_nutrition_db_lookup.md`
- **Screenshots directory:** `data/chrome_test_images/260419_1004_stage5_phase2_1_nutrition_db_lookup/`
- **Number of tests:** 10 total — 5 desktop + 5 mobile.
- **Users involved:** placeholder `test_user_alpha` (replace before running).
- **Rough screenshot budget:** ~50 PNGs + several terminal captures (SQL truncate / restore, env toggles, log tails).
- **Viewport notes:** Test 1 Action 01 sets 1080 × 1280; Test 6 Action 01 sets 375 × 1080.
- **Critical caveats:**
  - Tests 2 and 7 **destructively truncate** `nutrition_foods`. The spec includes a backup + restore cycle; operator must verify the restore SQL succeeds before running subsequent tests.
  - Tests 2/7 also require a **backend restart** so the lazy `_INSTANCE` singleton is discarded. Without the restart, Phase 2.1 will still see the cached (pre-truncate) corpus.
  - Tests 3/8 toggle `GEMINI_API_KEY`. Restart required on both flip and restore.
  - `docs/technical/testing_context.md` still missing — placeholder username.
- **Next step:** spec stays `IN QUEUE`. `feature-implement-full` will trigger `chrome-test-execute`.
