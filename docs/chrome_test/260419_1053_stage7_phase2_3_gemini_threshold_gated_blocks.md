# Chrome E2E Test Spec — Stage 7: Phase 2.3 (Gemini Analysis with Threshold-Gated Reference Blocks)

**Feature:** The Step 2 Gemini 2.5 Pro call now conditionally consumes `result_gemini.nutrition_db_matches` (Stage 5) and `result_gemini.personalized_matches` (Stage 6) via two threshold-gated prompt blocks. Placeholder tokens `__NUTRITION_DB_BLOCK__` and `__PERSONALIZED_BLOCK__` in `step2_nutritional_analysis.md` are substituted when gates pass, stripped otherwise. The top-1 personalization match's image is optionally attached as a second image part when its similarity ≥ 0.35. The Step 2 output schema gains seven new flat `reasoning_*` fields (sources, calories, fiber, carbs, protein, fat, micronutrients) so the AI cites which source drove each number. Backend-only.

**Spec generated:** 2026-04-19 10:53
**Plan target:** `docs/plan/260419_stage7_phase2_3_gemini_threshold_gated_blocks.md`
**Screenshots directory:** `data/chrome_test_images/260419_1053_stage7_phase2_3_gemini_threshold_gated_blocks/`

---

## Remarks

### Context

- **Frontend base URL:** `http://localhost:2512` (from `start_app.sh`).
- **Backend base URL:** `http://localhost:2612` (from `start_app.sh`).
- **Login page:** `http://localhost:2512/login`.
- **Test users:** placeholders (no `docs/technical/testing_context.md`):
  - `TEST_USER_ALPHA`
  - `TEST_USER_BETA`
- **Thresholds** (from `configs.py` / plan):
  - `THRESHOLD_DB_INCLUDE = 80` (vs `confidence_score`, 0-100 scale).
  - `THRESHOLD_PERSONALIZATION_INCLUDE = 0.30` (vs `similarity_score`, 0-1 scale).
  - `THRESHOLD_PHASE_2_2_IMAGE = 0.35` (vs `similarity_score`, 0-1 scale).
- **Cleanup between runs:** standard personalization + dish-query delete for both users; `nutrition_foods` untouched.

### Observability surface

Stage 7 changes the *outbound* Gemini prompt and the *inbound* schema. Both sides need visibility:

1. **Outbound prompt** — operator temporarily adds a log line in `gemini_analyzer.py` immediately before `client.models.generate_content(...)` to dump the prompt (truncated to 1000 chars), `image_parts=N`, and whether the two placeholders are present (`__NUTRITION_DB_BLOCK__` / `__PERSONALIZED_BLOCK__`) or have been substituted. Revert before committing.
2. **Inbound schema** — the Chrome spec fetches `GET /api/item/{id}` and asserts the seven `reasoning_*` fields are present (and populated on the warm-DB / warm-personalization paths).
3. **Image part count** — same backend log technique as Stage 3 (`image_parts=N`). Two image parts when `personalized_matches[0].similarity_score ≥ 0.35`; one image part otherwise.

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

`nutrition_foods` remains seeded.

### Test image assets

- `chicken_rice_1.jpg`, `chicken_rice_2.jpg` — two similar chicken-rice plates (high DB confidence, high personalization similarity on the second upload).
- `obscure_dish.jpg` — a dish with no good DB match (low confidence).

### Backend logging aid (Tests 1–3 + 7)

Operator adds in `gemini_analyzer.py::analyze_step2_nutritional_analysis_async` right before `client.models.generate_content(...)`:

```python
prompt_preview = analysis_prompt[:800].replace("\n", " ")
n_images = sum(1 for c in contents if hasattr(c, "inline_data"))
logger.info(
    "Step 2 request: image_parts=%d db_block=%s persona_block=%s prompt_preview=%s",
    n_images,
    "__NUTRITION_DB_BLOCK__" not in analysis_prompt and "Nutrition Database Matches" in analysis_prompt,
    "__PERSONALIZED_BLOCK__" not in analysis_prompt and "Personalization Matches" in analysis_prompt,
    prompt_preview,
)
```

Revert before the test run commits.

---

## Pre-requisite

Cleanup SQL, `localStorage.clear()`, and confirm `nutrition_foods` has been seeded.

---

## Tests

### Test 1 — High-confidence DB match: DB block injected, reasoning_* cites the DB source (desktop, 1080 × 1280)

**User(s):** `test_user_alpha`

**Goal:** Confirm a dish whose DB lookup yields a top match with `confidence_score ≥ 80`. Prompt must carry the Nutrition Database Matches block; `step2_data.reasoning_sources` / `reasoning_calories` should cite the DB source. Image count stays 1 (cold-start user — no personalization match).

- [ ] **Action 01 — set desktop viewport:** `resize_window` 1080 × 1280. **Screenshot:** `test1_{HMMSS}_01_viewport.png`
- [ ] **Action 02 — sign in as alpha:** **Screenshot:** `test1_{HMMSS}_02_dashboard.png`
- [ ] **Action 03 — upload chicken_rice_1.jpg:** **Screenshot:** `test1_{HMMSS}_03_upload.png`
- [ ] **Action 04 — Confirm:** **Screenshot:** `test1_{HMMSS}_04_confirm.png`
- [ ] **Action 05 — API: step2_data with new reasoning_* fields:**
  ```js
  const j = await (await fetch(`/api/item/${window.location.pathname.split('/').pop()}`, { credentials: 'include' })).json();
  const s = j.result_gemini?.step2_data || {};
  const db = j.result_gemini?.nutrition_db_matches?.nutrition_matches || [];
  ({
    has_reasoning_keys: ["reasoning_sources","reasoning_calories","reasoning_fiber","reasoning_carbs","reasoning_protein","reasoning_fat","reasoning_micronutrients"].every(k => k in s),
    top_conf: db[0]?.confidence_score,
    reasoning_sources: s.reasoning_sources,
    reasoning_calories: s.reasoning_calories,
    cal: s.calories_kcal,
  });
  ```
  Expect `has_reasoning_keys: true, top_conf >= 80, reasoning_sources` non-empty and mentioning the DB source name (e.g. "malaysian_food_calories" or "Chicken Rice" dish from DB). **Screenshot:** `test1_{HMMSS}_05_api_reasoning.png`
- [ ] **Action 06 — backend.log: db_block=True, persona_block=False, image_parts=1:** `tail backend.log | grep "Step 2 request"`. **Screenshot:** `test1_{HMMSS}_06_log_db_block.png` (terminal)
- [ ] **Action 07 — Step 2 view renders normally:** UI regression guard. **Screenshot:** `test1_{HMMSS}_07_step2_view.png`

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time — record `cal` + `reasoning_sources` verbatim for audit)_
- **Improvement Proposals:**
  + good to have - Stage 8's ReasoningPanel should accept empty strings gracefully; flag any reasoning_* that comes back null/None instead of ""/string.

---

### Test 2 — Low-confidence DB match: DB block stripped; reasoning_* reflects LLM-only path (desktop)

**User(s):** `test_user_alpha`

**Goal:** Confirm an obscure dish whose DB matches all score below `confidence_score=80`. Prompt's `__NUTRITION_DB_BLOCK__` placeholder is stripped (no stray "Nutrition Database Matches" heading). `step2_data.reasoning_sources` mentions "LLM-only" or similar (no DB citation).

- [ ] **Action 01 — upload obscure_dish.jpg:** **Screenshot:** `test2_{HMMSS}_01_upload.png`
- [ ] **Action 02 — (optional) override dish name to a contrived string in Step 1 editor:** e.g. `"Fusion Mystery Platter"`. **Screenshot:** `test2_{HMMSS}_02_editor.png`
- [ ] **Action 03 — Confirm:** **Screenshot:** `test2_{HMMSS}_03_confirm.png`
- [ ] **Action 04 — API: top DB confidence_score < 80, reasoning_sources does not cite DB:**
  ```js
  const j = await (await fetch(`/api/item/${...}`, { credentials: 'include' })).json();
  const db = j.result_gemini?.nutrition_db_matches?.nutrition_matches || [];
  const s = j.result_gemini?.step2_data || {};
  ({
    top_conf: db[0]?.confidence_score,
    reasoning_sources: s.reasoning_sources,
    reasoning_calories: s.reasoning_calories,
  });
  ```
  Expect `top_conf < 80` (or matches empty). `reasoning_sources` should not mention malaysian_food_calories / myfcd / anuvaad / ciqual. **Screenshot:** `test2_{HMMSS}_04_api_llm_only.png`
- [ ] **Action 05 — backend.log: db_block=False, persona_block=False:** **Screenshot:** `test2_{HMMSS}_05_log_no_blocks.png` (terminal)

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time)_
- **Improvement Proposals:**
  + good to have - Consider a lightweight "LLM only (no DB match above threshold)" hint in reasoning_sources when the block is stripped, so users reading Stage 8's panel can tell when the DB was consulted but ignored.

---

### Test 3 — Warm personalization ≥ 0.35: personalization block + image B attached (desktop)

**User(s):** `test_user_alpha`

**Goal:** Second chicken-rice upload by alpha with Test 1's dish already in history. Top personalization match should have `similarity_score ≥ 0.35`. Prompt includes the Personalization Matches block AND image B is attached (image_parts=2). Reasoning cites the user's prior dish.

- [ ] **Action 01 — wait for Test 1's step2_data to land:** verify via API. **Screenshot:** `test3_{HMMSS}_01_prior_ready.png`
- [ ] **Action 02 — upload chicken_rice_2.jpg on slot 2:** **Screenshot:** `test3_{HMMSS}_02_upload.png`
- [ ] **Action 03 — Confirm:** **Screenshot:** `test3_{HMMSS}_03_confirm.png`
- [ ] **Action 04 — API: personalized_matches populated with similarity ≥ 0.35:**
  ```js
  const j = await (await fetch(`/api/item/${...}`, { credentials: 'include' })).json();
  const p = j.result_gemini?.personalized_matches || [];
  const s = j.result_gemini?.step2_data || {};
  ({
    top_sim: p[0]?.similarity_score,
    top_ref_query_id: p[0]?.query_id,
    reasoning_sources: s.reasoning_sources,
    reasoning_calories: s.reasoning_calories,
  });
  ```
  Expect `top_sim >= 0.35`. `reasoning_sources` should reference "prior dish" / "previous upload" / similar wording. **Screenshot:** `test3_{HMMSS}_04_api_warm.png`
- [ ] **Action 05 — backend.log: persona_block=True AND image_parts=2:** **Screenshot:** `test3_{HMMSS}_05_log_image_b.png` (terminal)

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time; record reasoning_sources verbatim)_
- **Improvement Proposals:**
  + must have - Add a boolean `image_b_attached` on `result_gemini.step2_data.debug` (dev-only) so future debugging does not require log tailing.

---

### Test 4 — Block included (0.30) but image below 0.35: block + single image (desktop)

**User(s):** `test_user_alpha`

**Goal:** Exercise the gap between `THRESHOLD_PERSONALIZATION_INCLUDE = 0.30` and `THRESHOLD_PHASE_2_2_IMAGE = 0.35`. A match in `[0.30, 0.35)` must include the text block BUT NOT image B. Single-image request; block substituted; reasoning cites the user's history.

**Setup is hard:** max-in-batch normalization makes the top hit always = 1.0. To force a `similarity_score` in `[0.30, 0.35)`, the operator would need multiple prior rows where the top hit lands just above 0.30 but below 0.35 post-normalization. In practice this requires seeding a crafted corpus — document as a "manual-setup test" and allow skipping if the operator cannot stage the corpus.

- [ ] **Action 01 — manually seed a corpus that yields top_similarity in [0.30, 0.35):** SQL to insert a few `personalized_food_descriptions` rows plus their referenced `dish_image_query_prod_dev` rows such that a new upload against "chicken rice" returns a top-1 with `similarity_score` in this band. Alternative: operator can temporarily raise `THRESHOLD_PHASE_2_2_IMAGE` to 0.99 to force the below-image-threshold branch for any warm-start match. **Screenshot:** `test4_{HMMSS}_01_setup.png` (terminal)
- [ ] **Action 02 — upload similar dish on new slot:** **Screenshot:** `test4_{HMMSS}_02_upload.png`
- [ ] **Action 03 — Confirm:** **Screenshot:** `test4_{HMMSS}_03_confirm.png`
- [ ] **Action 04 — API: top similarity in the gap; reasoning still cites user history:** **Screenshot:** `test4_{HMMSS}_04_api_gap.png`
- [ ] **Action 05 — backend.log: persona_block=True AND image_parts=1:** **Screenshot:** `test5_{HMMSS}_05_log_block_no_image.png` (terminal)

**Report:**

- **Status:** IN QUEUE (manual setup required; may be skipped with note if the operator cannot stage the corpus)
- **Findings:** _(populated at execution time)_
- **Improvement Proposals:**
  + good to have - Add a backend unit test that exercises this band with a patched `search_for_user` so the block-vs-image gating invariant is locked at the pytest layer; Chrome is best-effort.

---

### Test 5 — Both blocks absent; reasoning_* explains LLM-only path (desktop)

**User(s):** `test_user_beta`

**Goal:** Cold-start user on an obscure dish. No DB match above 80, no personalization match. Both placeholders stripped. `reasoning_*` fields describe an LLM-only path.

- [ ] **Action 01 — sign out alpha, sign in beta (cold-start for beta):** **Screenshot:** `test5_{HMMSS}_01_beta_dashboard.png`
- [ ] **Action 02 — upload obscure_dish.jpg:** **Screenshot:** `test5_{HMMSS}_02_upload.png`
- [ ] **Action 03 — Confirm:** **Screenshot:** `test5_{HMMSS}_03_confirm.png`
- [ ] **Action 04 — API: both blocks absent; all reasoning_* populated:**
  ```js
  const j = await (await fetch(`/api/item/${...}`, { credentials: 'include' })).json();
  const s = j.result_gemini?.step2_data || {};
  ({
    n_persona: (j.result_gemini?.personalized_matches || []).length,
    top_conf: (j.result_gemini?.nutrition_db_matches?.nutrition_matches || [])[0]?.confidence_score,
    reasoning_filled: {
      sources: !!s.reasoning_sources,
      calories: !!s.reasoning_calories,
      fiber: !!s.reasoning_fiber,
      carbs: !!s.reasoning_carbs,
      protein: !!s.reasoning_protein,
      fat: !!s.reasoning_fat,
      micronutrients: !!s.reasoning_micronutrients,
    },
  });
  ```
  Expect `n_persona === 0` (beta is cold-start). `top_conf < 80` (or matches empty). All `reasoning_*` at least non-empty strings — they describe the LLM-only path. **Screenshot:** `test5_{HMMSS}_04_api_llm_only.png`
- [ ] **Action 05 — backend.log: db_block=False, persona_block=False, image_parts=1:** **Screenshot:** `test5_{HMMSS}_05_log_no_blocks.png` (terminal)

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time)_
- **Improvement Proposals:** _(empty baseline)_

---

### Test 6 — Mobile: high-confidence DB match (mirrors Test 1)

**User(s):** `test_user_alpha`

**Goal:** Replay Test 1 at mobile viewport.

- [ ] **Action 01 — set mobile viewport:** `resize_window` 375 × 1080. **Screenshot:** `test6_{HMMSS}_01_viewport.png`
- [ ] **Action 02 — upload chicken_rice_1.jpg (alpha mobile):** **Screenshot:** `test6_{HMMSS}_02_upload.png`
- [ ] **Action 03 — Confirm:** **Screenshot:** `test6_{HMMSS}_03_confirm.png`
- [ ] **Action 04 — API: reasoning_* keys present; db_block substituted:** **Screenshot:** `test6_{HMMSS}_04_api_reasoning.png`
- [ ] **Action 05 — backend.log: db_block=True:** **Screenshot:** `test6_{HMMSS}_05_log.png` (terminal)
- [ ] **Action 06 — overflow + tap-target on Step 2 view:** **Screenshot:** `test6_{HMMSS}_06_mobile_assertions.png`

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time)_
- **Improvement Proposals:** _(empty baseline)_

---

### Test 7 — Mobile: warm personalization with image B (mirrors Test 3)

**User(s):** `test_user_alpha`

**Goal:** Second upload — image B attached, persona block injected, at mobile viewport.

- [ ] **Action 01 — upload chicken_rice_2.jpg at mobile:** **Screenshot:** `test7_{HMMSS}_01_upload.png`
- [ ] **Action 02 — Confirm:** **Screenshot:** `test7_{HMMSS}_02_confirm.png`
- [ ] **Action 03 — API: reasoning cites user's prior:** **Screenshot:** `test7_{HMMSS}_03_api.png`
- [ ] **Action 04 — backend.log: persona_block=True, image_parts=2:** **Screenshot:** `test7_{HMMSS}_04_log.png` (terminal)
- [ ] **Action 05 — readability + scroll-reachability on Step 2:** **Screenshot:** `test7_{HMMSS}_05_mobile_assertions.png`

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time)_
- **Improvement Proposals:** _(empty baseline)_

---

### Test 8 — Mobile: block + single image gap band (mirrors Test 4)

**User(s):** `test_user_alpha`

**Goal:** Same gap-band exercise on mobile. Same manual-setup caveat as Test 4; may be skipped with note.

- [ ] **Action 01 — (reuse Test 4 setup / threshold override):** **Screenshot:** `test8_{HMMSS}_01_setup.png` (terminal)
- [ ] **Action 02 — upload + confirm:** **Screenshot:** `test8_{HMMSS}_02_confirm.png`
- [ ] **Action 03 — API: block present, image_parts=1:** **Screenshot:** `test8_{HMMSS}_03_api.png`
- [ ] **Action 04 — backend.log check + overflow on Step 2:** **Screenshot:** `test8_{HMMSS}_04_log_mobile.png`

**Report:**

- **Status:** IN QUEUE (may be skipped — same as Test 4)
- **Findings:** _(populated at execution time)_
- **Improvement Proposals:** _(empty baseline)_

---

### Test 9 — Mobile: both blocks absent (mirrors Test 5)

**User(s):** `test_user_beta`

**Goal:** Cold-start + obscure dish on mobile. Both placeholders stripped; `reasoning_*` all populated with LLM-only rationale.

- [ ] **Action 01 — sign in beta on mobile:** **Screenshot:** `test9_{HMMSS}_01_beta.png`
- [ ] **Action 02 — upload obscure_dish.jpg:** **Screenshot:** `test9_{HMMSS}_02_upload.png`
- [ ] **Action 03 — Confirm + API check:** **Screenshot:** `test9_{HMMSS}_03_api.png`
- [ ] **Action 04 — readability on reasoning_* text (it will surface in Stage 8's panel):** body text ≥ 12 px. **Screenshot:** `test9_{HMMSS}_04_readability.png`

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time)_
- **Improvement Proposals:** _(empty baseline)_

---

### Test 10 — Mobile permission guard

**User(s):** _(unauthenticated)_

**Goal:** Unauthenticated confirm returns 401; no Phase 2.3 prompt leak via error body.

- [ ] **Action 01 — sign out, clear tokens:** **Screenshot:** `test10_{HMMSS}_01_logged_out.png`
- [ ] **Action 02 — POST /confirm-step1 without token → 401:** **Screenshot:** `test10_{HMMSS}_02_api_401.png`
- [ ] **Action 03 — GET /api/item/{any_id} without token → 401; no step2_data / reasoning_* leaked:** **Screenshot:** `test10_{HMMSS}_03_get_401.png`

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time)_
- **Improvement Proposals:** _(empty baseline)_

---

## Summary for the Caller

- **Output file:** `docs/chrome_test/260419_1053_stage7_phase2_3_gemini_threshold_gated_blocks.md`
- **Screenshots directory:** `data/chrome_test_images/260419_1053_stage7_phase2_3_gemini_threshold_gated_blocks/`
- **Number of tests:** 10 total — 5 desktop + 5 mobile.
- **Users involved:** placeholders `test_user_alpha`, `test_user_beta` (replace with seeded usernames).
- **Rough screenshot budget:** ~55 PNGs + several terminal captures.
- **Viewport notes:** Test 1 Action 01 sets 1080 × 1280; Test 6 Action 01 sets 375 × 1080.
- **Critical caveats:**
  - Temporary backend log line required in `gemini_analyzer.py` to assert block / image-part presence (see Remarks).
  - **Tests 4 and 8** require a crafted personalization corpus to land `similarity_score` in `[0.30, 0.35)`. Operator either stages the corpus or temporarily raises `THRESHOLD_PHASE_2_2_IMAGE` to 0.99. Mark as optional / skip with note if unstageable.
  - Runtime cost: each Stage 7 test exercises a real Gemini 2.5 Pro call (~5–10 s). 10 tests = 50–100 s of Gemini wall-clock + the OpenAI / Anthropic pricing tick for each call.
  - Placeholder usernames (no `docs/technical/testing_context.md`).
- **Next step:** spec stays `IN QUEUE`. `feature-implement-full` will invoke `chrome-test-execute` after Stage 7 lands.
