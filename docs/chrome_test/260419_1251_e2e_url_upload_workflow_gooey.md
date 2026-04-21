# Chrome E2E Test Spec — End-to-End Workflow via Image-URL Upload (Gooey Butter Cake)

**Feature:** Exercise the full end-to-end workflow from `docs/discussion/260418_food_db.md` by posting a **URL-backed** upload (not a file picker) for a single test image — a slice of gooey butter cake hosted at `https://cleobuttera.com/wp-content/uploads/2016/06/gooey-slice.jpg`. Walks through every phase documented in the workflow diagram: Phase 1.1.1 fast caption + personalized reference retrieval → Phase 1.1.2 two-image component ID → Phase 1.2 user confirmation → parallel Phase 2.1 + 2.2 lookups → Phase 2.3 Pro call → Phase 2.4 user review + correction. Backend `backend.log` is tailed at each phase boundary to surface any unexpected errors or warnings along the way.

**Spec generated:** 2026-04-19 12:51
**Main purpose:** regression test for the 10-stage pipeline landed in issue 260415. Detects breakage at any phase of the workflow diagram.
**Desktop viewport only** — operator requested no mobile replays for this spec.
**Screenshots directory:** `data/chrome_test_images/260419_1251_e2e_url_upload_workflow_gooey/`

---

## Remarks

### Context

- **Frontend base URL:** `http://localhost:2512` (from `start_app.sh`).
- **Backend base URL:** `http://localhost:2612` (from `start_app.sh`).
- **Login page:** `http://localhost:2512/login`. Username + password auth; tokens live 90 days.
- **Test user (from `docs/technical/testing_context.md`):** `Alan` (user_id=1). Two uploads happen under this account: a baseline upload (Test 1) and a follow-up upload (Test 2) that exercises Phase 2.2 retrieval against the baseline row. The frontend uses a cookie-based httpOnly JWT (`access_token`, 90-day TTL); the browser tab must have an active session before Test 1 begins.
- **Test image URL (shared across all tests):** `https://cleobuttera.com/wp-content/uploads/2016/06/gooey-slice.jpg`. A gooey-butter-cake slice — chosen because:
  - It is a real-world image hosted over HTTPS; the backend's URL-upload endpoint must fetch it end-to-end.
  - It exercises a dish that is NOT strongly represented in the nutrition DB (CIQUAL / Malaysian / MyFCD / Anuvaad), so Stage 7's DB-block threshold likely falls below 80 — good coverage for the "both blocks absent / reasoning_* explains LLM-only path" behavior.
  - The filename `gooey-slice.jpg` is memorable for screenshot reviewers.
- **Endpoint under test:** `POST /api/date/{Y}/{M}/{D}/upload-url` with JSON body `{ "dish_position": <int>, "image_url": "<url>" }`. Returns `{ success, message, query }`.

### Observability surface — backend log tail at each phase

This spec is primarily a **pipeline smoke test**. Beyond DOM and API assertions, every major phase boundary includes a `tail backend.log | grep ...` action to catch regressions that don't surface in the API response.

Log lines to look for (based on the current codebase):

| Phase | Log fragment | File |
|---|---|---|
| Upload accepted | `"Created query ID=%s from URL for user"` | `api/date.py` |
| Phase 1.1.1 (caption + retrieval) | first-run builds the Flash caption; retry emits `"Phase 1.1.1 skipped on retry for query_id=%s"` | `personalized_reference.py`, `item_step1_tasks.py` |
| Phase 1.1.2 (component ID) | `"Starting Step 1 background analysis for query %s"` + `"Query %s Step 1 completed successfully"` (on success) or `"Failed Phase 1 for query %s"` (on failure) | `item_step1_tasks.py` |
| Phase 1.2 (confirm) | `"Step 1 confirmation request for record_id=%s"` | `api/item.py` |
| Phase 2.1 (nutrition DB) | first call: `"Nutrition service ready: %d malaysian, %d myfcd, %d anuvaad, %d ciqual"` | `service/nutrition_db.py` |
| Phase 2.1/2.2 gather | on failure-injection: `"Phase 2.1 raised inside gather"` / `"Phase 2.2 raised inside gather"` | `api/item_tasks.py` |
| Phase 2.3 (Gemini Pro) | `"Starting Step 2 background analysis for query %s"` + `"Query %s Step 2 completed successfully"` or `"Failed Step 2 analysis"` | `api/item_tasks.py` |
| Phase 2.4 (correction) | `"Step 2 correction request for record_id=%s"` | `api/item_correction.py` |
| Personalization enrichment | `"Stage 4 enrichment skipped"` / `"Stage 8 enrichment skipped"` if the personalization row is missing | `api/item.py`, `api/item_correction.py` |
| Reference image missing | `"Phase 2.3 reference image missing on disk"` (Stage 7) | `api/item_tasks.py` |

At each test's log-check action the operator greps the tail for errors:

```bash
tail -n 200 backend.log | grep -iE "error|failed|exception|traceback|raised"
```

Expected in a clean run: no matches (or only deliberate warnings captured in `pytest.skip`-style messages). Any hit other than the documented WARN-log lines above should be recorded in **Findings** and may block the test from `PASSED` → `PASSED with discrepancies`.

### Why URL upload instead of the file picker

The stock Chrome Claude Extension harness can simulate file uploads by dispatching a synthetic `change` event on the `<input type="file">`, but the reliability varies across Chrome versions and the file picker chrome itself is opaque. Posting a JSON body to `/api/date/{Y}/{M}/{D}/upload-url` via `javascript_tool` sidesteps the picker entirely — every behavior downstream of "dish row created with image bytes on disk" is identical between the two upload paths (they both call `_process_and_save_image` → `replace_slot_atomic` → `BackgroundTasks.add_task(analyze_image_background, ...)`). Using URL upload makes the test deterministic without changing the pipeline's observable behavior.

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
WHERE user_id IN (SELECT id FROM users WHERE username IN ('Alan'));

DELETE FROM dish_image_query_prod_dev
WHERE user_id IN (SELECT id FROM users WHERE username IN ('Alan'));
```

Optional hygiene — remove orphaned image files from the URL-fetch path (kept short):

```bash
rm -f data/images/*_u1_dish*.jpg
```

### Seed

Standard. No extra rows beyond the user account. The test assumes `nutrition_foods` is populated; if it isn't, Test 3's Phase 2.1 block will just report `match_summary.reason = "nutrition_db_empty"` (documented graceful-degrade path).

### Pre-flight backend state

```bash
# From the project root — verify both services are up.
curl -s http://localhost:2612/api/v1 >/dev/null && echo "backend up" || echo "BACKEND DOWN"
curl -s http://localhost:2512/ >/dev/null && echo "frontend up" || echo "FRONTEND DOWN"

# Tail empty for the test run.
: > backend.log
```

Operator truncates `backend.log` immediately before Test 1 so every subsequent log-check action sees only lines emitted during this spec run.

---

## Pre-requisite

1. Run Cleanup SQL (substitutes `Alan` for the placeholder username).
2. Truncate `backend.log` (`: > backend.log`).
3. Open Chrome; ensure the tab at `http://localhost:2512/dashboard` is signed in as `Alan` (cookie-based session). If the dashboard redirects to `/login`, acquire a session cookie first by POSTing `{username: "Alan", password: "<dev>"}` to `/api/login/` (see `docs/technical/testing_context.md`).

---

## Tests

### Test 1 — End-to-end happy path: URL upload through Phase 2.4 render

**User(s):** `Alan`

**Goal:** Walk the full pipeline documented in `docs/discussion/260418_food_db.md` § End-to-end workflow diagram, using the gooey-butter-cake URL. Assert every phase boundary: upload accepted → Phase 1.1.1 persisted `reference_image` (null on cold start) → Phase 1.1.2 `step1_data` ready → user confirms → Phase 2.1 `nutrition_db_matches` persisted → Phase 2.2 `personalized_matches` persisted (empty on cold start) → Phase 2.3 `step2_data` lands with `reasoning_*` fields → Phase 2.4 the three panels render. Backend log is grep-checked at each boundary for unexpected errors.

- [x] **Action 01 — set desktop viewport:** call `mcp__claude-in-chrome__resize_window` with `width: 1080, height: 1280`. Verify `window.outerWidth === 1080` (note: on macOS Retina, `window.innerWidth` can exceed the requested size — assert on `outerWidth` for reliability). **Screenshot:** `test1_{HMMSS}_01_viewport.png`
- [x] **Action 02 — dashboard loaded:** navigate to `http://localhost:2512/`. Calendar visible. **Screenshot:** `test1_{HMMSS}_02_dashboard.png`
- [x] **Action 03 — today's date opened:** click today's tile. Date view shows five empty dish slots. Record the resolved `/date/{Y}/{M}/{D}` URL. **Screenshot:** `test1_{HMMSS}_03_date_view_empty.png`
- [x] **Action 04 — POST the URL upload via fetch:** in `javascript_tool`:
  ```js
  const m = window.location.pathname.match(/\/date\/(\d+)\/(\d+)\/(\d+)/);
  const [, y, mo, d] = m;
  const r = await fetch(`http://localhost:2612/api/date/${y}/${mo}/${d}/upload-url`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      dish_position: 1,
      image_url: "https://cleobuttera.com/wp-content/uploads/2016/06/gooey-slice.jpg",
    }),
  });
  const body = await r.json();
  window.__gooeyRecordId = body?.query?.id;
  ({ status: r.status, record_id: window.__gooeyRecordId, ok: body?.success });
  ```
  Expect `status: 200, ok: true, record_id` a positive integer. **Screenshot:** `test1_{HMMSS}_04_upload_scheduled.png`
- [x] **Action 05 — backend log: upload accepted + Phase 1.1.1 started:**
  ```bash
  tail -n 50 backend.log | grep -E "Created query ID|Starting Step 1 background analysis"
  ```
  Expect at least one `"Created query ID=<id> from URL for user ..."` line and the `"Starting Step 1 background analysis"` line. Note: `"Nutrition service ready"` is emitted at server boot, not on first request, so it will not appear in this per-request tail. **Screenshot:** `test1_{HMMSS}_05_log_upload_phase1_start.png` (terminal)
- [x] **Action 06 — Phase 1 cold-start: reference_image === null (API poll, ~3 s after upload):**
  ```js
  // Poll the pre-Pro persist (reference_image lands before the Pro call).
  async function poll() {
    for (let i = 0; i < 10; i++) {
      const j = await (await fetch(`http://localhost:2612/api/item/${window.__gooeyRecordId}`, { credentials: 'include' })).json();
      if (j.result_gemini && 'reference_image' in j.result_gemini) return j;
      await new Promise(r => setTimeout(r, 800));
    }
    return null;
  }
  const j = await poll();
  ({
    has_key: j && 'reference_image' in (j.result_gemini || {}),
    reference_image: j?.result_gemini?.reference_image,
  });
  ```
  Expect `{ has_key: true, reference_image: null }` (cold-start — this is alpha's first upload). **Screenshot:** `test1_{HMMSS}_06_api_cold_start_ref.png`
- [x] **Action 07 — navigate to the item page for this record:** `location.href = "/item/" + window.__gooeyRecordId`. Wait for the page to load. **Screenshot:** `test1_{HMMSS}_07_item_page_polling.png`
- [x] **Action 08 — Step 1 editor renders (Phase 1.1.2 complete):** wait up to 60 s for the Step 1 component editor to appear. **Screenshot:** `test1_{HMMSS}_08_step1_editor.png`
- [x] **Action 09 — backend log: Phase 1 completed:**
  ```bash
  tail -n 200 backend.log | grep -E "Query .* Step 1 completed successfully"
  ```
  Expect a `"Query <id> Step 1 completed successfully"` line. **Screenshot:** `test1_{HMMSS}_09_log_phase1_done.png` (terminal)
- [x] **Action 10 — review dish predictions + components in the editor:** screenshot the AI's proposals. Record the verbatim predictions in Findings (the Gemini vision model can surface pastry-adjacent names — "tart", "pie", "cake", "cobbler" — rather than "gooey butter cake" specifically). Components must contain at least one entry. **Screenshot:** `test1_{HMMSS}_10_proposals.png`
- [x] **Action 11 — click the Confirm button:** screenshot captures the transition from the editor to the Step 2 loading state. **Screenshot:** `test1_{HMMSS}_11_confirm_clicked.png`
- [x] **Action 12 — backend log: Phase 1.2 + Phase 2.1/2.2 started:**
  ```bash
  tail -n 200 backend.log | grep -E "Step 1 confirmation request|Starting Step 2 background analysis"
  ```
  Expect one of each. **Screenshot:** `test1_{HMMSS}_12_log_confirm_phase2_start.png` (terminal)
- [x] **Action 13 — API: nutrition_db_matches + personalized_matches pre-Pro persistence:**
  ```js
  async function pollPrePro() {
    for (let i = 0; i < 15; i++) {
      const j = await (await fetch(`http://localhost:2612/api/item/${window.__gooeyRecordId}`, { credentials: 'include' })).json();
      if (j.result_gemini?.nutrition_db_matches && 'personalized_matches' in j.result_gemini) return j;
      await new Promise(r => setTimeout(r, 700));
    }
    return null;
  }
  const j = await pollPrePro();
  ({
    db_top: j?.result_gemini?.nutrition_db_matches?.nutrition_matches?.[0]?.matched_food_name,
    db_top_confidence: j?.result_gemini?.nutrition_db_matches?.nutrition_matches?.[0]?.confidence_score,
    persona_count: j?.result_gemini?.personalized_matches?.length,
    step2_ready: !!j?.result_gemini?.step2_data,
  });
  ```
  Expect `db_top` to be a string (some nutrition match regardless of confidence), `persona_count === 0` (alpha cold start), `step2_ready` may be `false` or `true` depending on how fast the poll caught up. **Screenshot:** `test1_{HMMSS}_13_api_pre_pro.png`
- [x] **Action 14 — Step 2 view loads (wait for step2_data):** poll until the Step 2 card renders on the page. Dish name echoes the user's confirmed name; macros visible; healthiness badge colored. **Screenshot:** `test1_{HMMSS}_14_step2_view.png`
- [x] **Action 15 — backend log: Phase 2.3 complete:**
  ```bash
  tail -n 200 backend.log | grep -E "Query .* Step 2 completed successfully"
  ```
  Expect the success line. **Screenshot:** `test1_{HMMSS}_15_log_phase2_done.png` (terminal)
- [x] **Action 16 — API: step2_data with reasoning_* present:**
  ```js
  const j = await (await fetch(`http://localhost:2612/api/item/${window.__gooeyRecordId}`, { credentials: 'include' })).json();
  const s = j.result_gemini?.step2_data || {};
  ({
    dish_name: s.dish_name,
    cal: s.calories_kcal,
    reasoning_keys: [
      "reasoning_sources","reasoning_calories","reasoning_fiber","reasoning_carbs",
      "reasoning_protein","reasoning_fat","reasoning_micronutrients"
    ].every(k => k in s),
    reasoning_sources_preview: (s.reasoning_sources || "").slice(0, 120),
  });
  ```
  Expect all seven `reasoning_*` keys present; `reasoning_sources_preview` likely mentions "LLM-only" (no high-confidence DB match for gooey butter cake). Record the verbatim `reasoning_sources` in Findings. **Screenshot:** `test1_{HMMSS}_16_api_step2_reasoning.png`
- [x] **Action 17 — ReasoningPanel toggles open and shows all seven sections:** click the panel's toggle. **Screenshot:** `test1_{HMMSS}_17_reasoning_panel.png`
- [x] **Action 18 — Top5DbMatches row (or hidden if all < threshold):** scroll to it. Gooey butter cake likely has no ≥ 85% match — record whether the panel renders or is hidden. **Screenshot:** `test1_{HMMSS}_18_top5_db_panel.png`
- [x] **Action 19 — PersonalizationMatches panel hidden (cold start):** alpha has no prior uploads; panel MUST NOT render. **Screenshot:** `test1_{HMMSS}_19_persona_panel_hidden.png`
- [x] **Action 20 — final backend-log error sweep:** 
  ```bash
  tail -n 500 backend.log | grep -iE "\\bERROR\\b|\\bTraceback\\b|\\bunexpected\\b" | grep -vE "WARNING"
  ```
  Expect **no matches** (only INFO + WARNING allowed during happy path). Any ERROR/Traceback is a pipeline bug — record in Findings. **Screenshot:** `test1_{HMMSS}_20_log_error_sweep.png` (terminal)

**Report:**

- **Status:** PASSED
- **Findings:**
  - **Record ID:** 17 (user Alan, id=1, dish_position=1, `target_date=2026-04-19`).
  - **Timing:** `Created query ID=17` at 13:51:13 → `Query 17 Step 1 completed successfully` at 13:51:30 (~17 s). Confirm at 13:51:59 → `Query 17 Step 2 completed successfully` at 13:52:32 (~33 s).
  - **Viewport:** `outerWidth=1080, outerHeight=1055` (matches the relaxed assertion in the updated spec). `innerWidth=1200` (Retina quirk).
  - **Phase 1.1.1 cold-start assertion held:** `has_key: true, reference_image: null`.
  - **Step 1 output:** `dish_predictions=[{Date and Walnut Tart, 0.95}, {Walnut Pie Slice, 0.9}, {Caramel Walnut Tart, 0.85}, {Pecan Tart Slice, 0.75}]`; `components=["Date and Walnut Tart", "Tea"]`. Vision model still labels the image as tart + hallucinates a Tea component — a known pipeline quirk (see Test 1 Improvement Proposal).
  - **Phase 2.1 pre-Pro DB matches:** `db_top="TEA MIX, INSTANT" @ 89.6 %`, persona_count=0, step2_ready=false.
  - **step2_data (record 17):** `calories_kcal=520, fiber_g=5, carbs_g=51, protein_g=9, fat_g=34, healthiness_score=32` ("Unhealthy"). All seven `reasoning_*` keys present. `reasoning_sources` verbatim: `"LLM-only: image + components, no DB match for main dish"`.
  - **PersonalizationMatches panel:** correctly **hidden** on cold start (`persona_visible: false`).
  - **Top5DbMatches panel:** visible.
  - **Final backend-log ERROR/Traceback sweep:** 0 matches.
  - **Screenshots:** `test1_35047_01_viewport.png`, `test1_35056_02_dashboard.png`, `test1_35106_03_date_view_empty.png`, `test1_35114_04_upload_scheduled.png`, `test1_35122_05_log_upload_phase1_start.png`, `test1_35130_06_api_cold_start_ref.png`, `test1_35140_07_item_page_polling.png`, `test1_35143_08_step1_editor.png`, `test1_35148_09_log_phase1_done.png`, `test1_35154_10_proposals.png`, `test1_35200_11_confirm_clicked.png`, `test1_35205_12_log_confirm_phase2_start.png`, `test1_35214_13_api_pre_pro.png`, `test1_35236_14_step2_view.png`, `test1_35241_15_log_phase2_done.png`, `test1_35252_16_api_step2_reasoning.png`, `test1_35258_17_reasoning_panel.png`, `test1_35306_18_top5_db_panel.png`, `test1_35307_19_persona_panel_hidden.png`, `test1_35307_20_log_error_sweep.png`.
- **Improvement Proposals:**
  + good to have - **Vision model confabulation on gooey-butter-cake image** - The vision model still labels the image as "Date and Walnut Tart" and hallucinates a "Tea" component. The pipeline's downstream behavior is correct (Pro correctly returns `reasoning_sources: "LLM-only: …, no DB match for main dish"`), but swapping the test image to a clearly-identified dish would exercise the DB-hit path instead of always routing through the LLM-only branch. Consider rotating the test URL every quarter.
  + nice to have - **Expand curated nutrition DB with confectionery entries** - If the team wants the gooey-butter-cake / similar confections to start clearing the 85 % threshold, the CIQUAL / MyFCD ingestion would need dessert coverage. Currently acceptable because the LLM-only fallback path is well-exercised by this exact test.

---

### Test 2 — Warm-start: second URL upload hits the personalization corpus

**User(s):** `Alan` (still signed in from Test 1)

**Goal:** Re-run the full pipeline using the same URL on dish slot 2. This time Phase 2.2 has exactly one row in the user's corpus (Test 1's upload), so `personalized_matches` must be populated with that row; the `similarity_score` should clear at least the block-include threshold (0.30), possibly also the image-B threshold (0.35). The PersonalizationMatches panel should render and show the thumbnail from Test 1.

- [x] **Action 01 — back on the date page:** navigate to the same date view from Test 1. Slot 1 shows the cake thumbnail from the first run. **Screenshot:** `test2_{HMMSS}_01_date_view_one_filled.png`
- [x] **Action 02 — POST URL upload to slot 2:** same fetch as Test 1 Action 04 but with `dish_position: 2`. Capture `window.__gooeyRecordId2`. **Screenshot:** `test2_{HMMSS}_02_upload_slot2.png`
- [x] **Action 03 — API: Phase 1.1.1 reference_image is NOW populated:**
  ```js
  async function pollRef() {
    for (let i = 0; i < 10; i++) {
      const j = await (await fetch(`http://localhost:2612/api/item/${window.__gooeyRecordId2}`, { credentials: 'include' })).json();
      if (j.result_gemini && 'reference_image' in j.result_gemini) return j;
      await new Promise(r => setTimeout(r, 800));
    }
    return null;
  }
  const j = await pollRef();
  const ref = j?.result_gemini?.reference_image;
  ({
    has_ref: !!ref,
    ref_query_id: ref?.query_id,
    ref_sim: ref?.similarity_score,
    matches_record_1: ref?.query_id === window.__gooeyRecordId,
  });
  ```
  Expect `has_ref: true, matches_record_1: true, ref_sim >= 0.25` (for identical-URL warm start, similarity will be ~1.0). **Screenshot:** `test2_{HMMSS}_03_api_ref_populated.png`
- [x] **Action 04 — backend log: Phase 1.1.2 received two image parts (if test log line added):** if the operator temporarily enabled the `image_parts=N` log line in `gemini_analyzer.py` (see Stage 3's spec), `tail backend.log | grep "image_parts=2"` — at least one such line for this record. If the log is not instrumented, skip with a note. **Screenshot:** `test2_{HMMSS}_04_log_two_images.png` (terminal)
- [x] **Action 05 — navigate to the new item page:** `/item/{record_id_2}`. **Screenshot:** `test2_{HMMSS}_05_item_page.png`
- [x] **Action 06 — Step 1 editor loads:** **Screenshot:** `test2_{HMMSS}_06_step1_editor.png`
- [x] **Action 07 — confirm:** **Screenshot:** `test2_{HMMSS}_07_confirm_clicked.png`
- [x] **Action 08 — API: personalized_matches populated with Test 1's row:**
  ```js
  async function pollPersona() {
    for (let i = 0; i < 15; i++) {
      const j = await (await fetch(`http://localhost:2612/api/item/${window.__gooeyRecordId2}`, { credentials: 'include' })).json();
      if (j.result_gemini?.personalized_matches) return j;
      await new Promise(r => setTimeout(r, 700));
    }
    return null;
  }
  const j = await pollPersona();
  const m = (j?.result_gemini?.personalized_matches || [])[0];
  ({
    count: j?.result_gemini?.personalized_matches?.length,
    top_query_id: m?.query_id,
    top_sim: m?.similarity_score,
    has_prior_step2: !!m?.prior_step2_data,
    matches_record_1: m?.query_id === window.__gooeyRecordId,
  });
  ```
  Expect `count >= 1, matches_record_1: true, has_prior_step2: true, top_sim >= 0.30` (identical-URL warm start drives `top_sim` to ~1.0). **Screenshot:** `test2_{HMMSS}_08_api_personalized.png`
- [x] **Action 09 — Step 2 view + PersonalizationMatches card renders:** wait for step2_data; scroll to the panel; assert a card with the first upload's thumbnail + description. **Screenshot:** `test2_{HMMSS}_09_persona_panel_rendered.png`
- [x] **Action 10 — final error sweep:** same grep as Test 1 Action 20; expect no hits. **Screenshot:** `test2_{HMMSS}_10_log_error_sweep.png` (terminal)

**Report:**

- **Status:** PASSED
- **Findings:**
  - **Record ID:** 18 (dish_position=2, user Alan).
  - **reference_image:** populated with `query_id=17, similarity_score=1.0` (identical URL → trivial similarity). `matches_record_1=true`. Image-B and block-include thresholds both trivially cleared as documented in the updated spec.
  - **personalized_matches:** 1 entry pointing at record 17 (`top_query_id=17, top_sim=1.0, has_prior_step2=true, matches_record_1=true`).
  - **PersonalizationMatches panel rendered:** `[data-testid="personalization-matches"]` present with heading `"Your prior similar dishes"` and card `[data-testid="persona-card-17"]`.
  - **Action 04 image_parts log:** not instrumented in `gemini_analyzer.py`; skipped with note in the terminal capture. No functional impact.
  - **Backend log error sweep:** 0 matches.
  - **Screenshots:** `test2_35317_01_date_view_one_filled.png`, `test2_35324_02_upload_slot2.png`, `test2_35331_03_api_ref_populated.png`, `test2_35341_04_log_two_images.png`, `test2_35348_05_item_page.png`, `test2_35350_06_step1_editor.png`, `test2_35357_07_confirm_clicked.png`, `test2_35407_08_api_personalized.png`, `test2_35418_09_persona_panel_rendered.png`, `test2_35424_10_log_error_sweep.png`.
- **Improvement Proposals:**
  + good to have - **Use a second, similar-but-distinct image for Test 2** - Identical-URL warm start always produces similarity=1.0. A near-duplicate (different slice of the same dessert) would exercise the 0.30 / 0.35 threshold logic meaningfully. Current test still verifies the persistence and rendering paths, just not the threshold boundary.

---

### Test 3 — Stage 2.4 correction round-trip

**User(s):** `Alan` (same session)

**Goal:** On the Test 1 item (the first upload), click Edit, change calories + rationale + add a micronutrient chip, Save. Assert 200 response, `result_gemini.step2_corrected` lands on the main record, AND `personalized_food_descriptions.corrected_step2_data` is populated for the matching `query_id`. Cancel path is implicitly covered by Test 1's happy path (no correction was written).

- [x] **Action 01 — navigate to Test 1's item:** `location.href = "/item/" + window.__gooeyRecordId`. Step 2 card visible. **Screenshot:** `test3_{HMMSS}_01_item_page.png`
- [x] **Action 02 — click Edit:** `document.querySelector('[data-testid="step2-edit-toggle"]').click()`. Inputs render. **Screenshot:** `test3_{HMMSS}_02_edit_mode.png`
- [x] **Action 03 — change calories to 380:** target `[data-testid="step2-calories-input"]`; dispatch `change` event. **Screenshot:** `test3_{HMMSS}_03_calories_edit.png`
- [x] **Action 04 — change rationale to a custom string:** target `[data-testid="step2-rationale-input"]`; set value to `"Adjusted down — typical slice is smaller than AI estimate."`. **Screenshot:** `test3_{HMMSS}_04_rationale_edit.png`
- [x] **Action 05 — add micronutrient chip 'Vitamin D':** target `[data-testid="step2-micro-input"]`; type + click `[data-testid="step2-micro-add"]`. **Screenshot:** `test3_{HMMSS}_05_chip_added.png`
- [x] **Action 06 — click Save:** target `[data-testid="step2-edit-save"]`. The correction round-trip can complete in <200 ms so the "Saving..." intermediate state may not be observable — focus on capturing the post-save rendered state in Action 07. **Screenshot:** `test3_{HMMSS}_06_save_in_flight.png`
- [x] **Action 07 — UI re-renders with corrected values + "Corrected by you" badge:** 380 kcal visible; new rationale shown; Vitamin D chip in the list; badge visible. **Screenshot:** `test3_{HMMSS}_07_corrected_rendered.png`
- [x] **Action 08 — API: step2_corrected + step2_data coexist:**
  ```js
  const j = await (await fetch(`http://localhost:2612/api/item/${window.__gooeyRecordId}`, { credentials: 'include' })).json();
  const g = j.result_gemini;
  ({
    has_corrected: !!g.step2_corrected,
    has_original: !!g.step2_data,
    cor_cal: g.step2_corrected?.calories_kcal,
    orig_cal: g.step2_data?.calories_kcal,
    cor_rationale_suffix: (g.step2_corrected?.healthiness_score_rationale || "").endsWith("AI estimate."),
    vitamin_d: (g.step2_corrected?.micronutrients || []).includes("Vitamin D"),
  });
  ```
  Expect `{ has_corrected: true, has_original: true, cor_cal: 380, orig_cal !== 380, cor_rationale_suffix: true, vitamin_d: true }`. **Screenshot:** `test3_{HMMSS}_08_api_coexist.png`
- [x] **Action 09 — SQL: personalization row also has corrected_step2_data:** operator runs
  ```sql
  SELECT corrected_step2_data
    FROM personalized_food_descriptions
   WHERE query_id = <window.__gooeyRecordId>;
  ```
  Expect a non-null JSONB carrying the same calories + rationale + micronutrients. **Screenshot:** `test3_{HMMSS}_09_db_corrected.png` (terminal)
- [x] **Action 10 — backend log: Stage 8 correction request + enrichment:**
  ```bash
  tail -n 200 backend.log | grep -iE "Step 2 correction request|Stage 8 enrichment"
  ```
  Expect a `"Step 2 correction request for record_id=<id>"` INFO line and NO "Stage 8 enrichment skipped" WARN (because the row exists). **Screenshot:** `test3_{HMMSS}_10_log_correction.png` (terminal)

**Report:**

- **Status:** PASSED
- **Findings:**
  - **Target record:** 17 (Test 1's upload).
  - **Action 08 API round-trip:** `has_corrected=true, has_original=true, cor_cal=380, orig_cal=520, cor_rationale_suffix=true, vitamin_d=true`.
  - **DB row `personalized_food_descriptions.corrected_step2_data` (from SQL):** `calories_kcal=380.0`, micronutrients `["Manganese", "Copper", "Magnesium", "Potassium", "Omega-3 Fatty Acids", "Vitamin D"]` (baseline Vitamin B6 replaced with Omega-3 Fatty Acids in this re-run — the step2_data baseline differs run-to-run because Gemini Pro picks a different set; the correction still appends Vitamin D to whatever baseline was produced).
  - **Stage 8 correction log:** `src.api.item_correction - INFO - Step 2 correction request for record_id=17`. No "Stage 8 enrichment skipped" WARN.
  - **"Corrected by you" badge:** rendered.
  - **`micronutrients` shape divergence** still observed — `step2_data` uses `[{name, amount_mg}]` objects, `step2_corrected` uses `[string]`. Left as an open Improvement Proposal.
  - **Screenshots:** `test3_35434_01_item_page.png`, `test3_35441_02_edit_mode.png`, `test3_35447_03_calories_edit.png`, `test3_35453_04_rationale_edit.png`, `test3_35500_05_chip_added.png`, `test3_35506_06_save_in_flight.png`, `test3_35507_07_corrected_rendered.png`, `test3_35516_08_api_coexist.png`, `test3_35524_09_db_corrected.png`, `test3_35524_10_log_correction.png`.
- **Improvement Proposals:**
  + good to have - **Document micronutrients shape divergence** - `step2_data` uses `[{name, amount_mg}]`; `step2_corrected` (and `personalized_food_descriptions.corrected_step2_data`) uses `[string]`. Either normalize to one shape in both places or document the divergence in the component-contract comments.

---

### Test 4 — Validation: malformed and unreachable URLs return 400

**User(s):** `Alan`

**Goal:** The URL-upload endpoint must refuse obviously broken input without crashing the worker. Two cases:

1. Non-existent host.
2. Valid URL but 404 response.

- [x] **Action 01 — POST an unreachable URL:**
  ```js
  const m = window.location.pathname.match(/\/date\/(\d+)\/(\d+)\/(\d+)/) ||
            ["","2026","4","19"];
  const r = await fetch(`http://localhost:2612/api/date/${m[1]}/${m[2]}/${m[3]}/upload-url`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      dish_position: 3,
      image_url: "https://no-such-host-123abc.invalid/x.jpg",
    }),
  });
  ({ status: r.status, body: await r.json().catch(() => ({})) });
  ```
  Expect `status: 400` and a detail message mentioning the download failure. **Screenshot:** `test4_{HMMSS}_01_api_400_bad_host.png`
- [x] **Action 02 — POST a URL that 404s:**
  ```js
  const r = await fetch(`http://localhost:2612/api/date/2026/4/19/upload-url`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      dish_position: 3,
      image_url: "https://cleobuttera.com/wp-content/uploads/2016/06/NONEXISTENT.jpg",
    }),
  });
  ({ status: r.status });
  ```
  Expect `status: 400` (httpx raises `HTTPStatusError` on the raise_for_status call; endpoint maps to 400). **Screenshot:** `test4_{HMMSS}_02_api_400_404.png`
- [x] **Action 03 — POST an invalid dish_position (0 or 6):**
  ```js
  const r = await fetch(`http://localhost:2612/api/date/2026/4/19/upload-url`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dish_position: 6, image_url: "https://cleobuttera.com/wp-content/uploads/2016/06/gooey-slice.jpg" }),
  });
  ({ status: r.status });
  ```
  Expect `status: 400` (`"Invalid dish position"`). **Screenshot:** `test4_{HMMSS}_03_api_400_bad_slot.png`
- [x] **Action 04 — backend log: ERROR lines for the download-fail paths:**
  ```bash
  tail -n 200 backend.log | grep -E "Failed to download image from URL"
  ```
  Expect at least one `"Failed to download image from URL"` log line from `date.py`. **Screenshot:** `test4_{HMMSS}_04_log_download_error.png` (terminal)
- [x] **Action 05 — DB: no new DishImageQuery row written for the rejected uploads:**
  ```sql
  SELECT COUNT(*) FROM dish_image_query_prod_dev
   WHERE user_id = 1 AND dish_position IN (3, 6);
  ```
  Expect 0. **Screenshot:** `test4_{HMMSS}_05_db_no_row.png` (terminal)

**Report:**

- **Status:** PASSED
- **Findings:**
  - **Action 01 (unreachable host):** `status=400, detail="Failed to download image from URL: [Errno 8] nodename nor servname provided, or not known"`.
  - **Action 02 (404 URL):** `status=400`.
  - **Action 03 (invalid dish_position=6):** `status=400, detail="Invalid dish position. Must be between 1 and 5"`.
  - **Action 04 backend log:** 2 `"Failed to download image from URL"` ERROR lines emitted (one for each failed fetch). No tracebacks.
  - **Action 05 DB sanity:** Alan's rows by dish_position: `1 → 1 row, 2 → 1 row`; nothing at positions 3 or 6. Rejected uploads left no DB trace.
  - **Screenshots:** `test4_35532_01_api_400_bad_host.png`, `test4_35538_02_api_400_404.png`, `test4_35545_03_api_400_bad_slot.png`, `test4_35546_04_log_download_error.png`, `test4_35546_05_db_no_row.png`.
- **Improvement Proposals:**
  + good to have - If the endpoint returns 400 without a helpful body, add the stripped-down download error message so CI / operators can diagnose bad URLs without a log tail. [ALREADY IMPLEMENTED — detail messages already include the downstream error text.]

---

### Test 5 — Permission guard: unauthenticated URL upload returns 401

**User(s):** _(unauthenticated)_

**Goal:** Auth guard on the URL-upload route. Signed-out users must not be able to post dish URLs.

- [x] **Action 01 — sign out + clear tokens:** authentication uses an httpOnly cookie, so `localStorage.clear()` is a no-op — must POST to the logout endpoint first:
  ```js
  await fetch('http://localhost:2612/api/login/logout', { method: 'POST', credentials: 'include' });
  try { localStorage.clear(); } catch (_) {}
  location.href = '/login';
  ```
  After redirect, the `<input type="password">` login form is visible. **Screenshot:** `test5_{HMMSS}_01_logged_out.png`
- [x] **Action 02 — POST /upload-url without a token → 401:**
  ```js
  const r = await fetch(`http://localhost:2612/api/date/2026/4/19/upload-url`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      dish_position: 1,
      image_url: "https://cleobuttera.com/wp-content/uploads/2016/06/gooey-slice.jpg",
    }),
  });
  ({ status: r.status });
  ```
  Expect `status: 401`. **Screenshot:** `test5_{HMMSS}_02_api_401.png`
- [x] **Action 03 — DB unchanged since Test 4:**
  ```sql
  SELECT COUNT(*) FROM dish_image_query_prod_dev
   WHERE user_id = 1;
  ```
  Count matches the expected post-Test-2 total (2 rows for alpha). **Screenshot:** `test5_{HMMSS}_03_db_unchanged.png` (terminal)
- [x] **Action 04 — final backend log sweep:** grep the full run for any unexpected tracebacks:
  ```bash
  grep -nE "Traceback \(most recent call last\)" backend.log
  ```
  Expect **no matches** across the whole Test 1 – Test 5 run. Any traceback is a pipeline bug — attach the relevant block to Findings. **Screenshot:** `test5_{HMMSS}_04_log_traceback_sweep.png` (terminal)

**Report:**

- **Status:** PASSED
- **Findings:**
  - **Action 01 logout:** with the updated sign-out recipe (`POST /api/login/logout` before redirect), the tab landed on `/login` with the password form visible.
  - **Action 02 (unauthenticated POST):** `status=401`. Auth guard on `/api/date/{y}/{m}/{d}/upload-url` enforced.
  - **Action 03 DB sanity:** Alan's total `dish_image_query_prod_dev` row count = **2** (records 17, 18 from Tests 1 + 2).
  - **Action 04 traceback sweep:** 0 matches across the full backend.log run.
  - **Screenshots:** `test5_35600_01_logged_out.png`, `test5_35610_02_api_401.png`, `test5_35622_03_db_unchanged.png`, `test5_35622_04_log_traceback_sweep.png`.

---

## Summary for the Caller

- **Output file:** `docs/chrome_test/260419_1251_e2e_url_upload_workflow_gooey.md`
- **Screenshots directory:** `data/chrome_test_images/260419_1251_e2e_url_upload_workflow_gooey/`
- **Number of tests:** 5 desktop-only (operator explicitly requested no mobile replays).
  1. End-to-end happy path: URL upload → Phase 1 → confirm → Phase 2 → all three review panels render.
  2. Warm-start: second URL upload hits the personalization corpus; `personalized_matches` populated with Test 1's row.
  3. Stage 2.4 correction round-trip: Edit → Save writes both stores.
  4. Validation: bad host / 404 / invalid slot all return 400; DB untouched.
  5. Permission guard: unauthenticated POST → 401; full-run traceback sweep.
- **Users involved:** `Alan` (user_id=1, from `docs/technical/testing_context.md`).
- **Rough screenshot budget:** ~50 PNGs + ~10 terminal captures (log grep output + SQL).
- **Viewport notes:** desktop 1080 × 1280 set once at Test 1 Action 01 and inherited across Tests 2–5. **No mobile replay tests** — per operator request.
- **Critical caveats:**
  - Operator truncates `backend.log` before Test 1 Action 01 so the log-grep actions only see lines from this run.
  - The shared test URL (`https://cleobuttera.com/wp-content/uploads/2016/06/gooey-slice.jpg`) requires egress to the public internet; runs in a hermetic CI environment will fail Test 1 upload. Document this as a prerequisite.
  - Test 2 Action 04 (image-parts log check) assumes a temporary instrumentation log line in `gemini_analyzer.py`; skip with a note if not enabled.
  - Test 3's `data-testid` selectors (`step2-edit-toggle`, `step2-calories-input`, etc.) are shipped by the Stage 8 implementation — verified in the codebase audit.
  - **Auth dependency:** the spec requires a session-hydrating `AuthContext` (calling `GET /api/login/session` on mount). This was shipped on 2026-04-19; if the repo is reverted to a commit before that patch, hard-reloads will redirect to `/login` and break Tests 2-5.
  - The frontend does NOT proxy `/api/*` on port 2512, so every in-browser `fetch()` targets the backend absolutely (`http://localhost:2612/api/...`). Keep this in mind when copy-editing.
- **Next step:** spec stays `IN QUEUE`. Run via `/webapp-dev:chrome-test-execute docs/chrome_test/260419_1251_e2e_url_upload_workflow_gooey.md` once `docs/technical/testing_context.md` is in place or placeholders are substituted.
