"""
Tests for Phase 1 background task in src/api/item_step1_tasks.py.

Mocks the Gemini call (`analyze_step1_component_identification_async`) and the
prompt loader so the task runs synchronously in-process without network or
filesystem.
"""

# pylint: disable=missing-class-docstring,missing-function-docstring
# pylint: disable=redefined-outer-name,unused-argument

import asyncio
import pytest

from src.api import item_step1_tasks
from tests.conftest import make_record


@pytest.fixture()
def patch_prompt(monkeypatch):
    monkeypatch.setattr(
        item_step1_tasks,
        "get_step1_component_identification_prompt",
        lambda: "STEP1 SYSTEM PROMPT",
    )


@pytest.fixture()
def patch_crud(monkeypatch, captured_writes):
    writes, capture = captured_writes
    monkeypatch.setattr(item_step1_tasks, "update_dish_image_query_results", capture)
    return writes


@pytest.fixture()
def patch_phase_1_1_1_noop(monkeypatch):
    """Default Phase 1.1.1 to cold-start (no prior row, reference=None).

    Tests that need warm-start / short-circuit behavior override these
    individually after applying this fixture.
    """
    monkeypatch.setattr(
        item_step1_tasks.crud_personalized_food,
        "get_row_by_query_id",
        lambda _qid: None,
    )

    async def _noop(**_kw):
        return None

    monkeypatch.setattr(item_step1_tasks, "resolve_reference_for_upload", _noop)


def _set_record(monkeypatch, record):
    monkeypatch.setattr(item_step1_tasks, "get_dish_image_query_by_id", lambda _id: record)


def _set_analyzer(monkeypatch, *, returns=None, raises=None):
    async def fake(*_a, **_kw):
        if raises is not None:
            raise raises
        return returns

    monkeypatch.setattr(item_step1_tasks, "analyze_step1_component_identification_async", fake)


def test_success_persists_step1_data_and_clears_prior_error(
    monkeypatch, patch_prompt, patch_crud, patch_phase_1_1_1_noop
):
    record = make_record(
        result_gemini={"step": 0, "step1_data": None, "step1_error": {"old": True}}
    )

    # Re-read returns the latest persisted blob so the Phase 1.1.2 merge
    # sees the reference_image key written in the pre-Pro step.
    def _get_record(_id):
        if patch_crud:
            record.result_gemini = patch_crud[-1]["result_gemini"]
        return record

    monkeypatch.setattr(item_step1_tasks, "get_dish_image_query_by_id", _get_record)
    _set_analyzer(
        monkeypatch,
        returns={"dish_predictions": [{"name": "Burger", "confidence": 0.9}]},
    )

    asyncio.run(
        item_step1_tasks.analyze_image_background(
            query_id=7, file_path="/tmp/foo.jpg", retry_count=1
        )
    )

    # Two writes: pre-Pro reference_image=None, then the success merge.
    assert len(patch_crud) == 2
    written = patch_crud[-1]["result_gemini"]
    assert written["step"] == 1
    assert written["step1_data"]["dish_predictions"][0]["name"] == "Burger"
    assert "step1_error" not in written
    assert written["iterations"][0]["iteration_number"] == 1
    assert written["reference_image"] is None


def test_analyze_image_background_persists_reference_image_key_on_cold_start(
    monkeypatch, patch_prompt, captured_writes
):
    """Phase 1.1.1 runs, returns None (cold start), key persisted as null."""
    record = make_record(result_gemini=None)
    writes, capture = captured_writes
    monkeypatch.setattr(item_step1_tasks, "update_dish_image_query_results", capture)

    # Re-read returns the latest persisted blob so the Phase 1.1.2 merge
    # sees the reference_image key written in the pre-Pro step.
    def _get_record(_id):
        if writes:
            record.result_gemini = writes[-1]["result_gemini"]
        return record

    monkeypatch.setattr(item_step1_tasks, "get_dish_image_query_by_id", _get_record)

    # No prior personalization row → not a retry short-circuit
    monkeypatch.setattr(
        item_step1_tasks.crud_personalized_food, "get_row_by_query_id", lambda _qid: None
    )

    async def fake_resolve(**_kw):
        return None

    monkeypatch.setattr(item_step1_tasks, "resolve_reference_for_upload", fake_resolve)

    _set_analyzer(
        monkeypatch,
        returns={
            "dish_predictions": [{"name": "Burger", "confidence": 0.9}],
            "components": [{"component_name": "Burger"}],
        },
    )

    asyncio.run(
        item_step1_tasks.analyze_image_background(
            query_id=7, file_path="/tmp/foo.jpg", retry_count=0
        )
    )

    # Two writes: one post-Phase-1.1.1 (reference_image=None), one post-success.
    assert len(writes) == 2
    assert writes[0]["result_gemini"]["reference_image"] is None
    final = writes[1]["result_gemini"]
    assert final["reference_image"] is None
    assert final["step1_data"]["dish_predictions"][0]["name"] == "Burger"


def test_analyze_image_background_persists_reference_image_key_on_warm_user(
    monkeypatch, patch_prompt, captured_writes
):
    """Phase 1.1.1 returns a reference dict; key persisted with that dict."""
    record = make_record(result_gemini=None)
    writes, capture = captured_writes
    monkeypatch.setattr(item_step1_tasks, "update_dish_image_query_results", capture)

    # Simulate merge-on-re-read: return the pre-write blob when Phase 1.1.2
    # reads the record after writes[0] landed. make_record returns a
    # SimpleNamespace, which we update in-place between reads.
    def _get_record(_id):
        if writes:
            record.result_gemini = writes[-1]["result_gemini"]
        return record

    monkeypatch.setattr(item_step1_tasks, "get_dish_image_query_by_id", _get_record)

    monkeypatch.setattr(
        item_step1_tasks.crud_personalized_food, "get_row_by_query_id", lambda _qid: None
    )

    reference = {
        "query_id": 42,
        "image_url": "/images/prior.jpg",
        "description": "chicken rice",
        "similarity_score": 0.87,
        "prior_step1_data": {"dish_predictions": [{"name": "Chicken Rice"}]},
    }

    async def fake_resolve(**_kw):
        return reference

    monkeypatch.setattr(item_step1_tasks, "resolve_reference_for_upload", fake_resolve)

    _set_analyzer(
        monkeypatch,
        returns={"dish_predictions": [{"name": "Burger", "confidence": 0.9}], "components": []},
    )

    asyncio.run(
        item_step1_tasks.analyze_image_background(
            query_id=7, file_path="/tmp/foo.jpg", retry_count=0
        )
    )

    assert len(writes) == 2
    assert writes[0]["result_gemini"]["reference_image"] == reference
    final = writes[1]["result_gemini"]
    # reference_image must survive the Phase 1.1.2 merge
    assert final["reference_image"] == reference
    assert final["step1_data"]["dish_predictions"][0]["name"] == "Burger"


def test_analyze_image_background_preserves_reference_image_on_phase1_1_2_failure(
    monkeypatch, patch_prompt, captured_writes
):
    """Phase 1.1.1 writes the reference; Phase 1.1.2 raises; reference_image survives."""
    record = make_record(result_gemini=None)
    writes, capture = captured_writes

    monkeypatch.setattr(item_step1_tasks, "update_dish_image_query_results", capture)

    def _get_record(_id):
        if writes:
            record.result_gemini = writes[-1]["result_gemini"]
        return record

    monkeypatch.setattr(item_step1_tasks, "get_dish_image_query_by_id", _get_record)
    monkeypatch.setattr("src.api._phase_errors.get_dish_image_query_by_id", _get_record)
    monkeypatch.setattr("src.api._phase_errors.update_dish_image_query_results", capture)

    monkeypatch.setattr(
        item_step1_tasks.crud_personalized_food, "get_row_by_query_id", lambda _qid: None
    )

    reference = {
        "query_id": 42,
        "image_url": "/images/prior.jpg",
        "description": "chicken rice",
        "similarity_score": 0.87,
        "prior_step1_data": None,
    }

    async def fake_resolve(**_kw):
        return reference

    monkeypatch.setattr(item_step1_tasks, "resolve_reference_for_upload", fake_resolve)
    _set_analyzer(monkeypatch, raises=ValueError("GEMINI_API_KEY missing"))

    asyncio.run(
        item_step1_tasks.analyze_image_background(
            query_id=7, file_path="/tmp/foo.jpg", retry_count=2
        )
    )

    # Two writes: pre-Pro reference, then error path.
    assert len(writes) == 2
    assert writes[0]["result_gemini"]["reference_image"] == reference
    # The error writer merges onto the existing result_gemini, so
    # reference_image must still be present alongside step1_error.
    final = writes[1]["result_gemini"]
    assert final["reference_image"] == reference
    assert final["step1_error"]["error_type"] == "config_error"
    assert final["step1_error"]["retry_count"] == 2


def test_analyze_image_background_retry_short_circuit_preserves_reference(
    monkeypatch, patch_prompt, captured_writes
):
    """Retry path (row already exists) must NOT overwrite prior reference_image."""
    prior_reference = {
        "query_id": 42,
        "image_url": "/images/prior.jpg",
        "description": "chicken rice",
        "similarity_score": 0.87,
        "prior_step1_data": None,
    }
    record = make_record(result_gemini={"reference_image": prior_reference})
    writes, capture = captured_writes
    monkeypatch.setattr(item_step1_tasks, "update_dish_image_query_results", capture)

    def _get_record(_id):
        if writes:
            record.result_gemini = writes[-1]["result_gemini"]
        return record

    monkeypatch.setattr(item_step1_tasks, "get_dish_image_query_by_id", _get_record)

    # Row already exists → retry short-circuit
    monkeypatch.setattr(
        item_step1_tasks.crud_personalized_food,
        "get_row_by_query_id",
        lambda _qid: object(),
    )

    # Orchestrator must NOT be called on short-circuit path
    async def must_not_call(**_kw):
        raise AssertionError("resolve_reference_for_upload called on retry short-circuit")

    monkeypatch.setattr(item_step1_tasks, "resolve_reference_for_upload", must_not_call)

    _set_analyzer(
        monkeypatch,
        returns={
            "dish_predictions": [{"name": "Burger", "confidence": 0.9}],
            "components": [],
        },
    )

    asyncio.run(
        item_step1_tasks.analyze_image_background(
            query_id=7, file_path="/tmp/foo.jpg", retry_count=1
        )
    )

    # Only one write (the Phase 1.1.2 success merge); no pre-Pro write.
    assert len(writes) == 1
    final = writes[0]["result_gemini"]
    assert final["reference_image"] == prior_reference
    assert final["step1_data"]["dish_predictions"][0]["name"] == "Burger"


def test_failure_writes_step1_error_via_shared_helper(
    monkeypatch, patch_prompt, captured_writes, patch_phase_1_1_1_noop
):
    """Use the shared `captured_writes` capture so we can introspect the write."""
    record = make_record(result_gemini=None)
    writes, capture = captured_writes

    # Monkey-patch both the task's and the error helper's CRUD hooks to the
    # same capture so we can inspect all writes and re-reads merge cleanly.
    monkeypatch.setattr(item_step1_tasks, "update_dish_image_query_results", capture)

    def _get_record(_id):
        if writes:
            record.result_gemini = writes[-1]["result_gemini"]
        return record

    monkeypatch.setattr(item_step1_tasks, "get_dish_image_query_by_id", _get_record)
    monkeypatch.setattr("src.api._phase_errors.get_dish_image_query_by_id", _get_record)
    monkeypatch.setattr("src.api._phase_errors.update_dish_image_query_results", capture)

    _set_analyzer(monkeypatch, raises=ValueError("GEMINI_API_KEY missing"))

    asyncio.run(
        item_step1_tasks.analyze_image_background(
            query_id=9, file_path="/tmp/foo.jpg", retry_count=3
        )
    )

    # Two writes: pre-Pro reference_image=None, then the error path.
    assert len(writes) == 2
    assert writes[0]["result_gemini"]["reference_image"] is None
    written = writes[-1]["result_gemini"]
    assert written["step"] == 0
    assert written["step1_data"] is None
    assert written["step1_error"]["error_type"] == "config_error"
    assert written["step1_error"]["retry_count"] == 3
    # reference_image key survived onto the error blob
    assert written["reference_image"] is None
