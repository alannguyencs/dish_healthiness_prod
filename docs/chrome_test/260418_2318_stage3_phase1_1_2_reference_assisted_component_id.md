# Chrome E2E Test Spec — Stage 3: Phase 1.1.2 (Two-Image, Reference-Assisted Component ID)

**Feature:** When Phase 1.1.1 (Stage 2) attaches a non-null `result_gemini.reference_image` with a populated `prior_step1_data`, Phase 1.1.2 now calls Gemini 2.5 Pro with **two image parts** (query + reference) and an injected "Reference results (HINT ONLY)" block carrying the referenced dish's prior analysis. Cold start, missing `prior_step1_data`, and missing-on-disk reference-image file all degrade to today's single-image path (per user decision 2026-04-18).

**Spec generated:** 2026-04-18 23:18
**Plan target:** `docs/plan/260418_stage3_phase1_1_2_reference_assisted_component_id.md`
**Screenshots directory:** `data/chrome_test_images/260418_2318_stage3_phase1_1_2_reference_assisted_component_id/`

---

## Remarks

### Context

- **Frontend base URL:** `http://localhost:2512` (resolved from `start_app.sh`).
- **Backend base URL:** `http://localhost:2612` (resolved from `start_app.sh`).
- **Login page:** `http://localhost:2512/login`. Username + password auth; tokens live 90 days.
- **Test users:** this project has no `docs/technical/testing_context.md` yet, so the two usernames below are **placeholders** — replace with seeded dev-DB usernames before running:
  - `TEST_USER_ALPHA` — primary tester.
  - `TEST_USER_BETA` — secondary tester for cross-user isolation.
- **Cleanup between runs:** the `Database Pre-Interaction` section below deletes personalization rows + dish image queries + (optionally) image files so each run starts cold.
- **Critical observation surface:** Stage 3 changes what the Gemini Pro request looks like, not what the DOM looks like. **Backend log inspection** (for "two image parts attached" and "reference block substituted") is the primary assertion channel. The Chrome harness uses `javascript_tool` + `fetch()` to read the persisted `result_gemini` shape and DOM screenshots for regression guards.

### How to detect "two image parts were sent" without a mock harness

Stage 3's acceptance criterion ("the request includes two image parts") is not directly observable from the browser — the call is server-to-Gemini. Three options for the operator:

1. **Add temporary backend INFO logs** before the `client.models.generate_content(...)` call that count the image parts in `contents`. The Chrome spec's mobile / warm-start tests then `tail backend.log | grep "image_parts"` to confirm. **Recommended** — one line of logging, removable before ship.
2. **Patch the analyzer at a known test toggle.** Out of scope for Stage 3.
3. **Rely on inspection of `step1_data.analysis_time` + `input_token`.** A two-image request has ~2× the input tokens of a single-image one. Not deterministic but a cheap smoke check. Usable when (1) is inconvenient.

All tests below use a combination of (1) and a `javascript_tool`-driven API poll to assert persisted state.

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

Same two dev users as the Stage 2 spec. Create them once if missing (see the Stage 2 spec for the optional `INSERT INTO users` helper).

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

For **Test 4** (missing image file) specifically, after uploading the first dish, the operator deletes the image file from disk before uploading the second:

```bash
rm data/images/*u{alpha_id}_dish1.jpg
```

### Test image assets

- `chicken_rice_1.jpg`, `chicken_rice_2.jpg` — two similar chicken-rice plates (same assets as Stage 2).
- `chocolate_cookie.jpg` — unrelated dish (optional; not required for Stage 3).

### Backend logging aid (Test 2 / Test 7)

Before executing Test 2, the operator temporarily adds this log line in `backend/src/service/llm/gemini_analyzer.py::analyze_step1_component_identification_async` immediately before `client.models.generate_content(...)`:

```python
logger.info(
    "Step 1 request assembled: image_parts=%d, reference_block_present=%s",
    sum(1 for c in contents if hasattr(c, "mime_type") or (hasattr(c, "inline_data") and c.inline_data)),
    "__REFERENCE_BLOCK__" not in analysis_prompt and "Reference results" in analysis_prompt,
)
```

Revert before committing the test run. The `backend.log` tail is inspected at key points in the spec.

---

## Pre-requisite

Before Test 1, run the Cleanup SQL, sign out any existing session, and confirm `localStorage.token` is empty. Tests proceed from a logged-out state.

---

## Tests

### Test 1 — Cold-start upload (desktop, 1080 × 1280) → single-image regression guard

**User(s):** `test_user_alpha`

**Goal:** First upload for a freshly-cleaned user. `result_gemini.reference_image === null`. Phase 1.1.2 runs single-image exactly as today. Step 1 editor renders normally.

- [ ] **Action 01 — set desktop viewport:** call `mcp__claude-in-chrome__resize_window` with `width: 1080, height: 1280`. Verify `window.innerWidth === 1080`. **Screenshot:** `test1_{HMMSS}_01_desktop_viewport_set.png`
- [ ] **Action 02 — sign in as alpha:** navigate to `/login`, fill credentials, submit. **Screenshot:** `test1_{HMMSS}_02_alpha_dashboard.png`
- [ ] **Action 03 — date view:** click today's tile. Five empty dish slots. **Screenshot:** `test1_{HMMSS}_03_date_view_empty.png`
- [ ] **Action 04 — upload chicken_rice_1 on slot 1:** **Screenshot:** `test1_{HMMSS}_04_upload_scheduled.png`
- [ ] **Action 05 — Step 1 editor loads:** wait up to 60 s. Dish predictions + components render as today. **Screenshot:** `test1_{HMMSS}_05_step1_editor_ready.png`
- [ ] **Action 06 — reference_image === null (API assertion):** `javascript_tool`:
  ```js
  const r = await fetch(`/api/item/${window.location.pathname.split('/').pop()}`, { credentials: 'include' });
  const j = await r.json();
  ({ step1_ok: !!j.result_gemini?.step1_data, ref: j.result_gemini?.reference_image });
  ```
  Expect `{ step1_ok: true, ref: null }`. **Screenshot:** `test1_{HMMSS}_06_api_cold_start.png`
- [ ] **Action 07 — backend log single-image confirmed:** operator tails `backend.log | grep "image_parts=1"`. Expect one matching line for this upload. **Screenshot:** `test1_{HMMSS}_07_log_image_parts_1.png` (terminal)

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time)_
- **Improvement Proposals:**
  + good to have - Promote the temporary `image_parts` log line to a permanent DEBUG-level metric - useful long-term for retrieval-usage analytics.

---

### Test 2 — Warm-start full reference (desktop) → two image parts + reference block

**User(s):** `test_user_alpha`

**Goal:** Second upload, same user, similar dish. `reference_image` is populated with `prior_step1_data`. Phase 1.1.2 attaches TWO image parts and the "Reference results (HINT ONLY)" block is present in the outbound prompt. `step1_data` eventually renders and reflects use of the reference on manual inspection.

- [ ] **Action 01 — confirm Step 1 on Test 1's dish (so prior_step1_data is populated):** back on `/item/{record_1}`, use the Step 1 editor to confirm (or at least save current proposals). This populates `result_gemini.step1_data` on record_1 so Phase 1.1.1 for record_2 can carry it as `prior_step1_data`. **Screenshot:** `test2_{HMMSS}_01_step1_confirmed_record1.png`
- [ ] **Action 02 — back to date view:** navigate to alpha's date page. Slot 1 filled. **Screenshot:** `test2_{HMMSS}_02_date_view_one_filled.png`
- [ ] **Action 03 — upload chicken_rice_2 on slot 2:** **Screenshot:** `test2_{HMMSS}_03_upload_scheduled_slot2.png`
- [ ] **Action 04 — Step 1 editor loads for slot 2:** wait for the editor. **Screenshot:** `test2_{HMMSS}_04_step1_editor_slot2.png`
- [ ] **Action 05 — reference_image populated (API assertion):**
  ```js
  const r = await fetch(`/api/item/${window.location.pathname.split('/').pop()}`, { credentials: 'include' });
  const j = await r.json();
  const ref = j.result_gemini?.reference_image;
  ({
    has_ref: ref !== null && ref !== undefined,
    ref_query_id: ref?.query_id,
    has_prior: !!ref?.prior_step1_data,
    sim: ref?.similarity_score,
  });
  ```
  Expect `has_ref: true, ref_query_id: <record_1>, has_prior: true, sim >= 0.25`. **Screenshot:** `test2_{HMMSS}_05_api_warm_full_ref.png`
- [ ] **Action 06 — backend log: two image parts + reference block:** operator tails `backend.log | grep "image_parts=2"`. Expect a matching line whose `reference_block_present=True`. **Screenshot:** `test2_{HMMSS}_06_log_two_parts_with_block.png` (terminal)
- [ ] **Action 07 — step1_data quality (manual inspection):** read `step1_data.dish_predictions` and `step1_data.components` off the API. Check whether they match or reasonably differ from `reference_image.prior_step1_data`. Record the comparison verbatim in Findings. **Screenshot:** `test2_{HMMSS}_07_api_step1_vs_prior.png`

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time; include the verbatim comparison from Action 07)_
- **Improvement Proposals:**
  + must have - Capture the outbound prompt (with block substituted) in a per-request log file - makes prompt-drift debugging tractable without re-deriving.
  + good to have - Persist the `reference_block_used: true|false` boolean on `result_gemini.step1_data` so Stage 4+ can correlate confirmation-rate uplift with reference usage.

---

### Test 3 — Warm-start with reference image but NULL prior_step1_data (desktop) → single-image fallback

**User(s):** `test_user_alpha` → sign out → `test_user_beta` → sign out → `test_user_alpha`

**Goal:** Exercise the edge case where `reference_image` is populated but `prior_step1_data` is null. Per user decision (Option B, 2026-04-18) the Pro call degrades to single-image.

**Setup precondition:** a `personalized_food_descriptions` row exists for alpha whose `query_id` references a dish whose `DishImageQuery.result_gemini.step1_data` is null. Simplest way to create: upload a dish as alpha, watch Phase 1 fail (e.g., temporarily break `GEMINI_API_KEY` for the first request, then restore). The personalization row is inserted by Phase 1.1.1 before Phase 1.1.2 fires, so row exists with a null prior.

Alternative: operator directly `UPDATE dish_image_query_prod_dev SET result_gemini = '{"step": 0, "step1_data": null, "reference_image": null}' WHERE id = <record_A>` between the Phase 1.1.1 and Phase 1.1.2 writes — doable only if the operator has DB access mid-test.

- [ ] **Action 01 — seed a row with null prior_step1_data:** run one of the setups above. Confirm via SQL: `SELECT query_id FROM personalized_food_descriptions WHERE user_id = <alpha_id>` returns the row; `SELECT result_gemini->'step1_data' FROM dish_image_query_prod_dev WHERE id = <that query_id>` returns `null`. **Screenshot:** `test3_{HMMSS}_01_db_setup.png` (terminal)
- [ ] **Action 02 — upload similar dish as alpha:** new upload, chicken_rice_2.jpg on an empty slot. **Screenshot:** `test3_{HMMSS}_02_upload_scheduled.png`
- [ ] **Action 03 — Step 1 editor loads:** **Screenshot:** `test3_{HMMSS}_03_step1_editor.png`
- [ ] **Action 04 — reference_image populated BUT prior_step1_data is null:** API fetch. Expect `ref.query_id === <record_A>`, `ref.prior_step1_data === null`. **Screenshot:** `test3_{HMMSS}_04_api_ref_null_prior.png`
- [ ] **Action 05 — backend log: SINGLE image, NO reference block:** `backend.log | grep "image_parts=1"` for this upload. `reference_block_present=False`. **Screenshot:** `test3_{HMMSS}_05_log_fallback_single.png` (terminal)

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time)_
- **Improvement Proposals:**
  + good to have - Emit an INFO log at the skip decision: "Phase 1.1.2 reference attached=false (prior_step1_data missing)" so the three degrade paths are distinguishable in logs without grep'ing `image_parts=1`.

---

### Test 4 — Warm-start but reference image file missing on disk → single-image fallback + WARN

**User(s):** `test_user_alpha`

**Goal:** `reference_image` populated, but the referenced `image_url` file has been removed from disk. Phase 1.1.2 logs a WARN and degrades to single-image.

- [ ] **Action 01 — baseline upload (so reference exists):** upload chicken_rice_1.jpg, wait for Phase 1 success, confirm. **Screenshot:** `test4_{HMMSS}_01_baseline_upload.png`
- [ ] **Action 02 — delete image file from disk:** operator runs `rm data/images/*u{alpha_id}_dish1.jpg` between the baseline and the new upload. **Screenshot:** `test4_{HMMSS}_02_image_file_removed.png` (terminal)
- [ ] **Action 03 — upload similar dish as alpha on a different slot:** chicken_rice_2.jpg. Phase 1.1.1 retrieves the baseline row; its image_url now points at a missing file. **Screenshot:** `test4_{HMMSS}_03_upload_scheduled.png`
- [ ] **Action 04 — Step 1 editor loads:** **Screenshot:** `test4_{HMMSS}_04_step1_editor.png`
- [ ] **Action 05 — API: reference_image populated (prior_step1_data present):** fetch the item; `ref.prior_step1_data` is not null (the referenced dish's step1_data survived). `ref.image_url` points at the now-missing file. **Screenshot:** `test4_{HMMSS}_05_api_ref_present.png`
- [ ] **Action 06 — backend log: WARN + image_parts=1:** `backend.log | grep -E "WARN.*reference image.*missing|image_parts=1"`. Both matches expected: the WARN line about the missing file, and a single-image Pro call for this record. **Screenshot:** `test4_{HMMSS}_06_log_warn_single.png` (terminal)

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time)_
- **Improvement Proposals:**
  + must have - Sweep orphan `personalized_food_descriptions.image_url` rows on a periodic job, OR mark them inline on first miss so subsequent retrieval avoids them entirely - otherwise every future upload by this user re-triggers the WARN.

---

### Test 5 — Retry-step1 preserves two-image path (desktop)

**User(s):** `test_user_alpha`

**Goal:** After Phase 1.1.2 fails on a warm-user upload, `/retry-step1` reads the already-persisted `result_gemini.reference_image` and re-runs Phase 1.1.2 with two images. The retry short-circuits Phase 1.1.1 (Stage 2 invariant).

- [ ] **Action 01 — upload that will fail Phase 1.1.2:** temporarily break the `GEMINI_API_KEY` (or flip the Pro model to an invalid one if your dev env supports it). Upload a similar dish; Phase 1 errors out. `reference_image` is persisted because Stage 2's pre-Pro write already landed. **Screenshot:** `test5_{HMMSS}_01_upload_bad_config.png`
- [ ] **Action 02 — Phase 1 error surfaces:** `PhaseErrorCard` renders. **Screenshot:** `test5_{HMMSS}_02_step1_error_card.png`
- [ ] **Action 03 — API: reference_image already persisted:** fetch the item; `ref` is populated. `step1_data` is null, `step1_error` is set. **Screenshot:** `test5_{HMMSS}_03_api_ref_persisted_but_errored.png`
- [ ] **Action 04 — restore config:** operator restores `GEMINI_API_KEY` and restarts the backend. **Screenshot:** `test5_{HMMSS}_04_config_restored.png` (terminal)
- [ ] **Action 05 — click Retry:** on the `PhaseErrorCard`. **Screenshot:** `test5_{HMMSS}_05_retry_clicked.png`
- [ ] **Action 06 — Step 1 succeeds on retry:** editor renders. **Screenshot:** `test5_{HMMSS}_06_step1_editor_after_retry.png`
- [ ] **Action 07 — backend log: Phase 1.1.1 skipped, two image parts, reference block:** expect `"Phase 1.1.1 skipped on retry"` INFO + `image_parts=2 reference_block_present=True`. **Screenshot:** `test5_{HMMSS}_07_log_retry_two_parts.png` (terminal)
- [ ] **Action 08 — no duplicate personalization row:** SQL `SELECT COUNT(*) FROM personalized_food_descriptions WHERE query_id = <retry_record_id>` returns 1. **Screenshot:** `test5_{HMMSS}_08_db_no_duplicate.png` (terminal)

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time)_
- **Improvement Proposals:**
  + good to have - Include the `image_parts` count on the Step 1 response for dev builds so the user (or a test) can assert without log tailing.

---

### Test 6 — Cold-start mobile (mirrors Test 1)

**User(s):** `test_user_beta`

**Goal:** Replay Test 1's flow at 375 × 1080 to guard against UI regressions and add the standard mobile assertions.

- [ ] **Action 01 — set mobile viewport:** call `mcp__claude-in-chrome__resize_window` with `width: 375, height: 1080`. Verify `window.innerWidth === 375`. **Screenshot:** `test6_{HMMSS}_01_mobile_viewport_set.png`
- [ ] **Action 02 — sign in as beta:** **Screenshot:** `test6_{HMMSS}_02_beta_dashboard_mobile.png`
- [ ] **Action 02b — overflow check (dashboard):** horizontal overflow JS from `generation-rules.md`. Expect `hasOverflow === false`. **Screenshot:** `test6_{HMMSS}_02b_overflow_dashboard.png`
- [ ] **Action 03 — date view:** **Screenshot:** `test6_{HMMSS}_03_date_view_mobile.png`
- [ ] **Action 04 — upload chicken_rice_1.jpg on slot 1:** **Screenshot:** `test6_{HMMSS}_04_upload_mobile.png`
- [ ] **Action 05 — Step 1 editor loads:** **Screenshot:** `test6_{HMMSS}_05_step1_editor_mobile.png`
- [ ] **Action 05b — overflow check (item page):** **Screenshot:** `test6_{HMMSS}_05b_overflow_item.png`
- [ ] **Action 06 — API: reference_image === null:** **Screenshot:** `test6_{HMMSS}_06_api_cold_mobile.png`
- [ ] **Action 07 — backend log: image_parts=1:** **Screenshot:** `test6_{HMMSS}_07_log_single_mobile.png` (terminal)
- [ ] **Action 08 — scroll-reachability:** scroll to bottom of `/item/{record_id}`. **Screenshot:** `test6_{HMMSS}_08_scroll_bottom.png`

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time)_
- **Improvement Proposals:** _(empty baseline)_

---

### Test 7 — Warm-start full reference on mobile (mirrors Test 2)

**User(s):** `test_user_beta`

**Goal:** Two image parts + reference block at mobile viewport. Same assertions as Test 2, plus overflow / tap-target / readability.

- [ ] **Action 01 — confirm Step 1 on Test 6's dish:** Step 1 editor → confirm. **Screenshot:** `test7_{HMMSS}_01_confirmed_record6.png`
- [ ] **Action 02 — upload chicken_rice_2.jpg on slot 2 (mobile):** **Screenshot:** `test7_{HMMSS}_02_upload_mobile.png`
- [ ] **Action 03 — Step 1 editor on mobile:** **Screenshot:** `test7_{HMMSS}_03_step1_editor_mobile.png`
- [ ] **Action 04 — API: reference_image populated with prior_step1_data:** **Screenshot:** `test7_{HMMSS}_04_api_warm_mobile.png`
- [ ] **Action 05 — backend log: image_parts=2 with block:** **Screenshot:** `test7_{HMMSS}_05_log_two_parts_mobile.png` (terminal)
- [ ] **Action 06 — overflow + tap-target checks:** verify Step 1 editor at 375 px has no horizontal overflow; primary buttons ≥ 44 px tall. **Screenshot:** `test7_{HMMSS}_06_mobile_assertions.png`
- [ ] **Action 07 — text readability:** body text ≥ 12 px via `getComputedStyle`. **Screenshot:** `test7_{HMMSS}_07_readability.png`

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time)_
- **Improvement Proposals:** _(empty baseline)_

---

### Test 8 — Multi-user on mobile (mirrors Test 3 + cross-user guard)

**User(s):** `test_user_beta` → sign out → `test_user_alpha`

**Goal:** Cross-user isolation holds at mobile viewport. Alpha's prior records don't surface for beta. Beta's upload gets `reference_image === null` even though alpha has matching rows.

- [ ] **Action 01 — still as beta, date view:** **Screenshot:** `test8_{HMMSS}_01_beta_date_mobile.png`
- [ ] **Action 02 — sign out beta, sign in alpha:** **Screenshot:** `test8_{HMMSS}_02_alpha_mobile.png`
- [ ] **Action 03 — overflow check on alpha's date view:** **Screenshot:** `test8_{HMMSS}_03_overflow_alpha.png`
- [ ] **Action 04 — upload chicken_rice_2.jpg on alpha's next free slot:** **Screenshot:** `test8_{HMMSS}_04_alpha_upload.png`
- [ ] **Action 05 — API: reference points at alpha's own prior row, NOT beta's:** assert `ref.query_id` corresponds to one of alpha's records from Tests 1/2, not beta's from Test 6/7. **Screenshot:** `test8_{HMMSS}_05_api_cross_user_guard.png`

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time)_
- **Improvement Proposals:**
  + must have - Write an end-to-end pytest that seeds rows for user B and asserts `resolve_reference_for_upload` for user A never surfaces B's query_id, even at the BM25 layer. Chrome proves the pipeline; pytest locks the service invariant.

---

### Test 9 — Edge cases on mobile (mirrors Tests 3 + 4)

**User(s):** `test_user_alpha`

**Goal:** Replay Tests 3 and 4's degrade paths at mobile viewport. Each should end with `image_parts=1` in the backend log.

- [ ] **Action 01 — seed null-prior row for alpha (if not present):** use same method as Test 3 Action 01. **Screenshot:** `test9_{HMMSS}_01_db_seed_null_prior.png` (terminal)
- [ ] **Action 02 — upload that triggers reference_image with null prior:** **Screenshot:** `test9_{HMMSS}_02_upload_null_prior.png`
- [ ] **Action 03 — backend log: image_parts=1:** **Screenshot:** `test9_{HMMSS}_03_log_single_null_prior.png` (terminal)
- [ ] **Action 04 — remove an image file, upload similar dish (missing-on-disk path):** **Screenshot:** `test9_{HMMSS}_04_upload_after_rm.png`
- [ ] **Action 05 — backend log: WARN + image_parts=1:** **Screenshot:** `test9_{HMMSS}_05_log_warn_single.png` (terminal)
- [ ] **Action 06 — overflow check on both item pages:** **Screenshot:** `test9_{HMMSS}_06_overflow_edge_cases.png`

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time)_
- **Improvement Proposals:** _(empty baseline)_

---

### Test 10 — Permission guard on mobile (mirrors Test 5's retry guard)

**User(s):** _(unauthenticated)_

**Goal:** Unauthenticated attempts to hit `/item/{id}` or `/api/item/{id}/retry-step1` return 401 and do not leak reference_image or prior_step1_data.

- [ ] **Action 01 — sign out, clear tokens:** `localStorage.clear(); location.href = '/login'`. **Screenshot:** `test10_{HMMSS}_01_logged_out.png`
- [ ] **Action 02 — attempt direct navigation to alpha's latest item:** expect redirect or auth error. **Screenshot:** `test10_{HMMSS}_02_auth_guard.png`
- [ ] **Action 03 — API: GET /api/item/{id} without token → 401:** `javascript_tool` fetch. **Screenshot:** `test10_{HMMSS}_03_get_401.png`
- [ ] **Action 04 — API: POST /api/item/{id}/retry-step1 without token → 401:** **Screenshot:** `test10_{HMMSS}_04_retry_401.png`

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time)_
- **Improvement Proposals:** _(empty baseline)_

---

## Summary for the Caller

- **Output file:** `docs/chrome_test/260418_2318_stage3_phase1_1_2_reference_assisted_component_id.md`
- **Screenshots directory:** `data/chrome_test_images/260418_2318_stage3_phase1_1_2_reference_assisted_component_id/`
- **Number of tests:** 10 total — 5 desktop (1080 × 1280) + 5 mobile (375 × 1080).
- **Users involved:** placeholders `test_user_alpha` + `test_user_beta` (replace before running).
- **Rough screenshot budget:** ~65 PNGs + several terminal captures (`backend.log`, `rm`, SQL).
- **Viewport notes:** Test 1 Action 01 sets desktop; Test 6 Action 01 sets mobile.
- **Key dependencies before first execution:**
  - Add the temporary `image_parts` / `reference_block_present` log line in `gemini_analyzer.py` (see Remarks § "Backend logging aid"). Revert before committing the test run.
  - `docs/technical/testing_context.md` does not exist yet — placeholders must be replaced with real seeded usernames.
- **Next step:** spec stays `IN QUEUE`. `feature-implement-full` will trigger `chrome-test-execute`, or the operator runs manually via `/webapp-dev:chrome-test-execute`.
