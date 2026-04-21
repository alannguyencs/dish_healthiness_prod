# Stage 2 — Phase 1.1.1: Fast Caption + Personalized Reference Retrieval

**Feature**: Wire the first consumer of the Stage 0 foundation. Every upload now runs a Gemini 2.0 Flash fast caption, BM25-searches the user's prior personalization rows, and stamps `result_gemini.reference_image` with the top-1 match (or `null` on cold start / below threshold). The current upload is inserted into `personalized_food_descriptions` AFTER the search so it cannot self-match. No user-visible UI change in this stage — the new key is a silent handoff for Stage 3 (Phase 1.1.2).
**Plan Created:** 2026-04-18
**Status:** Plan
**Reference**:
- [Issues — 260415, Stage 2](../issues/260415.md)
- [Discussion — Food DB investigation & end-to-end redesign](../discussion/260418_food_db.md)
- [Plan — Stage 0 Personalized Food Index](./260418_stage0_personalized_food_index.md) (foundation this stage consumes)
- [Abstract — Dish Analysis](../abstract/dish_analysis/index.md)
- [Abstract — Component Identification](../abstract/dish_analysis/component_identification.md)
- [Technical — Dish Analysis](../technical/dish_analysis/index.md)
- [Technical — Component Identification](../technical/dish_analysis/component_identification.md)
- [Technical — Personalized Food Index](../technical/dish_analysis/personalized_food_index.md)
- [Chrome Test Spec — 260418_2013_stage2_phase1_1_1_fast_caption](../chrome_test/260418_2013_stage2_phase1_1_1_fast_caption.md)

---

## Problem Statement

1. Stage 0 shipped the `personalized_food_descriptions` table, CRUD, and BM25 service as pure library code. Nothing yet writes to the table, so the corpus stays empty and later stages (3 / 4 / 6 / 8) have nothing to retrieve.
2. The end-to-end workflow in `docs/discussion/260418_food_db.md` requires Phase 1.1.1 to run **before** the main component-ID call so Phase 1.1.2 can attach a reference image and reference `step1_data`. Without this stage, Phase 1.1.2 degenerates to today's single-image call forever.
3. The upload path (`backend/src/api/date.py → analyze_image_background`) currently goes straight to the Gemini 2.5 Pro structured-output call. There is no fast-caption primitive in the codebase; `gemini_analyzer.py` only knows Step 1 and Step 2 Pro calls.
4. The issue pins Stage 2 to three artifacts — a new fast-caption module, a new `personalized_reference` orchestrator, and a hook into `analyze_image_background` — plus one new config constant. It ships no API, no UI, no schema change.
5. The self-matching guarantee the discussion diagram relies on (upload N never retrieves upload N as its own reference) must be enforced at two independent layers: search uses `exclude_query_id=<current>`, AND the insert runs **after** the search. Either alone is insufficient under retry scenarios.

---

## Proposed Solution

Land four artifacts in a single PR:

1. **`fast_caption.py`** — thin Gemini 2.0 Flash async wrapper. Unstructured output (plain text, `response_mime_type` default, no schema). Reuses the `loop.run_in_executor` + `os.environ["GEMINI_API_KEY"]` pattern from `gemini_analyzer.py`. Lives at `backend/src/service/llm/fast_caption.py` to match the issue spec and sit next to the existing LLM call wrappers (confirmed with user 2026-04-18).
2. **`personalized_reference.py`** — the orchestrator that composes `fast_caption + tokenize + search_for_user + insert_description_row`. Returns the dict the new `result_gemini.reference_image` key takes on, or `None` on cold start / below threshold / graceful-degrade. Encapsulates the retry-idempotency check (skip fast-caption if a row already exists for this `query_id`).
3. **Hook into `analyze_image_background`** — one new call at the top of the background task, before the existing `get_step1_component_identification_prompt()` call. Attach the result to `result_gemini.reference_image`, persisting even when `None` so the frontend can tell cold-start from "not yet persisted". Do this regardless of whether Phase 1.1.2 succeeds or fails: the reference retrieval is independent of the component-ID outcome and we don't want a Phase 1.1.2 error to destroy the retrieval state.
4. **`THRESHOLD_PHASE_1_1_1_SIMILARITY` constant** in `configs.py` at `0.25`. Pinned by the issue; acknowledge openly (per Stage 0 docs) that `similarity_score` is a max-in-batch relative signal so the threshold only filters out corpora with very-low lexical overlap — the prompt framing in Stage 3 is the real quality control.

The new key on `result_gemini`:

```json
{
  "reference_image": {
    "query_id": 1234,
    "image_url": "/images/260418_200123_u7_dish1.jpg",
    "description": "grilled chicken rice with cucumber and chili sauce",
    "similarity_score": 0.87,
    "prior_step1_data": { ...full step1_data from the referenced DishImageQuery... }
  }
}
```

…or `"reference_image": null` when there is no match above threshold, when the user has no prior rows, or when the fast-caption call degraded gracefully.

### Failure modes and the graceful-degrade contract (confirmed with user 2026-04-18)

| Failure | Behavior | Effect on `reference_image` | Effect on `personalized_food_descriptions` |
|---|---|---|---|
| Gemini 2.0 Flash errors (rate limit, network, parse) | Catch inside `personalized_reference.resolve_reference_for_upload`, log WARN. | `null` | No row inserted |
| User has zero prior rows | BM25 service returns `[]`. | `null` | Row inserted for this upload (populates future searches) |
| Top-1 match below `THRESHOLD_PHASE_1_1_1_SIMILARITY` | BM25 service returns `[]` after threshold filter. | `null` | Row inserted (so next upload can match this one) |
| Retry of a prior-failed Phase 1 (`/retry-step1`) and the row is already present | Short-circuit: skip fast-caption, skip search, skip insert. | Preserve whatever was on the prior attempt's `result_gemini.reference_image` (if any) — do not overwrite. | No new row inserted; existing row untouched |
| Retry and the row is absent | Normal path — run caption + search + insert. | Whatever the search returns | New row inserted |

### Why persist `reference_image` even when `null`

- Stage 3 (Phase 1.1.2) needs to know "we tried and found nothing" vs "we haven't run retrieval yet". `result_gemini` in general is nullable until the background task writes; if we leave the key out when null, Stage 3 can't distinguish cold-start from not-yet-run.
- The frontend (Stage 3+ down the line) can render "No similar prior dish found" copy only when the key is present and null, rather than hiding the UI element on null-and-absent.

### Schema / data-model posture

Stage 2 does not touch the DB schema. The `personalized_food_descriptions` table was created in Stage 0 with the full column set (`description`, `tokens`, `similarity_score_on_insert` included) so this stage is a pure write-path wiring, not a migration.

---

## Current Implementation Analysis

### What Exists (keep as-is)

| Component | File | Status |
|-----------|------|--------|
| Upload endpoints | `backend/src/api/date.py` (`upload_dish`, `upload_dish_from_url`) | Keep — both call `analyze_image_background` unchanged; the new retrieval runs inside the background task, not in the HTTP handler. |
| Phase 1 background task | `backend/src/api/item_step1_tasks.py::analyze_image_background` | Modify (see below); do not move the file. |
| Retry endpoint | `backend/src/api/item_retry.py::retry_step1_analysis` | Keep — still calls `analyze_image_background` unchanged; the retry-idempotency guard lives inside the orchestrator, not in the retry route. |
| `DishImageQuery` CRUD (read/write `result_gemini`) | `backend/src/crud/dish_query_basic.py`, `backend/src/crud/crud_food_image_query.py` | Keep — the new data rides on existing columns. |
| Stage 0 personalization artifacts | `PersonalizedFoodDescription`, `crud_personalized_food`, `personalized_food_index` | Keep — this stage consumes them verbatim. `search_for_user(user_id, tokens, top_k, min_similarity, exclude_query_id)` is the only retrieval API Stage 2 touches. |
| Stage 1 nutrition DB artifacts | `NutritionCollectionService`, seed script | Keep — orthogonal to Stage 2; nothing to consume here. |
| Gemini call infrastructure | `backend/src/service/llm/gemini_analyzer.py`, `GEMINI_API_KEY` env var, `loop.run_in_executor` pattern | Keep — `fast_caption.py` reuses the same env var and the same executor pattern but is a separate module. |
| Pydantic schemas | `Step1ComponentIdentification` etc. | Keep — unchanged. |
| Frontend `ItemV2.jsx` / `useItemPolling.js` / `PhaseErrorCard.jsx` | `frontend/src/pages/ItemV2.jsx`, `frontend/src/hooks/useItemPolling.js` | Keep — the new `reference_image` key is silently added; the frontend will read it defensively (or not at all) in Stage 2. UI changes start in Stage 3. |
| `docs/technical/dish_analysis/personalized_food_index.md` Component Checklist | "Stage 2 (Phase 1.1.1): fast-caption + retrieval wired into `analyze_image_background`" row | Flip from `[ ]` to `[x]` in the documentation pass (see Documentation section). |

### What Changes

| Component | Current | Proposed |
|-----------|---------|----------|
| `backend/src/service/llm/fast_caption.py` | Does not exist. | Adds `generate_fast_caption_async(image_path)` — Gemini 2.0 Flash, temperature 0, plain-text response. Raises `ValueError` on missing API key or Gemini error; `FileNotFoundError` propagates. |
| `backend/src/service/personalized_reference.py` | Does not exist. | Adds `resolve_reference_for_upload(user_id, query_id, image_path)` orchestrator. Handles retry-idempotency, graceful-degrade on caption failure, write-after-read guarantee. |
| `backend/src/api/item_step1_tasks.py::analyze_image_background` | Goes straight from `get_step1_component_identification_prompt()` to the Pro call. | Calls `resolve_reference_for_upload(record.user_id, query_id, file_path)` first. Result stashed on `result_gemini.reference_image`. Component-ID call and downstream persistence logic unchanged. |
| `backend/src/configs.py` | `DATABASE_DIR` constant added in Stage 1. | Appends `THRESHOLD_PHASE_1_1_1_SIMILARITY = 0.25`. No other configs change. |
| `docs/technical/dish_analysis/component_identification.md` | "Personalization Store (foundation, not yet consumed)" forward-reference block. | Promote to a full "Phase 1.1.1 — Fast Caption + Reference Retrieval" sub-section documenting the new flow and the `reference_image` shape. |
| `docs/abstract/dish_analysis/component_identification.md` | Describes today's single-image Phase 1. | One-paragraph addition: "When the user has uploaded similar dishes before, the system silently retrieves one as an invisible reference. No user-facing change in this stage — the improved accuracy lands when Stage 3 consumes the reference." |
| `docs/technical/dish_analysis/personalized_food_index.md` Component Checklist | Stage 2 row `[ ]`. | Flip to `[x]` with a one-line link back to `item_step1_tasks.py`. |

---

## Implementation Plan

### Key Workflow

The new flow inserts itself as the first step of `analyze_image_background`, leaving the rest of the background task intact.

```
backend/src/api/date.py: upload_dish()
  └── BackgroundTasks.add_task(analyze_image_background, query_id, file_path)

analyze_image_background(query_id, file_path, retry_count=0)
  │
  ▼
record = get_dish_image_query_by_id(query_id)              (existing call — reused for reference_image persistence)
  │
  ▼ (NEW: Phase 1.1.1 runs here, before the Step 1 Pro call)
reference = resolve_reference_for_upload(
    user_id=record.user_id,
    query_id=query_id,
    image_path=file_path,
)
  │
  ├── if a personalized_food_descriptions row already exists for this query_id
  │     → return None  (retry short-circuit; existing row untouched)
  │
  ├── try:
  │     description = generate_fast_caption_async(image_path)        (Gemini 2.0 Flash, plain text)
  │   except (ValueError, FileNotFoundError) as exc:
  │     log.warning("Phase 1.1.1 fast caption failed ... graceful degrade")
  │     return None                                                   (no row inserted, reference_image = null)
  │
  ├── query_tokens = personalized_food_index.tokenize(description)
  │
  ├── matches = personalized_food_index.search_for_user(
  │       user_id, query_tokens,
  │       top_k=1,
  │       min_similarity=THRESHOLD_PHASE_1_1_1_SIMILARITY,
  │       exclude_query_id=query_id,
  │   )
  │   top = matches[0] if matches else None
  │
  ├── if top:
  │     prior = get_dish_image_query_by_id(top["query_id"])
  │     prior_step1_data = (prior.result_gemini or {}).get("step1_data")
  │     reference = {
  │         "query_id": top["query_id"],
  │         "image_url": top["image_url"],
  │         "description": top["description"],
  │         "similarity_score": top["similarity_score"],
  │         "prior_step1_data": prior_step1_data,
  │     }
  │   else:
  │     reference = None
  │
  └── insert_description_row(
          user_id, query_id,
          image_url=record.image_url,
          description=description,
          tokens=query_tokens,
          similarity_score_on_insert=(top["similarity_score"] if top else None),
      )
      return reference
  │
  ▼
step1_prompt = get_step1_component_identification_prompt()            (existing)
step1_result = analyze_step1_component_identification_async(...)     (existing — Stage 2 does NOT yet pass the reference into the prompt; that is Stage 3's job)
  │
  ▼
base = (record.result_gemini or {}).copy()                            (existing)
base["reference_image"] = reference                                    (NEW key — persisted even when None so cold-start is distinguishable)
base.update({ step: 1, step1_data: step1_result, ... })                (existing)
update_dish_image_query_results(query_id, result_openai=None, result_gemini=base)  (existing)
```

**Failure-path persistence.** On exception in Phase 1.1.2 (the existing Pro call), the current code flow through `persist_phase_error` wipes `result_gemini.step1_error`. That helper does NOT touch `reference_image` — it writes only the `step1_error` key. But because the error path skips the success-side `base["reference_image"] = reference` assignment, the `reference_image` we computed gets lost. Fix by writing `reference_image` to the record **before** the Pro call, so Phase 1.1.2 failures do not destroy Phase 1.1.1's output:

```
resolve reference (Phase 1.1.1)
  │
  ▼ NEW: persist reference_image immediately
partial = (record.result_gemini or {}).copy()
partial["reference_image"] = reference
update_dish_image_query_results(query_id, result_openai=None, result_gemini=partial)
  │
  ▼
run Step 1 Pro call (Phase 1.1.2) — may fail
  │
  ▼
on success: merge step1_data into the now-persisted blob (keep reference_image)
on failure: persist_phase_error writes step1_error; reference_image is preserved because it is already on the row
```

This keeps Phase 1.1.1 and Phase 1.1.2 on independent persistence writes — matching the cross-stage invariant "phase independence on `result_gemini`" in the issue.

#### To Delete

None.

#### To Update

- `backend/src/api/item_step1_tasks.py::analyze_image_background` — insert the Phase 1.1.1 block at the top, persist `reference_image` before the Pro call, merge into the post-success blob. Do not change function signature (`(query_id, file_path, retry_count=0)`) so `/retry-step1` and the upload routes keep working.

#### To Add New

- `backend/src/service/llm/fast_caption.py` — `generate_fast_caption_async(image_path) -> str`.
- `backend/src/service/personalized_reference.py` — `resolve_reference_for_upload(user_id, query_id, image_path) -> Optional[Dict[str, Any]]`.

---

### Database Schema

**No changes.** Stage 0 already created `personalized_food_descriptions` with every column Stage 2 writes (`description`, `tokens`, `image_url`, `similarity_score_on_insert`, plus the timestamp pair). The `uq_personalized_food_descriptions_query_id` unique index continues to guarantee one row per dish upload; Stage 2's retry-idempotency code path explicitly avoids triggering an `IntegrityError` by checking for row existence first rather than catching the exception (cleaner logs, avoids spurious `INSERT ... ON CONFLICT` semantics).

#### To Delete

None.

#### To Update

None.

#### To Add New

None.

---

### CRUD

No new CRUD. Stage 2 consumes the Stage 0 surface verbatim:

- `crud_personalized_food.insert_description_row(user_id, query_id, *, image_url, description, tokens, similarity_score_on_insert)` — already exists.
- `crud_personalized_food.get_all_rows_for_user(user_id, exclude_query_id=None)` — already exists (called indirectly via `personalized_food_index.search_for_user`).
- `crud_food_image_query.get_dish_image_query_by_id(query_id)` — already exists; used twice — once to read `record.user_id` and `record.image_url`, and once to pull the referenced dish's `result_gemini.step1_data` so we can populate `reference_image.prior_step1_data`.
- `crud_food_image_query.update_dish_image_query_results(query_id, result_openai, result_gemini)` — already exists; called twice from the task (once right after Phase 1.1.1, once after Phase 1.1.2 success).

**New helper needed in the orchestrator** (not CRUD-layer, keep it in `personalized_reference.py`): a `_row_exists_for_query(query_id)` probe. Thin; composes `crud_personalized_food.get_all_rows_for_user(user_id, exclude_query_id=None)` and checks membership, OR issues a direct `SELECT 1 FROM personalized_food_descriptions WHERE query_id = ?`. The cleaner option is a small addition to CRUD:

- **Add to `backend/src/crud/crud_personalized_food.py`:** `get_row_by_query_id(query_id: int) -> Optional[PersonalizedFoodDescription]`. Single-row lookup by the unique `query_id`. Returns the full row so callers can introspect `similarity_score_on_insert`, `description`, etc., when useful. Reuses the same `SessionLocal` pattern as the other four functions in this module.

This is a minimal, mechanical addition — not a schema change, not a new index (the existing unique index on `query_id` already serves the lookup).

#### To Delete

None.

#### To Update

- `backend/src/crud/crud_personalized_food.py` — append `get_row_by_query_id(query_id)`. No signature changes elsewhere.

#### To Add New

- `get_row_by_query_id(query_id: int) -> Optional[PersonalizedFoodDescription]` in the existing `crud_personalized_food.py`.

---

### Services

Two new service modules.

#### `backend/src/service/llm/fast_caption.py`

```python
async def generate_fast_caption_async(image_path: Path) -> str:
    """
    Run Gemini 2.0 Flash against the uploaded image and return a short,
    free-text dish description. Plain-text response — no structured output,
    no Pydantic schema, no thinking budget.

    Raises:
        ValueError: if GEMINI_API_KEY is missing or the API call fails
        FileNotFoundError: if image_path does not resolve on disk
    """
```

Implementation mirrors `analyze_step1_component_identification_async` but drops every structured-output affordance:

- `client.models.generate_content(model="gemini-2.0-flash", contents=[caption_instructions, image_part], config=types.GenerateContentConfig(temperature=0))`.
- No `response_mime_type`, no `response_schema`, no `thinking_config` — a single `response.text` strip is the full return.
- The `caption_instructions` string is a ~5-line inline prompt ("Describe the dish in the image in one short sentence. Use simple, concrete words — list main visible foods, cooking style if obvious, and any distinctive ingredients. Do not include nutrition, prices, or speculation."). Kept inline rather than in a `.md` resource because it is a single line of prompt engineering and a file read adds no value for this call shape.
- Reads the image via `open(image_path, "rb").read()` + `types.Part.from_bytes(data=..., mime_type="image/jpeg")` — same pattern as the existing analyzers.
- `loop.run_in_executor(None, _sync_gemini_call)` wrapper so the FastAPI event loop stays responsive.
- Pricing: `gemini-2.0-flash` is **not** currently in `src/service/llm/pricing.py`. Stage 2 does **not** add it to the pricing table — there is no downstream consumer of the flash call's token counts (the result is unstructured; we neither return it to the user nor record it on `result_gemini`). If we later want flash cost tracking, extend `pricing.py` then. Out of scope here.

#### `backend/src/service/personalized_reference.py`

```python
async def resolve_reference_for_upload(
    user_id: int,
    query_id: int,
    image_path: Path,
) -> Optional[Dict[str, Any]]:
    """
    Run Phase 1.1.1: fast caption, per-user BM25 search, write-after-read
    insert into personalized_food_descriptions. Returns the reference
    payload the caller should stash on result_gemini.reference_image, or
    None on cold start, below-threshold match, graceful-degrade, or
    retry-idempotency short-circuit.
    """
```

Logic (ordered):

1. **Retry idempotency** — `existing = crud_personalized_food.get_row_by_query_id(query_id)`. If `existing is not None`, log INFO "Phase 1.1.1 skipped on retry for query_id=%s" and return `None`. The prior attempt's `reference_image` (if any) is already persisted on `result_gemini`; the caller writes the new Phase 1.1.2 result without overwriting it.
2. **Fast caption (with graceful degrade)** — `try: description = await generate_fast_caption_async(image_path) except (ValueError, FileNotFoundError) as exc: log.warning(...); return None`. A `FileNotFoundError` in particular is a real bug (the image should exist when the background task fires), but we still degrade rather than raise — the retry path is available if the user wants to re-analyze. No row inserted on this path.
3. **Tokenize** — `query_tokens = personalized_food_index.tokenize(description)`. Empty tokens (e.g. fast-caption returns "..."): skip the search and treat as "no match". Still insert the row with the raw description so future uploads see the history.
4. **Search** — `matches = personalized_food_index.search_for_user(user_id, query_tokens, top_k=1, min_similarity=THRESHOLD_PHASE_1_1_1_SIMILARITY, exclude_query_id=query_id)`. The `exclude_query_id` parameter is redundant given the write-after-read order, but keep it as belt-and-suspenders so a future refactor that swaps ordering cannot silently break self-match prevention.
5. **Resolve reference record** — if `matches`, take `top = matches[0]`, call `get_dish_image_query_by_id(top["query_id"])` to fetch the referenced dish, pull `result_gemini.step1_data` as `prior_step1_data`. If the referenced dish has no `step1_data` yet (edge case: its Phase 1.1.2 never completed), set `prior_step1_data = None` and continue — the top-1 row is still a valid reference for Stage 3's image pair even if we can't carry a prior `step1_data`.
6. **Read uploader's image URL** — the caller does not pass it in. Pull `record = crud_food_image_query.get_dish_image_query_by_id(query_id)` to fetch `record.image_url`. Persistence of `image_url` on the personalization row lets Stage 6 read it without a second join (see Stage 0 docs).
7. **Insert (write-after-read)** — `crud_personalized_food.insert_description_row(user_id, query_id, image_url=record.image_url, description=description, tokens=query_tokens, similarity_score_on_insert=(top["similarity_score"] if matches else None))`. Wrap in a try-except for `IntegrityError` (race with a concurrent retry); on conflict, log WARN and proceed — the reference payload we already computed is still valid to return.
8. **Return** — the reference dict from step 5, or `None` if no match.

**Async vs sync boundary.** `generate_fast_caption_async` is `await`ed; `search_for_user`, `get_row_by_query_id`, `get_dish_image_query_by_id`, and `insert_description_row` are all sync. The orchestrator is declared `async def` and `await`s only the caption. This matches the existing `analyze_image_background` style.

#### Configs

Append to `backend/src/configs.py`:

```python
# Stage 2 (Phase 1.1.1) — minimum similarity_score a top-1 match must clear
# to be attached as a reference. Relative ranking signal (max-in-batch
# normalization, see docs/technical/dish_analysis/personalized_food_index.md);
# 0.25 is a soft floor that mainly rejects corpora with zero lexical overlap.
# Re-tune after we collect real retrieval-quality data post-launch.
THRESHOLD_PHASE_1_1_1_SIMILARITY = 0.25
```

Placed directly under `DATABASE_DIR` (added in Stage 1). Import in `personalized_reference.py` as `from src.configs import THRESHOLD_PHASE_1_1_1_SIMILARITY`.

#### To Delete

None.

#### To Update

- `backend/src/configs.py` — append `THRESHOLD_PHASE_1_1_1_SIMILARITY = 0.25`.

#### To Add New

- `backend/src/service/llm/fast_caption.py` — `generate_fast_caption_async`.
- `backend/src/service/personalized_reference.py` — `resolve_reference_for_upload`.

---

### API Endpoints

None. Stage 2 exposes no new routes. All behavior rides on the existing `POST /api/date/{Y}/{M}/{D}/upload` (+ `upload-url`) background task and is observed via the existing `GET /api/item/{record_id}` poll — which now silently starts returning a `reference_image` key inside `result_gemini`.

The retry route (`POST /api/item/{record_id}/retry-step1`) is unchanged. The retry-idempotency logic lives inside the orchestrator, not in the HTTP handler.

#### To Delete

None.

#### To Update

None.

#### To Add New

None.

---

### Testing

Test location: `backend/tests/`. Stage 2 uses the existing `conftest.py` harness; no new fixtures required. Unit tests mock the Gemini API at the `generate_fast_caption_async` boundary (monkeypatch `google.genai.Client` like the existing Phase 1 tests do). Integration tests exercise `resolve_reference_for_upload` end-to-end against a SQLite in-memory (or the dev Postgres — match whatever `test_crud_personalized_food.py` uses).

**Unit tests — fast caption (`backend/tests/test_fast_caption.py`):**

- `test_generate_fast_caption_async_returns_plain_text` — monkeypatch the Gemini client to return a `response.text` of `"grilled chicken with rice and cucumber"`. Assert the helper returns the same string (stripped).
- `test_generate_fast_caption_async_raises_on_missing_api_key` — pop `GEMINI_API_KEY` from the environment; assert `ValueError`.
- `test_generate_fast_caption_async_raises_on_api_error` — monkeypatch client to raise; assert `ValueError("Error calling Gemini API (Fast Caption): ...")`.
- `test_generate_fast_caption_async_propagates_file_not_found` — point at a non-existent image path; assert `FileNotFoundError` propagates (do not wrap).

**Unit tests — orchestrator (`backend/tests/test_personalized_reference.py`):**

- `test_resolve_reference_cold_start_returns_none_and_inserts_row` — user with zero prior rows, fast-caption returns `"chicken rice"`. Assert return is `None`, a row is inserted, and `similarity_score_on_insert is None`.
- `test_resolve_reference_warm_user_returns_reference` — user with one prior row that tokens-overlaps the caption. Assert return has `query_id == prior.query_id`, `similarity_score >= 0.25`, `prior_step1_data` matches the prior record's `result_gemini.step1_data`.
- `test_resolve_reference_excludes_self` — set up a scenario where a row for this `query_id` could theoretically be in the corpus (simulate a racing insert by pre-seeding). Assert the returned reference does NOT have `query_id == this_query_id`.
- `test_resolve_reference_below_threshold_returns_none_but_inserts_row` — prior rows exist, but their tokens barely overlap the caption; top similarity is below `0.25`. Assert return is `None`, new row is still inserted.
- `test_resolve_reference_retry_short_circuits_when_row_exists` — pre-insert a row with this `query_id`. Call `resolve_reference_for_upload`; assert `generate_fast_caption_async` is NOT called (patch and check `call_count == 0`), return is `None`, row count unchanged.
- `test_resolve_reference_graceful_degrade_on_caption_failure` — monkeypatch `generate_fast_caption_async` to raise `ValueError("Gemini down")`. Assert return is `None`, no row inserted, warning logged.
- `test_resolve_reference_graceful_degrade_on_image_missing` — monkeypatch caption to raise `FileNotFoundError`. Assert return is `None`, no row inserted.
- `test_resolve_reference_handles_prior_step1_data_missing` — seed a prior row whose `DishImageQuery.result_gemini.step1_data` is `None` (Phase 1.1.2 never completed). Current upload matches it. Assert the returned reference has `prior_step1_data: None` and is otherwise well-formed.
- `test_resolve_reference_cross_user_isolation` — seed rows under user B that would match. Call for user A. Assert return is `None` and the returned `matches` never surface user B's rows (verify via DB query post-call that user A's row count is 1).
- `test_resolve_reference_tokenize_empty_description_inserts_row_without_search` — monkeypatch caption to return `"..."` (tokenizer emits `[]`). Assert return is `None`, row IS inserted with `tokens=[]`. No call to `search_for_user` (patch and check `call_count == 0`).

**Unit tests — CRUD addition (`backend/tests/test_crud_personalized_food.py`):**

Append to the existing test file:

- `test_get_row_by_query_id_returns_row` — insert a row; `get_row_by_query_id(query_id)` returns it.
- `test_get_row_by_query_id_returns_none_for_missing` — returns `None` for a non-existent `query_id`.

**Integration test — pipeline (`backend/tests/test_item_step1_tasks.py`):**

Extend the existing file:

- `test_analyze_image_background_persists_reference_image_key_on_cold_start` — monkeypatch both the fast-caption and Step 1 Pro calls; invoke the background task end-to-end; assert `result_gemini.reference_image is None` (key present, value null) and `result_gemini.step1_data` is populated.
- `test_analyze_image_background_persists_reference_image_key_on_warm_user` — same but with a prior row in `personalized_food_descriptions` that the caption matches; assert `result_gemini.reference_image.query_id` equals the prior record's id.
- `test_analyze_image_background_preserves_reference_image_on_phase1_1_2_failure` — monkeypatch fast-caption to succeed, Step 1 Pro to raise. Assert that after the task, `result_gemini.reference_image` is set AND `result_gemini.step1_error` is set. Proves Phase 1.1.1's output survives Phase 1.1.2 failure.
- `test_analyze_image_background_retry_does_not_duplicate_row` — first run (both phases succeed) inserts a row and populates `reference_image`. Second run against the same `query_id` (simulate by re-invoking the task; in production this is gated behind `/retry-step1`): assert row count for the user is unchanged AND the previously-written `reference_image` is preserved (not overwritten with `null` / stale data).

**Pre-commit loop (mandatory per skill rules):**

1. `source venv/bin/activate && pre-commit run --all-files`.
2. Fix any lint / line-count issues. `personalized_reference.py` is likely to land near 80 lines; well under the 300-line cap. `fast_caption.py` is ~60 lines.
3. Re-run pre-commit — Prettier may reshape fixes. Run again. No frontend files in Stage 2 so the frontend line cap is not relevant.
4. Repeat until clean.

**Acceptance check from the issue's "done when":**

- Uploading two photos under the same user causes the second upload's `result_gemini.reference_image` to point at the first; the first upload's `reference_image` is `null`. Verify via the Chrome spec's Tests 1 + 2 (desktop) and 6 + 7 (mobile).
- Schema migration applied to dev DB — no-op for Stage 2 (Stage 0 shipped the schema).

#### To Delete

None.

#### To Update

- `backend/tests/test_crud_personalized_food.py` — two new tests for `get_row_by_query_id`.
- `backend/tests/test_item_step1_tasks.py` — four new end-to-end tests listed above.

#### To Add New

- `backend/tests/test_fast_caption.py` — unit tests for the Gemini 2.0 Flash wrapper.
- `backend/tests/test_personalized_reference.py` — unit tests for the orchestrator.

---

### Frontend

No UI changes in Stage 2. The new `result_gemini.reference_image` key is read by **no** frontend component yet. The existing `ItemV2.jsx` + `useItemPolling.js` + `PhaseErrorCard.jsx` flow continues to work unchanged; the polling response simply carries an additional key the frontend ignores.

Visual regression risk: zero (no markup changes, no new props, no service calls).

#### To Delete

None.

#### To Update

None.

#### To Add New

None.

---

### Documentation

Stage 2 is the first stage in the series to produce a user-observable (behavior, not UI) change: the pipeline learns to retrieve references. The documentation pass flips the Stage 0 forward-reference into a real sub-section and adds a one-paragraph note to the abstract layer.

#### Abstract (`docs/abstract/`)

- **Update** `docs/abstract/dish_analysis/component_identification.md` — add a one-paragraph "Personalization (silent in this stage)" note:
  - What: the system now remembers the dishes each user has uploaded so that future uploads can benefit from the history.
  - Why (from the user's perspective): cooking-style / portion / regional-variant details often repeat for the same user; reusing past analyses improves accuracy.
  - Scope caveat: in this stage the retrieval is invisible; the measurable benefit arrives when Stage 3 starts attaching the reference to the Phase 1 call.
  - Keep the existing Phase 1 user-flow description otherwise untouched.
- No changes to `docs/abstract/dish_analysis/index.md` — the per-feature row still accurately describes the two-phase workflow.
- No changes to `docs/abstract/dish_analysis/nutritional_analysis.md` or `user_customization.md` — Stage 2 touches Phase 1 only.

#### Technical (`docs/technical/`)

- **Update** `docs/technical/dish_analysis/component_identification.md`:
  - Promote the existing "Personalization Store (foundation, not yet consumed)" forward-reference under **Data Model** into a full "Phase 1.1.1 — Fast Caption + Reference Retrieval" sub-section, inserted **before** the current **Pipeline** section. This sub-section covers:
    - **Architecture** — Gemini 2.0 Flash caption, per-user BM25 over `personalized_food_descriptions`, write-after-read insertion.
    - **Pipeline** — the ASCII flow from the "Key Workflow" section of this plan.
    - **Data Model** — the new `result_gemini.reference_image` key and its nullable-dict shape.
    - **Backend — Service Layer** — signatures of `generate_fast_caption_async` and `resolve_reference_for_upload`.
    - **Failure Modes** — the five-row table from the "Proposed Solution" section of this plan.
  - Extend the existing **Pipeline** ASCII diagram so the Phase 1.1.1 block precedes the existing Step 1 Pro call. One new box before the `get_step1_component_identification_prompt()` line; one new `result_gemini.reference_image` persistence step.
  - Extend the **Component Checklist** at the bottom with:
    - `[x] generate_fast_caption_async() — Gemini 2.0 Flash plain-text wrapper (backend/src/service/llm/fast_caption.py)`
    - `[x] resolve_reference_for_upload() — Phase 1.1.1 orchestrator (backend/src/service/personalized_reference.py)`
    - `[x] analyze_image_background() extended — Phase 1.1.1 call + reference_image persistence`
    - `[x] THRESHOLD_PHASE_1_1_1_SIMILARITY = 0.25 config constant`
    - `[x] crud_personalized_food.get_row_by_query_id — retry-idempotency probe`
    - `[ ] Stage 3 (Phase 1.1.2): reference image + prior_step1_data injected into the Step 1 Pro call`
- **Update** `docs/technical/dish_analysis/personalized_food_index.md`:
  - Flip the Component Checklist row `[ ] Stage 2 (Phase 1.1.1): fast-caption + retrieval wired into analyze_image_background` to `[x]` and add a one-line link back to the component-identification page.
  - Add a one-paragraph note in **Constraints & Edge Cases** clarifying that the write-after-read contract is now double-guarded: `search_for_user(..., exclude_query_id=query_id)` (filter) **plus** insert-after-search (order). Stage 2 relies on both.
- **No change** to `docs/technical/dish_analysis/nutritional_analysis.md`, `user_customization.md`, or `nutrition_db.md` — Stage 2 does not touch Phase 2 or the nutrition DB.

#### API Documentation (`docs/api_doc/`)

No changes needed — Stage 2 adds no API endpoints and does not change the request / response contract of any existing endpoint. The `result_gemini` blob already carries arbitrary JSON through `GET /api/item/{record_id}`; a new top-level key is a non-breaking addition.

(The project does not yet ship a `docs/api_doc/` tree; no seeding is required for this stage.)

#### To Delete

None.

#### To Update

- `docs/abstract/dish_analysis/component_identification.md` — one-paragraph "Personalization (silent)" note.
- `docs/technical/dish_analysis/component_identification.md` — new Phase 1.1.1 sub-section, pipeline diagram extension, Component Checklist additions.
- `docs/technical/dish_analysis/personalized_food_index.md` — flip Stage 2 checklist row, expand Constraints note.

#### To Add New

None — all changes are appendages to existing docs.

---

### Chrome Claude Extension Execution

**Included this stage.** Spec at `docs/chrome_test/260418_2013_stage2_phase1_1_1_fast_caption.md` (generated via the `chrome-test-generate` sub-skill). The spec contains 10 tests — 5 desktop + 5 mobile — exercising:

- Cold-start (`reference_image === null` on first upload).
- Warm-start match (`reference_image.query_id` points at the prior upload; `similarity_score >= 0.25`).
- Cross-user isolation (user B never sees user A's rows).
- Unrelated image edge case (`reference_image === null` even with history).
- Retry-step1 idempotency (no duplicate personalization row; prior `reference_image` preserved).

**Scope caveats in the spec:**

- Stage 2 ships no DOM change, so every retrieval assertion runs via `javascript_tool` + in-page `fetch(/api/item/{id})` on the backend payload. DOM screenshots prove the UI did not regress.
- Test 5 (retry idempotency) requires a selective Phase-1.1.2 failure-injection mechanism; the spec flags that this may reduce to "toggle `GEMINI_API_KEY`" which affects both phases. Document the chosen injection path in `docs/technical/testing_context.md` before the first run.
- `docs/technical/testing_context.md` does not exist in the repo today, so the spec uses two placeholder usernames (`test_user_alpha`, `test_user_beta`) — the operator replaces them with seeded dev-DB usernames before running.

Execution flow: after Stage 2 code lands, `feature-implement-full` (or the operator manually, via `/webapp-dev:chrome-test-execute`) will run the spec and fill in each test's Report block.

#### To Delete

None.

#### To Update

None.

#### To Add New

- `docs/chrome_test/260418_2013_stage2_phase1_1_1_fast_caption.md` (already written by `chrome-test-generate` in Step 1.6).

---

## Dependencies

- **Stage 0 (Phase 0 foundation)** — consumed verbatim: `personalized_food_descriptions` table, `crud_personalized_food.insert_description_row / get_all_rows_for_user`, `personalized_food_index.tokenize / search_for_user`. A new `crud_personalized_food.get_row_by_query_id` helper is appended in this stage; the addition is mechanical and does not change the Stage 0 contract.
- **Existing Phase 1 pipeline** — `analyze_image_background` (`item_step1_tasks.py`), `get_step1_component_identification_prompt`, `analyze_step1_component_identification_async`, and the `persist_phase_error` helper. None of these change behavior; they get one new call inserted ahead of them.
- **Existing Gemini infrastructure** — `GEMINI_API_KEY` env var, `google.genai.Client`, `loop.run_in_executor` pattern. The new `fast_caption.py` module reuses all three.
- **No frontend dependencies** — Stage 2 ships no UI.
- **No new external libraries** — `rank-bm25` arrived in Stage 0. The Gemini SDK is already a project dependency.

---

## Resolved Decisions

- **Fast-caption failure policy — graceful degrade, no row inserted** (confirmed with user 2026-04-18). If Gemini 2.0 Flash fails (rate limit, network, parse, missing key), log a warning, set `result_gemini.reference_image = null`, and do **not** insert a personalization row for this upload. Phase 1.1.2 proceeds as today's single-image call. Trade-off: a transient fast-caption outage creates a permanent gap in the user's personalization corpus for the affected uploads. Acceptable — the missing rows don't break any invariant, and the user can always re-trigger via `/retry-step1` once the outage clears (the retry path now re-runs Phase 1.1.1 because no row exists yet for that `query_id`).
- **Retry behavior — skip Phase 1.1.1 if a row already exists for this `query_id`** (confirmed with user 2026-04-18). The retry endpoint does not differentiate "first failure" from "N-th retry"; the orchestrator queries the DB at entry and short-circuits. Trade-off: if a prior Phase 1.1.1 succeeded with a stale caption (e.g. image was re-uploaded into the same slot before the retry — today this is prevented because `replace_slot_atomic` creates a new `query_id`), the retry uses the stale caption. Considered acceptable because the slot-replacement always mints a new query row, so this corner case cannot actually occur under the current upload contract.
- **Module location for the fast-caption wrapper — `backend/src/service/llm/fast_caption.py`** (confirmed with user 2026-04-18). Sits next to `gemini_analyzer.py` because it is an LLM-call wrapper, not a service primitive. The issue's pin and the architectural affinity agree; the discussion diagram's `backend/src/service/fast_caption.py` path is superseded.
- **Threshold value — `THRESHOLD_PHASE_1_1_1_SIMILARITY = 0.25`** (pinned by the issue). Retained as-is. Document explicitly (in the technical doc's Constraints & Edge Cases subsection) that `similarity_score` is a max-in-batch relative ranking signal, so the threshold mainly filters out corpora with zero lexical overlap rather than "bad" matches in the absolute sense. Re-tune after we have real retrieval-quality data post-launch.
- **`reference_image` persistence timing — write it to the DB immediately after Phase 1.1.1 completes, before the Step 1 Pro call** (decision recorded by the planner). This ensures a Phase 1.1.2 failure does not destroy Phase 1.1.1's output, matching the cross-stage invariant "phase independence on `result_gemini`" in the issue. Requires two `update_dish_image_query_results` calls in `analyze_image_background` on the success path (one post-Phase-1.1.1, one post-Phase-1.1.2 merge). The second call reads the current `result_gemini` and merges, so `reference_image` carries through. Trade-off: two DB writes per upload instead of one. Acceptable — each write is a single-row UPDATE on a primary-key lookup, <1 ms.
- **Failure-injection for Test 5 (retry idempotency) — `GEMINI_API_KEY` toggle today; dedicated dev knob deferred** (decision recorded by the planner). `GEMINI_API_KEY` unset affects both Phase 1.1.1 AND Phase 1.1.2; the test as written accepts this coupling and records which phase failed. A cleaner selective-failure knob (e.g. env var `FORCE_PHASE_1_1_2_FAILURE=true`) would make the retry path easier to exercise but is out of scope for Stage 2; add only if the test repeatedly produces ambiguous reports.

## Open Questions

None — all decisions resolved 2026-04-18. Ready for implementation.
