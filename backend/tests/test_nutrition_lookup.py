"""
Tests for backend/src/service/nutrition_lookup.py — Phase 2.1 orchestrator.

Patches `get_nutrition_service` + the service's `collect_from_nutrition_db`
at the module boundary so no BM25 corpus is built.
"""

# pylint: disable=missing-class-docstring,missing-function-docstring
# pylint: disable=redefined-outer-name,unused-argument

import pytest

from src.service import nutrition_lookup


def _result(top_confidence, *, n_matches=1, input_text=""):
    matches = (
        [
            {
                "matched_food_name": f"M{i}",
                "source": "myfcd",
                "confidence": top_confidence - (i * 0.05),
                "confidence_score": round((top_confidence - (i * 0.05)) * 100, 1),
                "nutrition_data": {},
                "search_method": "Direct BM25",
                "raw_bm25_score": 1.0,
                "matched_keywords": 1,
                "total_keywords": 1,
            }
            for i in range(n_matches)
        ]
        if n_matches
        else []
    )
    return {
        "success": True,
        "method": "Direct BM25 Text Matching",
        "input_text": input_text,
        "nutrition_matches": matches,
        "total_nutrition": {},
        "recommendations": [],
        "match_summary": {
            "total_matched": len(matches),
            "match_rate": 1.0 if matches else 0.0,
            "avg_confidence": round(top_confidence * 100, 1) if matches else 0.0,
            "deduplication_enabled": True,
            "search_method": "Direct BM25",
        },
        "processing_info": {},
    }


class _FakeService:
    def __init__(self, per_query_results=None, error=None):
        self.per_query_results = per_query_results or {}
        self.error = error
        self.calls = []

    def collect_from_nutrition_db(self, text, *, min_confidence=70, deduplicate=True):
        self.calls.append({"text": text, "min_confidence": min_confidence})
        if self.error is not None:
            raise self.error
        return self.per_query_results.get(text, _result(0.0, n_matches=0, input_text=text))


@pytest.fixture()
def patch_service(monkeypatch):
    def _apply(fake):
        monkeypatch.setattr(nutrition_lookup, "get_nutrition_service", lambda: fake)

    return _apply


def test_extract_and_lookup_empty_db_returns_empty_response(monkeypatch):
    def _raise():
        raise nutrition_lookup.NutritionDBEmptyError("nutrition_foods is empty")

    monkeypatch.setattr(nutrition_lookup, "get_nutrition_service", _raise)

    out = nutrition_lookup.extract_and_lookup_nutrition("Chicken Rice", [])
    assert out["nutrition_matches"] == []
    assert out["match_summary"]["reason"] == "nutrition_db_empty"
    assert out["success"] is True
    assert out["dish_candidates"] == ["Chicken Rice"]


def test_extract_and_lookup_happy_path_dish_name_wins(patch_service):
    fake = _FakeService(
        per_query_results={
            "Chicken Rice": _result(0.90, input_text="Chicken Rice"),
            "Rice": _result(0.60, input_text="Rice"),
        }
    )
    patch_service(fake)
    out = nutrition_lookup.extract_and_lookup_nutrition(
        "Chicken Rice",
        [{"component_name": "Rice"}],
    )
    assert out["search_strategy"].startswith("individual_dish_name: Chicken Rice")
    assert out["nutrition_matches"][0]["confidence"] == pytest.approx(0.90)


def test_extract_and_lookup_component_wins_over_dish_name(patch_service):
    fake = _FakeService(
        per_query_results={
            "Weird Dish": _result(0.60, input_text="Weird Dish"),
            "Grilled Chicken": _result(0.85, input_text="Grilled Chicken"),
        }
    )
    patch_service(fake)
    out = nutrition_lookup.extract_and_lookup_nutrition(
        "Weird Dish",
        [{"component_name": "Grilled Chicken"}],
    )
    assert out["search_strategy"] == "individual_dish_name: Grilled Chicken"


def test_extract_and_lookup_triggers_fallback_when_best_below_075(patch_service):
    fake = _FakeService(
        per_query_results={
            "Weird Dish": _result(0.55, input_text="Weird Dish"),
            "Weird Dish, Mystery Meat": _result(0.80, input_text="combo"),
        }
    )
    patch_service(fake)
    out = nutrition_lookup.extract_and_lookup_nutrition(
        "Weird Dish",
        [{"component_name": "Mystery Meat"}],
    )
    # components list gets deduped against dish name; query becomes
    # "Weird Dish, Mystery Meat"
    assert out["search_strategy"].startswith("combined_terms:")
    attempts = out["search_attempts"]
    assert any(a["query"] == "Weird Dish, Mystery Meat" for a in attempts)


def test_extract_and_lookup_fallback_skipped_when_best_at_or_above_075(patch_service):
    fake = _FakeService(
        per_query_results={
            "Chicken Rice": _result(0.80, input_text="Chicken Rice"),
        }
    )
    patch_service(fake)
    nutrition_lookup.extract_and_lookup_nutrition("Chicken Rice", [])
    # Only the single candidate was queried — no combined call
    assert [c["text"] for c in fake.calls] == ["Chicken Rice"]


def test_extract_and_lookup_fallback_retained_when_combined_is_lower(patch_service):
    fake = _FakeService(
        per_query_results={
            "Weird Dish": _result(0.60, input_text="Weird Dish"),
            "Weird Dish, Mystery Meat": _result(0.55, input_text="combo"),
        }
    )
    patch_service(fake)
    out = nutrition_lookup.extract_and_lookup_nutrition(
        "Weird Dish",
        [{"component_name": "Mystery Meat"}],
    )
    # Best was individual at 0.60; combined at 0.55 must not replace.
    assert out["search_strategy"] == "individual_dish_name: Weird Dish"


def test_extract_and_lookup_all_empty_returns_empty_shape(patch_service):
    fake = _FakeService()  # default: 0-match result for every query
    patch_service(fake)
    out = nutrition_lookup.extract_and_lookup_nutrition(
        "Unknown",
        [{"component_name": "Alpha"}, {"component_name": "Beta"}],
    )
    assert out["nutrition_matches"] == []
    assert out["match_summary"]["reason"] == "no_matches_across_strategies"
    # 3 individual queries + 1 combined fallback
    assert len(out["search_attempts"]) == 4


def test_extract_and_lookup_search_attempts_shape(patch_service):
    fake = _FakeService(
        per_query_results={
            "Dish": _result(0.80, input_text="Dish"),
        }
    )
    patch_service(fake)
    out = nutrition_lookup.extract_and_lookup_nutrition("Dish", [])
    for attempt in out["search_attempts"]:
        assert set(attempt.keys()) >= {"query", "success", "matches", "top_confidence"}


def test_extract_and_lookup_dedupes_component_names_equal_to_dish_name(patch_service):
    fake = _FakeService(
        per_query_results={"Chicken Rice": _result(0.80, input_text="Chicken Rice")}
    )
    patch_service(fake)
    nutrition_lookup.extract_and_lookup_nutrition(
        "Chicken Rice",
        [{"component_name": "Chicken Rice"}],
    )
    # Only one individual query, not two
    assert [c["text"] for c in fake.calls] == ["Chicken Rice"]
