"""
Tests for Phase 1 background task in src/api/item_identification_tasks.py.

Mocks the Gemini call (`analyze_component_identification_async`) and the
prompt loader so the task runs synchronously in-process without network or
filesystem.
"""

# pylint: disable=missing-class-docstring,missing-function-docstring
# pylint: disable=redefined-outer-name,unused-argument

import asyncio
import pytest

from src.api import item_identification_tasks
from tests.conftest import make_record


@pytest.fixture()
def patch_prompt(monkeypatch):
    monkeypatch.setattr(
        item_identification_tasks,
        "get_component_identification_prompt",
        lambda *, reference=None: "STEP1 SYSTEM PROMPT",
    )


@pytest.fixture()
def patch_crud(monkeypatch, captured_writes):
    writes, capture = captured_writes
    monkeypatch.setattr(item_identification_tasks, "update_dish_image_query_results", capture)
    return writes


@pytest.fixture()
def patch_phase_1_1_1_noop(monkeypatch):
    """Default Phase 1.1.1 to cold-start (no prior row, reference=None).

    Tests that need warm-start / short-circuit behavior override these
    individually after applying this fixture.
    """
    monkeypatch.setattr(
        item_identification_tasks.crud_personalized_food,
        "get_row_by_query_id",
        lambda _qid: None,
    )

    async def _noop(**_kw):
        return {"flash_caption": None, "reference_image": None}

    monkeypatch.setattr(item_identification_tasks, "resolve_reference_for_upload", _noop)


def _set_record(monkeypatch, record):
    monkeypatch.setattr(item_identification_tasks, "get_dish_image_query_by_id", lambda _id: record)


def _set_analyzer(monkeypatch, *, returns=None, raises=None):
    async def fake(*_a, **_kw):
        if raises is not None:
            raise raises
        return returns

    monkeypatch.setattr(item_identification_tasks, "analyze_component_identification_async", fake)


def test_success_persists_step1_data_and_clears_prior_error(
    monkeypatch, patch_prompt, patch_crud, patch_phase_1_1_1_noop
):
    record = make_record(
        result_gemini={"phase": 0, "identification_data": None, "identification_error": {"old": True}}
    )

    # Re-read returns the latest persisted blob so the Phase 1.1.2 merge
    # sees the reference_image key written in the pre-Pro step.
    def _get_record(_id):
        if patch_crud:
            record.result_gemini = patch_crud[-1]["result_gemini"]
        return record

    monkeypatch.setattr(item_identification_tasks, "get_dish_image_query_by_id", _get_record)
    _set_analyzer(
        monkeypatch,
        returns={"dish_predictions": [{"name": "Burger", "confidence": 0.9}]},
    )

    asyncio.run(
        item_identification_tasks.analyze_image_background(
            query_id=7, file_path="/tmp/foo.jpg", retry_count=1
        )
    )

    # Two writes: pre-Pro reference_image=None, then the success merge.
    assert len(patch_crud) == 2
    written = patch_crud[-1]["result_gemini"]
    assert written["phase"] == 1
    assert written["identification_data"]["dish_predictions"][0]["name"] == "Burger"
    assert "identification_error" not in written
    assert written["iterations"][0]["iteration_number"] == 1
    assert written["reference_image"] is None


def test_analyze_image_background_persists_reference_image_key_on_cold_start(
    monkeypatch, patch_prompt, captured_writes
):
    """Phase 1.1.1 runs and returns a caption with null reference (cold start)."""
    record = make_record(result_gemini=None)
    writes, capture = captured_writes
    monkeypatch.setattr(item_identification_tasks, "update_dish_image_query_results", capture)

    # Re-read returns the latest persisted blob so the Phase 1.1.2 merge
    # sees the reference_image key written in the pre-Pro step.
    def _get_record(_id):
        if writes:
            record.result_gemini = writes[-1]["result_gemini"]
        return record

    monkeypatch.setattr(item_identification_tasks, "get_dish_image_query_by_id", _get_record)

    # No prior personalization row → not a retry short-circuit
    monkeypatch.setattr(
        item_identification_tasks.crud_personalized_food, "get_row_by_query_id", lambda _qid: None
    )

    async def fake_resolve(**_kw):
        return {"flash_caption": "plate of food", "reference_image": None}

    monkeypatch.setattr(item_identification_tasks, "resolve_reference_for_upload", fake_resolve)

    _set_analyzer(
        monkeypatch,
        returns={
            "dish_predictions": [{"name": "Burger", "confidence": 0.9}],
            "components": [{"component_name": "Burger"}],
        },
    )

    asyncio.run(
        item_identification_tasks.analyze_image_background(
            query_id=7, file_path="/tmp/foo.jpg", retry_count=0
        )
    )

    # Two writes: one post-Phase-1.1.1 (caption=str, reference_image=None),
    # one post-success that merges step1_data in.
    assert len(writes) == 2
    pre = writes[0]["result_gemini"]
    assert pre["reference_image"] is None
    assert pre["flash_caption"] == "plate of food"
    final = writes[1]["result_gemini"]
    assert final["reference_image"] is None
    assert final["flash_caption"] == "plate of food"
    assert final["identification_data"]["dish_predictions"][0]["name"] == "Burger"


def test_analyze_image_background_persists_reference_image_key_on_warm_user(
    monkeypatch, patch_prompt, captured_writes
):
    """Phase 1.1.1 returns a reference dict; key persisted with that dict."""
    record = make_record(result_gemini=None)
    writes, capture = captured_writes
    monkeypatch.setattr(item_identification_tasks, "update_dish_image_query_results", capture)

    # Simulate merge-on-re-read: return the pre-write blob when Phase 1.1.2
    # reads the record after writes[0] landed. make_record returns a
    # SimpleNamespace, which we update in-place between reads.
    def _get_record(_id):
        if writes:
            record.result_gemini = writes[-1]["result_gemini"]
        return record

    monkeypatch.setattr(item_identification_tasks, "get_dish_image_query_by_id", _get_record)

    monkeypatch.setattr(
        item_identification_tasks.crud_personalized_food, "get_row_by_query_id", lambda _qid: None
    )

    reference = {
        "query_id": 42,
        "image_url": "/images/prior.jpg",
        "description": "chicken rice",
        "similarity_score": 0.87,
        "prior_identification_data": {"dish_predictions": [{"name": "Chicken Rice"}]},
    }

    async def fake_resolve(**_kw):
        return {"flash_caption": "grilled chicken on rice", "reference_image": reference}

    monkeypatch.setattr(item_identification_tasks, "resolve_reference_for_upload", fake_resolve)

    _set_analyzer(
        monkeypatch,
        returns={"dish_predictions": [{"name": "Burger", "confidence": 0.9}], "components": []},
    )

    asyncio.run(
        item_identification_tasks.analyze_image_background(
            query_id=7, file_path="/tmp/foo.jpg", retry_count=0
        )
    )

    assert len(writes) == 2
    pre = writes[0]["result_gemini"]
    assert pre["reference_image"] == reference
    assert pre["flash_caption"] == "grilled chicken on rice"
    final = writes[1]["result_gemini"]
    # reference_image + flash_caption must survive the Phase 1.1.2 merge
    assert final["reference_image"] == reference
    assert final["flash_caption"] == "grilled chicken on rice"
    assert final["identification_data"]["dish_predictions"][0]["name"] == "Burger"


def test_analyze_image_background_preserves_reference_image_on_phase1_1_2_failure(
    monkeypatch, patch_prompt, captured_writes
):
    """Phase 1.1.1 writes the reference; Phase 1.1.2 raises; reference_image survives."""
    record = make_record(result_gemini=None)
    writes, capture = captured_writes

    monkeypatch.setattr(item_identification_tasks, "update_dish_image_query_results", capture)

    def _get_record(_id):
        if writes:
            record.result_gemini = writes[-1]["result_gemini"]
        return record

    monkeypatch.setattr(item_identification_tasks, "get_dish_image_query_by_id", _get_record)
    monkeypatch.setattr("src.api._phase_errors.get_dish_image_query_by_id", _get_record)
    monkeypatch.setattr("src.api._phase_errors.update_dish_image_query_results", capture)

    monkeypatch.setattr(
        item_identification_tasks.crud_personalized_food, "get_row_by_query_id", lambda _qid: None
    )

    reference = {
        "query_id": 42,
        "image_url": "/images/prior.jpg",
        "description": "chicken rice",
        "similarity_score": 0.87,
        "prior_identification_data": None,
    }

    async def fake_resolve(**_kw):
        return {"flash_caption": "plate of chicken rice", "reference_image": reference}

    monkeypatch.setattr(item_identification_tasks, "resolve_reference_for_upload", fake_resolve)
    _set_analyzer(monkeypatch, raises=ValueError("GEMINI_API_KEY missing"))

    asyncio.run(
        item_identification_tasks.analyze_image_background(
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
    assert final["identification_error"]["error_type"] == "config_error"
    assert final["identification_error"]["retry_count"] == 2


def test_analyze_image_background_retry_short_circuit_preserves_reference(
    monkeypatch, patch_prompt, captured_writes
):
    """Retry path (row already exists) must NOT overwrite prior reference_image."""
    prior_reference = {
        "query_id": 42,
        "image_url": "/images/prior.jpg",
        "description": "chicken rice",
        "similarity_score": 0.87,
        "prior_identification_data": None,
    }
    record = make_record(result_gemini={"reference_image": prior_reference})
    writes, capture = captured_writes
    monkeypatch.setattr(item_identification_tasks, "update_dish_image_query_results", capture)

    def _get_record(_id):
        if writes:
            record.result_gemini = writes[-1]["result_gemini"]
        return record

    monkeypatch.setattr(item_identification_tasks, "get_dish_image_query_by_id", _get_record)

    # Row already exists → retry short-circuit
    monkeypatch.setattr(
        item_identification_tasks.crud_personalized_food,
        "get_row_by_query_id",
        lambda _qid: object(),
    )

    # Orchestrator must NOT be called on short-circuit path
    async def must_not_call(**_kw):
        raise AssertionError("resolve_reference_for_upload called on retry short-circuit")

    monkeypatch.setattr(item_identification_tasks, "resolve_reference_for_upload", must_not_call)

    _set_analyzer(
        monkeypatch,
        returns={
            "dish_predictions": [{"name": "Burger", "confidence": 0.9}],
            "components": [],
        },
    )

    asyncio.run(
        item_identification_tasks.analyze_image_background(
            query_id=7, file_path="/tmp/foo.jpg", retry_count=1
        )
    )

    # Only one write (the Phase 1.1.2 success merge); no pre-Pro write.
    assert len(writes) == 1
    final = writes[0]["result_gemini"]
    assert final["reference_image"] == prior_reference
    assert final["identification_data"]["dish_predictions"][0]["name"] == "Burger"


def test_analyze_image_background_passes_single_image_on_cold_start(
    monkeypatch, patch_prompt, patch_phase_1_1_1_noop, captured_writes, tmp_path
):
    """Cold start: analyzer called with bytes=None, prompt with reference=None."""
    # Patch the prompt fixture so we can inspect the `reference=` kwarg.
    captured_prompt = {}

    def _capture_prompt(*, reference=None):
        captured_prompt["reference"] = reference
        return "STEP1 SYSTEM PROMPT"

    monkeypatch.setattr(
        item_identification_tasks, "get_component_identification_prompt", _capture_prompt
    )

    record = make_record(result_gemini=None)
    writes, capture = captured_writes
    monkeypatch.setattr(item_identification_tasks, "update_dish_image_query_results", capture)

    def _get_record(_id):
        if writes:
            record.result_gemini = writes[-1]["result_gemini"]
        return record

    monkeypatch.setattr(item_identification_tasks, "get_dish_image_query_by_id", _get_record)

    captured_analyzer = {}

    async def _capture_analyzer(**kwargs):
        captured_analyzer.update(kwargs)
        return {
            "dish_predictions": [{"name": "X", "confidence": 0.9}],
            "components": [{"component_name": "X"}],
        }

    monkeypatch.setattr(
        item_identification_tasks, "analyze_component_identification_async", _capture_analyzer
    )

    asyncio.run(
        item_identification_tasks.analyze_image_background(
            query_id=7, file_path=str(tmp_path / "q.jpg"), retry_count=0
        )
    )

    assert captured_analyzer["reference_image_bytes"] is None
    assert captured_prompt["reference"] is None


def test_analyze_image_background_passes_two_images_on_full_warm_start(
    monkeypatch, patch_prompt, captured_writes, tmp_path
):
    """Warm start with full reference → analyzer gets bytes, prompt gets reference."""
    ref_image_bytes = b"reference-jpeg-bytes"
    ref_filename = "q_prior.jpg"
    (tmp_path / ref_filename).write_bytes(ref_image_bytes)
    # Point the task's IMAGE_DIR constant at the tmp_path so disk resolution works.
    monkeypatch.setattr(item_identification_tasks, "IMAGE_DIR", tmp_path)

    prior_identification = {
        "dish_predictions": [{"name": "Chicken Rice", "confidence": 0.9}],
        "components": [{"component_name": "Grilled Chicken", "serving_sizes": ["3 oz"]}],
    }
    persisted_reference = {
        "query_id": 99,
        "image_url": f"/images/{ref_filename}",
        "description": "chicken rice",
        "similarity_score": 0.87,
        "prior_identification_data": prior_identification,
    }

    record = make_record(result_gemini={"reference_image": persisted_reference})
    writes, capture = captured_writes
    monkeypatch.setattr(item_identification_tasks, "update_dish_image_query_results", capture)

    def _get_record(_id):
        if writes:
            record.result_gemini = writes[-1]["result_gemini"]
        return record

    monkeypatch.setattr(item_identification_tasks, "get_dish_image_query_by_id", _get_record)

    # Retry short-circuit (row exists) so Phase 1.1.1 doesn't run and
    # reference_image on the record stays as seeded.
    monkeypatch.setattr(
        item_identification_tasks.crud_personalized_food,
        "get_row_by_query_id",
        lambda _qid: object(),
    )

    async def must_not_call(**_kw):
        raise AssertionError("orchestrator should not run on short-circuit")

    monkeypatch.setattr(item_identification_tasks, "resolve_reference_for_upload", must_not_call)

    captured_prompt = {}

    def _capture_prompt(*, reference=None):
        captured_prompt["reference"] = reference
        return "STEP1 SYSTEM PROMPT"

    monkeypatch.setattr(
        item_identification_tasks, "get_component_identification_prompt", _capture_prompt
    )

    captured_analyzer = {}

    async def _capture_analyzer(**kwargs):
        captured_analyzer.update(kwargs)
        return {
            "dish_predictions": [{"name": "X", "confidence": 0.9}],
            "components": [{"component_name": "X"}],
        }

    monkeypatch.setattr(
        item_identification_tasks, "analyze_component_identification_async", _capture_analyzer
    )

    asyncio.run(
        item_identification_tasks.analyze_image_background(
            query_id=7, file_path=str(tmp_path / "q.jpg"), retry_count=0
        )
    )

    assert captured_analyzer["reference_image_bytes"] == ref_image_bytes
    assert captured_prompt["reference"] is not None
    assert captured_prompt["reference"]["prior_identification_data"] == prior_identification


def test_analyze_image_background_degrades_when_prior_identification_data_is_null(
    monkeypatch, patch_prompt, captured_writes, tmp_path
):
    """Reference+file present but prior_identification_data null → single-image (Option B)."""
    ref_filename = "q_prior.jpg"
    (tmp_path / ref_filename).write_bytes(b"reference-jpeg-bytes")
    monkeypatch.setattr(item_identification_tasks, "IMAGE_DIR", tmp_path)

    persisted_reference = {
        "query_id": 99,
        "image_url": f"/images/{ref_filename}",
        "description": "chicken rice",
        "similarity_score": 0.87,
        "prior_identification_data": None,
    }

    record = make_record(result_gemini={"reference_image": persisted_reference})
    writes, capture = captured_writes
    monkeypatch.setattr(item_identification_tasks, "update_dish_image_query_results", capture)

    def _get_record(_id):
        if writes:
            record.result_gemini = writes[-1]["result_gemini"]
        return record

    monkeypatch.setattr(item_identification_tasks, "get_dish_image_query_by_id", _get_record)
    monkeypatch.setattr(
        item_identification_tasks.crud_personalized_food,
        "get_row_by_query_id",
        lambda _qid: object(),
    )

    async def must_not_call(**_kw):
        raise AssertionError("orchestrator should not run on short-circuit")

    monkeypatch.setattr(item_identification_tasks, "resolve_reference_for_upload", must_not_call)

    captured_prompt = {}

    def _capture_prompt(*, reference=None):
        captured_prompt["reference"] = reference
        return "STEP1 SYSTEM PROMPT"

    monkeypatch.setattr(
        item_identification_tasks, "get_component_identification_prompt", _capture_prompt
    )

    captured_analyzer = {}

    async def _capture_analyzer(**kwargs):
        captured_analyzer.update(kwargs)
        return {
            "dish_predictions": [{"name": "X", "confidence": 0.9}],
            "components": [{"component_name": "X"}],
        }

    monkeypatch.setattr(
        item_identification_tasks, "analyze_component_identification_async", _capture_analyzer
    )

    asyncio.run(
        item_identification_tasks.analyze_image_background(
            query_id=7, file_path=str(tmp_path / "q.jpg"), retry_count=0
        )
    )

    assert captured_analyzer["reference_image_bytes"] is None
    assert captured_prompt["reference"] is None


def test_analyze_image_background_degrades_on_missing_image_file(
    monkeypatch, patch_prompt, captured_writes, tmp_path, caplog
):
    """Reference populated with prior data, but file missing on disk → single-image + WARN."""
    monkeypatch.setattr(item_identification_tasks, "IMAGE_DIR", tmp_path)  # tmp_path has no image files

    persisted_reference = {
        "query_id": 99,
        "image_url": "/images/ghost.jpg",
        "description": "chicken rice",
        "similarity_score": 0.87,
        "prior_identification_data": {
            "dish_predictions": [{"name": "Chicken Rice"}],
            "components": [{"component_name": "X"}],
        },
    }

    record = make_record(result_gemini={"reference_image": persisted_reference})
    writes, capture = captured_writes
    monkeypatch.setattr(item_identification_tasks, "update_dish_image_query_results", capture)

    def _get_record(_id):
        if writes:
            record.result_gemini = writes[-1]["result_gemini"]
        return record

    monkeypatch.setattr(item_identification_tasks, "get_dish_image_query_by_id", _get_record)
    monkeypatch.setattr(
        item_identification_tasks.crud_personalized_food,
        "get_row_by_query_id",
        lambda _qid: object(),
    )

    async def must_not_call(**_kw):
        raise AssertionError("orchestrator should not run on short-circuit")

    monkeypatch.setattr(item_identification_tasks, "resolve_reference_for_upload", must_not_call)

    captured_prompt = {}

    def _capture_prompt(*, reference=None):
        captured_prompt["reference"] = reference
        return "STEP1 SYSTEM PROMPT"

    monkeypatch.setattr(
        item_identification_tasks, "get_component_identification_prompt", _capture_prompt
    )

    captured_analyzer = {}

    async def _capture_analyzer(**kwargs):
        captured_analyzer.update(kwargs)
        return {
            "dish_predictions": [{"name": "X", "confidence": 0.9}],
            "components": [{"component_name": "X"}],
        }

    monkeypatch.setattr(
        item_identification_tasks, "analyze_component_identification_async", _capture_analyzer
    )

    with caplog.at_level("WARNING"):
        asyncio.run(
            item_identification_tasks.analyze_image_background(
                query_id=7, file_path=str(tmp_path / "q.jpg"), retry_count=0
            )
        )

    assert captured_analyzer["reference_image_bytes"] is None
    assert captured_prompt["reference"] is None
    assert any("reference image missing" in r.message for r in caplog.records)


def test_failure_writes_step1_error_via_shared_helper(
    monkeypatch, patch_prompt, captured_writes, patch_phase_1_1_1_noop
):
    """Use the shared `captured_writes` capture so we can introspect the write."""
    record = make_record(result_gemini=None)
    writes, capture = captured_writes

    # Monkey-patch both the task's and the error helper's CRUD hooks to the
    # same capture so we can inspect all writes and re-reads merge cleanly.
    monkeypatch.setattr(item_identification_tasks, "update_dish_image_query_results", capture)

    def _get_record(_id):
        if writes:
            record.result_gemini = writes[-1]["result_gemini"]
        return record

    monkeypatch.setattr(item_identification_tasks, "get_dish_image_query_by_id", _get_record)
    monkeypatch.setattr("src.api._phase_errors.get_dish_image_query_by_id", _get_record)
    monkeypatch.setattr("src.api._phase_errors.update_dish_image_query_results", capture)

    _set_analyzer(monkeypatch, raises=ValueError("GEMINI_API_KEY missing"))

    asyncio.run(
        item_identification_tasks.analyze_image_background(
            query_id=9, file_path="/tmp/foo.jpg", retry_count=3
        )
    )

    # Two writes: pre-Pro reference_image=None, then the error path.
    assert len(writes) == 2
    assert writes[0]["result_gemini"]["reference_image"] is None
    written = writes[-1]["result_gemini"]
    assert written["phase"] == 0
    assert written["identification_data"] is None
    assert written["identification_error"]["error_type"] == "config_error"
    assert written["identification_error"]["retry_count"] == 3
    # reference_image key survived onto the error blob
    assert written["reference_image"] is None
