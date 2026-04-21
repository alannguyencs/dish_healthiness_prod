# Chrome E2E Test Spec — Stage 2: Phase 1.1.1 (Fast Caption + Personalized Reference Retrieval)

**Feature:** Stage 2 ships no new UI. After an image upload, the backend runs a Gemini 2.0 Flash fast-caption, BM25-searches this user's prior personalization rows, and stamps a new `result_gemini.reference_image` key (or `null` on cold-start / below threshold). The current upload row is inserted into `personalized_food_descriptions` AFTER the search so it cannot self-match.

**Spec generated:** 2026-04-18 20:13
**Plan target:** `docs/plan/260418_stage2_phase1_1_1_fast_caption.md`
**Screenshots directory:** `data/chrome_test_images/260418_2013_stage2_phase1_1_1_fast_caption/`

---

## Remarks

### Context

- **Frontend base URL:** `http://localhost:2512` (resolved from `start_app.sh`).
- **Backend base URL:** `http://localhost:2612` (resolved from `start_app.sh`).
- **Login page:** `http://localhost:2512/login`. This project uses username + password auth (no email), issued tokens live 90 days. Sign-in POSTs to the backend and the SPA navigates to `/` on success.
- **Test users:** the project's `docs/technical/testing_context.md` does not exist yet, so the concrete usernames/passwords below are **placeholders** — the operator running this spec MUST have two real accounts seeded in the dev DB before starting and replace the two placeholders below:
  - `TEST_USER_ALPHA` — primary tester; owns both uploads in the "same-user match" golden path.
  - `TEST_USER_BETA` — secondary tester; proves cross-user isolation (does not see user alpha's prior rows).
- **Sign-out procedure:** the React SPA clears the JWT from `localStorage` on sign-out and navigates to `/login`. Use whatever sign-out UI exists in the header; if none, clear `localStorage.token` via `javascript_tool` and navigate to `/login`.
- **Cleanup between runs:** the `Database Pre-Interaction` section below deletes personalization rows + dish image queries + uploaded images for the two test users so each run starts from a cold-start state for both.

### Why this spec is mostly API-assertion, not DOM-assertion

Stage 2 is a **backend-only** stage: the Step 1 editor and upload flow look and behave exactly as they did before. The only observable change is the new `result_gemini.reference_image` key on `GET /api/item/{record_id}`. Every test below therefore includes at least one assertion on that JSON via the Chrome extension's `javascript_tool` issuing an in-page `fetch()` against the backend (or reading `window.fetch`-cached responses surfaced by the already-running poller) — the DOM-level screenshots are there to prove the UI did not regress, not to prove that retrieval happened.

If the user later adds Phase 1.1.2 reference-image UI (Stage 3), refresh this spec to capture the visible reference.

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

### Seed (preconditions)

The app already ships real user accounts; these tests rely on TWO **pre-existing** accounts (`TEST_USER_ALPHA`, `TEST_USER_BETA`) that the operator must have in the local dev DB. The tests do not seed users — they only clean up dish uploads and personalization rows.

If the operator needs to create the users from scratch, adapt this helper (run from `backend/` with the venv activated):

```sql
-- Optional one-shot user seed (run once per fresh DB). Replace the bcrypt hashes with
-- hashes of the operator's chosen passwords, generated via python:
--   python -c "import bcrypt; print(bcrypt.hashpw(b'<password>', bcrypt.gensalt()).decode())"
INSERT INTO users (username, hashed_password, role)
VALUES
  ('test_user_alpha', '$2b$12$...REPLACE...', NULL),
  ('test_user_beta',  '$2b$12$...REPLACE...', NULL)
ON CONFLICT (username) DO NOTHING;
```

### Cleanup (run before AND after every execution)

```sql
-- Kill personalization rows first (FK ON DELETE CASCADE from dish_image_query_prod_dev
-- would also handle this, but being explicit keeps the intent visible).
DELETE FROM personalized_food_descriptions
WHERE user_id IN (
    SELECT id FROM users WHERE username IN ('test_user_alpha', 'test_user_beta')
);

-- Kill dish uploads (orphan image files on disk are removed by the upload handler's
-- _delete_old_image_files on the next upload to the same slot; the operator may
-- also rm data/images/*u{alpha_id}_dish*.jpg and *u{beta_id}_dish*.jpg manually).
DELETE FROM dish_image_query_prod_dev
WHERE user_id IN (
    SELECT id FROM users WHERE username IN ('test_user_alpha', 'test_user_beta')
);
```

### Test image assets

The operator needs **two visually/textually similar dish photos** (same meal type) plus **one clearly different photo** on the local file system. Suggested sources:

- `chicken_rice_1.jpg` — e.g. a Hainanese chicken rice plate.
- `chicken_rice_2.jpg` — another Hainanese chicken rice plate, different angle / lighting.
- `chocolate_cookie.jpg` — unrelated dish (used in Test 4 to force `reference_image = null` even with prior history).

Any JPEG/PNG ≤ 5 MB is fine; the backend resizes to 384 px on upload.

---

## Pre-requisite

Before Test 1, sign out any existing session and verify `localStorage.token` is empty:

1. Open `http://localhost:2512` in Chrome.
2. In DevTools console: `localStorage.clear(); location.href = '/login'`.
3. Confirm the login form is visible. Do **not** sign in yet — each test starts with its own sign-in action so viewport + auth state are explicit.

---

## Tests

### Test 1 — Cold-start upload (desktop, 1080 × 1280) — `reference_image === null`

**User(s):** `test_user_alpha`

**Goal:** First upload for a freshly-cleaned user. Assert the backend returns `result_gemini.reference_image === null` and that a personalization row was inserted post-search.

- [ ] **Action 01 — set desktop viewport:** call `mcp__claude-in-chrome__resize_window` with `width: 1080, height: 1280`. Verify `window.innerWidth === 1080` via `javascript_tool`. **Screenshot:** `test1_{HMMSS}_01_desktop_viewport_set.png`
- [ ] **Action 02 — login page loaded:** navigate to `http://localhost:2512/login`. Verify the sign-in form is visible. **Screenshot:** `test1_{HMMSS}_02_login_page.png`
- [ ] **Action 03 — credentials entered:** as `test_user_alpha`, fill username + password. **Screenshot:** `test1_{HMMSS}_03_credentials_filled.png`
- [ ] **Action 04 — signed in:** click "Sign in". Expect redirect to `/` (the calendar dashboard). Verify `localStorage.token` is set. **Screenshot:** `test1_{HMMSS}_04_dashboard_loaded.png`
- [ ] **Action 05 — target date opened:** click today's tile. Expect navigation to `/date/{Y}/{M}/{D}` and five empty dish slots. **Screenshot:** `test1_{HMMSS}_05_date_view_empty.png`
- [ ] **Action 06 — file picker opened:** click the upload input on dish slot 1. Expect the OS file picker to appear. **Screenshot:** `test1_{HMMSS}_06_upload_input.png`
- [ ] **Action 07 — image selected:** select `chicken_rice_1.jpg`. The slot shows a spinner / "Analysis in progress". Capture `record_id` from the XHR response by reading `window.__lastItemId` or parsing the URL the SPA navigates to. **Screenshot:** `test1_{HMMSS}_07_upload_scheduled.png`
- [ ] **Action 08 — item page reached:** navigate to `/item/{record_id}` (if the SPA did not auto-navigate). Verify the polling spinner is visible. **Screenshot:** `test1_{HMMSS}_08_item_polling.png`
- [ ] **Action 09 — Step 1 completes:** wait up to 60 s for the Step 1 editor to render. Verify the dish predictions list is visible (no regression on the existing UI). **Screenshot:** `test1_{HMMSS}_09_step1_editor_ready.png`
- [ ] **Action 10 — reference_image === null (API assertion):** in `javascript_tool`, run
  ```js
  const r = await fetch(`/api/item/${window.location.pathname.split('/').pop()}`, { credentials: 'include' });
  const j = await r.json();
  ({ step1_ok: !!j.result_gemini?.step1_data, reference_image: j.result_gemini?.reference_image });
  ```
  Expect `{ step1_ok: true, reference_image: null }`. **Screenshot:** `test1_{HMMSS}_10_api_reference_image_null.png`
- [ ] **Action 11 — personalization row exists (DB assertion, optional):** if the operator has a DB CLI handy, run `SELECT query_id, description, tokens, similarity_score_on_insert FROM personalized_food_descriptions WHERE user_id = <alpha_id>` and confirm exactly one row exists whose `query_id === record_id` and whose `similarity_score_on_insert IS NULL` (cold start). This is an out-of-browser check; the test spec records the expected result but does not require Chrome to perform it. **Screenshot:** `test1_{HMMSS}_11_db_one_row.png` (screenshot the terminal output)

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time)_
- **Improvement Proposals:**
  + good to have - Surface `reference_image` in the Step 1 editor UI (chip / thumbnail) - makes cold-start vs warm-start observable without DevTools.
  + must have - Confirm the upload response body includes the new `record_id` explicitly; today the frontend reads it from the JSON's `query.id`.

---

### Test 2 — Warm-start same-user match (desktop) — `reference_image` points at Test 1's upload

**User(s):** `test_user_alpha` (still signed in from Test 1)

**Goal:** Second upload, same user, visually/textually similar dish. The backend's fast caption should match Test 1's `personalized_food_descriptions` row; `result_gemini.reference_image` should be a populated object with `query_id` equal to Test 1's `record_id` and `similarity_score >= THRESHOLD_PHASE_1_1_1_SIMILARITY`.

- [ ] **Action 01 — back to today's date view:** navigate to the date page reached in Test 1 Action 05. Expect dish slot 1 to show Test 1's thumbnail. **Screenshot:** `test2_{HMMSS}_01_date_view_one_filled.png`
- [ ] **Action 02 — file picker opened on slot 2:** click the upload input on dish slot 2. **Screenshot:** `test2_{HMMSS}_02_upload_input_slot2.png`
- [ ] **Action 03 — image selected:** select `chicken_rice_2.jpg` (a second chicken-rice plate). **Screenshot:** `test2_{HMMSS}_03_upload_scheduled_slot2.png`
- [ ] **Action 04 — Step 1 completes on slot 2:** navigate to the new `/item/{record_id_2}` page and wait for the Step 1 editor. **Screenshot:** `test2_{HMMSS}_04_step1_editor_slot2.png`
- [ ] **Action 05 — reference_image populated (API assertion):** run
  ```js
  const r = await fetch(`/api/item/${window.location.pathname.split('/').pop()}`, { credentials: 'include' });
  const j = await r.json();
  const ref = j.result_gemini?.reference_image;
  ({
    has_ref: ref !== null && ref !== undefined,
    ref_query_id: ref?.query_id,
    sim: ref?.similarity_score,
    desc: ref?.description?.slice(0, 80),
    image_url: ref?.image_url,
    has_prior_step1: !!ref?.prior_step1_data,
  });
  ```
  Expect `has_ref === true`, `ref_query_id === <Test 1 record_id>`, `sim >= 0.25`, `has_prior_step1 === true`. **Screenshot:** `test2_{HMMSS}_05_api_reference_image_warm.png`
- [ ] **Action 06 — self-match prevented (API assertion):** confirm `ref_query_id !== <Test 2 record_id>` by asserting the returned `reference_image.query_id` is strictly the earlier upload. **Screenshot:** `test2_{HMMSS}_06_self_match_guarded.png`
- [ ] **Action 07 — two rows exist (DB assertion, optional):** run `SELECT query_id, similarity_score_on_insert FROM personalized_food_descriptions WHERE user_id = <alpha_id> ORDER BY id ASC`. Expect two rows — Test 1's `similarity_score_on_insert IS NULL` (cold start), Test 2's `similarity_score_on_insert >= 0.25`. **Screenshot:** `test2_{HMMSS}_07_db_two_rows.png`

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time)_
- **Improvement Proposals:**
  + must have - Log the top-1 `similarity_score` and matched `query_id` in backend `analyze_image_background` INFO logs - essential for retrieval-quality debugging once Stage 3 consumes this.
  + good to have - Add a `reference_image.reason: "cold_start" | "below_threshold" | "no_rows"` field when `reference_image` is null so later stages can distinguish cases without re-deriving them.

---

### Test 3 — Cross-user isolation (desktop) — `test_user_beta` cannot see `test_user_alpha`'s rows

**User(s):** `test_user_alpha` → sign out → `test_user_beta`

**Goal:** Prove the user-scoping contract: user beta uploading a similar dish must NOT surface user alpha's prior rows as a reference.

- [ ] **Action 01 — sign out alpha:** from the header (or via `localStorage.clear(); location.href = '/login'`). Expect `/login`. **Screenshot:** `test3_{HMMSS}_01_login_after_signout.png`
- [ ] **Action 02 — sign in as beta:** fill beta credentials. **Screenshot:** `test3_{HMMSS}_02_beta_credentials.png`
- [ ] **Action 03 — beta's dashboard:** click sign-in; land on dashboard. **Screenshot:** `test3_{HMMSS}_03_beta_dashboard.png`
- [ ] **Action 04 — today's date view for beta:** click today's tile. Expect all five slots empty (cold start for beta). **Screenshot:** `test3_{HMMSS}_04_beta_date_empty.png`
- [ ] **Action 05 — upload similar chicken rice:** select `chicken_rice_1.jpg` on slot 1. **Screenshot:** `test3_{HMMSS}_05_beta_upload_scheduled.png`
- [ ] **Action 06 — Step 1 complete for beta's upload:** wait for the editor. **Screenshot:** `test3_{HMMSS}_06_beta_step1_editor.png`
- [ ] **Action 07 — reference_image === null for beta (API assertion):** same fetch as Test 1 Action 10. Expect `reference_image === null` even though alpha has matching rows. **Screenshot:** `test3_{HMMSS}_07_api_beta_null.png`
- [ ] **Action 08 — beta's corpus scoped (DB assertion, optional):** `SELECT user_id, query_id FROM personalized_food_descriptions WHERE user_id = <beta_id>` returns exactly one row, and a separate `SELECT FROM ... WHERE user_id = <alpha_id>` returns the two rows from Tests 1+2 (unchanged). **Screenshot:** `test3_{HMMSS}_08_db_scoped.png`

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time)_
- **Improvement Proposals:**
  + must have - Add a DB-level pytest that explicitly asserts `search_for_user(user_id=beta, ...)` returns `[]` when the only matching rows belong to alpha - Chrome proves the pipeline end-to-end, pytest locks the service invariant.

---

### Test 4 — Edge case: unrelated image → `reference_image === null` even with history (desktop)

**User(s):** `test_user_alpha` (sign in as alpha again after Test 3)

**Goal:** A truly dissimilar upload (`chocolate_cookie.jpg`) should not match alpha's existing chicken-rice rows. `reference_image` must be `null` because no prior row crosses the similarity threshold.

- [ ] **Action 01 — sign out beta, sign in alpha:** full sign-out + re-sign-in cycle. **Screenshot:** `test4_{HMMSS}_01_alpha_signed_in.png`
- [ ] **Action 02 — today's date view, two slots filled:** navigate to alpha's date page. Slots 1 and 2 show thumbnails. **Screenshot:** `test4_{HMMSS}_02_date_view_two_filled.png`
- [ ] **Action 03 — upload unrelated dish:** select `chocolate_cookie.jpg` on slot 3. **Screenshot:** `test4_{HMMSS}_03_upload_cookie.png`
- [ ] **Action 04 — Step 1 completes:** wait for the editor. **Screenshot:** `test4_{HMMSS}_04_step1_editor_cookie.png`
- [ ] **Action 05 — reference_image === null (API assertion):** same fetch call. Expect `reference_image: null` because no chicken-rice row crosses `THRESHOLD_PHASE_1_1_1_SIMILARITY = 0.25` for tokens like `["chocolate", "cookie"]`. **Screenshot:** `test4_{HMMSS}_05_api_cookie_null.png`
- [ ] **Action 06 — cookie row inserted anyway (DB assertion, optional):** `SELECT COUNT(*) FROM personalized_food_descriptions WHERE user_id = <alpha_id>` returns 3. Cookie row has `similarity_score_on_insert IS NULL` (no match above threshold at insert time). **Screenshot:** `test4_{HMMSS}_06_db_three_rows.png`

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time)_
- **Improvement Proposals:**
  + good to have - Persist the top-1 raw BM25 score even when `reference_image` ends up `null` (on `similarity_score_on_insert`) so retrieval quality can be audited without re-running the index.

---

### Test 5 — Retry-step1 idempotency: Phase 1.1.1 does NOT duplicate the personalization row (desktop)

**User(s):** `test_user_alpha`

**Goal:** When Phase 1 fails and the user hits the retry button, Phase 1.1.1 must short-circuit (row already inserted). Only Phase 1.1.2 re-runs. The unique index on `query_id` guarantees no duplicate, but the test also asserts that the row's `description` / `tokens` remain from the FIRST attempt.

**Precondition:** the operator temporarily makes Phase 1.1.2 fail for the next upload. Easiest way: unset `GEMINI_API_KEY` for the backend process (or replace with an invalid value), then restart the backend. The fast-caption call (Phase 1.1.1) and the component-ID call (Phase 1.1.2) both use `GEMINI_API_KEY`, so both will fail. **This test is therefore skipped-with-note** unless a selective failure mechanism is available.

If there is no selective failure path, rewrite this test to force a retry by invoking the retry endpoint directly **after** a successful upload (the `/retry-step1` guard requires a prior `step1_error`, so this path may not be exercisable without a real failure). Document the outcome.

- [ ] **Action 01 — trigger an upload that will fail Phase 1:** the operator either (a) invalidates `GEMINI_API_KEY` then uploads, or (b) exercises whatever failure-injection path the project has. Upload `chicken_rice_2.jpg` on slot 4. **Screenshot:** `test5_{HMMSS}_01_upload_bad_key.png`
- [ ] **Action 02 — Step 1 error surfaces:** wait for `PhaseErrorCard` to render (shows the Step 1 error headline). Capture the error. **Screenshot:** `test5_{HMMSS}_02_step1_error.png`
- [ ] **Action 03 — row exists anyway (DB assertion, optional):** `SELECT query_id, description, tokens FROM personalized_food_descriptions WHERE user_id = <alpha_id> ORDER BY id DESC LIMIT 1`. Expect the new row to be present IF the fast-caption succeeded before the component-ID call failed. If graceful-degrade kicked in on the fast-caption itself, the new row is absent (valid per spec). Record which branch occurred. **Screenshot:** `test5_{HMMSS}_03_db_post_error.png`
- [ ] **Action 04 — fix the failure injection:** the operator restores `GEMINI_API_KEY` and restarts the backend. **Screenshot:** `test5_{HMMSS}_04_key_restored.png`
- [ ] **Action 05 — click retry:** on the `PhaseErrorCard`, click "Try again". **Screenshot:** `test5_{HMMSS}_05_retry_clicked.png`
- [ ] **Action 06 — Step 1 succeeds on retry:** wait for the editor. **Screenshot:** `test5_{HMMSS}_06_step1_editor_after_retry.png`
- [ ] **Action 07 — no duplicate row (DB assertion, optional):** `SELECT COUNT(*) FROM personalized_food_descriptions WHERE user_id = <alpha_id> AND query_id = <retry_record_id>` returns exactly `1`. If the row existed before the retry, its `description` / `tokens` are UNCHANGED (no re-captioning on retry — matches the user-clarified contract). **Screenshot:** `test5_{HMMSS}_07_db_no_duplicate.png`

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time)_
- **Improvement Proposals:**
  + must have - Document the failure-injection recipe in `docs/technical/testing_context.md` - today there is no reliable way to selectively fail Phase 1.1.2 while keeping Phase 1.1.1 working, which limits retry coverage to "both succeed" or "both fail".
  + good to have - Emit an INFO log at the top of Phase 1.1.1 saying "skipping fast-caption for query_id=X, row already exists" so the retry skip path is observable in backend.log.

---

### Test 6 — Cold-start upload on mobile (375 × 1080) — mirrors Test 1

**User(s):** `test_user_beta` (sign in as beta at mobile viewport)

**Goal:** Replay Test 1's flow at mobile resolution. Stage 2 has no UI changes, so this is a regression guard plus the standard mobile-layout checks.

- [ ] **Action 01 — set mobile viewport:** call `mcp__claude-in-chrome__resize_window` with `width: 375, height: 1080`. Verify `window.innerWidth === 375`. **Screenshot:** `test6_{HMMSS}_01_mobile_viewport_set.png`
- [ ] **Action 02 — sign in as beta (after a fresh DB cleanup for beta's dish rows):** run the Cleanup SQL, navigate to `/login`, fill credentials, sign in. **Screenshot:** `test6_{HMMSS}_02_beta_dashboard_mobile.png`
- [ ] **Action 02b — overflow check (dashboard):** run the horizontal-overflow JS from `generation-rules.md` §Mobile assertions. Expect `hasOverflow === false`. **Screenshot:** `test6_{HMMSS}_02b_overflow_check_dashboard.png`
- [ ] **Action 03 — date view on mobile:** click today's tile. Expect the dish slots stacked vertically (or whatever the mobile layout prescribes). **Screenshot:** `test6_{HMMSS}_03_date_view_mobile.png`
- [ ] **Action 03b — tap-target check on slot 1 uploader:** assert the upload button on slot 1 has `getBoundingClientRect().height >= 44`. **Screenshot:** `test6_{HMMSS}_03b_tap_target_upload.png`
- [ ] **Action 04 — upload `chicken_rice_1.jpg` on slot 1:** same as Test 1 Action 07. **Screenshot:** `test6_{HMMSS}_04_upload_mobile.png`
- [ ] **Action 05 — Step 1 editor on mobile:** wait for the editor. **Screenshot:** `test6_{HMMSS}_05_step1_editor_mobile.png`
- [ ] **Action 05b — overflow check (item page):** same overflow JS. Expect no horizontal scroll. **Screenshot:** `test6_{HMMSS}_05b_overflow_check_item.png`
- [ ] **Action 06 — reference_image === null (API assertion):** same fetch call as Test 1 Action 10. **Screenshot:** `test6_{HMMSS}_06_api_reference_image_null_mobile.png`
- [ ] **Action 07 — scroll-reachability check:** scroll to the very bottom of `/item/{record_id}`. Confirm no content is hidden behind fixed headers/footers. **Screenshot:** `test6_{HMMSS}_07_scroll_bottom_mobile.png`

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time)_
- **Improvement Proposals:**
  + good to have - If any overflow is detected on the Step 1 editor at 375 px, flag it - Stage 2 should not introduce any regression since no DOM changes.

---

### Test 7 — Warm-start mobile match (mirrors Test 2)

**User(s):** `test_user_beta` (mobile viewport already set from Test 6)

**Goal:** Second mobile upload, same user, similar dish. `reference_image` should point at Test 6's upload.

- [ ] **Action 01 — back to date view:** navigate to beta's date page. **Screenshot:** `test7_{HMMSS}_01_date_view_one_filled_mobile.png`
- [ ] **Action 02 — upload `chicken_rice_2.jpg` on slot 2:** **Screenshot:** `test7_{HMMSS}_02_upload_mobile_slot2.png`
- [ ] **Action 03 — Step 1 editor ready:** **Screenshot:** `test7_{HMMSS}_03_step1_editor_mobile_slot2.png`
- [ ] **Action 04 — reference_image populated (API assertion):** same fetch as Test 2 Action 05. Expect `ref_query_id === <Test 6 record_id>`. **Screenshot:** `test7_{HMMSS}_04_api_ref_populated_mobile.png`
- [ ] **Action 05 — overflow check:** horizontal-overflow JS. **Screenshot:** `test7_{HMMSS}_05_overflow_check_mobile.png`
- [ ] **Action 06 — text readability check:** assert body text ≥ 12 px via `getComputedStyle(document.body).fontSize`. **Screenshot:** `test7_{HMMSS}_06_text_readability_mobile.png`

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time)_
- **Improvement Proposals:**
  + good to have - If Stage 3 later surfaces `reference_image` in the UI, ensure the reference thumbnail is full-width on mobile (avoid side-by-side layouts at 375 px).

---

### Test 8 — Cross-user isolation on mobile (mirrors Test 3)

**User(s):** `test_user_beta` → sign out → `test_user_alpha` (mobile)

**Goal:** Same invariant as Test 3, replayed at 375 × 1080 after a user switch.

- [ ] **Action 01 — sign out beta:** via `localStorage.clear(); location.href = '/login'`. **Screenshot:** `test8_{HMMSS}_01_login_after_signout_mobile.png`
- [ ] **Action 02 — sign in as alpha on mobile:** fill alpha credentials. **Screenshot:** `test8_{HMMSS}_02_alpha_dashboard_mobile.png`
- [ ] **Action 03 — date view on mobile (alpha has 3 filled slots from Tests 1/2/4):** **Screenshot:** `test8_{HMMSS}_03_alpha_date_three_filled_mobile.png`
- [ ] **Action 04 — overflow check with filled slots:** confirm the slot layout fits 375 px with no scroll. **Screenshot:** `test8_{HMMSS}_04_overflow_alpha_mobile.png`
- [ ] **Action 05 — upload `chicken_rice_2.jpg` on slot 5:** **Screenshot:** `test8_{HMMSS}_05_alpha_upload_mobile_slot5.png`
- [ ] **Action 06 — reference_image populated for alpha's chicken-rice upload (API assertion):** expect it to point at Test 1 or Test 2's upload (whichever scores higher). Crucially, it must NOT point at beta's Test 6 row — cross-user leak would show a beta `query_id`. **Screenshot:** `test8_{HMMSS}_06_api_alpha_ref_cross_user_guard_mobile.png`

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time)_
- **Improvement Proposals:**
  + must have - The cross-user invariant is already guaranteed by the SQL `WHERE user_id = ?` filter, but add an explicit assertion in the test so a future refactor cannot silently break it.

---

### Test 9 — Validation & edge cases on mobile (mirrors Test 4)

**User(s):** `test_user_alpha` (mobile)

**Goal:** Unrelated image uploaded on mobile. `reference_image === null`. Confirm the Step 1 editor renders cleanly at 375 px.

- [ ] **Action 01 — upload `chocolate_cookie.jpg` on the next free slot:** (the operator may need to clean up a slot first since alpha has used 3 on mobile). **Screenshot:** `test9_{HMMSS}_01_upload_cookie_mobile.png`
- [ ] **Action 02 — Step 1 editor loaded:** **Screenshot:** `test9_{HMMSS}_02_step1_editor_cookie_mobile.png`
- [ ] **Action 03 — reference_image === null (API assertion):** **Screenshot:** `test9_{HMMSS}_03_api_cookie_null_mobile.png`
- [ ] **Action 04 — overflow + tap-target check:** run both assertions. **Screenshot:** `test9_{HMMSS}_04_mobile_assertions.png`
- [ ] **Action 05 — empty-personalization UI (no-op for Stage 2):** confirm the Step 1 editor does not render any stray "No reference" banner — Stage 2 ships no such UI, so the editor should look identical to a cold-start upload. **Screenshot:** `test9_{HMMSS}_05_no_extra_banner_mobile.png`

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time)_
- **Improvement Proposals:**
  + good to have - Add a "Reference: none (cold start or below threshold)" debug footer, gated behind a dev-only flag, so operators running E2E tests can see retrieval state without DevTools.

---

### Test 10 — Permission guard on mobile (mirrors Test 5)

**User(s):** _(no user — unauthenticated)_

**Goal:** Hitting `/item/{any_id}` without a valid token must not surface another user's `reference_image` (or any other data). This is a general auth guard, not Stage-2-specific, but is included so the mobile pass parallels the desktop set.

- [ ] **Action 01 — sign out and clear tokens:** `localStorage.clear(); location.href = '/login'`. **Screenshot:** `test10_{HMMSS}_01_logged_out_mobile.png`
- [ ] **Action 02 — attempt direct navigation to alpha's most recent item:** `location.href = '/item/<alpha_last_record_id>'`. Expect either a redirect to `/login` or an auth-error state (no item data rendered). **Screenshot:** `test10_{HMMSS}_02_auth_guard_mobile.png`
- [ ] **Action 03 — API call rejected:** in `javascript_tool`, `fetch('/api/item/<alpha_last_record_id>', { credentials: 'include' })` with no token → expect HTTP 401 (or whatever status the auth layer uses). Do NOT leak the JSON. **Screenshot:** `test10_{HMMSS}_03_api_401_mobile.png`
- [ ] **Action 04 — overflow check on login page:** confirm the login form has no horizontal overflow at 375 px. **Screenshot:** `test10_{HMMSS}_04_login_overflow_mobile.png`

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time)_
- **Improvement Proposals:**
  + must have - The auth guard is pre-existing; this test is a passive verification. If it fails, the fix is in `src.auth.authenticate_user_from_request`, not in Stage 2 code.

---

## Summary for the Caller

- **Output file:** `docs/chrome_test/260418_2013_stage2_phase1_1_1_fast_caption.md`
- **Screenshots directory:** `data/chrome_test_images/260418_2013_stage2_phase1_1_1_fast_caption/`
- **Number of tests:** 10 total — 5 desktop (Tests 1–5) + 5 mobile (Tests 6–10).
- **Users involved:** two placeholders — `test_user_alpha` and `test_user_beta`. Replace with real seeded usernames before running. No role differences.
- **Rough screenshot budget:** ~65 screenshots across the 10 tests (desktop ~32, mobile ~33 with extra overflow / tap-target / readability / scroll-reachability assertions).
- **Viewport notes:** Test 1 Action 01 sets desktop to 1080 × 1280; Tests 2–5 inherit. Test 6 Action 01 sets mobile to 375 × 1080; Tests 7–10 inherit.
- **Noteworthy scope caveats:**
  - Stage 2 ships no UI change, so every assertion on retrieval behavior runs via `javascript_tool` + `fetch()` on the backend JSON, not DOM scraping.
  - DB assertions ("row exists", "row count") are marked **optional** — the operator can run them in a terminal or skip them; the browser-side API fetches are authoritative.
  - Test 5 (retry idempotency) depends on a reliable way to fail Phase 1 mid-flight. Document that in `docs/technical/testing_context.md` before the first run — today the only reliable path is toggling `GEMINI_API_KEY`, which affects both 1.1.1 and 1.1.2.
- **Next step:** leave all tests as `IN QUEUE`. They will be executed by `feature-implement-full` after Stage 2 lands, or manually via `/webapp-dev:chrome-test-execute`.
