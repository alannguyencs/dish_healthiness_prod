# Stage 9 — Regression Gate for Retrieval Quality

**Feature**: Ship an 846-query labeled evaluation set and a pytest benchmark that asserts `NutritionCollectionService._search_dishes_direct` produces aggregate NDCG@10 ≥ 0.75 against it. The benchmark is gated behind a `@pytest.mark.benchmark` marker so the fast unit-test suite skips it; operators run it via `pytest -m benchmark` for a nightly / manual regression profile. Pure CI addition — no pipeline changes, no user-visible behavior, no schema change.
**Plan Created:** 2026-04-19
**Status:** Plan
**Reference**:
- [Issues — 260415, Stage 9](../issues/260415.md)
- [Plan — Stage 1 Nutrition DB](./260418_stage1_nutrition_db.md) (ships the confidence formula that this regression gate guards)
- [Technical — Nutrition DB](../technical/dish_analysis/nutrition_db.md)
- [Chrome Test Spec — 260419_1238](../chrome_test/260419_1238_stage9_retrieval_regression_gate.md) (skipped — no UI)

---

## Problem Statement

1. Stage 1 committed to a verbatim port of the reference project's BM25 + confidence-scoring formula: 0.85 core / 0.15 descriptors, +0.20 / +0.15 bonuses, 0.8 keyword + 0.2 BM25-quality mix, scaled into `[0.50, 0.95]`. These constants were tuned against an 846-query labeled eval set and measured NDCG@10 = 0.7744. Altering any constant invalidates the benchmark.
2. Nothing in the current test suite guards that baseline. A future refactor — or a well-meaning "cleanup" of the scoring function, or a change to `searchable_document` generation in the seed script — could silently drop retrieval quality. Stage 7 thresholds (`THRESHOLD_DB_INCLUDE = 80`) implicitly bind to the formula's calibration; a drift would quietly starve Phase 2.3's prompt of evidence without any visible alert.
3. The eval set already exists in the reference project at `/Volumes/wd/projects/dish_healthiness/data/nutrition_db/retrieval_eval_dataset.csv` (847 lines: 1 header + 846 queries). Each row carries `query, relevant_dish_ids (JSON list), relevance_scores (JSON list of ints 1–3), query_type` — everything needed to compute NDCG@10.
4. The benchmark cannot run in the fast unit-test profile. It requires a populated `nutrition_foods` table (~4,493 rows) and runs 846 BM25 queries. Even on warm indices it's a ~5–15 s run; on fresh indices it adds the ~1 s initial build. Fast unit tests must stay under a few seconds.
5. There is no existing CI pipeline to hook into, so "CI-only" in this project means "explicitly marked and opt-in via `pytest -m benchmark` by an operator". The gate lives on `main` as documented ops runbook, not as a scheduled job — re-evaluate once a CI system is wired up.

---

## Proposed Solution

Three artifacts, all under `backend/tests/`:

1. **`backend/tests/data/retrieval_eval_dataset.csv`** — verbatim copy of the reference project's 846-query eval set. The schema is stable across the two codebases because the reference project is also our port's historical source; the `relevant_dish_ids` values are source-specific IDs (`ASC161` for Anuvaad, `8240` / `25609` for CIQUAL, etc.) that line up with this project's seeded `nutrition_foods.source_food_id` column.

2. **`backend/tests/test_nutrition_retrieval_benchmark.py`** — single pytest module:
   - `@pytest.mark.benchmark` on the top-level test so it's deselected by default.
   - Module-level skip if `nutrition_foods` is empty: `pytest.skip("Run `python -m scripts.seed.load_nutrition_db` first")`.
   - Loads the CSV, runs each query through `get_nutrition_service()._search_dishes_direct(text, top_k=10, min_confidence=0.0)`, extracts the per-match source-food-id, computes per-query NDCG@10, asserts `mean(ndcg_at_10) >= 0.75`.
   - Logs the computed aggregate (e.g. `Aggregate NDCG@10 = 0.7744 over 846 queries`) so a regression surfaces the drop numerically, not just as a fail/pass.

3. **`backend/pytest.ini`** — register the `benchmark` marker + exclude it from the default `addopts`:

```ini
[pytest]
testpaths = tests
pythonpath = .
asyncio_mode = auto
addopts = -m "not benchmark"
markers =
    benchmark: slow retrieval-quality benchmark; run nightly / manually via `pytest -m benchmark`.
filterwarnings =
    ignore::DeprecationWarning
```

Operators run `pytest -m benchmark` for the benchmark profile or `pytest backend/tests/test_nutrition_retrieval_benchmark.py` to force collection of just that one file.

### NDCG@10 implementation

Hand-rolled, no sklearn dependency (not in `requirements.txt` today; pulling it in for one metric would be overkill). The standard NDCG@10 formula:

```
DCG_K = sum over i=1..K of (2^{rel_i} - 1) / log2(i + 1)
IDCG_K = DCG_K computed against the ideal (sorted-descending) relevance list
NDCG_K = DCG_K / IDCG_K    (0 when IDCG_K == 0)
```

For each query:
- `relevant_dish_ids` → dict `{dish_id: relevance_score}`.
- Run the search; take top 10 matches; for each match extract its `source_food_id` (see "ID mapping" below).
- Build the per-rank relevance list: `rel[i] = relevant.get(match_id, 0)`.
- Compute `DCG_10` against this list; `IDCG_10` against `sorted(relevance_scores, reverse=True)[:10]` padded with zeros.
- `ndcg_10 = DCG_10 / IDCG_10` when `IDCG_10 > 0`, else `0`.

Aggregate is the arithmetic mean across all queries — same definition the reference's `retrieval_performance_metrics.json` uses (`"ndcg_at_10": 0.7744273641175244`).

### ID mapping — reading `source_food_id` off each match

`NutritionCollectionService._search_dishes_direct` returns rows with `nutrition_data` (the materialized per-source dict) plus `source`. The source-food-id lives in different keys per source:

- **MyFCD** — `nutrition_data["ndb_id"]` (explicit; `_materialize_myfcd` attaches it).
- **Malaysian** — derived at seed time from the source-file name (`ang_koo_kuih_mungbean` etc.). The seed script writes `source_food_id` onto the row but does NOT surface it into `raw_data` beyond the `food_item` field. The `_materialize_food` helper doesn't add it explicitly either.
- **Anuvaad** — `raw_data["food_code"]` (e.g. `ASC161`). Seed script preserves the verbatim CSV row.
- **CIQUAL** — `raw_data["food_code"]` (e.g. `25609`). Same.

A helper `_extract_match_id(match: Dict) -> Optional[str]` in the test module handles all four: checks `nutrition_data.get("ndb_id")`, `nutrition_data.get("food_code")`, and a new `nutrition_data.get("source_food_id")` fallback. For the Malaysian path where none of these is set, the test falls back to the tuple `(source, matched_food_name)` and compares against `relevant_dish_ids` case-insensitively — but the eval dataset's Malaysian entries are few and use the same `source_food_id` format the seed script writes.

**If this helper turns out brittle during implementation**, the cleaner alternative is to extend `NutritionCollectionService._materialize_food` to always attach `source_food_id` onto every materialized match dict (one line: `raw.setdefault("source_food_id", row.source_food_id)`). Prefer that over test-side brittle extraction. Flagged as an implementation-time decision; the plan ships the test-side helper first and defers the service-side addition unless the helper proves insufficient.

### Why a floor of 0.75 (not 0.77)

The reference measured 0.7744. The issue-spec floor of 0.75 gives us:

- ~3% slack for implementation drift (CIQUAL edge cases, Malaysian ID mapping, per-source `_materialize_food` differences from the reference).
- Headroom for the seed script's variation/synonym maps — if someone edits `scripts/seed/_variations.py` in a reasonable way and the aggregate drops from 0.7744 to 0.76, the gate does NOT fire; only a substantive regression (say to 0.72) fails. This is the right sensitivity for a historical anchor.

If the first measured NDCG on our codebase significantly exceeds 0.77, re-open the floor and raise it to `max(0.75, measured - 0.02)` to keep the gate tight. Recorded as a follow-up decision rather than a hard plan requirement.

---

## Current Implementation Analysis

### What Exists (keep as-is)

| Component | File | Status |
|-----------|------|--------|
| `NutritionCollectionService._search_dishes_direct(text, top_k, min_confidence)` | `backend/src/service/nutrition_db.py` | Keep — the benchmark calls this function unchanged. |
| `get_nutrition_service()` lazy singleton accessor | same | Keep — the benchmark uses the accessor to avoid rebuilding indices. |
| `NutritionDBEmptyError` | same | Keep — the benchmark catches it to emit a clean `pytest.skip`. |
| `nutrition_foods` schema + seed script | `backend/sql/create_tables.sql`, `backend/scripts/seed/load_nutrition_db.py` | Keep — benchmark depends on the seeded corpus. |
| Existing pytest harness | `backend/pytest.ini`, `backend/tests/conftest.py` | Extend `pytest.ini` with marker + `addopts`; `conftest.py` untouched. |
| Existing smoke test `backend/tests/test_nutrition_db.py` | runs against fixture rows, not the seeded DB | Keep — the benchmark is a separate file; the smoke test stays fast. |

### What Changes

| Component | Current | Proposed |
|-----------|---------|----------|
| `backend/pytest.ini` | No markers, no `addopts`. | Add `markers: benchmark: ...` registration + `addopts = -m "not benchmark"` so the fast suite skips. |
| `backend/tests/test_nutrition_retrieval_benchmark.py` | Does not exist. | New; loads CSV, runs 846 queries, asserts NDCG@10 ≥ 0.75. Decorated with `@pytest.mark.benchmark`. |
| `backend/tests/data/retrieval_eval_dataset.csv` | Does not exist. | New; copied verbatim from the reference project (846 queries). |

---

## Implementation Plan

### Key Workflow

Stage 9 is a test-only addition. The only runtime flow is pytest invoking the benchmark.

```
operator: pytest -m benchmark
  │
  ▼
test_nutrition_retrieval_benchmark.py:
  ├── try: service = get_nutrition_service()
  │   except NutritionDBEmptyError: pytest.skip("Run seed script first")
  │
  ├── rows = csv.DictReader(backend/tests/data/retrieval_eval_dataset.csv)
  │   (846 rows)
  │
  ├── for each row:
  │     query = row["query"]
  │     relevant = dict(zip(
  │         json.loads(row["relevant_dish_ids"]),
  │         [int(s) for s in json.loads(row["relevance_scores"])]))
  │     matches = service._search_dishes_direct(query, top_k=10, min_confidence=0.0)
  │     ranked_ids = [_extract_match_id(m) for m in matches]
  │     rel_list = [relevant.get(mid, 0) for mid in ranked_ids]
  │     ndcg = _compute_ndcg(rel_list, ideal=sorted(relevant.values(), reverse=True), k=10)
  │     per_query_ndcg.append(ndcg)
  │
  ├── aggregate = mean(per_query_ndcg)
  ├── print(f"NDCG@10 = {aggregate:.4f} across {len(per_query_ndcg)} queries")
  └── assert aggregate >= 0.75, f"Retrieval quality regression: {aggregate:.4f} < 0.75"
```

#### To Delete

None.

#### To Update

- `backend/pytest.ini` — register `benchmark` marker + exclude via `addopts`.

#### To Add New

- `backend/tests/data/retrieval_eval_dataset.csv` — 847 lines (header + 846 queries); ~80 KB.
- `backend/tests/test_nutrition_retrieval_benchmark.py` — ~120 lines.
- `backend/tests/data/__init__.py` — empty package marker so pytest-importmode=prepend resolves the path cleanly; skip if the existing harness doesn't require it.

---

### Database Schema

**No changes.** The benchmark queries the existing `nutrition_foods` + `nutrition_myfcd_nutrients` tables Stage 1 shipped. Empty DB → `pytest.skip`.

#### To Delete

None.

#### To Update

None.

#### To Add New

None.

---

### CRUD

**No new CRUD.** The benchmark calls `get_nutrition_service()._search_dishes_direct(...)` directly — no CRUD-layer additions.

#### To Delete

None.

#### To Update

None.

#### To Add New

None.

---

### Services

**No new services.** Stage 9 is a consumer of Stage 1's service, not a producer of new service code.

One deferred follow-up flagged in **Proposed Solution**: if the test-side `_extract_match_id` helper turns out brittle, extend `NutritionCollectionService._materialize_food` to attach `source_food_id` onto every match. Implementation-time decision, not committed in the plan.

#### To Delete

None.

#### To Update

None.

#### To Add New

None.

---

### API Endpoints

None. Stage 9 is benchmarks-only.

#### To Delete

None.

#### To Update

None.

#### To Add New

None.

---

### Testing

**`backend/tests/test_nutrition_retrieval_benchmark.py`** — the primary artifact.

Skeleton:

```python
"""
Retrieval-quality benchmark (Stage 9).

Runs the 846-query reference eval set through NutritionCollectionService
._search_dishes_direct and asserts aggregate NDCG@10 >= 0.75. Gated
behind @pytest.mark.benchmark so the fast test suite skips it; operator
runs `pytest -m benchmark` for the benchmark profile.

The 0.75 floor is 3% below the reference project's measured NDCG@10 of
0.7744 — allows small implementation drift (CIQUAL / Malaysian ID
mapping, per-source materialization differences) without constant
false-positive failures, but catches substantive regressions.
"""

import csv
import json
import math
import statistics
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from src.service.nutrition_db import NutritionDBEmptyError, get_nutrition_service


EVAL_CSV = Path(__file__).parent / "data" / "retrieval_eval_dataset.csv"
MIN_NDCG_10 = 0.75


def _load_eval_rows(path: Path) -> List[Dict[str, Any]]:
    """Load and parse the eval CSV into a list of row dicts."""
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            rows.append(
                {
                    "query": row["query"],
                    "relevant": dict(
                        zip(
                            json.loads(row["relevant_dish_ids"]),
                            [int(s) for s in json.loads(row["relevance_scores"])],
                        )
                    ),
                    "query_type": row.get("query_type", "unknown"),
                }
            )
        return rows


def _extract_match_id(match: Dict[str, Any]) -> Optional[str]:
    """
    Source-aware extraction of the `source_food_id`-equivalent for a
    `_search_dishes_direct` match. The eval dataset's relevant_dish_ids
    use this key per source:
      - myfcd: ndb_id (e.g. 'R101061')
      - anuvaad: food_code (e.g. 'ASC161')
      - ciqual: food_code (e.g. '25609')
      - malaysian_food_calories: source_food_id (derived from source_file at seed time)
    """
    data = match.get("nutrition_data") or {}
    for key in ("ndb_id", "food_code", "source_food_id"):
        value = data.get(key)
        if value:
            return str(value)
    return None


def _ndcg_at_k(rel_list: List[int], ideal_rels: List[int], k: int = 10) -> float:
    """Standard NDCG@k. Returns 0 when IDCG is 0."""

    def _dcg(rels: List[int]) -> float:
        return sum(
            (2 ** r - 1) / math.log2(i + 2) for i, r in enumerate(rels[:k])
        )

    idcg = _dcg(sorted(ideal_rels, reverse=True))
    if idcg == 0:
        return 0.0
    return _dcg(rel_list) / idcg


@pytest.mark.benchmark
def test_retrieval_ndcg_at_10_above_floor():
    """Aggregate NDCG@10 across the 846-query eval set must exceed 0.75."""
    try:
        service = get_nutrition_service()
    except NutritionDBEmptyError as exc:
        pytest.skip(
            f"nutrition_foods is empty — run "
            f"`python -m scripts.seed.load_nutrition_db` from backend/. ({exc})"
        )

    rows = _load_eval_rows(EVAL_CSV)
    per_query: List[float] = []
    for row in rows:
        matches = service._search_dishes_direct(row["query"], top_k=10, min_confidence=0.0)
        ranked_ids = [_extract_match_id(m) for m in matches]
        rel_list = [row["relevant"].get(mid, 0) for mid in ranked_ids]
        ideal_rels = list(row["relevant"].values())
        per_query.append(_ndcg_at_k(rel_list, ideal_rels, k=10))

    aggregate = statistics.mean(per_query) if per_query else 0.0
    print(
        f"\nRetrieval NDCG@10 = {aggregate:.4f} across {len(per_query)} queries "
        f"(anchor: reference measured 0.7744; floor: {MIN_NDCG_10})"
    )
    assert aggregate >= MIN_NDCG_10, (
        f"Retrieval quality regression: NDCG@10 = {aggregate:.4f} < {MIN_NDCG_10}"
    )
```

**Additional unit tests (fast suite, no marker):**

Two small helpers are worth covering to keep the benchmark trustworthy without requiring the slow DB path:

- `test_ndcg_at_k_basic_ideal_ranking` — rel_list == ideal_rels → NDCG == 1.0.
- `test_ndcg_at_k_zero_idcg` — all zeros → NDCG == 0 (no div-by-zero).
- `test_ndcg_at_k_standard_case` — known [3,2,3,0,1,2] with ideal [3,3,2,2,1] → compare against a hand-computed value.
- `test_extract_match_id_myfcd` — match with `nutrition_data.ndb_id` → returns that value.
- `test_extract_match_id_anuvaad` — match with `nutrition_data.food_code` → returns it.
- `test_extract_match_id_none` — match with no ID keys → returns None.
- `test_load_eval_rows_parses_json_columns` — round-trip an inline CSV fixture.

These sit in the same file but are NOT marked `@pytest.mark.benchmark` — they run in the fast profile and protect the NDCG math + ID extraction from bugs that would otherwise only surface during a nightly benchmark run.

**Pre-commit loop (mandatory):**

1. `source venv/bin/activate && pre-commit run --all-files`.
2. Fast suite must stay fast — verify the benchmark is deselected by `addopts = -m "not benchmark"`. Expected: the 7 helper tests run; the benchmark test is deselected with a visible message.
3. `backend/tests/data/retrieval_eval_dataset.csv` is large (~80 KB). Pre-commit's `check for added large files` may warn — the default limit is 500 KB so should pass, but verify.
4. Re-run until clean.

**Acceptance check from the issue's "done when":**

- `pytest backend/tests/test_nutrition_retrieval_benchmark.py` passes on main (against a seeded dev DB).
- Fast suite (`pre-commit run --all-files`, which invokes pytest via the pytest hook) skips the benchmark via the marker — verified by output showing `test_retrieval_ndcg_at_10_above_floor` deselected.

#### To Delete

None.

#### To Update

- `backend/pytest.ini` — register marker + exclude via `addopts`.

#### To Add New

- `backend/tests/data/retrieval_eval_dataset.csv`.
- `backend/tests/test_nutrition_retrieval_benchmark.py` — benchmark test + 7 fast helper tests.

---

### Frontend

None.

#### To Delete

None.

#### To Update

None.

#### To Add New

None.

---

### Documentation

#### Abstract (`docs/abstract/`)

No changes needed — Stage 9 has zero user-visible behavior. Same rationale as Stages 0 and 1 (pure library / CI additions).

#### Technical (`docs/technical/`)

- **Update** `docs/technical/dish_analysis/nutrition_db.md`:
  - Flip `[ ] Stage 9: NDCG@10 ≥ 0.75 regression gate against the 846-query eval set` → `[x]` on the Component Checklist.
  - Add a short **"Regression gate (Stage 9)"** sub-section under **Constraints & Edge Cases** covering:
    - The location of the eval CSV + benchmark test.
    - How to run the benchmark profile: `pytest -m benchmark` or targeting the file directly.
    - The historical anchor (0.7744) and the current floor (0.75) + rationale for the 3% slack.
    - Empty-DB behavior: `pytest.skip` with the seed command.
    - Warning that editing the Stage 1 confidence-formula constants or the seed script's variation maps must be done alongside a benchmark run.

#### API Documentation (`docs/api_doc/`)

No changes needed — no API surface.

#### To Delete

None.

#### To Update

- `docs/technical/dish_analysis/nutrition_db.md` — flip Stage 9 row + add regression-gate sub-section.

#### To Add New

None.

---

### Chrome Claude Extension Execution

**Skipped for Stage 9.** Spec at `docs/chrome_test/260419_1238_stage9_retrieval_regression_gate.md` is a one-page explanation of the skip. Same rationale as Stages 0 and 1: pure CI addition with no UI, no observable HTTP behavior.

The acceptance check is operator-run `pytest -m benchmark`. No Chrome harness integration.

#### To Delete

None.

#### To Update

None.

#### To Add New

- `docs/chrome_test/260419_1238_stage9_retrieval_regression_gate.md` (already written — skip note).

---

## Dependencies

- **Stage 1** — `NutritionCollectionService._search_dishes_direct`, `get_nutrition_service`, `NutritionDBEmptyError`. Benchmark reads via the singleton accessor; no modifications.
- **Seeded `nutrition_foods` table** — the benchmark cannot run on an empty DB; `pytest.skip` when the table is empty.
- **No new external libraries** — `csv`, `json`, `math`, `statistics` are stdlib. No sklearn.
- **No schema changes.**

---

## Resolved Decisions

- **Gating via `@pytest.mark.benchmark` + `addopts = -m "not benchmark"`** (confirmed with user 2026-04-19). Marker registered in `pytest.ini`; fast suite excludes; operators run `pytest -m benchmark`. Cleanest idiom; no custom collection logic or env-var sentinels.
- **Empty DB → `pytest.skip` naming the seed command** (confirmed with user 2026-04-19). The benchmark is explicitly not a fast unit test, so skipping on missing data is honest. `pytest.fail` would cause spurious red builds whenever an ops team forgets to seed before a nightly run.
- **Overall NDCG@10 ≥ 0.75 only, no per-query-type bands** (confirmed with user 2026-04-19). The reference's per-type numbers (exact_match 0.996, short 0.24, long 0.843) are noise unless the scoring formula changes — and that drop would already break the aggregate. Five more numbers to maintain for no marginal signal. Re-open if a future prompt/vocabulary tweak causes per-type drift that the aggregate smooths over.
- **Floor of 0.75, not 0.77** (decision recorded by the planner). 3% slack below the reference's measured 0.7744 to tolerate per-source materialization differences (CIQUAL, Malaysian IDs) without constant false-positives. If the first measured NDCG on this codebase is significantly above 0.77, raise the floor to `max(0.75, measured - 0.02)` as a follow-up.
- **ID extraction in the test, not in the service** (decision recorded by the planner, with follow-up escape hatch). The test-side `_extract_match_id` checks `ndb_id` / `food_code` / `source_food_id` in that order. If this proves brittle during implementation (e.g. Malaysian matches never resolve), flip to a service-side change: add one line `raw.setdefault("source_food_id", row.source_food_id)` in `_materialize_food` so every match carries the ID uniformly. Preferred over test-side extraction if it comes up.
- **Eval CSV lives in `backend/tests/data/`, not in a separate package** (decision recorded by the planner). One existing conventional location for test fixtures; no reason to split it out into `fixtures/` or `benchmark_data/`. ~80 KB is well under the project's `check for added large files` threshold.
- **Seven fast helper tests stay unmarked** (decision recorded by the planner). They cover the NDCG math and the ID extraction. Running them on every `pre-commit` ensures the benchmark's scaffolding never breaks silently — only the heavy 846-query run is gated. Approximately 50 ms added to the fast suite.

## Open Questions

None — all decisions resolved 2026-04-19. Ready for implementation.
