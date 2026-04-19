# Chrome E2E Test Spec — Stage 4: Phase 1.2 (Confirm Endpoint Enriches the Personalization Row)

**Feature:** After `POST /api/item/{id}/confirm-step1` succeeds, the matching `personalized_food_descriptions` row gains non-null `confirmed_dish_name`, `confirmed_portions` (sum of components' `number_of_servings`), and `confirmed_tokens` (tokenized `confirmed_dish_name`). A subsequent upload by the same user whose fast caption token-overlaps `confirmed_tokens` surfaces the enriched row as its reference.

**Spec generated:** 2026-04-18 23:37
**Plan target:** `docs/plan/260418_stage4_phase1_2_confirm_enriches_personalization.md`
**Screenshots directory:** `data/chrome_test_images/260418_2337_stage4_phase1_2_confirm_enriches_personalization/`

---

## Remarks

### Context

- **Frontend base URL:** `http://localhost:2512` (from `start_app.sh`).
- **Backend base URL:** `http://localhost:2612` (from `start_app.sh`).
- **Login page:** `http://localhost:2512/login`. Username + password auth.
- **Test users:** placeholders (no `docs/technical/testing_context.md` yet) — replace with seeded usernames before running:
  - `TEST_USER_ALPHA`
  - `TEST_USER_BETA`
- **Failure policy:** Stage 4's enrichment call uses a swallow-log failure policy — the confirm endpoint returns 200 even if `update_confirmed_fields` errors. Tests assert on the **DB effect** (new columns populated), not on HTTP status, because all four test scenarios return 200.
- **Cleanup between runs:** same SQL as the Stage 2 / Stage 3 specs (deletes personalization rows + dish queries for both test users).

### Key assertion channel

Stage 4 is a **backend-only** stage with zero UI change. Assertions run in two forms:

1. **API fetch** via `javascript_tool`: after confirming, call `GET /api/item/{id}` and check `result_gemini.step1_confirmed === true` and `result_gemini.confirmed_dish_name`.
2. **Direct SQL** (optional per test): `SELECT confirmed_dish_name, confirmed_portions, confirmed_tokens FROM personalized_food_descriptions WHERE query_id = {id}`. This is the authoritative check for Stage 4; mark optional only because Chrome can't run it natively.

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

Same two dev users as the prior specs. Operator creates them once if missing.

### Cleanup (run before AND after every execution)

```sql
DELETE FROM personalized_food_descriptions
WHERE user_id IN (
    SELECT id FROM users WHERE username IN ('test_user_alpha', 'test_user_beta')
);

DELETE FROM dish_image_query_prod_dev
WHERE user_id IN (
    SELECT id FROM users WHERE username IN ('test_user_alpha', 'test_user_beta')
);
```

### Test image assets

- `chicken_rice_1.jpg`, `chicken_rice_2.jpg` — two similar chicken-rice plates (reused from Stage 2).

### Backend logging aid (Test 2 only)

For the "row missing" path, the operator temporarily patches `backend/src/api/item.py` to import a test helper that forces `update_confirmed_fields` to observe a missing row — OR more simply, deletes the personalization row via SQL between upload and confirm:

```sql
-- Run AFTER the upload has completed Phase 1.1.1 but BEFORE the user clicks Confirm.
DELETE FROM personalized_food_descriptions WHERE query_id = <record_id>;
```

---

## Pre-requisite

Before Test 1, run Cleanup SQL and clear `localStorage`.

---

## Tests

### Test 1 — Happy path: confirm enriches the personalization row (desktop, 1080 × 1280)

**User(s):** `test_user_alpha`

**Goal:** After Step 1 confirmation, `personalized_food_descriptions` shows the three new fields populated for the confirmed query.

- [ ] **Action 01 — set desktop viewport:** `resize_window` 1080 × 1280. **Screenshot:** `test1_{HMMSS}_01_desktop_viewport_set.png`
- [ ] **Action 02 — sign in as alpha:** **Screenshot:** `test1_{HMMSS}_02_alpha_dashboard.png`
- [ ] **Action 03 — date view:** click today's tile. **Screenshot:** `test1_{HMMSS}_03_date_view.png`
- [ ] **Action 04 — upload chicken_rice_1 on slot 1:** **Screenshot:** `test1_{HMMSS}_04_upload.png`
- [ ] **Action 05 — Step 1 editor loads:** wait for the editor. **Screenshot:** `test1_{HMMSS}_05_step1_editor.png`
- [ ] **Action 06 — modify dish name slightly (optional) + confirm a serving:** edit the dish name to e.g. `"Hainanese Chicken Rice"` in the Step 1 editor; adjust a serving size option / count if needed. **Screenshot:** `test1_{HMMSS}_06_dish_name_edited.png`
- [ ] **Action 07 — click Confirm:** the Confirm button at the bottom of the editor. **Screenshot:** `test1_{HMMSS}_07_confirm_clicked.png`
- [ ] **Action 08 — Step 2 loading state renders:** the SPA transitions to the Step 2 "Analysis in progress" state (no UI regression from Stage 4). **Screenshot:** `test1_{HMMSS}_08_step2_loading.png`
- [ ] **Action 09 — API: step1_confirmed and confirmed_dish_name persisted (baseline):**
  ```js
  const r = await fetch(`/api/item/${window.location.pathname.split('/').pop()}`, { credentials: 'include' });
  const j = await r.json();
  ({
    step1_confirmed: j.result_gemini?.step1_confirmed,
    confirmed_dish_name: j.result_gemini?.confirmed_dish_name,
    n_components: j.result_gemini?.confirmed_components?.length,
  });
  ```
  Expect `step1_confirmed: true, confirmed_dish_name: "Hainanese Chicken Rice"`. **Screenshot:** `test1_{HMMSS}_09_api_step1_confirmed.png`
- [ ] **Action 10 — DB: enrichment columns populated (authoritative):** run
  ```sql
  SELECT confirmed_dish_name, confirmed_portions, confirmed_tokens
  FROM personalized_food_descriptions WHERE query_id = <record_id>;
  ```
  Expect `confirmed_dish_name = 'Hainanese Chicken Rice'`, `confirmed_portions` = sum of component `number_of_servings` from Action 06 (e.g. `1.0` for one-component dish), `confirmed_tokens = ["hainanese", "chicken", "rice"]`. **Screenshot:** `test1_{HMMSS}_10_db_enrichment.png` (terminal)

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time)_
- **Improvement Proposals:**
  + good to have - Surface `confirmed_tokens` on the confirm response body (dev-only debug field) so operators can verify without DB access.

---

### Test 2 — Row missing (graceful degrade) — confirm still returns 200, no enrichment

**User(s):** `test_user_alpha`

**Goal:** When `update_confirmed_fields` finds no row (e.g. Phase 1.1.1 failed to insert, or it was manually deleted), the endpoint must still succeed. No row is created implicitly.

- [ ] **Action 01 — upload a new dish:** upload `chicken_rice_2.jpg` on slot 2. **Screenshot:** `test2_{HMMSS}_01_upload.png`
- [ ] **Action 02 — Step 1 editor:** wait for the editor. **Screenshot:** `test2_{HMMSS}_02_step1_editor.png`
- [ ] **Action 03 — DELETE the personalization row for this query_id:** operator runs
  ```sql
  DELETE FROM personalized_food_descriptions WHERE query_id = <record_id>;
  ```
  **Screenshot:** `test2_{HMMSS}_03_row_deleted.png` (terminal)
- [ ] **Action 04 — click Confirm:** **Screenshot:** `test2_{HMMSS}_04_confirm_clicked.png`
- [ ] **Action 05 — endpoint returned 200:** API `GET /api/item/{id}`; `step1_confirmed: true`. **Screenshot:** `test2_{HMMSS}_05_api_200.png`
- [ ] **Action 06 — DB: no row exists; no implicit insert:** `SELECT COUNT(*) FROM personalized_food_descriptions WHERE query_id = <record_id>` returns 0. **Screenshot:** `test2_{HMMSS}_06_db_no_row.png` (terminal)
- [ ] **Action 07 — backend log: WARN for missing row:** `tail backend.log | grep -i "personalization.*missing\|update_confirmed_fields"` returns at least one WARN line naming the query_id. **Screenshot:** `test2_{HMMSS}_07_log_warn.png` (terminal)

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time)_
- **Improvement Proposals:**
  + good to have - Add a lightweight metric counter for "Stage 4 enrichment missed row" so we can spot the rate in aggregate.

---

### Test 3 — Subsequent upload uses confirmed_tokens as the retrieval signal

**User(s):** `test_user_alpha`

**Goal:** After Test 1 populated `confirmed_tokens` for record_1, a new similar upload's Phase 1.1.1 retrieval should surface record_1 as the reference (the same behavior as Stage 2, but now the retrieval can match against the user-verified dish name's tokens — not just the fast-caption tokens).

- [ ] **Action 01 — upload similar dish on new slot:** `chicken_rice_2.jpg` on slot 3 (or whatever slot is free). **Screenshot:** `test3_{HMMSS}_01_upload.png`
- [ ] **Action 02 — Step 1 editor loads:** **Screenshot:** `test3_{HMMSS}_02_step1_editor.png`
- [ ] **Action 03 — API: reference_image points at Test 1's record:**
  ```js
  const r = await fetch(`/api/item/${window.location.pathname.split('/').pop()}`, { credentials: 'include' });
  const j = await r.json();
  const ref = j.result_gemini?.reference_image;
  ({
    ref_query_id: ref?.query_id,
    sim: ref?.similarity_score,
    has_prior: !!ref?.prior_step1_data,
  });
  ```
  Expect `ref_query_id === <Test 1 record_id>`, `sim >= 0.25`. **Screenshot:** `test3_{HMMSS}_03_api_ref_populated.png`
- [ ] **Action 04 — DB: confirm the matched row has both tokens + confirmed_tokens:**
  ```sql
  SELECT tokens, confirmed_tokens FROM personalized_food_descriptions WHERE query_id = <Test 1 record_id>;
  ```
  Expect both non-null; confirmed_tokens should include `"hainanese"` if the user chose that name in Test 1. **Screenshot:** `test3_{HMMSS}_04_db_token_pair.png` (terminal)

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time)_
- **Improvement Proposals:**
  + must have - Verify explicitly that the BM25 retrieval unions `tokens` and `confirmed_tokens` at the query side (Stage 6's contract). Add a backend unit test.

---

### Test 4 — Double-confirm returns 409, does NOT re-invoke update_confirmed_fields

**User(s):** `test_user_alpha`

**Goal:** The atomic CRUD layer rejects the second confirm with 409. `update_confirmed_fields` must not be called a second time — otherwise a concurrent double-click could stomp on the first confirmation's values (unlikely, but the contract should be checked).

- [ ] **Action 01 — use Test 1's record (already confirmed):** navigate back to Test 1's `/item/{record_1}`. **Screenshot:** `test4_{HMMSS}_01_item_page.png`
- [ ] **Action 02 — Step 2 view is visible (post-confirm):** confirmed dishes show the Step 2 analysis or Step 2 loading. **Screenshot:** `test4_{HMMSS}_02_step2_view.png`
- [ ] **Action 03 — try to POST confirm-step1 again via fetch:**
  ```js
  const payload = {
    selected_dish_name: "DIFFERENT NAME",
    components: [{ component_name: "X", selected_serving_size: "1 oz", number_of_servings: 1.0 }],
  };
  const r = await fetch(`/api/item/<record_1>/confirm-step1`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(payload),
  });
  ({ status: r.status, body: await r.json() });
  ```
  Expect `status: 409`. **Screenshot:** `test4_{HMMSS}_03_api_409.png`
- [ ] **Action 04 — DB: confirmed_dish_name unchanged:** `SELECT confirmed_dish_name FROM personalized_food_descriptions WHERE query_id = <record_1>`. Expect the original Test 1 value, NOT `"DIFFERENT NAME"`. **Screenshot:** `test4_{HMMSS}_04_db_unchanged.png` (terminal)
- [ ] **Action 05 — backend log: no second update_confirmed_fields call:** `tail backend.log | grep -c "update_confirmed_fields"` — depending on how the implementation logs, expect exactly 1 occurrence for this record (the original confirm). **Screenshot:** `test4_{HMMSS}_05_log_count.png` (terminal)

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time)_
- **Improvement Proposals:** _(empty baseline)_

---

### Test 5 — Cross-user isolation: beta's confirm does not touch alpha's row

**User(s):** `test_user_alpha` → sign out → `test_user_beta`

**Goal:** Beta confirms a dish; alpha's prior enrichment is untouched. Enforces the per-user scoping invariant that Stage 0 + Stage 4 assume.

- [ ] **Action 01 — sign out alpha:** `localStorage.clear(); location.href = '/login'`. **Screenshot:** `test5_{HMMSS}_01_signed_out.png`
- [ ] **Action 02 — sign in as beta:** **Screenshot:** `test5_{HMMSS}_02_beta_dashboard.png`
- [ ] **Action 03 — beta uploads chicken_rice_1.jpg and confirms with a different name:** full happy-path cycle for beta; confirm with e.g. `"Beta Chicken Rice"`. **Screenshot:** `test5_{HMMSS}_03_beta_confirmed.png`
- [ ] **Action 04 — DB: alpha's row untouched:** `SELECT confirmed_dish_name FROM personalized_food_descriptions WHERE query_id = <Test 1 record_1>`. Expect the original alpha value. **Screenshot:** `test5_{HMMSS}_04_db_alpha_untouched.png` (terminal)
- [ ] **Action 05 — DB: beta's row has beta's value:** `SELECT confirmed_dish_name FROM personalized_food_descriptions WHERE query_id = <beta's record>`. Expect `"Beta Chicken Rice"`. **Screenshot:** `test5_{HMMSS}_05_db_beta_populated.png` (terminal)

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time)_
- **Improvement Proposals:** _(empty baseline)_

---

### Test 6 — Mobile: happy-path confirm (mirrors Test 1)

**User(s):** `test_user_beta` (still signed in from Test 5)

**Goal:** Replay Test 1's happy-path at mobile viewport. Confirm button must be reachable and tappable; overflow checks clean.

- [ ] **Action 01 — set mobile viewport:** `resize_window` 375 × 1080. **Screenshot:** `test6_{HMMSS}_01_mobile_viewport_set.png`
- [ ] **Action 02 — upload new dish as beta:** slot 2 or next free. **Screenshot:** `test6_{HMMSS}_02_upload_mobile.png`
- [ ] **Action 03 — Step 1 editor on mobile:** **Screenshot:** `test6_{HMMSS}_03_editor_mobile.png`
- [ ] **Action 03b — overflow check:** **Screenshot:** `test6_{HMMSS}_03b_overflow.png`
- [ ] **Action 04 — tap-target check on Confirm button:** ≥ 44 px tall. **Screenshot:** `test6_{HMMSS}_04_tap_target.png`
- [ ] **Action 05 — click Confirm:** **Screenshot:** `test6_{HMMSS}_05_confirm_tapped.png`
- [ ] **Action 06 — API + DB assertions (same as Test 1 Actions 09, 10):** **Screenshot:** `test6_{HMMSS}_06_api_db_mobile.png`

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time)_
- **Improvement Proposals:** _(empty baseline)_

---

### Test 7 — Mobile: missing-row graceful degrade (mirrors Test 2)

**User(s):** `test_user_beta`

**Goal:** Same as Test 2 at mobile viewport.

- [ ] **Action 01 — upload another dish as beta:** **Screenshot:** `test7_{HMMSS}_01_upload_mobile.png`
- [ ] **Action 02 — Step 1 editor:** **Screenshot:** `test7_{HMMSS}_02_editor_mobile.png`
- [ ] **Action 03 — DELETE the personalization row:** operator SQL. **Screenshot:** `test7_{HMMSS}_03_row_deleted.png` (terminal)
- [ ] **Action 04 — confirm:** **Screenshot:** `test7_{HMMSS}_04_confirm_mobile.png`
- [ ] **Action 05 — 200 returned, no row created:** combined API + DB checks. **Screenshot:** `test7_{HMMSS}_05_api_db_checks.png`
- [ ] **Action 06 — readability check on the Step 2 loading view:** **Screenshot:** `test7_{HMMSS}_06_readability.png`

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time)_
- **Improvement Proposals:** _(empty baseline)_

---

### Test 8 — Mobile: subsequent upload retrieves enriched row (mirrors Test 3)

**User(s):** `test_user_beta`

**Goal:** After Test 6 enriched beta's row, a new beta upload's reference points at it with a similarity ≥ threshold.

- [ ] **Action 01 — upload similar dish:** **Screenshot:** `test8_{HMMSS}_01_upload_mobile.png`
- [ ] **Action 02 — Step 1 editor:** **Screenshot:** `test8_{HMMSS}_02_editor.png`
- [ ] **Action 03 — API: reference_image populated:** **Screenshot:** `test8_{HMMSS}_03_api_ref.png`
- [ ] **Action 04 — scroll-reachability on editor:** **Screenshot:** `test8_{HMMSS}_04_scroll.png`

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time)_
- **Improvement Proposals:** _(empty baseline)_

---

### Test 9 — Mobile: double-confirm returns 409 (mirrors Test 4)

**User(s):** `test_user_beta`

**Goal:** Double-confirm a previously-confirmed record; expect 409; DB unchanged.

- [ ] **Action 01 — navigate to an already-confirmed record:** (Test 6's record works). **Screenshot:** `test9_{HMMSS}_01_item_page_mobile.png`
- [ ] **Action 02 — POST /confirm-step1 via fetch with a different name:** **Screenshot:** `test9_{HMMSS}_02_api_409.png`
- [ ] **Action 03 — DB unchanged:** **Screenshot:** `test9_{HMMSS}_03_db_unchanged.png` (terminal)

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time)_
- **Improvement Proposals:** _(empty baseline)_

---

### Test 10 — Mobile: permission guard

**User(s):** _(unauthenticated)_

**Goal:** `POST /api/item/{id}/confirm-step1` without a token returns 401 and does not mutate state.

- [ ] **Action 01 — sign out, clear tokens:** **Screenshot:** `test10_{HMMSS}_01_logged_out.png`
- [ ] **Action 02 — fetch POST without token → 401:** `javascript_tool`:
  ```js
  const r = await fetch(`/api/item/<any_id>/confirm-step1`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ selected_dish_name: "X", components: [] }),
  });
  ({ status: r.status });
  ```
  Expect `status: 401`. **Screenshot:** `test10_{HMMSS}_02_api_401.png`
- [ ] **Action 03 — DB: confirmed_dish_name unchanged for the record:** **Screenshot:** `test10_{HMMSS}_03_db_unchanged.png` (terminal)

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time)_
- **Improvement Proposals:** _(empty baseline)_

---

## Summary for the Caller

- **Output file:** `docs/chrome_test/260418_2337_stage4_phase1_2_confirm_enriches_personalization.md`
- **Screenshots directory:** `data/chrome_test_images/260418_2337_stage4_phase1_2_confirm_enriches_personalization/`
- **Number of tests:** 10 total — 5 desktop + 5 mobile.
- **Users involved:** placeholders `test_user_alpha`, `test_user_beta` (replace before running).
- **Rough screenshot budget:** ~50 PNGs + several terminal captures.
- **Viewport notes:** Test 1 Action 01 sets 1080 × 1280; Test 6 Action 01 sets 375 × 1080.
- **Key scope caveats:**
  - Assertions rely on direct DB inspection (SQL SELECT) because the API does not surface `confirmed_tokens` / `confirmed_portions` on its response body. If SQL access is inconvenient, consider adding a dev-only debug field on `GET /api/item/{id}` (flagged as "good to have" in Test 1).
  - Test 2 relies on deleting a personalization row between upload and confirm — operator must perform the SQL manually at the right moment.
  - No `docs/technical/testing_context.md` exists yet; placeholders in place of real usernames.
- **Next step:** spec stays `IN QUEUE`. Executed by `feature-implement-full`, or manually via `/webapp-dev:chrome-test-execute`.
