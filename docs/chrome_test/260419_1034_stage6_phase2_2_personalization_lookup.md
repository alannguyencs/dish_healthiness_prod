# Chrome E2E Test Spec — Stage 6: Phase 2.2 (Personalization Lookup)

**Feature:** Phase 2 background task now runs `lookup_personalization(user_id, query_id, description, confirmed_dish_name)` **in parallel** with Phase 2.1 via `asyncio.gather`, persisting the raw list on `result_gemini.personalized_matches` **before** the Gemini 2.5 Pro call. Each match carries `prior_step2_data` (from the referenced dish's own Phase 2 result, if any) and `corrected_step2_data` (Stage 8's write, still null in Stage 6). Cold-start users and below-threshold searches surface `[]`.

**Spec generated:** 2026-04-19 10:34
**Plan target:** `docs/plan/260419_stage6_phase2_2_personalization_lookup.md`
**Screenshots directory:** `data/chrome_test_images/260419_1034_stage6_phase2_2_personalization_lookup/`

---

## Remarks

### Context

- **Frontend base URL:** `http://localhost:2512` (from `start_app.sh`).
- **Backend base URL:** `http://localhost:2612` (from `start_app.sh`).
- **Login page:** `http://localhost:2512/login`.
- **Test users:** placeholder (no `docs/technical/testing_context.md`):
  - `TEST_USER_ALPHA`
  - `TEST_USER_BETA`
- **Cleanup between runs:** standard personalization + dish-query delete for both users. `nutrition_foods` untouched.

### Key assertion channel

Stage 6 ships no DOM change. Assertions:

1. **API fetch** on `GET /api/item/{id}` — inspect `result_gemini.personalized_matches`.
2. **SQL** — verify `personalized_food_descriptions` rows (Stage 2 writer, Stage 4 enrichment).
3. **backend.log** — grep for `Phase 2.2` timing + any gather WARN lines.

### Parallel timing note

Phase 2.1 and Phase 2.2 are scheduled via `asyncio.gather(asyncio.to_thread(phase_2_1), asyncio.to_thread(phase_2_2))`. Both are in-process BM25 (~ms); the dominant per-lookup wall-clock is the Postgres SELECT that hydrates the user's corpus. The **parallel timing test (Test 3)** requires a visible wall-clock delta to demonstrate concurrent execution. Operator can temporarily add timing log lines in `item_tasks.py` immediately before and after the `gather` call:

```python
import time
t0 = time.perf_counter()
nutrition_db_matches, personalized_matches = await asyncio.gather(...)
logger.info("Phase 2.1+2.2 gather took %.3f ms", (time.perf_counter() - t0) * 1000)
```

Revert before committing.

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

- `chicken_rice_1.jpg`, `chicken_rice_2.jpg` — two similar chicken-rice plates.
- `chocolate_cookie.jpg` — unrelated dish (optional; used in Test 4).

### Failure injection (Test 5 / Test 10 only)

Operator temporarily patches `lookup_personalization` to raise, exercising the gather error-isolation branch. Simplest injection: `export DEBUG_FORCE_PHASE_2_2_FAIL=1` — plan should include a feature-flag helper, or ops can raise in a monkeypatch during test execution. If no injection path is wired, document and skip with a note in the report.

---

## Pre-requisite

Before Test 1: run Cleanup SQL, clear `localStorage`. Confirm `nutrition_foods` is populated (Phase 2.1 still runs):

```sql
SELECT COUNT(*) FROM nutrition_foods;  -- expect ~4,493
```

---

## Tests

### Test 1 — Cold-start: no prior history → `personalized_matches === []` (desktop 1080 × 1280)

**User(s):** `test_user_alpha`

**Goal:** Very first upload for a freshly-cleaned user. `personalized_matches` is persisted as `[]` (key present, list empty). Phase 2.1 still produces its own result; no interaction between the two halves.

- [ ] **Action 01 — set desktop viewport:** `resize_window` 1080 × 1280. **Screenshot:** `test1_{HMMSS}_01_desktop_viewport_set.png`
- [ ] **Action 02 — sign in as alpha:** **Screenshot:** `test1_{HMMSS}_02_dashboard.png`
- [ ] **Action 03 — upload chicken_rice_1.jpg on slot 1:** **Screenshot:** `test1_{HMMSS}_03_upload.png`
- [ ] **Action 04 — Step 1 editor → Confirm:** **Screenshot:** `test1_{HMMSS}_04_confirm.png`
- [ ] **Action 05 — API: personalized_matches present but empty:**
  ```js
  const r = await fetch(`/api/item/${window.location.pathname.split('/').pop()}`, { credentials: 'include' });
  const j = await r.json();
  ({
    has_key: 'personalized_matches' in (j.result_gemini || {}),
    matches: j.result_gemini?.personalized_matches,
    has_nutrition: !!j.result_gemini?.nutrition_db_matches,
  });
  ```
  Expect `{ has_key: true, matches: [], has_nutrition: true }`. **Screenshot:** `test1_{HMMSS}_05_api_empty_matches.png`
- [ ] **Action 06 — Step 2 view renders as today:** UI regression guard. **Screenshot:** `test1_{HMMSS}_06_step2_view.png`

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time)_
- **Improvement Proposals:**
  + good to have - Surface `personalized_matches.length` on the Step 2 debug panel (dev-only) so operators can see retrieval depth at a glance.

---

### Test 2 — Warm user: prior history populates matches (desktop)

**User(s):** `test_user_alpha`

**Goal:** Second upload by the same user of a similar dish. `personalized_matches[]` is populated. Each match carries `query_id`, `image_url`, `description`, `similarity_score >= 0.30`, `prior_step2_data` (non-null because Test 1's Phase 2 landed), `corrected_step2_data` (null until Stage 8).

**Pre-step:** Test 1 completes first (its dish's `step2_data` becomes the prior).

- [ ] **Action 01 — wait for Test 1's step2_data to land:** verify via API `GET /api/item/<Test 1 record>` that `step2_data` is non-null. **Screenshot:** `test2_{HMMSS}_01_api_step2_ready.png`
- [ ] **Action 02 — upload chicken_rice_2.jpg on slot 2:** **Screenshot:** `test2_{HMMSS}_02_upload.png`
- [ ] **Action 03 — Step 1 editor → Confirm:** **Screenshot:** `test2_{HMMSS}_03_confirm.png`
- [ ] **Action 04 — API: personalized_matches populated with full shape:**
  ```js
  const j = await (await fetch(`/api/item/${...}`, { credentials: 'include' })).json();
  const matches = j.result_gemini?.personalized_matches || [];
  ({
    n_matches: matches.length,
    top_keys: matches[0] ? Object.keys(matches[0]).sort() : [],
    top_ref_query_id: matches[0]?.query_id,
    top_similarity: matches[0]?.similarity_score,
    top_has_prior_step2: !!matches[0]?.prior_step2_data,
    top_corrected: matches[0]?.corrected_step2_data,
  });
  ```
  Expect `n_matches >= 1, top_ref_query_id === <Test 1 record_id>, top_similarity >= 0.30, top_has_prior_step2 === true, top_corrected === null`. `top_keys` must include `query_id, image_url, description, similarity_score, prior_step2_data, corrected_step2_data`. **Screenshot:** `test2_{HMMSS}_04_api_matches.png`
- [ ] **Action 05 — self-match prevented:** confirm `matches[0].query_id !== <this upload's record_id>`. **Screenshot:** `test2_{HMMSS}_05_api_self_match_guarded.png`
- [ ] **Action 06 — SQL: personalized_food_descriptions has row for this query with description+tokens populated:**
  ```sql
  SELECT description, tokens IS NOT NULL AS has_tokens
    FROM personalized_food_descriptions
   WHERE query_id = <this record_id>;
  ```
  Both non-null (Phase 1.1.1 wrote them, Stage 4 will add `confirmed_*` after the confirm landed). **Screenshot:** `test2_{HMMSS}_06_db_row.png` (terminal)

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time; record `top_similarity` + `top_ref_query_id` for audit)_
- **Improvement Proposals:**
  + must have - Add a backend assertion that `top_keys` never drifts from the documented shape; Stage 7's prompt hydration will bind against these exact keys.

---

### Test 3 — Parallel timing: Phase 2.1 and Phase 2.2 complete concurrently (desktop)

**User(s):** `test_user_alpha`

**Goal:** Demonstrate that `asyncio.gather` runs both lookups in parallel. Wall-clock gather duration ≤ (individual Phase 2.1 time + 100 ms tolerance), not ≈ sum.

**Pre-step:** Operator adds the timing log line described in Remarks § "Parallel timing note" and restarts the backend.

- [ ] **Action 01 — upload fresh dish:** **Screenshot:** `test3_{HMMSS}_01_upload.png`
- [ ] **Action 02 — Confirm Step 1:** **Screenshot:** `test3_{HMMSS}_02_confirm.png`
- [ ] **Action 03 — backend.log: gather duration line:** `tail -f backend.log | grep "Phase 2.1+2.2 gather"`. Record the millisecond value. **Screenshot:** `test3_{HMMSS}_03_log_gather.png` (terminal)
- [ ] **Action 04 — manual comparison:** temporarily replace the gather call with sequential awaits (or consult a prior run's individual-phase timing logs). Expect the gather wall-clock to be within 20% of the slower single-phase time, NOT the sum. Record findings verbatim. **Screenshot:** `test3_{HMMSS}_04_comparison.png` (terminal)

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time; attach before/after timing numbers)_
- **Improvement Proposals:**
  + good to have - Promote the gather-duration log from WARN → DEBUG once the parallelism is confirmed in production. Optional metric.

---

### Test 4 — Cross-user isolation: beta's upload does not see alpha's rows

**User(s):** `test_user_alpha` → sign out → `test_user_beta`

**Goal:** Enforce per-user scoping at the Phase 2.2 layer. Beta uploads a similar chicken-rice plate; `personalized_matches === []` even though alpha has matching history.

- [ ] **Action 01 — sign out alpha, sign in beta:** `localStorage.clear(); location.href='/login'` then fill beta credentials. **Screenshot:** `test4_{HMMSS}_01_beta_dashboard.png`
- [ ] **Action 02 — beta uploads chicken_rice_1.jpg:** **Screenshot:** `test4_{HMMSS}_02_upload.png`
- [ ] **Action 03 — Confirm:** **Screenshot:** `test4_{HMMSS}_03_confirm.png`
- [ ] **Action 04 — API: personalized_matches empty for beta:**
  ```js
  const j = await (await fetch(`/api/item/${...}`, { credentials: 'include' })).json();
  ({ matches: j.result_gemini?.personalized_matches });
  ```
  Expect `matches: []`. Alpha's rows must NOT surface. **Screenshot:** `test4_{HMMSS}_04_api_empty_beta.png`
- [ ] **Action 05 — SQL: beta has one row scoped to beta's user_id only:**
  ```sql
  SELECT user_id FROM personalized_food_descriptions WHERE query_id = <beta's record_id>;
  ```
  Returns beta's id. **Screenshot:** `test4_{HMMSS}_05_db_scoped.png` (terminal)

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time)_
- **Improvement Proposals:**
  + must have - Keep a pytest that explicitly asserts `search_for_user(user_id=beta, ...)` returns `[]` when only user_id=alpha has matching rows. Chrome proves end-to-end; pytest locks the invariant.

---

### Test 5 — Gather error isolation: Phase 2.2 failure does not break Phase 2.1 or Pro call

**User(s):** `test_user_alpha`

**Goal:** Simulate an unexpected exception inside `lookup_personalization`. Phase 2.1 still lands `nutrition_db_matches`; the Pro call still runs; `personalized_matches` is `[]`; a WARN line names the exception in `backend.log`.

**Pre-step:** Operator enables the failure-injection flag (e.g. `DEBUG_FORCE_PHASE_2_2_FAIL=1` — plan should land with a test-only knob, or the operator monkeypatches the service at runtime).

- [ ] **Action 01 — enable failure injection + restart backend:** **Screenshot:** `test5_{HMMSS}_01_injection_on.png` (terminal)
- [ ] **Action 02 — upload + confirm:** **Screenshot:** `test5_{HMMSS}_02_confirm.png`
- [ ] **Action 03 — API: personalized_matches is empty list, nutrition_db_matches is populated, step2_data populated:**
  ```js
  const j = await (await fetch(`/api/item/${...}`, { credentials: 'include' })).json();
  ({
    personalized: j.result_gemini?.personalized_matches,
    nutrition_non_empty: (j.result_gemini?.nutrition_db_matches?.nutrition_matches?.length || 0) > 0,
    step2_ok: !!j.result_gemini?.step2_data,
    step2_error: j.result_gemini?.step2_error,
  });
  ```
  Expect `{ personalized: [], nutrition_non_empty: true, step2_ok: true, step2_error: undefined }`. **Screenshot:** `test5_{HMMSS}_03_api_isolation.png`
- [ ] **Action 04 — backend.log: WARN names the exception:** `tail backend.log | grep -i "phase 2.2"` or similar; confirm a WARN line names the injected error. **Screenshot:** `test5_{HMMSS}_04_log_warn.png` (terminal)
- [ ] **Action 05 — disable injection + restart:** **Screenshot:** `test5_{HMMSS}_05_injection_off.png` (terminal)

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time)_
- **Improvement Proposals:**
  + good to have - Ship the injection env var permanently (gated on dev builds) so this assertion is repeatable without code edits.

---

### Test 6 — Cold-start on mobile (mirrors Test 1)

**User(s):** `test_user_beta`

**Goal:** Replay Test 1 at 375 × 1080. `personalized_matches === []` on cold start. Layout checks on the Step 2 view.

- [ ] **Action 01 — set mobile viewport:** `resize_window` 375 × 1080. **Screenshot:** `test6_{HMMSS}_01_viewport.png`
- [ ] **Action 02 — sign in beta (after cleanup for beta):** **Screenshot:** `test6_{HMMSS}_02_dashboard.png`
- [ ] **Action 02b — overflow check on dashboard:** horizontal overflow JS. **Screenshot:** `test6_{HMMSS}_02b_overflow.png`
- [ ] **Action 03 — upload on mobile:** **Screenshot:** `test6_{HMMSS}_03_upload.png`
- [ ] **Action 04 — Confirm:** **Screenshot:** `test6_{HMMSS}_04_confirm.png`
- [ ] **Action 05 — API: personalized_matches empty:** **Screenshot:** `test6_{HMMSS}_05_api_empty.png`
- [ ] **Action 06 — overflow + readability on Step 2:** **Screenshot:** `test6_{HMMSS}_06_mobile_assertions.png`

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time)_
- **Improvement Proposals:** _(empty baseline)_

---

### Test 7 — Warm-start mobile (mirrors Test 2)

**User(s):** `test_user_beta`

**Goal:** Second upload populates `personalized_matches[]` with full shape on mobile. Tap-target and readability checks.

- [ ] **Action 01 — wait for Test 6's step2_data:** **Screenshot:** `test7_{HMMSS}_01_prior_ready.png`
- [ ] **Action 02 — upload similar dish on slot 2:** **Screenshot:** `test7_{HMMSS}_02_upload.png`
- [ ] **Action 03 — Confirm:** **Screenshot:** `test7_{HMMSS}_03_confirm.png`
- [ ] **Action 04 — API: matches populated:** **Screenshot:** `test7_{HMMSS}_04_api_matches.png`
- [ ] **Action 05 — tap-target check on Confirm/Retry buttons in Step 2:** **Screenshot:** `test7_{HMMSS}_05_tap_targets.png`
- [ ] **Action 06 — readability on Step 2 body text:** **Screenshot:** `test7_{HMMSS}_06_readability.png`

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time)_
- **Improvement Proposals:** _(empty baseline)_

---

### Test 8 — Parallel timing on mobile (mirrors Test 3)

**User(s):** `test_user_beta`

**Goal:** Same gather-wall-clock check on the mobile pass. Primary useful signal is the log line — mobile vs desktop shouldn't matter (Phase 2.1/2.2 are server-side), but this test locks the invariant in the mobile suite.

- [ ] **Action 01 — upload new dish:** **Screenshot:** `test8_{HMMSS}_01_upload.png`
- [ ] **Action 02 — Confirm:** **Screenshot:** `test8_{HMMSS}_02_confirm.png`
- [ ] **Action 03 — backend.log: gather duration line:** **Screenshot:** `test8_{HMMSS}_03_log.png` (terminal)

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time)_
- **Improvement Proposals:** _(empty baseline)_

---

### Test 9 — Edge cases on mobile (mirrors Tests 4 + 5)

**User(s):** `test_user_beta` → sign out → `test_user_alpha`

**Goal:** Replay cross-user isolation + gather error isolation on mobile.

- [ ] **Action 01 — sign out beta, sign in alpha at mobile viewport:** **Screenshot:** `test9_{HMMSS}_01_alpha_mobile.png`
- [ ] **Action 02 — alpha upload:** `personalized_matches` should match alpha's own priors (from Tests 1–3), NOT beta's. **Screenshot:** `test9_{HMMSS}_02_upload.png`
- [ ] **Action 03 — Confirm + API cross-user check:** **Screenshot:** `test9_{HMMSS}_03_api_cross_user.png`
- [ ] **Action 04 — enable failure injection + upload again:** **Screenshot:** `test9_{HMMSS}_04_injected_upload.png`
- [ ] **Action 05 — API: isolation holds on mobile too:** **Screenshot:** `test9_{HMMSS}_05_api_isolation.png`
- [ ] **Action 06 — disable injection:** **Screenshot:** `test9_{HMMSS}_06_injection_off.png` (terminal)

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time)_
- **Improvement Proposals:** _(empty baseline)_

---

### Test 10 — Permission guard on mobile (mirrors Test 5 of earlier specs)

**User(s):** _(unauthenticated)_

**Goal:** Unauthenticated confirm returns 401; no Phase 2.2 lookup runs; no personalized data leaks.

- [ ] **Action 01 — sign out, clear tokens:** **Screenshot:** `test10_{HMMSS}_01_logged_out.png`
- [ ] **Action 02 — POST /confirm-step1 without token → 401:** **Screenshot:** `test10_{HMMSS}_02_api_401.png`
- [ ] **Action 03 — GET /api/item/{any_id} without token → 401; no personalized_matches leaked:** **Screenshot:** `test10_{HMMSS}_03_get_401.png`

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time)_
- **Improvement Proposals:** _(empty baseline)_

---

## Summary for the Caller

- **Output file:** `docs/chrome_test/260419_1034_stage6_phase2_2_personalization_lookup.md`
- **Screenshots directory:** `data/chrome_test_images/260419_1034_stage6_phase2_2_personalization_lookup/`
- **Number of tests:** 10 total — 5 desktop + 5 mobile.
- **Users involved:** placeholders `test_user_alpha`, `test_user_beta` (replace with seeded usernames).
- **Rough screenshot budget:** ~55 PNGs + several terminal captures.
- **Viewport notes:** Test 1 Action 01 sets 1080 × 1280; Test 6 Action 01 sets 375 × 1080.
- **Critical caveats:**
  - Tests 3 / 8 need a temporary timing log line in `item_tasks.py` (see Remarks). Revert before committing.
  - Test 5 / Test 9 need a failure-injection knob for `lookup_personalization`. The plan should include a test-only env var (e.g. `DEBUG_FORCE_PHASE_2_2_FAIL=1`) or the operator monkeypatches at runtime.
  - Placeholder usernames (no `docs/technical/testing_context.md` yet).
- **Next step:** spec stays `IN QUEUE`. `feature-implement-full` will trigger `chrome-test-execute` after Stage 6 lands.
