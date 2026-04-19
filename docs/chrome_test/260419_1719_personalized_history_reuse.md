# Chrome E2E Test Spec — Personalized History Reuse (Ayam Goreng 7-portions propagation)

**Feature:** Verify that the LLM pipeline **consumes the user's manual Phase 1.2 + Phase 2.4 edits** on a prior upload when a similar new upload arrives. Specifically, after record 34 was confirmed with `confirmed_dish_name = "Ayam Goreng (family style, 7 portions)"` and `confirmed_portions = 7`, a fresh Ayam Goreng upload should:

1. **Phase 1.1.1(b)** — retrieve record 34 as the top personalization hit.
2. **Phase 1.1.2** — run with record 34's image as image B and its `prior_step1_data` (including the user-verified `confirmed_dish_name` + serving counts) injected into the `Reference results (HINT ONLY)` prompt block.
3. **Phase 1.1.2 output** — Gemini 2.5 Pro should be nudged toward "Ayam Goreng"-style predictions and toward 7 servings per component (subject to the "reference is a hint, not ground truth" framing).
4. **Phase 2.2** — `personalized_matches` should include record 34 with its `prior_step2_data` (the LLM-generated nutrients from record 34's Phase 2.3 run).
5. **Phase 2.3** — if record 34's personalization row carries `corrected_step2_data` (none in this run — we only edited Phase 1.2, not Phase 2.4), the new record's `step2_data` reasoning should cite personalization.

**Spec generated:** 2026-04-19 17:19
**Screenshots directory:** `data/chrome_test_images/260419_1719_personalized_history_reuse/`
**Viewport:** desktop 1080 × 1280.

---

## Remarks

### Context

- **Frontend base URL:** `http://localhost:2512`.
- **Backend base URL:** `http://localhost:2612`.
- **Test user:** `Alan` (user_id=1, from `docs/technical/testing_context.md`).
- **Canary URL:** `AYAM_URL = "https://www.marionskitchen.com/wp-content/uploads/2021/08/20201216_Malaysian-Fried-Chicken-Ayam-Goreng-11-Web-1024x1024-1.jpeg"`.
- **Prerequisite — baseline record 34** seeded with `confirmed_dish_name="Ayam Goreng (family style, 7 portions)"`, `confirmed_portions=7`, Phase 2.3 complete (carries `prior_step2_data`).

Because the frontend uploads to `/api/date/{Y}/{M}/{D}/upload-url` and the dish-position slots for 2026-04-19 are already full (slots 1–5 used by records 30–34), this spec lands the new upload on **2026-04-20 slot 1** instead. That keeps the user-level BM25 corpus intact (Alan has 4 Ayam Goreng-flavored rows: 30, 31, 32-Daal, 33-Quiche, 34 with user edits) while isolating the new upload on a fresh date.

### Screenshot convention

One PNG per Chrome action, filename `test{id}_{HMMSS}_{NN}_{name}.png`. Tab-activation AppleScript + `screencapture -R`. Terminal output via `.capture_text.sh`.

---

## Database Pre-Interaction

### No cleanup — rely on the state left by `260419_full_workflow` Tests 1-6

This spec EXPECTS the following corpus at execution time (left by the prior `docs/chrome_test/260419_full_workflow.md` run):

```sql
SELECT query_id, confirmed_dish_name, confirmed_portions FROM personalized_food_descriptions WHERE user_id = 1 ORDER BY query_id;
-- Expected:
--  30 | Fried Chicken Plate                    | 4
--  31 | Ayam Goreng (Malaysian style)          | 3
--  32 | Dal Tadka                              | 2
--  33 | Quiche with Salad                      | 8
--  34 | Ayam Goreng (family style, 7 portions) | 7
```

If the corpus is missing, purge + re-run the full_workflow spec first.

### Pre-flight

```bash
curl -s http://localhost:2612/ >/dev/null && echo "backend up" || echo "BACKEND DOWN"
curl -s http://localhost:2512/ >/dev/null && echo "frontend up" || echo "FRONTEND DOWN"
```

No `backend.log` truncation — we want to grep the whole run's context to correlate Phase 1.1.2's reference-block injection.

---

## Pre-requisite

1. Corpus check above passes.
2. Chrome tab at `http://localhost:2512/dashboard` signed in as `Alan`.
3. Navigate to `http://localhost:2512/date/2026/4/20` — five empty dish slots.

---

## Tests

### Test 1 — New Ayam Goreng upload warm-starts against record 34 (7 portions)

**User(s):** `Alan`

**Feature under test:** the end-to-end "LLM consumes user-verified history" loop.

- [x] **Action 01 — navigate to the 2026-04-20 date view (empty):** `http://localhost:2512/date/2026/4/20`. All five slots empty. **Screenshot:** `test1_{HMMSS}_01_date_view_empty.png`
- [x] **Action 02a — click slot 1 "Or paste image URL":** same UI flow as the full_workflow spec. **Screenshot:** `test1_{HMMSS}_02a_url_field_open.png`
- [x] **Action 02b — paste Ayam Goreng URL:** `AYAM_URL`. **Screenshot:** `test1_{HMMSS}_02b_url_pasted.png`
- [x] **Action 02c — click Load:** auto-navigates to `/item/{newRecordId}`. Capture `newRecordId`. **Screenshot:** `test1_{HMMSS}_02c_auto_nav.png`
- [x] **Action 03 — assert warm-start retrieval pulled record 34:** expand the Personalized Data (Research only) card on the Step 1 view. The reference section must render a card with `Query #34`, similarity ≥ 0.25, link to `/item/34`. **Screenshot:** `test1_{HMMSS}_03_reference_points_at_34.png`
  ```js
  const j = await (await fetch(`http://localhost:2612/api/item/${newRecordId}`, { credentials: 'include' })).json();
  const ref = j?.result_gemini?.reference_image;
  ({
    ref_query_id: ref?.query_id,
    ref_sim: ref?.similarity_score,
    ref_carries_prior_step1: !!ref?.prior_step1_data,
    ref_prior_components: (ref?.prior_step1_data?.components || []).map(c => ({ name: c.component_name, servings: c.number_of_servings ?? c.predicted_servings })),
  });
  ```
  Expect `ref_query_id: 34, ref_sim >= 0.25, ref_carries_prior_step1: true`, and `ref_prior_components` includes a "Fried Chicken"-ish row.
- [x] **Action 04 — assert `step1_data` for the new record is nudged toward Ayam Goreng / 7 servings:** poll until `step1_data` lands; record `dish_predictions[0].name`, `components[0].number_of_servings`. Compare against record 30's cold-start run (4 servings, "Fried Chicken Plate"). The spec does NOT strictly require `number_of_servings == 7` — the prompt frames the reference as a *hint*, and Gemini can disagree. What we're measuring is whether the output moves in the direction of the user's override (more portions, more region-specific name) when a user-verified prior is injected. **Screenshot:** `test1_{HMMSS}_04_step1_data_with_hint.png`
- [x] **Action 05 — click Confirm (accept AI's proposal as-is):** measures whether the LLM's step2 run, without further user edits, inherits the user's prior serving count via the personalization block. **Screenshot:** `test1_{HMMSS}_05_confirm_clicked.png`
- [x] **Action 06 — assert `personalized_matches` carries record 34's `prior_step2_data`:**
  ```js
  async function poll() {
    for (let i = 0; i < 30; i++) {
      const j = await (await fetch(`http://localhost:2612/api/item/${newRecordId}`, { credentials: 'include' })).json();
      if (j.result_gemini?.personalized_matches) return j;
      await new Promise(r => setTimeout(r, 700));
    }
    return null;
  }
  const j = await poll();
  const m = (j?.result_gemini?.personalized_matches || []).find(pm => pm.query_id === 34);
  ({
    has_match_to_34: !!m,
    match_sim: m?.similarity_score,
    has_prior_step2: !!m?.prior_step2_data,
    prior_calories: m?.prior_step2_data?.calories_kcal,
    has_corrected: !!m?.corrected_step2_data,
  });
  ```
  Expect `has_match_to_34: true, has_prior_step2: true, has_corrected: false` (we didn't do Phase 2.4 on record 34). `prior_calories` non-null.
  **Screenshot:** `test1_{HMMSS}_06_personalized_matches.png`
- [x] **Action 07 — assert new record's `step2_data` + `reasoning_sources`:**
  ```js
  async function pollStep2() {
    for (let i = 0; i < 80; i++) {
      const j = await (await fetch(`http://localhost:2612/api/item/${newRecordId}`, { credentials: 'include' })).json();
      if (j.result_gemini?.step2_data) return j;
      await new Promise(r => setTimeout(r, 1000));
    }
    return null;
  }
  const j = await pollStep2();
  const s = j?.result_gemini?.step2_data || {};
  ({
    dish_name: s.dish_name,
    calories_kcal: s.calories_kcal,
    reasoning_sources: (s.reasoning_sources || '').slice(0, 300),
    cites_personalization: /personaliz|prior|history|previous/i.test(s.reasoning_sources || ''),
  });
  ```
  Record the verbatim values in Findings. Key questions:
  - Does `reasoning_sources` mention the user's prior upload?
  - Does `calories_kcal` / serving-count language match record 34's step2_data?
  **Screenshot:** `test1_{HMMSS}_07_step2_reasoning.png`
- [x] **Action 08 — error sweep:** `tail -n 600 backend.log | grep -iE "ERROR|Traceback"` — expect no new unexpected errors. **Screenshot:** `test1_{HMMSS}_08_log_error_sweep.png` (terminal)

**Report:**

- **Status:** PASSED with discrepancies
- **Findings (new record 35 vs. user-verified record 34):**

  **Side-by-side of the two records' pipeline outputs:**

  | Field | Record 34 (user's prior, confirmed with edits) | Record 35 (new upload, AI-accepted) |
  |---|---|---|
  | `confirmed_dish_name` (Phase 1.2) | `Ayam Goreng (family style, 7 portions)` | `Fried Chicken` (AI default) |
  | `confirmed_portions` (Phase 1.2) | `7` (user override) | `4` (AI default) |
  | `step2_data.dish_name` (Phase 2.3) | `Ayam Goreng (family style, 7 portions)` | `Fried Chicken` |
  | `step2_data.calories_kcal` | `2380` (~340 × 7 servings) | `1362` (~340 × 4 servings) |

  **What propagated across the two records via the personalization pipeline:**

  - ✓ **Phase 1.1.1(b) retrieval** correctly landed record 34 as the top match (`ref_query_id: 34, ref_sim: 1.0`).
  - ✓ **Phase 2.2 personalization lookup** populated `personalized_matches` with record 34's `prior_step2_data` (`prior_dish_name = "Ayam Goreng (family style, 7 portions)", prior_calories = 2380`). Total 3 matches surfaced (records 34, 31, 30), all Ayam-Goreng-related priors.
  - ✓ **Phase 2.3 reasoning cites the personalization block explicitly.** `step2_data.reasoning_sources = "User prior: similar upload"` and `reasoning_calories = "Based on 16oz (454g) of fried chicken, aligning with a similar user prior upload."` — textbook personalization-aware reasoning.
  - ✓ **Per-serving nutrition profile carried over.** Record 35's 1362 kcal = ~340 kcal/serving × 4 servings, matching record 34's per-serving density (2380 / 7 ≈ 340). The LLM correctly inferred the per-portion nutrient profile from the prior and scaled it to record 35's own portion count.

  **What did NOT propagate (architectural finding):**

  - ✗ **`confirmed_portions = 7` did NOT carry into record 35's Step 1.** Record 35's `predicted_servings` came back as 4 — the AI's cold-start default, unaffected by the user's override. Phase 1.1.2's reference block injects `prior_step1_data` (the AI's ORIGINAL step1 output for record 34, which also predicted 4 servings), NOT the user's `confirmed_*` fields. The user-verified portions-count lives in `personalized_food_descriptions.confirmed_portions` but nothing reads that column back into a Phase 1.1.2 prompt.
  - ✗ **`confirmed_dish_name = "Ayam Goreng (family style, 7 portions)"` did NOT surface in record 35's dish_predictions** either. Record 35's top prediction was plain `Fried Chicken`. The reference block's `prior_step1_data.dish_predictions` is the AI's original list (`["Fried Chicken", "Fried Chicken Plate", "Southern Fried Chicken"]`), not the user's custom name.

  **Interpretation:** Phase 1.2's user corrections improve the BM25 retrieval corpus (via `confirmed_tokens`) and ride along as `prior_dish_name` inside Phase 2.2's `prior_step2_data` (which Phase 2.3 reads verbatim), but they do NOT feed back into the Phase 1.1.2 prompt. A user who renames a dish once will NOT see that custom name re-suggested on future uploads' Step 1 predictions — they'll have to apply the same edit each time, unless the architecture changes to inject `confirmed_dish_name` into the reference block.

  - **Backend log error sweep:** 0 matches.
  - **Screenshots:** `test1_72053_01_date_view_empty.png`, `test1_72103_02a_url_field_open.png`, `test1_72105_02b_url_pasted.png`, `test1_72142_02c_auto_nav.png`, `test1_72155_03_reference_points_at_34.png`, `test1_72213_04_step1_data_with_hint.png`, `test1_72226_05_confirm_clicked.png`, `test1_72234_06_personalized_matches.png`, `test1_72248_07_step2_reasoning.png`, `test1_72310_08_log_error_sweep.png`.

- **Improvement Proposals:**
  + good to have - **Inject `confirmed_*` into Phase 1.1.2's reference block** - Today the block carries only `prior_step1_data` (the AI's pre-edit proposal). Adding `prior_confirmed_dish_name` and `prior_confirmed_portions` into the same block would let Gemini echo the user's corrections on repeat uploads. Suggested prompt snippet: "If the reference dish was corrected by the user (`confirmed_dish_name` present), prefer that name and serving count unless the query image clearly shows a different dish or portion." Would require extending `reference_image` to carry `confirmed_dish_name` + `confirmed_portions` too.
  + good to have - **Expose the personalization citation pattern to the Step 2 UI** - `reasoning_sources: "User prior: similar upload"` is a strong signal for end users that their history improved the estimate. Consider surfacing a small "Refined from your prior upload" badge on the Step 2 results card whenever `reasoning_sources` regex-matches `/user prior/i`.

---

## Summary for the Caller

- **Output file:** `docs/chrome_test/260419_1719_personalized_history_reuse.md`
- **Screenshots directory:** `data/chrome_test_images/260419_1719_personalized_history_reuse/`
- **Number of tests:** 1 desktop-only test.
- **Precondition:** record 34 in Alan's corpus with `confirmed_portions=7` and completed Phase 2.3.
- **Next step:** run `/webapp-dev:chrome-test-execute docs/chrome_test/260419_1719_personalized_history_reuse.md`.
