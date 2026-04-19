"""
Tests for backend/src/api/item_tasks.py — Phase 2 background task + Phase 2.1 hook.

Patches the Gemini analyzer, the prompt loader, and the Phase 2.1
orchestrator so the task runs in-process without network / BM25 cost.
"""

# pylint: disable=missing-class-docstring,missing-function-docstring
# pylint: disable=redefined-outer-name,unused-argument

import asyncio

import pytest

from src.api import item_tasks
from tests.conftest import make_record


NUTRITION_FIXTURE = {
    "success": True,
    "method": "Direct BM25 Text Matching",
    "input_text": "Chicken Rice",
    "nutrition_matches": [
        {
            "matched_food_name": "Chicken Rice",
            "source": "malaysian_food_calories",
            "confidence": 0.88,
            "confidence_score": 88.0,
            "nutrition_data": {"calories": 500},
            "search_method": "Direct BM25",
            "raw_bm25_score": 2.5,
            "matched_keywords": 2,
            "total_keywords": 2,
        }
    ],
    "total_nutrition": {"total_calories": 500},
    "recommendations": ["variety"],
    "match_summary": {"total_matched": 1, "avg_confidence": 88.0},
    "processing_info": {},
    "search_strategy": "individual_dish_name: Chicken Rice",
    "search_attempts": [
        {"query": "Chicken Rice", "success": True, "matches": 1, "top_confidence": 0.88}
    ],
    "dish_candidates": ["Chicken Rice"],
}


COMPONENTS = [
    {
        "component_name": "Chicken Rice",
        "selected_serving_size": "1 cup",
        "number_of_servings": 1.0,
    }
]


@pytest.fixture()
def patch_prompt(monkeypatch):
    monkeypatch.setattr(
        item_tasks,
        "get_step2_nutritional_analysis_prompt",
        lambda dish_name, components: "STEP2 PROMPT",
    )


@pytest.fixture()
def patch_lookup(monkeypatch):
    calls = []

    def _stub(dish_name, components):
        calls.append({"dish_name": dish_name, "components": components})
        return NUTRITION_FIXTURE

    monkeypatch.setattr(item_tasks, "extract_and_lookup_nutrition", _stub)
    return calls


def _set_analyzer(monkeypatch, *, returns=None, raises=None):
    async def fake(*_a, **_kw):
        if raises is not None:
            raise raises
        return returns

    monkeypatch.setattr(item_tasks, "analyze_step2_nutritional_analysis_async", fake)


def test_phase2_task_persists_nutrition_db_matches_before_pro_call(
    monkeypatch, patch_prompt, patch_lookup, captured_writes
):
    """The first write must carry nutrition_db_matches before the Pro call runs."""
    record = make_record(result_gemini={"step": 1, "step1_data": {}, "step1_confirmed": True})
    writes, capture = captured_writes

    def _get_record(_id):
        if writes:
            record.result_gemini = writes[-1]["result_gemini"]
        return record

    monkeypatch.setattr(item_tasks, "get_dish_image_query_by_id", _get_record)
    monkeypatch.setattr(item_tasks, "update_dish_image_query_results", capture)
    _set_analyzer(monkeypatch, returns={"dish_name": "Chicken Rice", "calories_kcal": 500})

    asyncio.run(
        item_tasks.trigger_step2_analysis_background(
            query_id=1,
            image_path="/tmp/x.jpg",
            dish_name="Chicken Rice",
            components=COMPONENTS,
        )
    )

    assert len(writes) == 2
    # First write is the pre-Pro Phase 2.1 persist.
    assert "nutrition_db_matches" in writes[0]["result_gemini"]
    assert writes[0]["result_gemini"]["nutrition_db_matches"] == NUTRITION_FIXTURE


def test_phase2_task_preserves_nutrition_db_matches_on_pro_success(
    monkeypatch, patch_prompt, patch_lookup, captured_writes
):
    record = make_record(result_gemini={"step": 1, "step1_data": {}, "step1_confirmed": True})
    writes, capture = captured_writes

    def _get_record(_id):
        if writes:
            record.result_gemini = writes[-1]["result_gemini"]
        return record

    monkeypatch.setattr(item_tasks, "get_dish_image_query_by_id", _get_record)
    monkeypatch.setattr(item_tasks, "update_dish_image_query_results", capture)
    _set_analyzer(monkeypatch, returns={"dish_name": "Chicken Rice", "calories_kcal": 500})

    asyncio.run(
        item_tasks.trigger_step2_analysis_background(
            query_id=1,
            image_path="/tmp/x.jpg",
            dish_name="Chicken Rice",
            components=COMPONENTS,
        )
    )

    final = writes[-1]["result_gemini"]
    assert final["step"] == 2
    assert final["nutrition_db_matches"] == NUTRITION_FIXTURE
    assert final["step2_data"]["calories_kcal"] == 500


def test_phase2_task_preserves_nutrition_db_matches_on_pro_failure(
    monkeypatch, patch_prompt, patch_lookup, captured_writes
):
    record = make_record(result_gemini={"step": 1, "step1_data": {}, "step1_confirmed": True})
    writes, capture = captured_writes

    def _get_record(_id):
        if writes:
            record.result_gemini = writes[-1]["result_gemini"]
        return record

    monkeypatch.setattr(item_tasks, "get_dish_image_query_by_id", _get_record)
    monkeypatch.setattr(item_tasks, "update_dish_image_query_results", capture)
    monkeypatch.setattr("src.api._phase_errors.get_dish_image_query_by_id", _get_record)
    monkeypatch.setattr("src.api._phase_errors.update_dish_image_query_results", capture)
    _set_analyzer(monkeypatch, raises=ValueError("GEMINI_API_KEY missing"))

    asyncio.run(
        item_tasks.trigger_step2_analysis_background(
            query_id=1,
            image_path="/tmp/x.jpg",
            dish_name="Chicken Rice",
            components=COMPONENTS,
            retry_count=2,
        )
    )

    # Pre-Pro persist then the error path.
    assert len(writes) == 2
    assert writes[0]["result_gemini"]["nutrition_db_matches"] == NUTRITION_FIXTURE
    error_blob = writes[-1]["result_gemini"]
    assert error_blob["nutrition_db_matches"] == NUTRITION_FIXTURE
    assert error_blob["step2_error"]["retry_count"] == 2


def test_phase2_task_empty_db_still_schedules_and_succeeds(
    monkeypatch, patch_prompt, captured_writes
):
    """Orchestrator returns empty-response shape; Phase 2 still proceeds."""
    empty_result = {
        "success": True,
        "method": "Direct BM25 Text Matching",
        "input_text": "Chicken Rice",
        "nutrition_matches": [],
        "total_nutrition": {},
        "recommendations": [],
        "match_summary": {"total_matched": 0, "reason": "nutrition_db_empty"},
        "processing_info": {},
        "search_strategy": "none",
        "search_attempts": [],
        "dish_candidates": ["Chicken Rice"],
    }
    monkeypatch.setattr(
        item_tasks, "extract_and_lookup_nutrition", lambda *_a, **_kw: empty_result
    )

    record = make_record(result_gemini={"step": 1, "step1_data": {}, "step1_confirmed": True})
    writes, capture = captured_writes

    def _get_record(_id):
        if writes:
            record.result_gemini = writes[-1]["result_gemini"]
        return record

    monkeypatch.setattr(item_tasks, "get_dish_image_query_by_id", _get_record)
    monkeypatch.setattr(item_tasks, "update_dish_image_query_results", capture)
    _set_analyzer(monkeypatch, returns={"dish_name": "Chicken Rice", "calories_kcal": 500})

    asyncio.run(
        item_tasks.trigger_step2_analysis_background(
            query_id=1,
            image_path="/tmp/x.jpg",
            dish_name="Chicken Rice",
            components=COMPONENTS,
        )
    )

    assert writes[0]["result_gemini"]["nutrition_db_matches"]["nutrition_matches"] == []
    assert writes[-1]["result_gemini"]["step2_data"]["calories_kcal"] == 500


def test_phase2_task_skips_pre_pro_persist_when_no_result_gemini(
    monkeypatch, patch_prompt, patch_lookup, captured_writes
):
    """If Phase 1 never landed result_gemini, the pre-Pro write is skipped."""
    record = make_record(result_gemini=None)
    writes, capture = captured_writes

    def _get_record(_id):
        if writes:
            record.result_gemini = writes[-1]["result_gemini"]
        return record

    monkeypatch.setattr(item_tasks, "get_dish_image_query_by_id", _get_record)
    monkeypatch.setattr(item_tasks, "update_dish_image_query_results", capture)
    _set_analyzer(monkeypatch, returns={"dish_name": "X", "calories_kcal": 100})

    asyncio.run(
        item_tasks.trigger_step2_analysis_background(
            query_id=1,
            image_path="/tmp/x.jpg",
            dish_name="X",
            components=COMPONENTS,
        )
    )

    # Pre-Pro persist skipped — the function bails after the analyzer returns
    # because result_gemini is still None when the post-Pro re-read happens.
    # No writes at all.
    assert writes == []
