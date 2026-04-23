# Nutrition Lookup — Combined Search Strategy

**Feature**: Replace the per-component + fallback two-stage nutrition DB lookup with a single combined-terms search that weights dish-name tokens higher than component tokens
**Plan Created:** 2026-04-23
**Status:** Plan
**Reference**:
- [Technical — Nutrition DB](../technical/dish_analysis/nutrition_db.md)
- [Technical — Nutritional Analysis](../technical/dish_analysis/nutritional_analysis.md)
- [Abstract — Nutritional Analysis](../abstract/dish_analysis/nutritional_analysis.md)
- [Plan — Stage 5 (original)](./260419_stage5_phase2_1_nutrition_db_lookup.md)

---

## Problem Statement

1. The current `extract_and_lookup_nutrition` orchestrator in `nutrition_lookup.py` runs **N independent searches** — one per candidate (`dish_name` + each `component_name`) — and keeps only the **single best result** by top confidence. If one component (e.g., "egg") matches at 85%, the entire `nutrition_db_matches` payload reflects only that query's results, and the other components (rice, sambal, etc.) get zero nutrition DB coverage in the Gemini prompt.
2. The Stage 2 combined-terms fallback only triggers when the best individual match scores below 0.75. When any single component scores well, the fallback never fires — even though the combined query would have provided broader coverage.
3. The existing `search_nutrition_database_enhanced` method already implements dish-token-priority search (sets `_current_dish_tokens` so the confidence formula applies `0.85` weight to dish-name matches and `0.15` to descriptors). This is the exact behaviour we want but is not used by Stage 5.

---

## Proposed Solution

Replace the two-stage (per-component → combined fallback) strategy with a **single combined search** that:

1. Joins `dish_name` + all `component_name` values into one token set.
2. Marks `dish_name` tokens as **core** (`_current_dish_tokens`) so the confidence formula weights them at `0.85` vs `0.15` for component-name tokens.
3. Runs one `_search_dishes_direct` call across all four BM25 indices.
4. Returns the top-K results from the merged, sorted result list.

This leverages the scoring formula's existing dish-token weighting — no changes to `_nutrition_scoring.py` constants, so Stage 9's NDCG benchmark stays valid.

```
Before (two-stage):
  for each candidate in [dish_name, comp_1, comp_2, ...]:
      search(candidate, min_confidence=70)     ← independent searches
      keep single best result
  if best < 0.75:
      search(all candidates joined, min_confidence=60)  ← fallback

After (combined):
  tokens = dish_name_tokens ∪ comp_1_tokens ∪ comp_2_tokens ∪ ...
  _current_dish_tokens = dish_name_tokens     ← 0.85 weight
  search(all tokens, min_confidence=60)       ← single search, broader coverage
```

**Why `min_confidence=60`:** The combined query includes component tokens as descriptors, which dilutes per-token match ratios compared to a narrow dish-name-only query. The lower threshold compensates, matching the existing Stage 2 level. Empirical validation via Stage 9 benchmark will confirm.

---

## Current Implementation Analysis

### What Exists (keep as-is)

| Component | File | Status |
|---|---|---|
| `NutritionCollectionService` singleton | `backend/src/service/nutrition_db.py` | Keep — BM25 indices, scoring |
| `_search_dishes_direct` | same | Keep — cross-source search |
| `_current_dish_tokens` mechanism | same | Keep — dish-token weighting |
| `direct_bm25_search` + confidence formula | `backend/src/service/_nutrition_scoring.py` | Keep — tuned constants unchanged |
| `collect_from_nutrition_db` | `backend/src/service/_nutrition_collect.py` | Keep — Stage-7-compatible shape |
| `_nutrition_aggregation.py` helpers | `backend/src/service/_nutrition_aggregation.py` | Keep — dedup, aggregate, recommendations |
| `render_nutrition_db_block` | `backend/src/service/llm/_nutrition_blocks.py` | Keep — prompt block renderer |
| Stage 9 benchmark | `backend/tests/test_nutrition_retrieval_benchmark.py` | Keep — regression gate |

### What Changes

| Component | Current | Proposed |
|---|---|---|
| `extract_and_lookup_nutrition` | N individual searches + conditional combined fallback; keeps single best | Single combined search with dish-token weighting; returns top-K from one merged result |
| `_FALLBACK_TRIGGER_THRESHOLD` | 0.75 (gates Stage 2 entry) | Remove — no fallback stage |
| `_STAGE_1_MIN_CONFIDENCE` | 70 (per-component searches) | Remove — single threshold |
| `_STAGE_2_MIN_CONFIDENCE` | 60 (combined fallback) | Rename to `_MIN_CONFIDENCE = 60` — sole threshold |
| `search_attempts` in response | Records every individual + combined query | Records single combined query |

---

## Implementation Plan

### Key Workflow

#### To Delete

- The `for query in candidates:` loop (lines 145-152 of `nutrition_lookup.py`) — per-candidate individual searches.
- The `if best_confidence < _FALLBACK_TRIGGER_THRESHOLD` block (lines 154-162) — Stage 2 fallback logic.
- Constants `_FALLBACK_TRIGGER_THRESHOLD` (0.75) and `_STAGE_1_MIN_CONFIDENCE` (70).

#### To Update

`extract_and_lookup_nutrition` in `backend/src/service/nutrition_lookup.py` — replace the body with:

```python
_MIN_CONFIDENCE = 60

def extract_and_lookup_nutrition(
    dish_name: str,
    components: List[Dict[str, Any]],
) -> Dict[str, Any]:
    try:
        svc = get_nutrition_service()
    except NutritionDBEmptyError as exc:
        logger.warning(...)
        return _empty_response(...)

    component_names = [c.get("component_name", "") for c in components or []]
    all_terms = _dedupe_preserve([dish_name] + component_names)
    combined_text = ", ".join(all_terms)
    dish_candidates = [dish_name] if dish_name else []

    # Set dish-name tokens as core for higher weighting in confidence formula
    dish_tokens = set(_normalize_text(dish_name or "").split())
    prior = svc._current_dish_tokens
    svc._current_dish_tokens = dish_tokens
    try:
        attempt, result = _single_query_attempt(svc, combined_text, _MIN_CONFIDENCE)
    finally:
        svc._current_dish_tokens = prior

    search_attempts = [attempt]

    if result is None or not result.get("nutrition_matches"):
        return _empty_response(
            dish_name or "",
            reason="no_matches_across_strategies",
            search_attempts=search_attempts,
            dish_candidates=dish_candidates,
        )

    result["search_strategy"] = f"combined_weighted: {combined_text}"
    result["search_attempts"] = search_attempts
    result["dish_candidates"] = dish_candidates
    return result
```

```
Phase 2.1 — Combined Weighted Search
  │
  ▼
Build token set: dish_name ∪ comp_1 ∪ comp_2 ∪ ...
  │
  ▼
Set _current_dish_tokens = dish_name tokens (0.85 weight)
  │
  ▼
collect_from_nutrition_db(combined_text, min_confidence=60)
  │
  ├── _search_dishes_direct across 4 BM25 indices
  │     per-hit confidence: dish_ratio × 0.85 + descriptor_ratio × 0.15
  │     + bonuses for ≥2 / ≥3 dish-token matches
  │
  ├── deduplicate_matches
  ├── calculate_optimal_nutrition
  └── generate_recommendations
  │
  ▼
Persist on result_gemini.nutrition_db_matches
```

#### To Add New

None.

### Database Schema

#### To Delete

None.

#### To Update

None.

#### To Add New

None.

### CRUD

#### To Delete

None.

#### To Update

None.

#### To Add New

None.

### Services

#### To Delete

- `_FALLBACK_TRIGGER_THRESHOLD`, `_STAGE_1_MIN_CONFIDENCE`, `_STAGE_2_MIN_CONFIDENCE` constants from `nutrition_lookup.py`.

#### To Update

- `extract_and_lookup_nutrition` — rewrite as described in Key Workflow. Imports `_normalize_text` from `nutrition_db.py` (already a module-level function there).
- `_single_query_attempt` — no signature change, but now called once instead of N+1 times.

#### To Add New

- `_MIN_CONFIDENCE = 60` constant in `nutrition_lookup.py`.

### API Endpoints

#### To Delete

None.

#### To Update

None — the endpoint that triggers Phase 2 (`POST /confirm-identification`) is unchanged; only the internal orchestrator logic changes.

#### To Add New

None.

### Testing

#### To Delete

None.

#### To Update

- `backend/tests/test_nutrition_lookup.py` — update test cases:
  - Remove tests that assert per-component individual search behaviour.
  - Remove tests that assert the 0.75 fallback trigger threshold.
  - Update assertions to expect a single `search_attempts` entry with the combined query.
  - Update `search_strategy` assertions to match `"combined_weighted: ..."`.

#### To Add New

- Test case: combined search sets and restores `_current_dish_tokens` correctly (no leakage).
- Test case: combined search with `min_confidence=60` returns matches that individual searches at `min_confidence=70` would have missed.
- Run Stage 9 benchmark after changes: `cd backend && source ../venv/bin/activate && pytest -m benchmark` to verify NDCG@10 ≥ 0.75 still holds.

Final pre-commit loop:

1. Run `source venv/bin/activate && pre-commit run --all-files`.
2. Fix any issues (e.g., lint errors, line count violations).
3. Re-run pre-commit again — Prettier may reformat the fixes and push files back over the line limit (max 300 lines per frontend file). If so, fix again.
4. Repeat until pre-commit passes cleanly on a full re-run with no new failures.

### Frontend

#### To Delete

None.

#### To Update

None — the frontend consumes `result_gemini.nutrition_db_matches` via the existing prompt block; the shape is unchanged.

#### To Add New

None.

### Documentation

#### Abstract (`docs/abstract/`)

- **Update** `docs/abstract/dish_analysis/nutritional_analysis.md` — under the "Curated nutrition database" sub-section, update the description to reflect a single combined search instead of per-component + fallback. No user-facing behaviour change (the DB block still appears or not based on the same confidence gate), so the change is one sentence of clarification.

#### Technical (`docs/technical/`)

- **Update** `docs/technical/dish_analysis/nutrition_db.md` — under "Downstream consumers → Stage 5", rewrite the description from "per-component + dish_name queries at min_confidence=70 and a combined-terms fallback at min_confidence=60" to "single combined-terms query with dish-token weighting at min_confidence=60".
- **Update** `docs/technical/dish_analysis/nutritional_analysis.md` — if Phase 2.1 is described there, update the search strategy description to match.

#### API Documentation (`docs/api_doc/`)

No changes needed — no endpoint signatures or response schemas change.

### Chrome Claude Extension Execution

Not applicable — this is a pure backend service refactor with no UI changes.

---

## Dependencies

- Stage 1 `NutritionCollectionService` must be seeded and functional.
- Stage 9 benchmark must pass after the change to validate retrieval quality is maintained.

## Open Questions

1. **Should `min_confidence` be 60 or tuned lower?** The combined query has more tokens, which can improve BM25 recall but may dilute per-token confidence. Stage 9 benchmark will be the arbiter — if NDCG drops, we may need to adjust.
2. **Should `_current_dish_tokens` be set via a public API rather than reaching into `svc._current_dish_tokens`?** Currently `search_nutrition_database_enhanced` does the same private-attribute mutation pattern. Could add a context-manager wrapper if we want cleaner encapsulation, but it's a cosmetic concern.
