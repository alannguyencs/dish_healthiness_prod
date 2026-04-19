"""
Retrieval-quality benchmark (Stage 9).

Runs the 846-query reference eval set through
`NutritionCollectionService._search_dishes_direct` and asserts aggregate
NDCG@10 >= 0.75. Gated behind `@pytest.mark.benchmark` so the fast test
suite skips it; operators run `pytest -m benchmark` (or target the file
directly) for the benchmark profile.

The 0.75 floor sits 3% below the reference project's measured NDCG@10
of 0.7744 — tolerates small per-source materialization drift without
false positives, catches substantive regressions. See
`docs/plan/260419_stage9_retrieval_regression_gate.md` for the rationale.
"""

# pylint: disable=missing-function-docstring,redefined-outer-name
# pylint: disable=unused-argument,protected-access

import csv
import io
import json
import math
import statistics
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from src.service.nutrition_db import NutritionDBEmptyError, get_nutrition_service


EVAL_CSV = Path(__file__).parent / "data" / "retrieval_eval_dataset.csv"
MIN_NDCG_10 = 0.75


# ---------------------------------------------------------------------------
# Helpers (exercised by the fast-suite unit tests below + the benchmark)
# ---------------------------------------------------------------------------


def _load_eval_rows(path: Path) -> List[Dict[str, Any]]:
    """Load and parse the eval CSV into a list of normalized row dicts."""
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows: List[Dict[str, Any]] = []
        for row in reader:
            relevant_ids = json.loads(row["relevant_dish_ids"])
            relevance_scores = [int(s) for s in json.loads(row["relevance_scores"])]
            rows.append(
                {
                    "query": row["query"],
                    "relevant": dict(zip(relevant_ids, relevance_scores)),
                    "query_type": row.get("query_type", "unknown"),
                }
            )
        return rows


def _extract_match_id(match: Dict[str, Any]) -> Optional[str]:
    """
    Source-aware extraction of the `source_food_id`-equivalent for a
    `_search_dishes_direct` match.

    The eval dataset's `relevant_dish_ids` use this key per source:
      - myfcd: ndb_id (e.g. 'R101061')
      - anuvaad: food_code (e.g. 'ASC161')
      - ciqual: food_code (e.g. '25609')
      - malaysian_food_calories: source_food_id (derived from source_file
        at seed time; attached when `_materialize_food` preserves it)
    """
    data = match.get("nutrition_data") or {}
    for key in ("ndb_id", "food_code", "source_food_id"):
        value = data.get(key)
        if value:
            return str(value)
    return None


def _dcg(rels: List[int], k: int) -> float:
    return sum((2**r - 1) / math.log2(i + 2) for i, r in enumerate(rels[:k]))


def _ndcg_at_k(rel_list: List[int], ideal_rels: List[int], k: int = 10) -> float:
    """Standard NDCG@k. Returns 0 when IDCG is 0 (no relevant docs)."""
    idcg = _dcg(sorted(ideal_rels, reverse=True), k)
    if idcg == 0:
        return 0.0
    return _dcg(rel_list, k) / idcg


# ---------------------------------------------------------------------------
# Fast-suite unit tests (NOT marked benchmark — run on every pre-commit)
# ---------------------------------------------------------------------------


def test_ndcg_at_k_basic_ideal_ranking():
    """rel_list == ideal (perfect ranking) → NDCG == 1.0."""
    assert _ndcg_at_k([3, 2, 1], [3, 2, 1], k=10) == pytest.approx(1.0)


def test_ndcg_at_k_zero_idcg():
    """All-zero ideals → NDCG == 0 (no div-by-zero)."""
    assert _ndcg_at_k([0, 0, 0], [0, 0, 0], k=10) == 0.0


def test_ndcg_at_k_standard_case():
    """Known case — compare against a hand-computed value."""
    # ideal = [3,3,2,2,1]; ranking = [3,2,3,0,1,2]
    # dcg = (2^3-1)/log2(2) + (2^2-1)/log2(3) + (2^3-1)/log2(4)
    #     + 0 + (2^1-1)/log2(6) + (2^2-1)/log2(7)
    # idcg = (2^3-1)/log2(2) + (2^3-1)/log2(3) + (2^2-1)/log2(4)
    #      + (2^2-1)/log2(5) + (2^1-1)/log2(6)
    ranking = [3, 2, 3, 0, 1, 2]
    ideal = [3, 3, 2, 2, 1]
    result = _ndcg_at_k(ranking, ideal, k=10)
    expected_dcg = (
        (2**3 - 1) / math.log2(2)
        + (2**2 - 1) / math.log2(3)
        + (2**3 - 1) / math.log2(4)
        + 0
        + (2**1 - 1) / math.log2(6)
        + (2**2 - 1) / math.log2(7)
    )
    expected_idcg = (
        (2**3 - 1) / math.log2(2)
        + (2**3 - 1) / math.log2(3)
        + (2**2 - 1) / math.log2(4)
        + (2**2 - 1) / math.log2(5)
        + (2**1 - 1) / math.log2(6)
    )
    assert result == pytest.approx(expected_dcg / expected_idcg)


def test_extract_match_id_myfcd():
    match = {"nutrition_data": {"ndb_id": "R101061", "food_name": "Biscuit"}}
    assert _extract_match_id(match) == "R101061"


def test_extract_match_id_anuvaad():
    match = {"nutrition_data": {"food_code": "ASC161", "food_name": "Daal"}}
    assert _extract_match_id(match) == "ASC161"


def test_extract_match_id_source_food_id_fallback():
    match = {"nutrition_data": {"source_food_id": "malaysian_123"}}
    assert _extract_match_id(match) == "malaysian_123"


def test_extract_match_id_none_when_no_id_keys():
    assert _extract_match_id({"nutrition_data": {"food_name": "No ID here"}}) is None
    assert _extract_match_id({"nutrition_data": {}}) is None
    assert _extract_match_id({}) is None


def test_load_eval_rows_parses_json_columns(tmp_path):
    csv_text = (
        "query,relevant_dish_ids,relevance_scores,query_type\n"
        'chicken rice,"[""R101061"", ""ASC200""]","[3, 2]",exact_match\n'
    )
    path = tmp_path / "tiny.csv"
    path.write_text(csv_text, encoding="utf-8")
    rows = _load_eval_rows(path)
    assert len(rows) == 1
    assert rows[0]["query"] == "chicken rice"
    assert rows[0]["relevant"] == {"R101061": 3, "ASC200": 2}
    assert rows[0]["query_type"] == "exact_match"


def test_load_eval_rows_reads_shipped_dataset():
    """Sanity check the dataset shipped under backend/tests/data/."""
    rows = _load_eval_rows(EVAL_CSV)
    assert len(rows) == 846, f"expected 846 queries, got {len(rows)}"
    for row in rows[:5]:
        assert row["query"]
        assert row["relevant"]
        assert all(isinstance(v, int) for v in row["relevant"].values())


# ---------------------------------------------------------------------------
# Benchmark (deselected by default via pytest.ini `addopts = -m "not benchmark"`)
# ---------------------------------------------------------------------------


@pytest.mark.benchmark
def test_retrieval_ndcg_at_10_above_floor(capsys):
    """Aggregate NDCG@10 across the 846-query eval set must exceed 0.75."""
    try:
        service = get_nutrition_service()
    except NutritionDBEmptyError as exc:
        pytest.skip(
            "nutrition_foods is empty — run "
            "`python -m scripts.seed.load_nutrition_db` from backend/. "
            f"({exc})"
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

    # Emit to stdout for nightly-run visibility (captured by pytest).
    out = io.StringIO()
    out.write(
        f"\nRetrieval NDCG@10 = {aggregate:.4f} across {len(per_query)} queries "
        f"(anchor: reference measured 0.7744; floor: {MIN_NDCG_10})\n"
    )
    print(out.getvalue())

    assert (
        aggregate >= MIN_NDCG_10
    ), f"Retrieval quality regression: NDCG@10 = {aggregate:.4f} < {MIN_NDCG_10}"
