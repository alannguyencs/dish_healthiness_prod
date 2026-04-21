# Stage 5 — Phase 2.1: Nutrition DB Lookup Integration

**Feature**: Wire the Stage 1 `NutritionCollectionService` into the Phase 2 background task. Every Step 2 run now calls a new orchestrator `extract_and_lookup_nutrition(dish_name, components)` **before** the Gemini 2.5 Pro call fires, and persists the structured result on `result_gemini.nutrition_db_matches`. The lookup survives Step 2 failure / retry. Stage 5 ships backend-only; Phase 2's prompt itself is unchanged — Stage 7 is the first consumer.
**Plan Created:** 2026-04-19
**Status:** Plan
**Reference**:
- [Issues — 260415, Stage 5](../issues/260415.md)
- [Discussion — Food DB investigation & end-to-end redesign](../discussion/260418_food_db.md)
- [Plan — Stage 1 Nutrition DB](./260418_stage1_nutrition_db.md) (the library this stage consumes)
- [Abstract — Nutritional Analysis](../abstract/dish_analysis/nutritional_analysis.md)
- [Technical — Nutritional Analysis](../technical/dish_analysis/nutritional_analysis.md)
- [Technical — Nutrition DB](../technical/dish_analysis/nutrition_db.md)
- [Chrome Test Spec — 260419_1004](../chrome_test/260419_1004_stage5_phase2_1_nutrition_db_lookup.md)

---

## Problem Statement

1. Stage 1 shipped `NutritionCollectionService` + `get_nutrition_service()` as pure library code with no pipeline call sites. The service loads `nutrition_foods` + `nutrition_myfcd_nutrients` into four per-source BM25 indices at first use, but nothing in the app exercises it yet.
2. The end-to-end workflow in `docs/discussion/260418_food_db.md` places Phase 2.1 as the first sub-step of Phase 2 — it must run in parallel with Phase 2.2 (personalization lookup, Stage 6) and complete before Phase 2.3 (the Pro call that will eventually consume both, Stage 7). Stage 5 lands only the Phase 2.1 half.
3. The reference project's `ai_agent.py::_extract_and_lookup_nutrition` implements the per-component + dish_name search loop with a combined-terms fallback. The issue spec pins these numbers — `min_confidence=70` for Stage 1, `0.75` threshold for triggering the Stage 2 fallback, `min_confidence=60` for the combined search. These constants were tuned against the reference's 846-query NDCG eval set; re-deriving them would invalidate the Stage 9 benchmark.
4. The return shape must match what Stage 7's prompt will expect: `{success, input_text, nutrition_matches, total_nutrition, recommendations, match_summary, processing_info, search_strategy, search_attempts, dish_candidates}`. Fixing that shape now keeps Stage 7 a pure prompt-engineering change.
5. The lookup must be persisted **before** the Pro call so a Step 2 Gemini failure doesn't destroy the retrieval work. Stage 5 adds a pre-Pro write to `result_gemini.nutrition_db_matches`; the retry path reuses the stored value.
6. Two edge cases matter on day one:
   - **Empty `nutrition_foods`.** Dev envs may not have run the seed script. Phase 2 must still succeed — the result carries empty matches and Step 2 proceeds exactly as today.
   - **Low-confidence per-component searches.** The issue's fallback formula replaces the best result only when the comma-joined combined search scores higher; `search_attempts` records every query for debugging.

---

## Proposed Solution

Four artifacts — three new, one updated.

### 1. `NutritionCollectionService.collect_from_nutrition_db(text, min_confidence, deduplicate) -> Dict`

New method on the existing Stage 1 service (not a standalone module). Wraps `_search_dishes_direct` with the full Stage-7-compatible return shape. Ported from the reference project's method of the same name, with these simplifications:

- Confidence arrives as `0–100` (int), converted to `0–1` internally (same as reference).
- No `pandas` / `resource_dir` references; uses the Stage 1 seeded-DB path exclusively.
- Calls the existing `_deduplicate_matches` + `_calculate_optimal_nutrition` + `_generate_recommendations` helpers, which we port as **module-private functions** in a new `backend/src/service/_nutrition_aggregation.py` file (parallels the existing `_nutrition_scoring.py` split).

### 2. `backend/src/service/_nutrition_aggregation.py`

Module-private helpers, ported verbatim from the reference:

- `deduplicate_matches(matches) -> List[match]` — keep highest-confidence occurrence per `matched_food_name`; BM25 score as tiebreaker.
- `aggregate_nutrition(matches) -> Dict` — sum calories / protein / carbs / fat per source-specific rules (Malaysian: `calories`; MyFCD: `nutrients.{Energy,Protein,Carbohydrate,Fat}.value_per_serving`; Anuvaad: `energy_kcal * 1.5`, etc., where `1.5` is the reference's 150g-serving scale assumption; CIQUAL: `Energy, Regulation EU No 1169/2011 (kcal/100g)` etc. — new for our codebase since reference didn't ship CIQUAL in this path).
- `calculate_optimal_nutrition(matches) -> Dict` — if top match has `confidence >= 0.90` AND `len(matches) > 1`, use `extract_single_match_nutrition(top)`; else `aggregate_nutrition(matches)`.
- `extract_single_match_nutrition(match) -> Dict` — single-source nutrition extractor.
- `generate_recommendations(total_nutrition) -> List[str]` — deterministic tips based on calorie + macro thresholds.

These all live in `_nutrition_aggregation.py` (leading underscore, same convention as `_nutrition_scoring.py`) so the public surface in `nutrition_db.py` stays focused on retrieval. Prior stages' constants (0.85/0.15, +0.20/+0.15, 0.8/0.2, 0.50–0.95) are untouched.

### 3. `backend/src/service/nutrition_lookup.py::extract_and_lookup_nutrition(dish_name, components) -> Dict`

New module — the Phase 2.1 orchestrator. Pseudocode:

```python
def extract_and_lookup_nutrition(
    dish_name: str,
    components: List[Dict[str, Any]],
) -> Dict[str, Any]:
    try:
        svc = get_nutrition_service()
    except NutritionDBEmptyError as exc:
        logger.warning("Phase 2.1 nutrition DB is empty; returning empty match set: %s", exc)
        return _empty_response(dish_name, reason="nutrition_db_empty")

    candidates = _dedupe_preserve([dish_name] + [c.get("component_name") for c in components])
    dish_candidates = [dish_name]   # only the dish name is surfaced as "candidate"; components are query-time-only

    best_result: Optional[Dict[str, Any]] = None
    best_confidence = 0.0
    search_attempts: List[Dict[str, Any]] = []

    # Stage 1 — per-query search @ min_confidence=70
    for query in candidates:
        attempt, result = _single_query_attempt(svc, query, min_confidence=70)
        search_attempts.append(attempt)
        if result and attempt["top_confidence"] > best_confidence:
            best_confidence = attempt["top_confidence"]
            best_result = result
            best_result["search_strategy"] = f"individual_dish_name: {query}"

    # Stage 2 — fallback: comma-joined @ min_confidence=60, only if best is weak
    if best_confidence < 0.75:
        combined_text = ", ".join(candidates)
        attempt, combined = _single_query_attempt(svc, combined_text, min_confidence=60)
        search_attempts.append(attempt)
        if combined and attempt["top_confidence"] > best_confidence:
            best_result = combined
            best_result["search_strategy"] = f"combined_terms: {combined_text}"

    if best_result is None:
        return _empty_response(dish_name, reason="no_matches_across_strategies",
                               search_attempts=search_attempts,
                               dish_candidates=dish_candidates)

    best_result["search_attempts"] = search_attempts
    best_result["dish_candidates"] = dish_candidates
    return best_result
```

Supporting helpers stay module-private:

- `_single_query_attempt(svc, query, min_confidence)` — wraps `svc.collect_from_nutrition_db(query, min_confidence, deduplicate=True)`; returns `(attempt_dict, full_result_or_None)`. The attempt dict carries `{query, success, matches, top_confidence, error?}` for `search_attempts`.
- `_empty_response(input_text, reason, search_attempts=None, dish_candidates=None)` — returns the Stage-7-expected shape with `nutrition_matches: []` and a `reason` field in `match_summary`. Stage 7's prompt will gate off `nutrition_matches[0].confidence_score >= THRESHOLD_DB_INCLUDE`; an empty list short-circuits cleanly.
- `_dedupe_preserve(strings)` — order-preserving dedupe of `[dish_name, *component_names]`.

Exception handling is per-query; a single query's error (unlikely — `_search_dishes_direct` doesn't raise) is captured in the attempt's `error` key and the loop continues.

### 4. `item_tasks.py::trigger_step2_analysis_background` — pre-Pro write

Before the `get_step2_nutritional_analysis_prompt(...)` call, run Phase 2.1 synchronously (it's in-process BM25, <50 ms once the singleton is warm) and persist the result:

```python
# Stage 5 — Phase 2.1 nutrition DB lookup. Runs before the Pro call so the
# data survives Step 2 failure / retry.
nutrition_db_matches = extract_and_lookup_nutrition(dish_name, components)
pre_record = get_dish_image_query_by_id(query_id)
if pre_record and pre_record.result_gemini is not None:
    pre_blob = pre_record.result_gemini.copy()
    pre_blob["nutrition_db_matches"] = nutrition_db_matches
    update_dish_image_query_results(
        query_id=query_id, result_openai=None, result_gemini=pre_blob
    )
```

Persistence is best-effort: if the record read races with a concurrent write, the pre-Pro blob simply won't land and Stage 7 will see no `nutrition_db_matches` for that query (same as an empty-DB response from Stage 7's perspective). Stage 5 explicitly does **not** plumb `nutrition_db_matches` into the Pro prompt — that is Stage 7's job. The Stage 5 orchestrator returns immediately on failure in `get_nutrition_service()` via the `NutritionDBEmptyError` branch, so the confirm → Phase 2 handoff never blocks on DB-state.

### Why pre-Pro write rather than post-Pro merge

- **Retry safety.** Today's Step 2 retry endpoint calls `trigger_step2_analysis_background` and relies on the existing persisted state. Writing `nutrition_db_matches` pre-Pro means a crash halfway through the Pro call still persists the lookup (matches the Stage 2 pattern for `reference_image`).
- **Observability.** Operators can inspect `nutrition_db_matches` on a failed query to correlate retrieval quality vs. Gemini failure rate.
- **Two writes per successful run** (pre-Pro + post-Pro merge) is the same pattern Stage 2 uses for `reference_image`. `trigger_step2_analysis_background`'s final write already does a read-merge, so nothing special on the merge side — the `nutrition_db_matches` key carries through.

### Why the "replace, not merge" strategy for search_attempts

The issue explicitly pins reference-project behavior: `best_result = combined_result` when the combined search scores higher. Keeping only one winner preserves the 0.50–0.95 confidence scale semantics; merging per-query match lists would mix query-relative calibrations across attempts. `search_attempts` is the debug artefact that records every query's top_confidence; if Stage 7 later decides to inspect all attempts, the data is there.

---

## Current Implementation Analysis

### What Exists (keep as-is)

| Component | File | Status |
|-----------|------|--------|
| `NutritionCollectionService` | `backend/src/service/nutrition_db.py` | Keep — Stage 5 adds a new method but does not change `_search_dishes_direct` / `search_nutrition_database_enhanced` / singleton / constructor. |
| `direct_bm25_search` scoring primitive | `backend/src/service/_nutrition_scoring.py` | Keep unchanged. Confidence formula constants are eval-set-pinned. |
| `NutritionDBEmptyError` | `backend/src/service/nutrition_db.py` | Keep — caught by the Phase 2.1 orchestrator as the "empty DB" signal. |
| `get_nutrition_service()` lazy singleton | `backend/src/service/nutrition_db.py` | Keep. |
| `nutrition_foods` + `nutrition_myfcd_nutrients` schema | `backend/sql/create_tables.sql` | Keep — no schema change. |
| `crud_nutrition` | `backend/src/crud/crud_nutrition.py` | Keep — Stage 5 doesn't change CRUD. |
| Phase 2 background task structure (success merge, error helper) | `backend/src/api/item_tasks.py`, `backend/src/api/_phase_errors.py` | Keep — Stage 5 only inserts a pre-Pro block; success / error paths unchanged. |
| Retry endpoint | `backend/src/api/item_retry.py::retry_step2_analysis` | Keep. The retry path reuses the already-persisted `nutrition_db_matches` because Stage 5 writes it before the Pro call. |
| Step 2 response schema / frontend UI | `backend/src/service/llm/models.py`, `frontend/src/pages/ItemV2.jsx`, Step 2 components | Keep — Stage 5 surfaces no new frontend data. |

### What Changes

| Component | Current | Proposed |
|-----------|---------|----------|
| `backend/src/service/nutrition_db.py` | Has `_search_dishes_direct` + `search_nutrition_database_enhanced` + accessor. | Adds `collect_from_nutrition_db(text, min_confidence, deduplicate)` method on `NutritionCollectionService`. Builds the Stage-7-compatible full return shape via `_nutrition_aggregation` helpers. |
| `backend/src/service/_nutrition_aggregation.py` | Does not exist. | New module with `deduplicate_matches / aggregate_nutrition / calculate_optimal_nutrition / extract_single_match_nutrition / generate_recommendations` (all module-private to the service layer, leading-underscore convention). |
| `backend/src/service/nutrition_lookup.py` | Does not exist. | New module with `extract_and_lookup_nutrition(dish_name, components) -> Dict`. Phase 2.1 orchestrator. |
| `backend/src/api/item_tasks.py::trigger_step2_analysis_background` | Goes straight from prompt-build to Pro call. | Adds pre-Pro `nutrition_db_matches` write. Existing success-merge read pattern carries the new key through. |

---

## Implementation Plan

### Key Workflow

```
POST /api/item/{record_id}/confirm-step1  (existing)
  │
  ▼
background_tasks.add_task(trigger_step2_analysis_background, ...)
  │
  ▼
trigger_step2_analysis_background(query_id, image_path, dish_name, components)
  │
  ▼ (NEW — Phase 2.1)
nutrition_db_matches = extract_and_lookup_nutrition(dish_name, components)
  │
  ├── try: get_nutrition_service()
  │   except NutritionDBEmptyError: log WARN, return _empty_response(..., reason="nutrition_db_empty")
  │
  ├── candidates = _dedupe_preserve([dish_name, *components.component_name])
  ├── for q in candidates:
  │       result = svc.collect_from_nutrition_db(q, min_confidence=70, deduplicate=True)
  │       track best_confidence / best_result / search_attempts
  │
  ├── if best_confidence < 0.75:
  │       combined = svc.collect_from_nutrition_db(", ".join(candidates), min_confidence=60)
  │       if combined top_confidence > best_confidence: best_result = combined
  │
  └── return best_result (with search_attempts + dish_candidates attached)
         OR _empty_response(...)  if no winner
  │
  ▼ (NEW — pre-Pro persistence)
record = get_dish_image_query_by_id(query_id)
pre_blob = record.result_gemini.copy()
pre_blob["nutrition_db_matches"] = nutrition_db_matches
update_dish_image_query_results(query_id, None, pre_blob)
  │
  ▼ (existing)
step2_prompt = get_step2_nutritional_analysis_prompt(dish_name, components)
step2_result = await analyze_step2_nutritional_analysis_async(image_path, prompt, ...)
  │
  ▼ (existing — already merges onto current result_gemini so nutrition_db_matches carries through)
result_gemini = record.result_gemini.copy()
result_gemini["step"] = 2
result_gemini["step2_data"] = step2_result
result_gemini.pop("step2_error", None)
update_dish_image_query_results(query_id, None, result_gemini)
```

#### To Delete

None.

#### To Update

- `backend/src/api/item_tasks.py::trigger_step2_analysis_background` — insert the Phase 2.1 block at the top of the try-body (before `get_step2_nutritional_analysis_prompt`). Extract the two-write persistence into a private helper `_persist_nutrition_db_matches(query_id, nutrition_db_matches)` to keep cyclomatic complexity in budget (the file is currently ~90 lines; Stage 5 adds ~30).

#### To Add New

- `backend/src/service/_nutrition_aggregation.py` — aggregation helpers (see Services).
- `backend/src/service/nutrition_lookup.py` — `extract_and_lookup_nutrition` + module-private helpers (see Services).
- `NutritionCollectionService.collect_from_nutrition_db(...)` — new method on the existing class (same file).

---

### Database Schema

**No changes.** Stage 1 shipped the `nutrition_foods` + `nutrition_myfcd_nutrients` schema and the seed script. Stage 5 is pure read + new call-site plumbing.

#### To Delete

None.

#### To Update

None.

#### To Add New

None.

---

### CRUD

**No new CRUD.** The orchestrator reads via the service singleton; the pre-Pro write uses the existing `update_dish_image_query_results`. The existing `get_dish_image_query_by_id` is called once more inside the background task.

#### To Delete

None.

#### To Update

None.

#### To Add New

None.

---

### Services

#### `backend/src/service/_nutrition_aggregation.py` (new)

Module-private helpers, ported from the reference project verbatim where possible. All functions are module-level; no class.

```python
def deduplicate_matches(matches: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Remove duplicate matches by matched_food_name, keeping the highest-
    confidence occurrence. BM25 raw score is the tiebreaker.
    """


def extract_single_match_nutrition(match: Dict[str, Any]) -> Dict[str, Any]:
    """
    Pull macros out of a single match's nutrition_data in source-aware fashion.
      - malaysian_food_calories → nutrition_data.calories (per-serving)
      - myfcd → nutrients.Energy / Protein / Carbohydrate / Fat value_per_serving
      - anuvaad → energy_kcal / protein_g / carb_g / fat_g * 1.5 (per-100g scaled)
      - ciqual → calories_field / protein_field / carbs_field / fat_field (per-100g, no scaling — CIQUAL values are already per-100g and the Stage 7 prompt will reconcile servings)
    Returns {total_calories, total_protein_g, total_carbohydrates_g,
             total_fat_g, foods_included, disclaimer}.
    """


def aggregate_nutrition(matches: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Sum-aggregate the same four macros across `matches`."""


def calculate_optimal_nutrition(matches: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Return extract_single_match_nutrition(matches[0]) when the top match
    has confidence >= 0.90 AND len(matches) > 1 (reference's 'high-confidence
    exact match' short-circuit). Otherwise aggregate_nutrition(matches).
    """


def generate_recommendations(nutrition_data: Dict[str, Any]) -> List[str]:
    """Deterministic tips based on calorie and macro thresholds."""
```

**CIQUAL handling** is new vs. the reference (which didn't wire CIQUAL through this path). The seeded `raw_data` already carries the per-100g macro fields; we read the same column names Stage 1's seed script wrote. No scaling multiplier for CIQUAL — Stage 7's prompt will reconcile servings. This is a conservative default for dev; can be revisited when Stage 7 lands.

#### `backend/src/service/nutrition_db.py` (extended)

Add `collect_from_nutrition_db` method on `NutritionCollectionService`:

```python
def collect_from_nutrition_db(
    self,
    text: str,
    min_confidence: int = 70,
    deduplicate: bool = True,
) -> Dict[str, Any]:
    """
    Full-shape lookup used by Stage 5's orchestrator.

    Returns the Stage-7-expected shape:
      {success, method, input_text, nutrition_matches, total_nutrition,
       recommendations, match_summary, processing_info}
    """
    if not text or not text.strip():
        raise ValueError("Text input cannot be empty")

    min_confidence_normalized = min_confidence / 100.0
    matches = self._search_dishes_direct(
        text, top_k=10, min_confidence=min_confidence_normalized
    )
    if not matches:
        return _empty_collect_response(text, self, reason="no_relevant_dishes")

    if deduplicate:
        matches = deduplicate_matches(matches)

    total_nutrition = calculate_optimal_nutrition(matches)
    recommendations = generate_recommendations(total_nutrition)
    avg_confidence = sum(m["confidence"] for m in matches) / len(matches) if matches else 0.0

    return {
        "success": True,
        "method": "Direct BM25 Text Matching",
        "input_text": text,
        "nutrition_matches": matches,
        "total_nutrition": total_nutrition,
        "recommendations": recommendations,
        "match_summary": {
            "total_matched": len(matches),
            "match_rate": 1.0,
            "avg_confidence": round(avg_confidence * 100, 1),
            "deduplication_enabled": deduplicate,
            "search_method": "Direct BM25",
        },
        "processing_info": {
            "malaysian_foods_count": len(self.malaysian_foods),
            "myfcd_foods_count": len(self.myfcd_foods),
            "anuvaad_foods_count": len(self.anuvaad_foods),
            "ciqual_foods_count": len(self.ciqual_foods),
            "min_confidence_threshold": min_confidence,
            "approach": "Full text to dish matching",
        },
    }
```

`_empty_collect_response(text, service, reason)` is a module-private helper at the bottom of `nutrition_db.py` returning the same shape but with `nutrition_matches: []` and `match_summary.total_matched: 0`.

#### `backend/src/service/nutrition_lookup.py` (new)

Phase 2.1 orchestrator as described in **Proposed Solution**. Public surface is one function:

```python
def extract_and_lookup_nutrition(
    dish_name: str,
    components: List[Dict[str, Any]],
) -> Dict[str, Any]:
    ...
```

Module-private helpers: `_dedupe_preserve`, `_single_query_attempt`, `_empty_response`.

Not a class — mirrors the pattern of `personalized_food_index.py` and `personalized_reference.py` (Stages 0/2).

#### Configs

No changes. The threshold constants (0.75 fallback trigger, min_confidence=70/60) live as literals inside `extract_and_lookup_nutrition` per the issue spec. They are not knobs to tune from `configs.py`; editing them changes the NDCG@10 baseline the reference measured.

#### To Delete

None.

#### To Update

- `backend/src/service/nutrition_db.py` — add `collect_from_nutrition_db` method + `_empty_collect_response` helper.

#### To Add New

- `backend/src/service/_nutrition_aggregation.py` — aggregation helpers.
- `backend/src/service/nutrition_lookup.py` — Phase 2.1 orchestrator.

---

### API Endpoints

None. Stage 5 exposes no new routes and does not change the contract of `POST /confirm-step1` or `GET /api/item/{id}` — the latter simply starts returning an additional key (`result_gemini.nutrition_db_matches`) that the frontend ignores.

#### To Delete

None.

#### To Update

None.

#### To Add New

None.

---

### Testing

Test location: `backend/tests/`. Extend + add files.

**Unit tests — `_nutrition_aggregation` (`backend/tests/test_nutrition_aggregation.py` — NEW):**

- `test_deduplicate_matches_keeps_highest_confidence` — three matches with same `matched_food_name`, different confidences; assert the highest-confidence one survives.
- `test_deduplicate_matches_uses_bm25_as_tiebreaker` — two matches with equal confidence but different `raw_bm25_score`; assert the higher BM25 one wins.
- `test_extract_single_match_nutrition_malaysian` — Malaysian source with `nutrition_data.calories`; other macros 0.
- `test_extract_single_match_nutrition_myfcd` — MyFCD source with nested `nutrients` dict; all four macros extracted from `value_per_serving`.
- `test_extract_single_match_nutrition_anuvaad_applies_serving_scale` — Anuvaad source; assert macros are raw_fields × 1.5 rounded to 2 dp.
- `test_extract_single_match_nutrition_ciqual_reads_per_100g_fields` — CIQUAL source; assert macros are read from the raw_data per-100g column names (no scale).
- `test_aggregate_nutrition_sums_across_sources` — one match per source; assert the four totals are the sum of each source's contribution.
- `test_calculate_optimal_nutrition_uses_single_match_when_top_is_high_confidence` — top match `confidence=0.92`, three other matches; assert the returned `foods_included` has only the top match's name.
- `test_calculate_optimal_nutrition_falls_back_to_aggregate` — top match `confidence=0.85`; assert aggregation runs across all four matches.
- `test_generate_recommendations_high_calorie` — `total_calories=1000`; assert a high-calorie warning string is present.
- `test_generate_recommendations_low_calorie` — `total_calories=100`; assert a low-calorie nudge is present.
- `test_generate_recommendations_low_protein_ratio` — `total_protein_g=5, total_carbohydrates_g=100`; assert the low-protein tip is present.
- `test_generate_recommendations_fallback_default` — balanced nutrition; assert the default "maintain a balanced diet" string is returned.

**Unit tests — `nutrition_db.collect_from_nutrition_db` (`backend/tests/test_nutrition_db.py` — append):**

- `test_collect_from_nutrition_db_returns_full_shape` — pre-seed the service instance with fixture matches via monkey-patching `_search_dishes_direct`; call with a query; assert every documented top-level key exists.
- `test_collect_from_nutrition_db_raises_on_empty_text` — empty string; assert `ValueError`.
- `test_collect_from_nutrition_db_returns_empty_shape_on_no_matches` — monkeypatched `_search_dishes_direct` returns `[]`; assert `nutrition_matches: []` and `match_summary.total_matched: 0`.
- `test_collect_from_nutrition_db_avg_confidence_is_rounded` — seed three matches with confidences `[0.9, 0.7, 0.5]`; assert `match_summary.avg_confidence == 70.0` (percent, 1 dp).

**Unit tests — `nutrition_lookup` (`backend/tests/test_nutrition_lookup.py` — NEW):**

- `test_extract_and_lookup_empty_db_returns_empty_response` — monkeypatch `get_nutrition_service` to raise `NutritionDBEmptyError`; assert the returned dict has `nutrition_matches: []`, `match_summary.reason == "nutrition_db_empty"`, and `success: True`.
- `test_extract_and_lookup_happy_path_dish_name_wins` — mock `svc.collect_from_nutrition_db` to return a high-confidence result for the dish name and a lower one for each component; assert `search_strategy == "individual_dish_name: <dish>"`.
- `test_extract_and_lookup_component_wins_over_dish_name` — mock to return higher confidence for one component than for dish name; assert `search_strategy` names that component.
- `test_extract_and_lookup_triggers_fallback_when_best_below_075` — mock all per-query results below 0.70 confidence and combined result above; assert `search_strategy` starts with `"combined_terms:"` and the combined result replaces the best.
- `test_extract_and_lookup_fallback_skipped_when_best_at_or_above_075` — mock dish_name to score 0.80; assert only individual searches run (combined is never called — patch counter).
- `test_extract_and_lookup_fallback_retained_when_combined_is_lower` — mock all per-query < 0.75 and combined < all; assert the original best_result wins and `search_strategy` stays individual-mode.
- `test_extract_and_lookup_all_empty_returns_empty_shape` — mock every query to return empty matches; assert `nutrition_matches: []` and `search_attempts` has an entry per candidate + one combined attempt.
- `test_extract_and_lookup_search_attempts_shape` — assert every `search_attempts` entry has `query`, `success`, `matches`, `top_confidence` keys.
- `test_extract_and_lookup_dedupes_component_names_equal_to_dish_name` — dish_name and a component share the same string; assert `search_attempts` has exactly one entry for it (dedupe preserves order).

**Integration tests — `trigger_step2_analysis_background` (`backend/tests/test_item_tasks.py` — NEW if absent; append if present):**

- `test_phase2_task_persists_nutrition_db_matches_before_pro_call` — monkeypatch `extract_and_lookup_nutrition` to return a known dict; monkeypatch the Pro analyzer + CRUD capture; assert the first `update_dish_image_query_results` write has `nutrition_db_matches` set.
- `test_phase2_task_preserves_nutrition_db_matches_on_pro_success` — the final success merge write must carry `nutrition_db_matches` through (re-read merge pattern).
- `test_phase2_task_preserves_nutrition_db_matches_on_pro_failure` — Pro raises; `persist_phase_error` writes `step2_error` but `nutrition_db_matches` remains on the record (verify via the capture).
- `test_phase2_task_empty_db_still_schedules_and_succeeds` — orchestrator returns the empty-response shape; assert the pre-Pro write landed with `nutrition_matches: []` and the Pro call ran normally.

**Pre-commit loop (mandatory):**

1. `source venv/bin/activate && pre-commit run --all-files`.
2. Fix lint / line-count / complexity issues. `item_tasks.py` will gain ~30 lines; likely to hover near but under the 300 cap. `_nutrition_aggregation.py` will be ~150 lines; `nutrition_lookup.py` ~120; `nutrition_db.py` extended by ~50.
3. Re-run. Repeat until clean.

**Acceptance check from the issue's "done when":**

- Every new query post-Stage-5 has `result_gemini.nutrition_db_matches` populated (possibly empty `nutrition_matches: []`).
- Stage 1 smoke test (`test_nutrition_db.py`) extended with a labeled-query end-to-end assertion (e.g. feed `"chicken rice"` through `collect_from_nutrition_db` and assert `nutrition_matches[0].matched_food_name.lower() in ("chicken rice", ...)`; confidence > 0.5).

#### To Delete

None.

#### To Update

- `backend/tests/test_nutrition_db.py` — append the four `collect_from_nutrition_db` tests + extended smoke test.

#### To Add New

- `backend/tests/test_nutrition_aggregation.py` — aggregation helpers tests.
- `backend/tests/test_nutrition_lookup.py` — orchestrator tests.
- `backend/tests/test_item_tasks.py` — four integration tests for the Phase 2.1 hook (create if absent).

---

### Frontend

None. Stage 5 ships no UI changes. The Step 2 view renders identically today.

#### To Delete

None.

#### To Update

None.

#### To Add New

None.

---

### Documentation

#### Abstract (`docs/abstract/`)

- **Update** `docs/abstract/dish_analysis/nutritional_analysis.md` — add a one-paragraph "Curated nutrition database (consulted silently)" note:
  - What: when nutritional analysis runs, the system now consults a curated database of ~4,500 foods across four international sources (Malaysian, MyFCD, Anuvaad, CIQUAL) to find close matches for the user's dish.
  - Effect this stage: the matches are recorded on the record but not yet shown to the user or fed into the AI. A later release will let the AI cite them for more consistent nutrition numbers.
  - Scope caveat: cold-start dev environments or edge-case dishes with no matches continue to run exactly as today — the AI is never blocked on DB coverage.

#### Technical (`docs/technical/`)

- **Update** `docs/technical/dish_analysis/nutritional_analysis.md`:
  - Extend the Architecture ASCII diagram so the Phase 2 background task shows a "Phase 2.1 — Nutrition DB lookup" pre-step before the Pro call.
  - Add a **Phase 2.1 — Nutrition DB Lookup** sub-section under Architecture documenting:
    - The per-component + dish_name Stage-1 search at `min_confidence=70`.
    - The Stage-2 fallback at `min_confidence=60` when `best_confidence < 0.75`.
    - The "replace, don't merge" rule.
    - The return shape with every top-level key.
    - The empty-DB swallow-log policy.
    - Forward-link to [Nutrition DB](./nutrition_db.md) for the retrieval service details.
  - Extend the Pipeline section with the two-write persistence pattern (pre-Pro + post-Pro merge).
  - Update the Component Checklist: add `[x] Phase 2.1 — extract_and_lookup_nutrition() + pre-Pro persistence`; add `[x] _nutrition_aggregation.py helpers (deduplicate_matches, aggregate_nutrition, calculate_optimal_nutrition, extract_single_match_nutrition, generate_recommendations)`; add `[x] NutritionCollectionService.collect_from_nutrition_db() method`.
- **Update** `docs/technical/dish_analysis/nutrition_db.md`:
  - Flip the "Stage 5 (Phase 2.1) wiring" row on the Component Checklist to `[x]`.
  - Add a short "Downstream consumers" bullet pointing at `extract_and_lookup_nutrition` in `nutrition_lookup.py`.

#### API Documentation (`docs/api_doc/`)

No changes needed — Stage 5 adds no API endpoints and does not change any existing contract. The project does not yet ship a `docs/api_doc/` tree.

#### To Delete

None.

#### To Update

- `docs/abstract/dish_analysis/nutritional_analysis.md` — add the one-paragraph curated-database note.
- `docs/technical/dish_analysis/nutritional_analysis.md` — Phase 2.1 sub-section, pipeline extension, checklist additions.
- `docs/technical/dish_analysis/nutrition_db.md` — flip Stage 5 row, add downstream consumer note.

#### To Add New

None.

---

### Chrome Claude Extension Execution

**Included this stage.** Spec at `docs/chrome_test/260419_1004_stage5_phase2_1_nutrition_db_lookup.md`. 10 tests, 5 desktop + 5 mobile. Covers:

1. Happy path — `nutrition_db_matches` populated; shape sanity.
2. Empty-DB graceful degrade — truncate + restart + confirm; empty matches persist; Step 2 still succeeds.
3. Retry preserves matches — break `GEMINI_API_KEY`, trigger Step 2 failure, retry; `nutrition_db_matches` unchanged.
4. Low-confidence fallback — custom dish name triggers combined search; `search_attempts` carries multiple entries.
5. Permission guard — unauthenticated confirm returns 401; no Phase 2.1 runs.

Scope caveats:
- Tests 2/7 **destructively truncate** `nutrition_foods` and require a backend restart (to discard the `_INSTANCE` singleton cache). Restore SQL included.
- Tests 3/8 flip `GEMINI_API_KEY`; restart required on both flip and restore.
- Placeholder usernames (no `docs/technical/testing_context.md`).

Execution flow: `feature-implement-full` invokes `chrome-test-execute` after Stage 5 lands.

#### To Delete

None.

#### To Update

None.

#### To Add New

- `docs/chrome_test/260419_1004_stage5_phase2_1_nutrition_db_lookup.md` (already written).

---

## Dependencies

- **Stage 1** — `NutritionCollectionService` + `get_nutrition_service()` + `NutritionDBEmptyError`. Consumed verbatim; extended with one new method.
- **Existing Phase 2 pipeline** — `trigger_step2_analysis_background`, `get_step2_nutritional_analysis_prompt`, `analyze_step2_nutritional_analysis_async`, `update_dish_image_query_results`, `persist_phase_error`. Stage 5 inserts a pre-Pro block; no signature changes.
- **Existing retry endpoint** — `item_retry.py::retry_step2_analysis`. Unchanged. The retry path reuses the persisted `nutrition_db_matches`.
- **No new external libraries.**
- **No schema changes.**

---

## Resolved Decisions

- **Empty-DB behavior — swallow + log WARN; stash empty-response shape on `result_gemini.nutrition_db_matches`; Phase 2 Gemini proceeds as today** (confirmed with user 2026-04-19). Keeps dev envs unblocked when the seed hasn't run, and makes a future nutrition-table purge non-destructive to Phase 2. The Stage 7 prompt-gating (`THRESHOLD_DB_INCLUDE`) will naturally short-circuit on an empty matches list.
- **Low-confidence fallback — replace, not merge** (confirmed with user 2026-04-19). Matches the reference project's NDCG-tuned behavior. Preserves the per-query confidence calibration; keeps Stage 7's prompt logic simple (one winning strategy per query, not a merged multi-strategy list).
- **Pre-Pro persistence of `nutrition_db_matches`** (decision recorded by the planner). Runs synchronously before the Pro call so a Pro-call failure cannot destroy the retrieval work. Two writes per successful Phase 2 run (one for nutrition_db_matches, one for step2_data); the second write is a read-merge so nutrition_db_matches carries through without explicit handling.
- **Retry path does NOT re-run Phase 2.1 by default** (decision recorded by the planner). `trigger_step2_analysis_background` does always re-run Phase 2.1 on invocation — but because the retry endpoint simply re-schedules the task, Phase 2.1 runs fresh on every retry. The "unchanged" guarantee the Chrome spec tests is approximate (same DB state + deterministic BM25 produces identical output byte-for-byte; no non-determinism in the lookup). Document explicitly — future dynamic-DB changes (e.g., live nutrition seeds) will need a conscious decision to cache or not.
- **CIQUAL scale factor = 1.0, not 1.5** (decision recorded by the planner). Reference project didn't wire CIQUAL through `ai_agent.py`; the 150g-serving assumption was Anuvaad-specific. CIQUAL's raw_data already carries per-100g macros; Stage 7's prompt reconciles servings. Revisit if Stage 9 benchmark reveals CIQUAL calibration drift.
- **Aggregation helpers live in `_nutrition_aggregation.py`, not inside `nutrition_db.py`** (decision recorded by the planner). Parallel to `_nutrition_scoring.py` (Stage 1's confidence-formula split). Keeps each module under the 300-line cap and makes the Stage 7 prompt-consumption layer cleaner to reason about.

## Open Questions

None — all decisions resolved 2026-04-19. Ready for implementation.
