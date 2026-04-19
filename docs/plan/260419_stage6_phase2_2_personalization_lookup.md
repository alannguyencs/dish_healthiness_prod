# Stage 6 — Phase 2.2: Personalization Lookup

**Feature**: Wire the per-user BM25 corpus (Stage 0 foundation + Stage 2's caption rows + Stage 4's confirmed enrichment) into the Phase 2 background task as a **parallel** lookup to Phase 2.1. `lookup_personalization(user_id, query_id, description, confirmed_dish_name)` returns up to 5 historical matches — each joined back to its `DishImageQuery` so downstream stages get `prior_step2_data` + `corrected_step2_data` without a second query. Persisted on `result_gemini.personalized_matches` before the Gemini Pro call so a Step 2 failure / retry preserves the lookup.
**Plan Created:** 2026-04-19
**Status:** Plan
**Reference**:
- [Issues — 260415, Stage 6](../issues/260415.md)
- [Discussion — Food DB investigation & end-to-end redesign](../discussion/260418_food_db.md)
- [Plan — Stage 0 Personalized Food Index](./260418_stage0_personalized_food_index.md) (foundation)
- [Plan — Stage 2 Phase 1.1.1](./260418_stage2_phase1_1_1_fast_caption.md) (writes `tokens` + `description`)
- [Plan — Stage 4 Phase 1.2](./260418_stage4_phase1_2_confirm_enriches_personalization.md) (writes `confirmed_tokens` + `confirmed_dish_name`)
- [Plan — Stage 5 Phase 2.1](./260419_stage5_phase2_1_nutrition_db_lookup.md) (parallel sibling; Stage 6 joins the same gather)
- [Abstract — Nutritional Analysis](../abstract/dish_analysis/nutritional_analysis.md)
- [Technical — Nutritional Analysis](../technical/dish_analysis/nutritional_analysis.md)
- [Technical — Personalized Food Index](../technical/dish_analysis/personalized_food_index.md)
- [Chrome Test Spec — 260419_1034](../chrome_test/260419_1034_stage6_phase2_2_personalization_lookup.md)

---

## Problem Statement

1. Stage 0 shipped the per-user BM25 foundation and Stages 2 / 4 populate the three query-time fields on `personalized_food_descriptions` (`description`, `tokens`, `confirmed_dish_name`, `confirmed_tokens`). No consumer reads those rows during Phase 2 yet; the personalization corpus is effectively write-only.
2. The end-to-end workflow in `docs/discussion/260418_food_db.md` pairs Phase 2.2 with Phase 2.1 as two **parallel** lookups that both complete before Phase 2.3 (Stage 7's Pro prompt). Running them sequentially would add ~50–100 ms of perceived latency to the confirm → Step 2 loop for every upload; running them in parallel keeps Phase 2 on the same wall-clock budget as Stage 5 alone.
3. The return shape is fixed by Stage 7's prompt and Stage 8's UI. Each match must carry `query_id`, `image_url`, `description`, `similarity_score`, and — crucially — `prior_step2_data` (from the referenced dish's own Phase 2 result) plus `corrected_step2_data` (from the personalization row; Stage 8 writes it). Stage 0's `search_for_user` returns a `row` key with the full ORM object; Stage 6 translates that into the Stage 7 / Stage 8 shape and drops the ORM handle.
4. Token source is the union of `tokenize(description)` (cached on `result_gemini.reference_image.description` from Phase 1.1.1) and `tokenize(confirmed_dish_name)`. Union — not concatenation — because the same token shouldn't be counted twice for BM25 scoring. When either is missing (cold-start Phase 1.1.1 degraded, or empty confirmed_dish_name), the remaining side should still produce a usable query.
5. Two failure modes need explicit handling:
   - **Phase 2.2 raises while Phase 2.1 succeeds (or vice versa).** `asyncio.gather` by default propagates the first exception and cancels the other. That would make a transient personalization bug take down Phase 2 entirely. Per user decision 2026-04-19, use `return_exceptions=True`: substitute the failing half's result with an empty shape and log WARN.
   - **User has no prior rows / no rows above threshold.** `[]` is a valid outcome; the stage must not error out on cold-start users.

---

## Proposed Solution

Two artifacts — one new service module, one signature-free extension on `trigger_step2_analysis_background`.

### 1. `backend/src/service/personalized_lookup.py` (new)

Public surface: one function.

```python
def lookup_personalization(
    user_id: int,
    query_id: int,
    description: Optional[str],
    confirmed_dish_name: str,
    top_k: int = 5,
    min_similarity: float = 0.30,
) -> List[Dict[str, Any]]:
    """
    Search the user's personalization corpus using tokens unioned from
    `description` (Phase 1.1.1 caption) and `confirmed_dish_name`
    (Stage 4 post-confirm). Returns up to `top_k` historical matches
    joined back to their DishImageQuery rows for `prior_step2_data`
    and to the personalization row itself for `corrected_step2_data`.
    """
```

Logic (ordered):

1. Build `query_tokens` = `list(set(tokenize(description)) | set(tokenize(confirmed_dish_name)))`. Empty union → return `[]` immediately. Order is undefined (set) — BM25 doesn't care.
2. Call `personalized_food_index.search_for_user(user_id, query_tokens, top_k=top_k, min_similarity=min_similarity, exclude_query_id=query_id)`. The existing Stage 0 helper already applies per-user scoping, threshold filtering, and self-exclusion.
3. For each hit, join back to the referenced `DishImageQuery` via `get_dish_image_query_by_id(hit["query_id"])` to pull `result_gemini.step2_data`. Stage 8's `corrected_step2_data` lives on the personalization row itself — Stage 0's `row` field on the hit carries it.
4. Reshape each hit: drop the `row` ORM handle, add `prior_step2_data` and `corrected_step2_data`.

Shape per match:

```python
{
    "query_id": int,                         # referenced DishImageQuery id
    "image_url": str | None,                 # referenced dish's image
    "description": str | None,               # Phase 1.1.1 caption on the referenced row
    "similarity_score": float,               # 0..1, normalized by max-in-batch
    "prior_step2_data": Dict | None,         # referenced dish's result_gemini.step2_data (may be null on mid-pipeline referents)
    "corrected_step2_data": Dict | None,     # personalization row's corrected_step2_data (null until Stage 8)
}
```

Module-private helper:

- `_build_query_tokens(description, confirmed_dish_name) -> List[str]` — union + empty-guard; keeps the function body under the pylint complexity limit.

No class — mirrors the pattern of `personalized_reference.py`, `nutrition_lookup.py`.

### 2. `backend/src/api/item_tasks.py::trigger_step2_analysis_background` — parallel gather

Refactor the Stage 5 block (which currently calls `extract_and_lookup_nutrition` synchronously) into a concurrent `asyncio.gather` that also calls `lookup_personalization`. Both halves keep their current sync signatures — the task wraps each in `asyncio.to_thread` so the gather runs them on the default executor.

```python
import asyncio

# Read user_id + reference description from the record before kicking off
# the parallel lookups.
record = get_dish_image_query_by_id(query_id)
if not record or record.result_gemini is None:
    logger.warning("Phase 2 skipped parallel lookups for query_id=%s (no result_gemini)", query_id)
    nutrition_db_matches = extract_and_lookup_nutrition(dish_name, components)  # still run Phase 2.1
    personalized_matches: List[Dict[str, Any]] = []
else:
    user_id = record.user_id
    ref_description = (record.result_gemini.get("reference_image") or {}).get("description")

    nutrition_task = asyncio.to_thread(extract_and_lookup_nutrition, dish_name, components)
    personalization_task = asyncio.to_thread(
        lookup_personalization,
        user_id,
        query_id,
        ref_description,
        dish_name,
    )
    nutrition_result, personalization_result = await asyncio.gather(
        nutrition_task, personalization_task, return_exceptions=True
    )
    nutrition_db_matches = _safe_phase_2_1_result(nutrition_result, dish_name, query_id)
    personalized_matches = _safe_phase_2_2_result(personalization_result, query_id)

_persist_pre_pro_state(query_id, nutrition_db_matches, personalized_matches)
```

The two guard helpers are module-private in `item_tasks.py`:

- `_safe_phase_2_1_result(result_or_exc, dish_name, query_id)` — if it's an Exception, log WARN and return the Stage 5 empty-response shape for the dish name; otherwise return the result unchanged.
- `_safe_phase_2_2_result(result_or_exc, query_id)` — if it's an Exception, log WARN and return `[]`; otherwise return the result unchanged.

The Stage 5 `_persist_nutrition_db_matches` helper is generalized to `_persist_pre_pro_state(query_id, nutrition_db_matches, personalized_matches)` that writes both keys in a single update.

### 3. `backend/src/configs.py` — one new constant

```python
# Stage 6 (Phase 2.2) — minimum similarity_score a personalization match must
# clear to be surfaced. Relative ranking signal (same max-in-batch normalization
# as Stage 2). 0.30 is the issue-pinned threshold; re-tune after real data.
THRESHOLD_PHASE_2_2_SIMILARITY = 0.30
```

### Why `asyncio.to_thread` and not `asyncio` internally

`extract_and_lookup_nutrition` (Stage 5) and `lookup_personalization` (new) are both sync — BM25 scoring + DB reads. Making them `async def` with internal `asyncio.to_thread` would hide their sync nature and create surface area at the call site. Keeping them sync + having the caller schedule on the default executor leaves the signatures honest and makes the parallel-gather intent explicit in the task file.

### Why not merge `nutrition_db_matches` and `personalized_matches` at the record layer

They're semantically different signals — Phase 2.1 is reference data, Phase 2.2 is this user's history. Stage 7 will threshold-gate each independently. Keeping separate `result_gemini.{nutrition_db_matches, personalized_matches}` keys matches the discussion doc and gives Stage 8 two distinct UI panels to render.

---

## Current Implementation Analysis

### What Exists (keep as-is)

| Component | File | Status |
|-----------|------|--------|
| Per-user BM25 foundation | `backend/src/service/personalized_food_index.py` | Keep — `search_for_user(...)` is the single BM25 call Stage 6 makes. |
| Stage 0 CRUD (`get_all_rows_for_user`, `insert_description_row`, etc.) | `backend/src/crud/crud_personalized_food.py` | Keep — Stage 6 reads rows via `search_for_user`, not directly. |
| Stage 2's `reference_image.description` on `result_gemini` | Written by `personalized_reference.py` | Keep — Stage 6 reads it verbatim. |
| Stage 4's `confirmed_dish_name` / `confirmed_tokens` on the personalization row | Written by `confirm_step1_and_trigger_step2` | Keep — already flows into the BM25 corpus via `row.tokens` at index time. Stage 6 queries the union with `tokenize(confirmed_dish_name)` at the query side. |
| Stage 5's Phase 2.1 orchestrator | `backend/src/service/nutrition_lookup.py::extract_and_lookup_nutrition` | Keep — Stage 6 runs it in parallel via gather. No signature change. |
| Stage 5's `_persist_nutrition_db_matches` helper | `backend/src/api/item_tasks.py` | Rename to `_persist_pre_pro_state`; write both keys in one go. |
| Phase 2 pipeline otherwise | `trigger_step2_analysis_background` → Pro call → success merge / error path | Keep — Stage 6 only replaces the pre-Pro block. |
| Retry endpoint | `backend/src/api/item_retry.py::retry_step2_analysis` | Keep — unchanged. The retry path reuses the persisted `personalized_matches` (and re-runs Phase 2.1/2.2 in parallel via the same task). |
| Frontend Step 2 view | `frontend/src/pages/ItemV2.jsx`, `Step2Results.jsx` | Keep — Stage 6 adds a new `result_gemini.personalized_matches` key the frontend ignores until Stage 8. |

### What Changes

| Component | Current | Proposed |
|-----------|---------|----------|
| `backend/src/service/personalized_lookup.py` | Does not exist. | Adds `lookup_personalization(user_id, query_id, description, confirmed_dish_name, top_k=5, min_similarity=0.30)` + `_build_query_tokens`. |
| `backend/src/api/item_tasks.py::trigger_step2_analysis_background` | Stage 5 calls `extract_and_lookup_nutrition` synchronously. | Gathers Phase 2.1 + Phase 2.2 via `asyncio.gather(..., return_exceptions=True)`. Two guard helpers (`_safe_phase_2_1_result`, `_safe_phase_2_2_result`) convert unexpected exceptions into empty-shape fallbacks. `_persist_nutrition_db_matches` renamed to `_persist_pre_pro_state` and writes both keys atomically. |
| `backend/src/configs.py` | No `THRESHOLD_PHASE_2_2_*` constant. | Adds `THRESHOLD_PHASE_2_2_SIMILARITY = 0.30`. |
| `docs/abstract/dish_analysis/nutritional_analysis.md` | "Curated nutrition database (consulted silently)" paragraph added in Stage 5. | Extend with a parallel "Personalization history (consulted silently)" paragraph. |
| `docs/technical/dish_analysis/nutritional_analysis.md` | Phase 2.1 sub-section documents Stage 5. | Add "Phase 2.2 — Personalization Lookup (Stage 6)" sub-section; extend Pipeline ASCII with the parallel-gather step; update Component Checklist. |
| `docs/technical/dish_analysis/personalized_food_index.md` | Stage 6 row on the Component Checklist is `[ ]`. | Flip to `[x]`; append Stage 6 to "Downstream consumers". |

---

## Implementation Plan

### Key Workflow

```
trigger_step2_analysis_background(query_id, image_path, dish_name, components)
  │
  ▼
record = get_dish_image_query_by_id(query_id)
  │
  ├── record or result_gemini missing → fallback: Phase 2.1 only, personalized=[]
  │
  ▼ (happy path)
user_id = record.user_id
ref_description = (record.result_gemini or {}).get("reference_image", {}).get("description")
  │
  ▼ (NEW — Stage 6 parallel gather)
nutrition_task       = asyncio.to_thread(extract_and_lookup_nutrition, dish_name, components)
personalization_task = asyncio.to_thread(
    lookup_personalization, user_id, query_id, ref_description, dish_name
)
nutrition_result, personalization_result = await asyncio.gather(
    nutrition_task, personalization_task, return_exceptions=True
)
  │
  ▼ (convert exceptions to empty-shape fallbacks)
nutrition_db_matches = _safe_phase_2_1_result(nutrition_result, dish_name, query_id)
personalized_matches = _safe_phase_2_2_result(personalization_result, query_id)
  │
  ▼ (Stage 5 style — one pre-Pro write; now carries both keys)
_persist_pre_pro_state(query_id, nutrition_db_matches, personalized_matches)
  │
  ▼ (existing Stage 5 flow continues)
step2_prompt = get_step2_nutritional_analysis_prompt(dish_name, components)
step2_result = await analyze_step2_nutritional_analysis_async(image_path, step2_prompt, ...)
  │
  ▼ (success merge already re-reads result_gemini so both Stage 6 keys survive)
```

#### Failure paths

- **Phase 2.2 raises** — `_safe_phase_2_2_result` logs WARN with `query_id` + exception class; returns `[]`. Phase 2.1 is unaffected. Pro call runs.
- **Phase 2.1 raises** — `_safe_phase_2_1_result` logs WARN; returns Stage 5's empty-response shape with `match_summary.reason = "unexpected_exception"`. Phase 2.2 is unaffected. Pro call runs.
- **`record.result_gemini` is None** — Phase 1 never landed; fall back to the Stage 5 sequential path with `personalized_matches = []`. The Stage 5 path already tolerates this.
- **`user_id` resolution fails** — shouldn't happen (FK enforced) but the fallback path above handles it.

#### To Delete

None.

#### To Update

- `backend/src/api/item_tasks.py`:
  - Rename `_persist_nutrition_db_matches` → `_persist_pre_pro_state`; write both keys in one update.
  - Insert `asyncio.gather` block in `trigger_step2_analysis_background`.
  - Add `_safe_phase_2_1_result` + `_safe_phase_2_2_result` module-private helpers.
- `backend/src/configs.py`: append `THRESHOLD_PHASE_2_2_SIMILARITY = 0.30`.

#### To Add New

- `backend/src/service/personalized_lookup.py` — `lookup_personalization` + `_build_query_tokens`.

---

### Database Schema

**No changes.** Stage 0 shipped every column Stage 6 needs. Reads only.

#### To Delete

None.

#### To Update

None.

#### To Add New

None.

---

### CRUD

**No new CRUD.**

Stage 6 reads via two existing paths:

- `personalized_food_index.search_for_user(...)` — Stage 0 call; returns `row` ORM handles.
- `crud_food_image_query.get_dish_image_query_by_id(...)` — called once per match to fetch `prior_step2_data`. Up to 5 extra SELECTs per Phase 2 run; still sub-50-ms given how small each row read is. If this becomes a hot spot, a future optimization is a bulk `get_by_ids(query_ids)` helper — out of scope for Stage 6.

#### To Delete

None.

#### To Update

None.

#### To Add New

None.

---

### Services

#### `backend/src/service/personalized_lookup.py` (new)

```python
"""
Phase 2.2 (Stage 6) — per-user personalization retrieval.

Queries the user's personalized_food_descriptions corpus with the union
of caption tokens (from Phase 1.1.1 reference_image.description) and
confirmed_dish_name tokens (from Stage 4 post-confirm). Each hit is
joined back to its DishImageQuery row to carry prior_step2_data and
to the personalization row itself for corrected_step2_data (Stage 8).

Called from trigger_step2_analysis_background in parallel with
extract_and_lookup_nutrition via asyncio.gather.
"""

import logging
from typing import Any, Dict, List, Optional

from src.configs import THRESHOLD_PHASE_2_2_SIMILARITY
from src.crud.crud_food_image_query import get_dish_image_query_by_id
from src.service import personalized_food_index

logger = logging.getLogger(__name__)

DEFAULT_TOP_K = 5


def _build_query_tokens(description: Optional[str], confirmed_dish_name: str) -> List[str]:
    """Union of caption + confirmed-dish-name tokens; dedupes via set."""
    caption_tokens = set(personalized_food_index.tokenize(description or ""))
    dish_tokens = set(personalized_food_index.tokenize(confirmed_dish_name or ""))
    return list(caption_tokens | dish_tokens)


def lookup_personalization(
    user_id: int,
    query_id: int,
    description: Optional[str],
    confirmed_dish_name: str,
    top_k: int = DEFAULT_TOP_K,
    min_similarity: float = THRESHOLD_PHASE_2_2_SIMILARITY,
) -> List[Dict[str, Any]]:
    """Return up to top_k historical matches joined to their DishImageQuery."""
    query_tokens = _build_query_tokens(description, confirmed_dish_name)
    if not query_tokens:
        return []

    hits = personalized_food_index.search_for_user(
        user_id,
        query_tokens,
        top_k=top_k,
        min_similarity=min_similarity,
        exclude_query_id=query_id,
    )

    matches: List[Dict[str, Any]] = []
    for hit in hits:
        referenced = get_dish_image_query_by_id(hit["query_id"])
        prior_step2_data = None
        if referenced and referenced.result_gemini:
            prior_step2_data = referenced.result_gemini.get("step2_data")
        matches.append(
            {
                "query_id": hit["query_id"],
                "image_url": hit["image_url"],
                "description": hit["description"],
                "similarity_score": hit["similarity_score"],
                "prior_step2_data": prior_step2_data,
                "corrected_step2_data": getattr(hit["row"], "corrected_step2_data", None),
            }
        )
    return matches
```

#### `backend/src/api/item_tasks.py` — parallel gather + renamed persist helper

Pseudocode-level diff (exact wiring lives in the commit):

```python
# BEFORE (Stage 5):
nutrition_db_matches = extract_and_lookup_nutrition(dish_name, components)
_persist_nutrition_db_matches(query_id, nutrition_db_matches)

# AFTER (Stage 6):
record = get_dish_image_query_by_id(query_id)
user_id = record.user_id if record else None
ref_description = (
    (record.result_gemini or {}).get("reference_image", {}).get("description")
    if record and record.result_gemini else None
)
if user_id is not None:
    nutrition_result, personalization_result = await asyncio.gather(
        asyncio.to_thread(extract_and_lookup_nutrition, dish_name, components),
        asyncio.to_thread(
            lookup_personalization, user_id, query_id, ref_description, dish_name
        ),
        return_exceptions=True,
    )
    nutrition_db_matches = _safe_phase_2_1_result(nutrition_result, dish_name, query_id)
    personalized_matches = _safe_phase_2_2_result(personalization_result, query_id)
else:
    # Fallback (shouldn't happen — record FK exists): Phase 2.1 only.
    nutrition_db_matches = extract_and_lookup_nutrition(dish_name, components)
    personalized_matches = []

_persist_pre_pro_state(query_id, nutrition_db_matches, personalized_matches)
```

`_persist_pre_pro_state`:

```python
def _persist_pre_pro_state(
    query_id: int,
    nutrition_db_matches: Dict[str, Any],
    personalized_matches: List[Dict[str, Any]],
) -> None:
    record = get_dish_image_query_by_id(query_id)
    if not record or record.result_gemini is None:
        logger.warning(
            "Phase 2 skipped pre-Pro persist for query_id=%s (no result_gemini)", query_id
        )
        return
    pre_blob = dict(record.result_gemini)
    pre_blob["nutrition_db_matches"] = nutrition_db_matches
    pre_blob["personalized_matches"] = personalized_matches
    update_dish_image_query_results(
        query_id=query_id, result_openai=None, result_gemini=pre_blob
    )
```

`_safe_phase_2_1_result` and `_safe_phase_2_2_result` are module-private guards that inspect the gather result:

```python
def _safe_phase_2_1_result(
    result_or_exc: Any, dish_name: str, query_id: int
) -> Dict[str, Any]:
    if isinstance(result_or_exc, Exception):
        logger.warning(
            "Phase 2.1 raised inside gather for query_id=%s; substituting empty shape: %s",
            query_id,
            result_or_exc,
        )
        return _nutrition_lookup._empty_response(  # pylint: disable=protected-access
            dish_name, reason="unexpected_exception"
        )
    return result_or_exc


def _safe_phase_2_2_result(result_or_exc: Any, query_id: int) -> List[Dict[str, Any]]:
    if isinstance(result_or_exc, Exception):
        logger.warning(
            "Phase 2.2 raised inside gather for query_id=%s; substituting empty list: %s",
            query_id,
            result_or_exc,
        )
        return []
    return result_or_exc
```

(The `_empty_response` re-use from `nutrition_lookup.py` keeps the shape consistent with the Stage 5 empty-DB branch. Alternative: move `_empty_response` to a public helper; small follow-up if callers multiply.)

#### Configs

- `THRESHOLD_PHASE_2_2_SIMILARITY = 0.30` added under `THRESHOLD_PHASE_1_1_1_SIMILARITY` in `backend/src/configs.py`. Imported by `personalized_lookup.py` as the default `min_similarity`.

#### To Delete

None.

#### To Update

- `backend/src/configs.py` — append `THRESHOLD_PHASE_2_2_SIMILARITY = 0.30`.
- `backend/src/api/item_tasks.py` — rename + extend the persist helper; insert gather; add safety guards.

#### To Add New

- `backend/src/service/personalized_lookup.py` — `lookup_personalization` + `_build_query_tokens`.

---

### API Endpoints

None. Stage 6 exposes no new routes. `GET /api/item/{id}` starts returning an additional `result_gemini.personalized_matches` key the frontend ignores until Stage 8.

#### To Delete

None.

#### To Update

None.

#### To Add New

None.

---

### Testing

Test location: `backend/tests/`. One new file + an extension to the existing `test_item_tasks.py`.

**Unit tests — `personalized_lookup` (`backend/tests/test_personalized_lookup.py` — NEW):**

- `test_build_query_tokens_unions_description_and_dish_name` — overlapping + disjoint cases; assert set semantics.
- `test_build_query_tokens_handles_none_description` — `description=None`; only dish-name tokens.
- `test_build_query_tokens_empty_on_both_empty` — `description=None`, `confirmed_dish_name=""` → `[]`.
- `test_lookup_personalization_cold_start_returns_empty` — mock `search_for_user` to return `[]`; assert `[]`.
- `test_lookup_personalization_populates_prior_step2_data_from_referenced_record` — seed a referenced `DishImageQuery` with `result_gemini.step2_data`; assert the match's `prior_step2_data` matches.
- `test_lookup_personalization_prior_step2_data_null_when_referenced_record_has_no_step2` — referenced `result_gemini.step2_data` is None; assert the match's `prior_step2_data` is None, other fields still populated.
- `test_lookup_personalization_passes_corrected_step2_data_from_row` — fixture row has `corrected_step2_data` set; assert it flows through.
- `test_lookup_personalization_respects_exclude_query_id_via_search_for_user` — verify `search_for_user` was called with `exclude_query_id=<caller query_id>`.
- `test_lookup_personalization_respects_top_k_and_min_similarity_defaults` — verify `search_for_user` was called with `top_k=5, min_similarity=0.30`.
- `test_lookup_personalization_drops_row_key_from_output` — returned match dicts must NOT contain `"row"`.
- `test_lookup_personalization_empty_tokens_skips_search` — mock tokenize to return `[]` for both inputs; assert `search_for_user` is never called.

**Unit tests — `trigger_step2_analysis_background` (`backend/tests/test_item_tasks.py` — extend):**

- `test_phase2_task_runs_phase_2_1_and_2_2_concurrently` — monkeypatch both orchestrators to return known fixtures; assert both `nutrition_db_matches` AND `personalized_matches` land on the pre-Pro write. Running both in one gather is exercised implicitly; parallelism timing is covered in the Chrome spec.
- `test_phase2_task_persists_personalized_matches_pre_pro` — assert the first write carries `personalized_matches` alongside `nutrition_db_matches`.
- `test_phase2_task_preserves_personalized_matches_on_pro_success` — success merge re-read keeps the Stage 6 key.
- `test_phase2_task_preserves_personalized_matches_on_pro_failure` — Pro raises; error blob still carries `personalized_matches`.
- `test_phase2_task_phase_2_2_exception_degrades_to_empty_list` — monkeypatch `lookup_personalization` to raise; assert `personalized_matches: []` lands AND WARN log line names the exception.
- `test_phase2_task_phase_2_1_exception_degrades_to_empty_shape` — mirror of the above on the Phase 2.1 side. Assert `nutrition_db_matches.nutrition_matches == []` and `match_summary.reason == "unexpected_exception"`.
- `test_phase2_task_both_exceptions_still_runs_pro_call` — monkeypatch both to raise; assert Pro call still runs and step2_data lands.
- `test_phase2_task_skips_phase_2_2_when_record_or_result_gemini_missing` — `get_dish_image_query_by_id` returns None; Phase 2.1 still runs via the sequential fallback; `personalized_matches = []`.

**Pre-commit loop (mandatory):**

1. `source venv/bin/activate && pre-commit run --all-files`.
2. Fix lint / line-count / complexity issues. `item_tasks.py` is ~130 lines post-Stage-5; Stage 6 adds ~40 lines — well under the 300 cap. `personalized_lookup.py` is a fresh ~80-line module.
3. Re-run. Repeat until clean.

**Acceptance check from the issue's "done when":**

- `result_gemini.personalized_matches` populated whenever the user has prior history; `[]` on cold start.
- The two lookups run concurrently (observable in timing logs — the Chrome spec's Test 3 records the wall-clock comparison).

#### To Delete

None.

#### To Update

- `backend/tests/test_item_tasks.py` — append ~8 new tests covering the gather, persistence, error-isolation, and the no-record fallback.

#### To Add New

- `backend/tests/test_personalized_lookup.py` — unit tests for the new module.

---

### Frontend

None. Stage 6 ships no UI changes. Step 2 view renders identically today.

#### To Delete

None.

#### To Update

None.

#### To Add New

None.

---

### Documentation

#### Abstract (`docs/abstract/`)

- **Update** `docs/abstract/dish_analysis/nutritional_analysis.md` — append a paragraph under the Stage 5 "Curated nutrition database (consulted silently)" note:
  > **Personalization history (consulted silently).** In parallel with the nutrition database lookup, the system also compares the user's confirmed dish + its short caption against the user's own prior uploads. Close historical matches are recorded on the record (but not yet shown to the user and not yet fed into the AI — the measurable benefit arrives when a later release lets the AI reuse the user's prior analyses). Strictly per-account: one user's history never influences another user's analyses.

#### Technical (`docs/technical/`)

- **Update** `docs/technical/dish_analysis/nutritional_analysis.md`:
  - Extend the existing **Phase 2.1** sub-section's Pipeline block to show the new parallel `asyncio.gather` call.
  - Add a new **Phase 2.2 — Personalization Lookup (Stage 6)** sub-section after Phase 2.1 documenting:
    - `lookup_personalization(user_id, query_id, description, confirmed_dish_name)` signature and defaults.
    - Token-union rule: `tokenize(description) ∪ tokenize(confirmed_dish_name)`.
    - The per-match shape (`query_id, image_url, description, similarity_score, prior_step2_data, corrected_step2_data`).
    - Parallel-gather pattern + `return_exceptions=True` fallback.
    - Forward-link to Stage 0's [Personalized Food Index](./personalized_food_index.md) for the BM25 details.
  - Update the Component Checklist: add `[x] Phase 2.2 — lookup_personalization + parallel gather in trigger_step2_analysis_background`; `[x] THRESHOLD_PHASE_2_2_SIMILARITY = 0.30`.
- **Update** `docs/technical/dish_analysis/personalized_food_index.md`:
  - Flip `- [ ] Stage 6 (Phase 2.2): search_for_user called in trigger_step2_analysis_background` → `[x]` with a back-link.
  - Append Stage 6 to the "Downstream consumers" section documenting `lookup_personalization` and the pre-Pro persistence.

#### API Documentation (`docs/api_doc/`)

No changes — no endpoints added or changed. Project has no `docs/api_doc/` tree.

#### To Delete

None.

#### To Update

- `docs/abstract/dish_analysis/nutritional_analysis.md` — append Personalization paragraph.
- `docs/technical/dish_analysis/nutritional_analysis.md` — Phase 2.2 sub-section, pipeline extension, checklist additions.
- `docs/technical/dish_analysis/personalized_food_index.md` — flip Stage 6 row, append Stage 6 downstream-consumer note.

#### To Add New

None.

---

### Chrome Claude Extension Execution

**Included this stage.** Spec at `docs/chrome_test/260419_1034_stage6_phase2_2_personalization_lookup.md`. 10 tests, 5 desktop + 5 mobile. Covers:

1. Cold-start → empty matches.
2. Warm user → full-shape matches.
3. Parallel timing (wall-clock check via temporary log line).
4. Cross-user isolation.
5. Gather error isolation (Phase 2.2 raises; Phase 2.1 still lands; Pro call still runs).

Scope caveats:
- Test 3 / Test 8 require a temporary `gather` timing log line (see spec Remarks). Revert before committing.
- Test 5 / Test 9 require a failure-injection knob (`DEBUG_FORCE_PHASE_2_2_FAIL=1` env var or runtime monkeypatch). Plan-level call: ship a dev-only flag? See Open Questions at the bottom — resolved to **do not ship**, operator can monkeypatch at runtime.
- Placeholder usernames (no `docs/technical/testing_context.md`).

Execution flow: `feature-implement-full` invokes `chrome-test-execute` after Stage 6 lands.

#### To Delete

None.

#### To Update

None.

#### To Add New

- `docs/chrome_test/260419_1034_stage6_phase2_2_personalization_lookup.md` (already written).

---

## Dependencies

- **Stage 0** — `personalized_food_descriptions` schema, `search_for_user`, `tokenize`. Consumed verbatim.
- **Stage 2** — writes `result_gemini.reference_image.description` (Phase 1.1.1 caption) that Stage 6 reads. Cold-start absence is tolerated (description is None → dish-name tokens only).
- **Stage 4** — enriches the personalization row with `confirmed_dish_name` / `confirmed_tokens`. Already reflected in the row's `tokens` column Stage 6 reads via `search_for_user`.
- **Stage 5** — `extract_and_lookup_nutrition` runs in parallel with Stage 6's lookup. No signature change on Stage 5.
- **Existing Phase 2 pipeline** — `trigger_step2_analysis_background`, `get_step2_nutritional_analysis_prompt`, `analyze_step2_nutritional_analysis_async`, `persist_phase_error`. Unchanged; Stage 6 only replaces the pre-Pro block.
- **No new external libraries.**
- **No schema changes.**

---

## Resolved Decisions

- **Default `top_k = 5`** (confirmed with user 2026-04-19). Matches the Stage 8 Top-5 panel. Five is enough signal for Stage 7's prompt gating (Top-1 above threshold) and for Stage 8's UI (one card per match, ~5 cards max before scroll).
- **`asyncio.gather(..., return_exceptions=True)`** (confirmed with user 2026-04-19). Isolates Phase 2.1 / Phase 2.2 failures from each other and from the Pro call. A Phase 2.2 bug takes the personalization block down but leaves nutrition + Pro intact. WARN log names the exception and `query_id` for debuggability.
- **`THRESHOLD_PHASE_2_2_SIMILARITY = 0.30`** (pinned by the issue). Kept at spec. As with Stage 2's threshold, this is a relative ranking signal (max-in-batch normalization) so 0.30 mainly filters out vocabulary-disjoint prior rows. Re-tune after real retrieval-quality data.
- **Sync `lookup_personalization` + `asyncio.to_thread`** (decision recorded by the planner). Keeps the function body honest (BM25 + DB reads are sync) and makes the parallel intent explicit in `item_tasks.py`. An `async def` wrapper with internal `to_thread` would hide the sync nature and buy nothing.
- **Drop the `row` ORM handle from the returned match dicts** (decision recorded by the planner). Stage 7's prompt and Stage 8's UI bind to the five typed fields only. Keeping the ORM handle across the async boundary also complicates serialization if a future stage moves the matches through a background queue.
- **Do NOT ship a permanent `DEBUG_FORCE_PHASE_2_2_FAIL` env var** (decision recorded by the planner). The Chrome error-isolation test exercises a pathway that is already testable via runtime monkeypatch. A permanent dev flag would drift over time and become a maintenance cost; the pytest coverage + Chrome spec's manual monkeypatch step are sufficient.
- **Renamed `_persist_nutrition_db_matches` → `_persist_pre_pro_state`** (decision recorded by the planner). The helper now writes both `nutrition_db_matches` and `personalized_matches` in a single `update_dish_image_query_results` call, avoiding an extra round-trip.

## Open Questions

None — all decisions resolved 2026-04-19. Ready for implementation.
