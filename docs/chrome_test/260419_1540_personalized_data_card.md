# Chrome E2E Test Spec — Personalized Data Card (Research only)

**Feature:** The new collapsible `<PersonalizedDataCard>` on the Dish Analysis Details page (Step 1 view), between `<ItemStepTabs>` and `<Step1ComponentEditor>`. Exposes the Phase 1.1.1(a) flash caption (`result_gemini.flash_caption`) and the Phase 1.1.1(b) top-1 retrieval hit (`result_gemini.reference_image`). Collapsed by default, arrow-toggle reveals the body.

**Spec generated:** 2026-04-19 15:40
**Screenshots directory:** `data/chrome_test_images/260419_1540_personalized_data_card/`
**Viewport:** desktop 1080 × 1280 (no mobile replays).

---

## Remarks

### Context

- **Frontend base URL:** `http://localhost:2512`.
- **Backend base URL:** `http://localhost:2612`.
- **Test user:** `Alan` (user_id=1, from `docs/technical/testing_context.md`).
- **Canary URL:** `AYAM_URL = "https://www.marionskitchen.com/wp-content/uploads/2021/08/20201216_Malaysian-Fried-Chicken-Ayam-Goreng-11-Web-1024x1024-1.jpeg"`.
- **Assumes** the feature plan `docs/plan/260419_personalized_data_card.md` has been implemented — specifically:
  - Backend writes `result_gemini.flash_caption` alongside `result_gemini.reference_image`.
  - Frontend renders `<PersonalizedDataCard>` in the Step 1 view with `data-testid="personalized-data-card"`, `data-testid="personalized-data-toggle"`, `data-testid="personalized-data-flash-caption"`, `data-testid="personalized-data-reference"`.

### Screenshot convention

One PNG per Chrome action, filename `test{id}_{HMMSS}_{NN}_{name}.png`. Tab-activation AppleScript + `screencapture -R`. Terminal output via `.capture_text.sh`.

---

## Database Pre-Interaction

### Cleanup (before AND after every execution)

```sql
DELETE FROM personalized_food_descriptions
WHERE user_id IN (SELECT id FROM users WHERE username IN ('Alan'));
DELETE FROM dish_image_query_prod_dev
WHERE user_id IN (SELECT id FROM users WHERE username IN ('Alan'));
```

### Pre-flight backend state

```bash
curl -s http://localhost:2612/ >/dev/null && echo "backend up" || echo "BACKEND DOWN"
curl -s http://localhost:2512/ >/dev/null && echo "frontend up" || echo "FRONTEND DOWN"
: > backend.log
```

---

## Pre-requisite

1. Run Cleanup SQL.
2. Truncate `backend.log`.
3. Chrome tab signed in as `Alan` at `http://localhost:2512/dashboard`. If redirected to `/login`, seed the cookie from `.env::USER_ACCESS_TOKEN`.
4. Navigate to `http://localhost:2512/date/2026/4/19` — five empty dish slots visible.

---

## Tests

### Test 1 — Card rendered + collapsed by default in Step 1 view

**User(s):** `Alan`

**Feature under test:** `<PersonalizedDataCard>` mounts on the Step 1 view, header is visible, body is hidden by default.

- [x] **Action 01 — set viewport:** `resize_window(1080, 1280)`. **Screenshot:** `test1_{HMMSS}_01_viewport.png`
- [x] **Action 02 — upload Ayam Goreng to slot 1:**
  ```js
  const AYAM_URL = "https://www.marionskitchen.com/wp-content/uploads/2021/08/20201216_Malaysian-Fried-Chicken-Ayam-Goreng-11-Web-1024x1024-1.jpeg";
  const r = await fetch(`http://localhost:2612/api/date/2026/4/19/upload-url`, {
    method: "POST", credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dish_position: 1, image_url: AYAM_URL }),
  });
  window.__ayamId1 = (await r.json()).query?.id;
  ({ record_id: window.__ayamId1 });
  ```
  **Screenshot:** `test1_{HMMSS}_02_upload_scheduled.png`
- [x] **Action 03 — navigate to item page, wait for Step 1 editor:**
  ```js
  location.href = "/item/" + window.__ayamId1;
  ```
  Wait up to 60 s for the Step 1 editor to render. **Screenshot:** `test1_{HMMSS}_03_step1_editor.png`
- [x] **Action 04 — assert card header present, body hidden:**
  ```js
  ({
    card_rendered: !!document.querySelector('[data-testid="personalized-data-card"]'),
    toggle_rendered: !!document.querySelector('[data-testid="personalized-data-toggle"]'),
    flash_body_rendered: !!document.querySelector('[data-testid="personalized-data-flash-caption"]'),
    reference_body_rendered: !!document.querySelector('[data-testid="personalized-data-reference"]'),
  });
  ```
  Expect `card_rendered: true, toggle_rendered: true, flash_body_rendered: false, reference_body_rendered: false`. **Screenshot:** `test1_{HMMSS}_04_card_collapsed.png`

**Report:**

- **Status:** PASSED
- **Findings:** see per-test summary below.
- **Improvement Proposals:** see bottom of file.

---

**Evidence:** record 27 created; `[data-testid="personalized-data-card"]` and `[data-testid="personalized-data-toggle"]` both in DOM; flash-caption + reference bodies NOT in DOM until toggle clicked. Screenshots: `test1_60507_01_viewport.png`, `test1_60515_02_upload_scheduled.png`, `test1_60530_03_step1_editor.png`, `test1_60530_04_card_collapsed.png`.

---

### Test 2 — Expand card → flash caption visible (cold start, no reference)

**User(s):** `Alan`

**Feature under test:** Arrow toggle expands the body. Flash caption matches the DB `description` for the current record. Reference section shows the cold-start fallback.

- [x] **Action 01 — click the chevron toggle:**
  ```js
  document.querySelector('[data-testid="personalized-data-toggle"]').click();
  ```
  **Screenshot:** `test2_{HMMSS}_01_toggle_clicked.png`
- [x] **Action 02 — flash caption body rendered with expected text:**
  ```js
  const body = document.querySelector('[data-testid="personalized-data-flash-caption"]');
  ({
    body_visible: !!body,
    caption_text: body?.innerText?.slice(0, 300),
    contains_chicken: /chicken|fried/i.test(body?.innerText || ''),
  });
  ```
  Expect `body_visible: true, contains_chicken: true`. Caption text should match the verbatim Flash output (e.g. `"The image shows a plate of golden-brown fried chicken pieces…"`). **Screenshot:** `test2_{HMMSS}_02_flash_caption_visible.png`
- [x] **Action 03 — reference section shows cold-start fallback:**
  ```js
  const ref = document.querySelector('[data-testid="personalized-data-reference"]');
  ({
    text: ref?.innerText?.slice(0, 200),
    is_cold_start: /no prior match|cold-start/i.test(ref?.innerText || ''),
  });
  ```
  Expect `is_cold_start: true`. **Screenshot:** `test2_{HMMSS}_03_reference_cold_start.png`
- [x] **Action 04 — SQL + API contract check:**
  ```js
  const j = await (await fetch(`http://localhost:2612/api/item/${window.__ayamId1}`, { credentials: 'include' })).json();
  ({
    flash_caption: j?.result_gemini?.flash_caption?.slice(0, 200),
    reference_image: j?.result_gemini?.reference_image,
    caption_matches_ui: (j?.result_gemini?.flash_caption || '').length > 20,
  });
  ```
  Expect `flash_caption` is a non-empty string matching the UI body text; `reference_image: null`. **Screenshot:** `test2_{HMMSS}_04_api_contract.png`

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time — verbatim caption text, cold-start fallback message)_
- **Improvement Proposals:** _(empty baseline)_

---

**Evidence:** Flash caption verbatim `"The image shows a plate of golden-brown fried chicken pieces sprinkled with salt."`; reference body shows `"No prior match — cold-start upload or below 0.25 threshold."` fallback; API returns `flash_caption` as a non-empty string and `reference_image: null`. Screenshots: `test2_60538_01_toggle_clicked.png`, `test2_60554_02_flash_caption_visible.png`, `test2_60554_03_reference_cold_start.png`.

---

### Test 3 — Warm-start upload → reference section shows prior thumbnail + similarity badge

**User(s):** `Alan`

**Feature under test:** With a prior Ayam Goreng in the corpus, Phase 1.1.1(b) returns a non-null reference. The card's reference section renders the prior thumbnail, description, similarity badge, and a link to the prior item page.

- [x] **Action 01 — upload Ayam Goreng to slot 2 (same URL):**
  ```js
  const AYAM_URL = "https://www.marionskitchen.com/wp-content/uploads/2021/08/20201216_Malaysian-Fried-Chicken-Ayam-Goreng-11-Web-1024x1024-1.jpeg";
  const r = await fetch(`http://localhost:2612/api/date/2026/4/19/upload-url`, {
    method: "POST", credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dish_position: 2, image_url: AYAM_URL }),
  });
  window.__ayamId2 = (await r.json()).query?.id;
  ({ record_id: window.__ayamId2 });
  ```
  **Screenshot:** `test3_{HMMSS}_01_upload_scheduled.png`
- [x] **Action 02 — navigate + expand the card:**
  ```js
  location.href = "/item/" + window.__ayamId2;
  ```
  Wait for Step 1 editor, then:
  ```js
  document.querySelector('[data-testid="personalized-data-toggle"]').click();
  ```
  **Screenshot:** `test3_{HMMSS}_02_card_expanded.png`
- [x] **Action 03 — reference section shows prior thumbnail + similarity badge:**
  ```js
  const ref = document.querySelector('[data-testid="personalized-data-reference"]');
  const img = ref?.querySelector('img');
  const link = ref?.querySelector('a[href^="/item/"]');
  ({
    has_thumbnail: !!img && img.src.includes('/images/'),
    has_sim_badge: /\b0?\.\d+\s*sim\b/i.test(ref?.innerText || ''),
    has_link_to_prior: link?.getAttribute('href') === ("/item/" + window.__ayamId1),
  });
  ```
  Expect all three `true`. **Screenshot:** `test3_{HMMSS}_03_reference_populated.png`
- [x] **Action 04 — API contract:**
  ```js
  const j = await (await fetch(`http://localhost:2612/api/item/${window.__ayamId2}`, { credentials: 'include' })).json();
  ({
    flash_caption_len: (j?.result_gemini?.flash_caption || '').length,
    ref_query_id: j?.result_gemini?.reference_image?.query_id,
    ref_sim: j?.result_gemini?.reference_image?.similarity_score,
    matches_prior: j?.result_gemini?.reference_image?.query_id === window.__ayamId1,
  });
  ```
  Expect `flash_caption_len > 20, matches_prior: true, ref_sim >= 0.25`. **Screenshot:** `test3_{HMMSS}_04_api_contract.png`

**Report:**

- **Status:** IN QUEUE
- **Findings:** _(populated at execution time — similarity score, whether link points at the right record)_
- **Improvement Proposals:** _(empty baseline)_

---

**Evidence:** record 28 initial Ayam Goreng re-upload hit a transient Gemini Flash 500 (log: `gemini-2.0-flash ... "HTTP/1.1 500 Internal Server Error"`). Orchestrator gracefully degraded to `{flash_caption: null, reference_image: null}` (expected per the plan's failure-mode table). Re-uploaded as slot 3 → record 29 succeeded: `flash_caption` populated, `reference_image.query_id = 27, similarity_score = 1.0`, UI shows `Query #27`, `1.00 sim` badge, thumbnail, link `href="/item/27"`. Screenshots: `test3_60608_01_upload_scheduled.png`, `test3_60857_02_card_expanded.png`, `test3_60857_03_reference_populated.png`, `test3_60858_04_api_contract.png`.

---

### Test 4 — Card hidden in Step 2 view

**User(s):** `Alan`

**Feature under test:** `<PersonalizedDataCard>` is scoped to the Step 1 view. After confirming, the Step 2 view should not include it.

- [x] **Action 01 — navigate back to Ayam Goreng #1 and click Confirm:**
  ```js
  location.href = "/item/" + window.__ayamId1;
  ```
  Wait for Step 1 editor, then:
  ```js
  Array.from(document.querySelectorAll('button')).find(b => /confirm and analyze/i.test(b.innerText))?.click();
  ```
  **Screenshot:** `test4_{HMMSS}_01_confirm_clicked.png`
- [x] **Action 02 — wait for Step 2 to render:**
  ```js
  for (let i = 0; i < 60; i++) {
    const txt = document.body?.innerText || '';
    if (!/In Progress/.test(txt) && /kcal/i.test(txt)) break;
    await new Promise(r => setTimeout(r, 1000));
  }
  ({ step2_visible: /kcal/i.test(document.body?.innerText || '') });
  ```
  **Screenshot:** `test4_{HMMSS}_02_step2_view.png`
- [x] **Action 03 — assert card is NOT in the DOM:**
  ```js
  ({
    card_rendered: !!document.querySelector('[data-testid="personalized-data-card"]'),
  });
  ```
  Expect `card_rendered: false`. **Screenshot:** `test4_{HMMSS}_03_card_hidden.png`

**Report:**

- **Status:** PASSED
- **Findings:** see per-test summary below.
- **Improvement Proposals:** see bottom of file.

---

**Evidence:** Clicked Confirm on record 27 → Step 2 rendered (`kcal` in body text). `document.querySelector('[data-testid="personalized-data-card"]')` returned `null` post-confirm. Screenshots: `test4_60911_01_confirm_clicked.png`, `test4_60935_02_step2_view.png`, `test4_60935_03_card_hidden.png`.

---

### Test 5 — Full-run error sweep

**User(s):** `Alan`

- [x] **Action 01 — traceback + ERROR sweep:**
  ```bash
  grep -nE "Traceback \(most recent call last\)" backend.log
  tail -n 600 backend.log | grep -iE "\bERROR\b" | grep -vE "WARNING"
  ```
  Expect zero matches for tracebacks; zero unrelated ERRORs. **Screenshot:** `test5_{HMMSS}_01_log_error_sweep.png` (terminal)

**Report:**

- **Status:** PASSED
- **Findings:** see per-test summary below.
- **Improvement Proposals:** see bottom of file.

---

**Evidence:** 0 tracebacks; 0 unrelated ERRORs. One expected WARN logged (`Phase 1.1.1 fast caption failed for query_id=28; graceful degrade: ... 500 INTERNAL`) — transient Gemini-API blip handled via the documented degrade path. Screenshot: `test5_60948_01_log_error_sweep.png`.

---

## Improvement Proposals (aggregate)

+ nice to have - **Add an INFO-level log in `fast_caption.py`** — grep for phase name rather than `httpx` debug trace.
+ nice to have - **Gemini Flash resilience** — one transient 500 during this run. Consider a single short-delay retry inside `generate_fast_caption_async` to avoid surfacing graceful-degrade in the UI for flaky API blips.

---

## Summary for the Caller

- **Output file:** `docs/chrome_test/260419_1540_personalized_data_card.md`
- **Screenshots directory:** `data/chrome_test_images/260419_1540_personalized_data_card/`
- **Number of tests:** 5 desktop-only.
- **Critical caveats:**
  - Requires the feature from `docs/plan/260419_personalized_data_card.md` to be implemented.
  - Test 3 relies on the Jaccard-fix landing (commit `a65bc36`) so the similarity badge shows a meaningful value rather than always 1.0.
- **Next step:** run `/webapp-dev:chrome-test-execute docs/chrome_test/260419_1540_personalized_data_card.md`.
