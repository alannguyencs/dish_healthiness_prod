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
    # Stage 7 passes nutrition_db_matches + personalized_matches kwargs; the
    # fixture signature accepts them all.
    monkeypatch.setattr(
        item_tasks,
        "get_nutritional_analysis_prompt",
        lambda **_kw: "STEP2 PROMPT",
    )


@pytest.fixture()
def patch_lookup(monkeypatch):
    calls = []

    def _stub(dish_name, components):
        calls.append({"dish_name": dish_name, "components": components})
        return NUTRITION_FIXTURE

    monkeypatch.setattr(item_tasks, "extract_and_lookup_nutrition", _stub)
    # Stage 6: also patch the personalization lookup so gather resolves
    # in-process. Default to the empty list; per-test overrides replace
    # this with a richer fixture as needed.
    monkeypatch.setattr(
        item_tasks,
        "lookup_personalization",
        lambda user_id, query_id, description, confirmed_dish_name: [],
    )
    return calls


def _set_analyzer(monkeypatch, *, returns=None, raises=None):
    async def fake(*_a, **_kw):
        if raises is not None:
            raise raises
        return returns

    monkeypatch.setattr(item_tasks, "analyze_nutritional_analysis_async", fake)


def test_phase2_task_persists_nutrition_db_matches_before_pro_call(
    monkeypatch, patch_prompt, patch_lookup, captured_writes
):
    """The first write must carry nutrition_db_matches before the Pro call runs."""
    record = make_record(result_gemini={"phase": 1, "identification_data": {}, "identification_confirmed": True})
    writes, capture = captured_writes

    def _get_record(_id):
        if writes:
            record.result_gemini = writes[-1]["result_gemini"]
        return record

    monkeypatch.setattr(item_tasks, "get_dish_image_query_by_id", _get_record)
    monkeypatch.setattr(item_tasks, "update_dish_image_query_results", capture)
    _set_analyzer(monkeypatch, returns={"dish_name": "Chicken Rice", "calories_kcal": 500})

    asyncio.run(
        item_tasks.trigger_nutrition_analysis_background(
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
    record = make_record(result_gemini={"phase": 1, "identification_data": {}, "identification_confirmed": True})
    writes, capture = captured_writes

    def _get_record(_id):
        if writes:
            record.result_gemini = writes[-1]["result_gemini"]
        return record

    monkeypatch.setattr(item_tasks, "get_dish_image_query_by_id", _get_record)
    monkeypatch.setattr(item_tasks, "update_dish_image_query_results", capture)
    _set_analyzer(monkeypatch, returns={"dish_name": "Chicken Rice", "calories_kcal": 500})

    asyncio.run(
        item_tasks.trigger_nutrition_analysis_background(
            query_id=1,
            image_path="/tmp/x.jpg",
            dish_name="Chicken Rice",
            components=COMPONENTS,
        )
    )

    final = writes[-1]["result_gemini"]
    assert final["phase"] == 2
    assert final["nutrition_db_matches"] == NUTRITION_FIXTURE
    assert final["nutrition_data"]["calories_kcal"] == 500


def test_phase2_task_preserves_nutrition_db_matches_on_pro_failure(
    monkeypatch, patch_prompt, patch_lookup, captured_writes
):
    record = make_record(result_gemini={"phase": 1, "identification_data": {}, "identification_confirmed": True})
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
        item_tasks.trigger_nutrition_analysis_background(
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
    assert error_blob["nutrition_error"]["retry_count"] == 2


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

    record = make_record(result_gemini={"phase": 1, "identification_data": {}, "identification_confirmed": True})
    writes, capture = captured_writes

    def _get_record(_id):
        if writes:
            record.result_gemini = writes[-1]["result_gemini"]
        return record

    monkeypatch.setattr(item_tasks, "get_dish_image_query_by_id", _get_record)
    monkeypatch.setattr(item_tasks, "update_dish_image_query_results", capture)
    _set_analyzer(monkeypatch, returns={"dish_name": "Chicken Rice", "calories_kcal": 500})

    asyncio.run(
        item_tasks.trigger_nutrition_analysis_background(
            query_id=1,
            image_path="/tmp/x.jpg",
            dish_name="Chicken Rice",
            components=COMPONENTS,
        )
    )

    assert writes[0]["result_gemini"]["nutrition_db_matches"]["nutrition_matches"] == []
    assert writes[-1]["result_gemini"]["nutrition_data"]["calories_kcal"] == 500


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
        item_tasks.trigger_nutrition_analysis_background(
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


# ---------------------------------------------------------------------------
# Stage 6 — Phase 2.2 parallel gather + personalized_matches persistence
# ---------------------------------------------------------------------------


PERSONALIZATION_FIXTURE = [
    {
        "query_id": 42,
        "image_url": "/images/prior.jpg",
        "description": "chicken rice hainanese",
        "similarity_score": 0.82,
        "prior_nutrition_data": {"calories_kcal": 480, "dish_name": "Chicken Rice"},
        "corrected_nutrition_data": None,
    }
]


def _patch_personalization(monkeypatch, *, returns=None, raises=None):
    calls = []

    def _stub(user_id, query_id, description, confirmed_dish_name):
        calls.append(
            {
                "user_id": user_id,
                "query_id": query_id,
                "description": description,
                "confirmed_dish_name": confirmed_dish_name,
            }
        )
        if raises is not None:
            raise raises
        return list(returns) if returns is not None else []

    monkeypatch.setattr(item_tasks, "lookup_personalization", _stub)
    return calls


def test_phase2_task_persists_personalized_matches_pre_pro(
    monkeypatch, patch_prompt, captured_writes
):
    """Stage 6: first write carries both nutrition_db_matches AND personalized_matches."""
    record = make_record(
        result_gemini={
            "phase": 1,
            "identification_data": {},
            "identification_confirmed": True,
            "reference_image": {"description": "chicken rice"},
        }
    )
    writes, capture = captured_writes

    def _get_record(_id):
        if writes:
            record.result_gemini = writes[-1]["result_gemini"]
        return record

    monkeypatch.setattr(item_tasks, "get_dish_image_query_by_id", _get_record)
    monkeypatch.setattr(item_tasks, "update_dish_image_query_results", capture)
    monkeypatch.setattr(
        item_tasks, "extract_and_lookup_nutrition", lambda *_a, **_kw: NUTRITION_FIXTURE
    )
    persona_calls = _patch_personalization(monkeypatch, returns=PERSONALIZATION_FIXTURE)
    _set_analyzer(monkeypatch, returns={"dish_name": "Chicken Rice", "calories_kcal": 500})

    asyncio.run(
        item_tasks.trigger_nutrition_analysis_background(
            query_id=1,
            image_path="/tmp/x.jpg",
            dish_name="Chicken Rice",
            components=COMPONENTS,
        )
    )

    assert len(persona_calls) == 1
    assert persona_calls[0]["description"] == "chicken rice"
    assert persona_calls[0]["confirmed_dish_name"] == "Chicken Rice"

    pre_pro = writes[0]["result_gemini"]
    assert pre_pro["nutrition_db_matches"] == NUTRITION_FIXTURE
    assert pre_pro["personalized_matches"] == PERSONALIZATION_FIXTURE


def test_phase2_task_preserves_personalized_matches_on_pro_success(
    monkeypatch, patch_prompt, captured_writes
):
    record = make_record(
        result_gemini={
            "phase": 1,
            "identification_data": {},
            "identification_confirmed": True,
            "reference_image": {"description": "chicken rice"},
        }
    )
    writes, capture = captured_writes

    def _get_record(_id):
        if writes:
            record.result_gemini = writes[-1]["result_gemini"]
        return record

    monkeypatch.setattr(item_tasks, "get_dish_image_query_by_id", _get_record)
    monkeypatch.setattr(item_tasks, "update_dish_image_query_results", capture)
    monkeypatch.setattr(
        item_tasks, "extract_and_lookup_nutrition", lambda *_a, **_kw: NUTRITION_FIXTURE
    )
    _patch_personalization(monkeypatch, returns=PERSONALIZATION_FIXTURE)
    _set_analyzer(monkeypatch, returns={"dish_name": "Chicken Rice", "calories_kcal": 500})

    asyncio.run(
        item_tasks.trigger_nutrition_analysis_background(
            query_id=1,
            image_path="/tmp/x.jpg",
            dish_name="Chicken Rice",
            components=COMPONENTS,
        )
    )

    final = writes[-1]["result_gemini"]
    assert final["phase"] == 2
    assert final["personalized_matches"] == PERSONALIZATION_FIXTURE


def test_phase2_task_preserves_personalized_matches_on_pro_failure(
    monkeypatch, patch_prompt, captured_writes
):
    record = make_record(
        result_gemini={
            "phase": 1,
            "identification_data": {},
            "identification_confirmed": True,
            "reference_image": {"description": "chicken rice"},
        }
    )
    writes, capture = captured_writes

    def _get_record(_id):
        if writes:
            record.result_gemini = writes[-1]["result_gemini"]
        return record

    monkeypatch.setattr(item_tasks, "get_dish_image_query_by_id", _get_record)
    monkeypatch.setattr(item_tasks, "update_dish_image_query_results", capture)
    monkeypatch.setattr("src.api._phase_errors.get_dish_image_query_by_id", _get_record)
    monkeypatch.setattr("src.api._phase_errors.update_dish_image_query_results", capture)
    monkeypatch.setattr(
        item_tasks, "extract_and_lookup_nutrition", lambda *_a, **_kw: NUTRITION_FIXTURE
    )
    _patch_personalization(monkeypatch, returns=PERSONALIZATION_FIXTURE)
    _set_analyzer(monkeypatch, raises=ValueError("GEMINI_API_KEY missing"))

    asyncio.run(
        item_tasks.trigger_nutrition_analysis_background(
            query_id=1,
            image_path="/tmp/x.jpg",
            dish_name="Chicken Rice",
            components=COMPONENTS,
            retry_count=1,
        )
    )

    error_blob = writes[-1]["result_gemini"]
    assert error_blob["personalized_matches"] == PERSONALIZATION_FIXTURE
    assert error_blob["nutrition_error"]["retry_count"] == 1


def test_phase2_task_phase_2_2_exception_degrades_to_empty_list(
    monkeypatch, patch_prompt, captured_writes, caplog
):
    """Phase 2.2 raises → personalized_matches=[]; Phase 2.1 still lands; Pro call still runs."""
    record = make_record(
        result_gemini={
            "phase": 1,
            "identification_data": {},
            "identification_confirmed": True,
            "reference_image": {"description": "chicken rice"},
        }
    )
    writes, capture = captured_writes

    def _get_record(_id):
        if writes:
            record.result_gemini = writes[-1]["result_gemini"]
        return record

    monkeypatch.setattr(item_tasks, "get_dish_image_query_by_id", _get_record)
    monkeypatch.setattr(item_tasks, "update_dish_image_query_results", capture)
    monkeypatch.setattr(
        item_tasks, "extract_and_lookup_nutrition", lambda *_a, **_kw: NUTRITION_FIXTURE
    )
    _patch_personalization(monkeypatch, raises=RuntimeError("personalization index down"))
    _set_analyzer(monkeypatch, returns={"dish_name": "Chicken Rice", "calories_kcal": 500})

    with caplog.at_level("WARNING"):
        asyncio.run(
            item_tasks.trigger_nutrition_analysis_background(
                query_id=1,
                image_path="/tmp/x.jpg",
                dish_name="Chicken Rice",
                components=COMPONENTS,
            )
        )

    pre_pro = writes[0]["result_gemini"]
    assert pre_pro["personalized_matches"] == []
    assert pre_pro["nutrition_db_matches"] == NUTRITION_FIXTURE
    final = writes[-1]["result_gemini"]
    assert final["nutrition_data"]["calories_kcal"] == 500
    assert any(
        "Phase 2.2 raised" in rec.message and "personalization index down" in rec.message
        for rec in caplog.records
    )


def test_phase2_task_phase_2_1_exception_degrades_to_empty_shape(
    monkeypatch, patch_prompt, captured_writes, caplog
):
    """Phase 2.1 raises → nutrition empty-shape; personalization + Pro call still run."""
    record = make_record(
        result_gemini={
            "phase": 1,
            "identification_data": {},
            "identification_confirmed": True,
            "reference_image": {"description": "chicken rice"},
        }
    )
    writes, capture = captured_writes

    def _get_record(_id):
        if writes:
            record.result_gemini = writes[-1]["result_gemini"]
        return record

    monkeypatch.setattr(item_tasks, "get_dish_image_query_by_id", _get_record)
    monkeypatch.setattr(item_tasks, "update_dish_image_query_results", capture)

    def _raise(*_a, **_kw):
        raise RuntimeError("nutrition index down")

    monkeypatch.setattr(item_tasks, "extract_and_lookup_nutrition", _raise)
    _patch_personalization(monkeypatch, returns=PERSONALIZATION_FIXTURE)
    _set_analyzer(monkeypatch, returns={"dish_name": "Chicken Rice", "calories_kcal": 500})

    with caplog.at_level("WARNING"):
        asyncio.run(
            item_tasks.trigger_nutrition_analysis_background(
                query_id=1,
                image_path="/tmp/x.jpg",
                dish_name="Chicken Rice",
                components=COMPONENTS,
            )
        )

    pre_pro = writes[0]["result_gemini"]
    assert pre_pro["nutrition_db_matches"]["nutrition_matches"] == []
    assert pre_pro["nutrition_db_matches"]["match_summary"]["reason"] == "unexpected_exception"
    assert pre_pro["personalized_matches"] == PERSONALIZATION_FIXTURE
    assert any("Phase 2.1 raised" in rec.message for rec in caplog.records)


def test_phase2_task_both_exceptions_still_runs_pro_call(
    monkeypatch, patch_prompt, captured_writes
):
    record = make_record(
        result_gemini={
            "phase": 1,
            "identification_data": {},
            "identification_confirmed": True,
            "reference_image": {"description": "chicken rice"},
        }
    )
    writes, capture = captured_writes

    def _get_record(_id):
        if writes:
            record.result_gemini = writes[-1]["result_gemini"]
        return record

    monkeypatch.setattr(item_tasks, "get_dish_image_query_by_id", _get_record)
    monkeypatch.setattr(item_tasks, "update_dish_image_query_results", capture)

    def _raise_nut(*_a, **_kw):
        raise RuntimeError("nut down")

    monkeypatch.setattr(item_tasks, "extract_and_lookup_nutrition", _raise_nut)
    _patch_personalization(monkeypatch, raises=RuntimeError("persona down"))
    _set_analyzer(monkeypatch, returns={"dish_name": "X", "calories_kcal": 100})

    asyncio.run(
        item_tasks.trigger_nutrition_analysis_background(
            query_id=1,
            image_path="/tmp/x.jpg",
            dish_name="X",
            components=COMPONENTS,
        )
    )

    pre_pro = writes[0]["result_gemini"]
    assert pre_pro["nutrition_db_matches"]["nutrition_matches"] == []
    assert pre_pro["personalized_matches"] == []
    final = writes[-1]["result_gemini"]
    assert final["nutrition_data"]["calories_kcal"] == 100


def test_phase2_task_reads_reference_description_from_record(
    monkeypatch, patch_prompt, captured_writes
):
    """lookup_personalization receives the reference_image.description from result_gemini."""
    record = make_record(
        result_gemini={
            "phase": 1,
            "identification_data": {},
            "identification_confirmed": True,
            "reference_image": {"description": "beef noodle soup"},
        }
    )
    writes, capture = captured_writes

    def _get_record(_id):
        if writes:
            record.result_gemini = writes[-1]["result_gemini"]
        return record

    monkeypatch.setattr(item_tasks, "get_dish_image_query_by_id", _get_record)
    monkeypatch.setattr(item_tasks, "update_dish_image_query_results", capture)
    monkeypatch.setattr(
        item_tasks, "extract_and_lookup_nutrition", lambda *_a, **_kw: NUTRITION_FIXTURE
    )
    persona_calls = _patch_personalization(monkeypatch, returns=[])
    _set_analyzer(monkeypatch, returns={"dish_name": "Pho Bo", "calories_kcal": 400})

    asyncio.run(
        item_tasks.trigger_nutrition_analysis_background(
            query_id=7,
            image_path="/tmp/x.jpg",
            dish_name="Pho Bo",
            components=COMPONENTS,
        )
    )

    assert persona_calls[0]["description"] == "beef noodle soup"
    assert persona_calls[0]["query_id"] == 7
    assert persona_calls[0]["user_id"] == record.user_id


# ---------------------------------------------------------------------------
# Stage 7 — Phase 2.3 threshold-gated blocks + image-B attach
# ---------------------------------------------------------------------------


def _patch_persisted_record(
    monkeypatch,
    writes_list,
    *,
    nutrition_db_matches=None,
    personalized_matches=None,
):
    """
    Install get_dish_image_query_by_id so Stage 7 sees persisted matches.
    `writes_list` is the shared capture list from the `captured_writes`
    fixture — passed in so re-reads after capture see the latest write.
    """
    base = {
        "phase": 1,
        "identification_data": {},
        "identification_confirmed": True,
        "reference_image": {"description": "chicken rice"},
        "nutrition_db_matches": nutrition_db_matches,
        "personalized_matches": personalized_matches,
    }
    record = make_record(result_gemini=base)

    def _get_record(_id):
        if writes_list:
            record.result_gemini = writes_list[-1]["result_gemini"]
        return record

    monkeypatch.setattr(item_tasks, "get_dish_image_query_by_id", _get_record)
    return record


def _patch_prompt_capture(monkeypatch):
    captured = {}

    def _capture(**kwargs):
        captured.update(kwargs)
        return "STEP2 PROMPT"

    monkeypatch.setattr(item_tasks, "get_nutritional_analysis_prompt", _capture)
    return captured


def _patch_analyzer_capture(monkeypatch):
    captured = {}

    async def _capture(**kwargs):
        captured.update(kwargs)
        return {
            "dish_name": "Chicken Rice",
            "calories_kcal": 500,
            "reasoning_sources": "stub",
        }

    monkeypatch.setattr(item_tasks, "analyze_nutritional_analysis_async", _capture)
    return captured


def test_stage7_plumbs_matches_into_prompt_builder(monkeypatch, captured_writes, tmp_path):
    """Stage 7: nutrition_db_matches + personalized_matches flow from record into the prompt."""
    nutrition_db_matches = {"nutrition_matches": [{"matched_food_name": "Chicken Rice"}]}
    personalized_matches = [{"query_id": 42, "similarity_score": 0.50, "image_url": None}]

    writes, capture = captured_writes
    _patch_persisted_record(
        monkeypatch,
        writes,
        nutrition_db_matches=nutrition_db_matches,
        personalized_matches=personalized_matches,
    )
    monkeypatch.setattr(item_tasks, "update_dish_image_query_results", capture)

    monkeypatch.setattr(
        item_tasks, "extract_and_lookup_nutrition", lambda *_a, **_kw: nutrition_db_matches
    )
    monkeypatch.setattr(
        item_tasks,
        "lookup_personalization",
        lambda user_id, query_id, description, confirmed_dish_name: personalized_matches,
    )
    prompt_captured = _patch_prompt_capture(monkeypatch)
    _patch_analyzer_capture(monkeypatch)

    # Fix IMAGE_DIR so the missing-image path is exercised cleanly
    monkeypatch.setattr(item_tasks, "IMAGE_DIR", tmp_path)

    asyncio.run(
        item_tasks.trigger_nutrition_analysis_background(
            query_id=1,
            image_path="/tmp/q.jpg",
            dish_name="Chicken Rice",
            components=COMPONENTS,
        )
    )

    assert prompt_captured["nutrition_db_matches"] == nutrition_db_matches
    assert prompt_captured["personalized_matches"] == personalized_matches


def test_stage7_resolves_image_bytes_when_similarity_above_035(
    monkeypatch, captured_writes, tmp_path
):
    """Top-1 similarity 0.50 + file on disk → analyzer receives reference_image_bytes."""
    ref_bytes = b"prior-jpeg-bytes"
    ref_file = tmp_path / "prior.jpg"
    ref_file.write_bytes(ref_bytes)

    personalized_matches = [
        {
            "query_id": 42,
            "similarity_score": 0.50,
            "image_url": "/images/prior.jpg",
            "description": "c",
            "prior_nutrition_data": None,
            "corrected_nutrition_data": None,
        }
    ]
    writes, capture = captured_writes
    _patch_persisted_record(
        monkeypatch,
        writes,
        nutrition_db_matches={"nutrition_matches": []},
        personalized_matches=personalized_matches,
    )
    monkeypatch.setattr(item_tasks, "update_dish_image_query_results", capture)
    monkeypatch.setattr(
        item_tasks, "extract_and_lookup_nutrition", lambda *_a, **_kw: {"nutrition_matches": []}
    )
    monkeypatch.setattr(
        item_tasks,
        "lookup_personalization",
        lambda *a, **kw: personalized_matches,
    )
    _patch_prompt_capture(monkeypatch)
    analyzer_captured = _patch_analyzer_capture(monkeypatch)

    monkeypatch.setattr(item_tasks, "IMAGE_DIR", tmp_path)

    asyncio.run(
        item_tasks.trigger_nutrition_analysis_background(
            query_id=1,
            image_path="/tmp/q.jpg",
            dish_name="Chicken Rice",
            components=COMPONENTS,
        )
    )

    assert analyzer_captured["reference_image_bytes"] == ref_bytes


def test_stage7_no_image_bytes_when_similarity_below_035(monkeypatch, captured_writes, tmp_path):
    personalized_matches = [
        {
            "query_id": 42,
            "similarity_score": 0.32,
            "image_url": "/images/prior.jpg",
            "description": "c",
            "prior_nutrition_data": None,
            "corrected_nutrition_data": None,
        }
    ]
    writes, capture = captured_writes
    _patch_persisted_record(
        monkeypatch,
        writes,
        nutrition_db_matches={"nutrition_matches": []},
        personalized_matches=personalized_matches,
    )
    monkeypatch.setattr(item_tasks, "update_dish_image_query_results", capture)
    monkeypatch.setattr(
        item_tasks, "extract_and_lookup_nutrition", lambda *_a, **_kw: {"nutrition_matches": []}
    )
    monkeypatch.setattr(
        item_tasks,
        "lookup_personalization",
        lambda *a, **kw: personalized_matches,
    )
    _patch_prompt_capture(monkeypatch)
    analyzer_captured = _patch_analyzer_capture(monkeypatch)

    monkeypatch.setattr(item_tasks, "IMAGE_DIR", tmp_path)

    asyncio.run(
        item_tasks.trigger_nutrition_analysis_background(
            query_id=1,
            image_path="/tmp/q.jpg",
            dish_name="Chicken Rice",
            components=COMPONENTS,
        )
    )

    assert analyzer_captured["reference_image_bytes"] is None


def test_stage7_no_image_bytes_when_file_missing_and_logs_warn(
    monkeypatch, captured_writes, tmp_path, caplog
):
    """similarity >= 0.35 but file missing → None + WARN log."""
    personalized_matches = [
        {
            "query_id": 42,
            "similarity_score": 0.70,
            "image_url": "/images/gone.jpg",
            "description": "c",
            "prior_nutrition_data": None,
            "corrected_nutrition_data": None,
        }
    ]
    writes, capture = captured_writes
    _patch_persisted_record(
        monkeypatch,
        writes,
        nutrition_db_matches={"nutrition_matches": []},
        personalized_matches=personalized_matches,
    )
    monkeypatch.setattr(item_tasks, "update_dish_image_query_results", capture)
    monkeypatch.setattr(
        item_tasks, "extract_and_lookup_nutrition", lambda *_a, **_kw: {"nutrition_matches": []}
    )
    monkeypatch.setattr(
        item_tasks,
        "lookup_personalization",
        lambda *a, **kw: personalized_matches,
    )
    _patch_prompt_capture(monkeypatch)
    analyzer_captured = _patch_analyzer_capture(monkeypatch)

    monkeypatch.setattr(item_tasks, "IMAGE_DIR", tmp_path)  # no file created

    with caplog.at_level("WARNING"):
        asyncio.run(
            item_tasks.trigger_nutrition_analysis_background(
                query_id=1,
                image_path="/tmp/q.jpg",
                dish_name="Chicken Rice",
                components=COMPONENTS,
            )
        )

    assert analyzer_captured["reference_image_bytes"] is None
    assert any("reference image missing" in rec.message for rec in caplog.records)


def test_stage7_no_image_bytes_when_no_personalized_matches(
    monkeypatch, captured_writes, tmp_path
):
    writes, capture = captured_writes
    _patch_persisted_record(
        monkeypatch,
        writes,
        nutrition_db_matches={"nutrition_matches": []},
        personalized_matches=[],
    )
    monkeypatch.setattr(item_tasks, "update_dish_image_query_results", capture)
    monkeypatch.setattr(
        item_tasks, "extract_and_lookup_nutrition", lambda *_a, **_kw: {"nutrition_matches": []}
    )
    monkeypatch.setattr(item_tasks, "lookup_personalization", lambda *a, **kw: [])
    _patch_prompt_capture(monkeypatch)
    analyzer_captured = _patch_analyzer_capture(monkeypatch)

    monkeypatch.setattr(item_tasks, "IMAGE_DIR", tmp_path)

    asyncio.run(
        item_tasks.trigger_nutrition_analysis_background(
            query_id=1,
            image_path="/tmp/q.jpg",
            dish_name="Chicken Rice",
            components=COMPONENTS,
        )
    )

    assert analyzer_captured["reference_image_bytes"] is None


def test_stage7_persists_reasoning_fields_from_step2_result(
    monkeypatch, captured_writes, tmp_path
):
    writes, capture = captured_writes
    _patch_persisted_record(
        monkeypatch,
        writes,
        nutrition_db_matches={"nutrition_matches": []},
        personalized_matches=[],
    )
    monkeypatch.setattr(item_tasks, "update_dish_image_query_results", capture)
    monkeypatch.setattr(
        item_tasks, "extract_and_lookup_nutrition", lambda *_a, **_kw: {"nutrition_matches": []}
    )
    monkeypatch.setattr(item_tasks, "lookup_personalization", lambda *a, **kw: [])
    _patch_prompt_capture(monkeypatch)

    async def _fake(**_kw):
        return {
            "dish_name": "Chicken Rice",
            "calories_kcal": 500,
            "reasoning_sources": "Nutrition DB: Chicken Rice (malaysian, 88%)",
            "reasoning_calories": "From DB top match, scaled to serving",
            "reasoning_micronutrients": "",
        }

    monkeypatch.setattr(item_tasks, "analyze_nutritional_analysis_async", _fake)
    monkeypatch.setattr(item_tasks, "IMAGE_DIR", tmp_path)

    asyncio.run(
        item_tasks.trigger_nutrition_analysis_background(
            query_id=1,
            image_path="/tmp/q.jpg",
            dish_name="Chicken Rice",
            components=COMPONENTS,
        )
    )

    final = writes[-1]["result_gemini"]
    assert final["nutrition_data"]["reasoning_sources"].startswith("Nutrition DB")
    assert final["nutrition_data"]["reasoning_calories"]
    assert final["nutrition_data"]["reasoning_micronutrients"] == ""
