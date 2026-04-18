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


def _set_record(monkeypatch, record):
    monkeypatch.setattr(item_step1_tasks, "get_dish_image_query_by_id", lambda _id: record)


def _set_analyzer(monkeypatch, *, returns=None, raises=None):
    async def fake(*_a, **_kw):
        if raises is not None:
            raise raises
        return returns

    monkeypatch.setattr(item_step1_tasks, "analyze_step1_component_identification_async", fake)


def test_success_persists_step1_data_and_clears_prior_error(monkeypatch, patch_prompt, patch_crud):
    record = make_record(
        result_gemini={"step": 0, "step1_data": None, "step1_error": {"old": True}}
    )
    _set_record(monkeypatch, record)
    _set_analyzer(
        monkeypatch,
        returns={"dish_predictions": [{"name": "Burger", "confidence": 0.9}]},
    )

    asyncio.run(
        item_step1_tasks.analyze_image_background(
            query_id=7, file_path="/tmp/foo.jpg", retry_count=1
        )
    )

    written = patch_crud[0]["result_gemini"]
    assert written["step"] == 1
    assert written["step1_data"]["dish_predictions"][0]["name"] == "Burger"
    assert "step1_error" not in written
    assert written["iterations"][0]["iteration_number"] == 1


def test_failure_writes_step1_error_via_shared_helper(monkeypatch, patch_prompt, captured_writes):
    """Use the shared `captured_writes` capture so we can introspect the write."""
    record = make_record(result_gemini=None)
    writes, capture = captured_writes

    # The Phase 1 task only reads via item_step1_tasks; the persist helper
    # reads via _phase_errors. Patch both.
    _set_record(monkeypatch, record)
    monkeypatch.setattr("src.api._phase_errors.get_dish_image_query_by_id", lambda _id: record)
    monkeypatch.setattr("src.api._phase_errors.update_dish_image_query_results", capture)

    _set_analyzer(monkeypatch, raises=ValueError("GEMINI_API_KEY missing"))

    asyncio.run(
        item_step1_tasks.analyze_image_background(
            query_id=9, file_path="/tmp/foo.jpg", retry_count=3
        )
    )

    assert len(writes) == 1
    written = writes[0]["result_gemini"]
    assert written["step"] == 0
    assert written["step1_data"] is None
    assert written["step1_error"]["error_type"] == "config_error"
    assert written["step1_error"]["retry_count"] == 3
