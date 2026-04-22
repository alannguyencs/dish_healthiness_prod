"""
Endpoint tests for POST /api/item/{record_id}/confirm-identification.

Focus: idempotency. A double-tapped Confirm must NOT enqueue two Phase-2
background tasks. The atomic CRUD `confirm_identification_atomic` enforces a single
winner via a row-level lock; the endpoint translates the loser into 409.
"""

# pylint: disable=missing-class-docstring,missing-function-docstring
# pylint: disable=redefined-outer-name,unused-argument

import pytest

from src.api import item
from tests.conftest import make_record


CONFIRM_BODY = {
    "selected_dish_name": "Beef Burger",
    "components": [
        {
            "component_name": "Beef Burger",
            "selected_serving_size": "5 oz",
            "number_of_servings": 1.0,
        }
    ],
}


PHASE1_DONE = {
    "phase": 1,
    "identification_data": {"dish_predictions": [{"name": "Beef Burger", "confidence": 0.9}]},
    "nutrition_data": None,
}


@pytest.fixture()
def mock_image_dir(tmp_path, monkeypatch):
    image_dir = tmp_path / "images"
    image_dir.mkdir()
    monkeypatch.setattr(item, "IMAGE_DIR", image_dir)
    image_file = image_dir / "240418_120000_dish1.jpg"
    image_file.write_bytes(b"fake-jpeg")
    return image_dir


@pytest.fixture()
def patch_auth(monkeypatch, fake_user):
    monkeypatch.setattr(item, "authenticate_user_from_request", lambda _r: fake_user)


@pytest.fixture()
def captured_tasks(monkeypatch):
    calls = []

    def _capture(self, func, *args, **kwargs):  # pylint: disable=unused-argument
        calls.append({"func": func, "args": args, "kwargs": kwargs})

    from fastapi import BackgroundTasks  # pylint: disable=import-outside-toplevel

    monkeypatch.setattr(BackgroundTasks, "add_task", _capture)
    return calls


# ---------------------------------------------------------------------------
# Auth + ownership
# ---------------------------------------------------------------------------


def test_returns_401_when_not_authenticated(client, monkeypatch):
    monkeypatch.setattr(item, "authenticate_user_from_request", lambda _r: None)
    res = client.post("/api/item/1/confirm-identification", json=CONFIRM_BODY)
    assert res.status_code == 401


def test_returns_404_for_other_users_record(client, monkeypatch, patch_auth, fake_user):
    other = make_record(user_id=fake_user.id + 1, result_gemini=PHASE1_DONE)
    monkeypatch.setattr(item, "get_dish_image_query_by_id", lambda _id: other)
    res = client.post("/api/item/1/confirm-identification", json=CONFIRM_BODY)
    assert res.status_code == 404


def test_returns_404_when_record_missing(client, monkeypatch, patch_auth):
    monkeypatch.setattr(item, "get_dish_image_query_by_id", lambda _id: None)
    res = client.post("/api/item/1/confirm-identification", json=CONFIRM_BODY)
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# Image guards (run before the atomic CRUD touches the row)
# ---------------------------------------------------------------------------


def test_400_when_no_image_url(client, monkeypatch, patch_auth):
    record = make_record(image_url=None, result_gemini=PHASE1_DONE)
    monkeypatch.setattr(item, "get_dish_image_query_by_id", lambda _id: record)
    res = client.post("/api/item/1/confirm-identification", json=CONFIRM_BODY)
    assert res.status_code == 400


def test_404_when_image_file_missing(client, monkeypatch, patch_auth, tmp_path):
    monkeypatch.setattr(item, "IMAGE_DIR", tmp_path / "no-such-dir")
    record = make_record(result_gemini=PHASE1_DONE)
    monkeypatch.setattr(item, "get_dish_image_query_by_id", lambda _id: record)
    res = client.post("/api/item/1/confirm-identification", json=CONFIRM_BODY)
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# Atomic CRUD outcome → HTTP status
# ---------------------------------------------------------------------------


def _patch_confirm(monkeypatch, returns):
    calls = []

    def _confirm(record_id, *, confirmed_dish_name, confirmed_components):
        calls.append(
            {
                "record_id": record_id,
                "confirmed_dish_name": confirmed_dish_name,
                "confirmed_components": confirmed_components,
            }
        )
        return returns

    monkeypatch.setattr(item, "confirm_identification_atomic", _confirm)
    return calls


def test_success_schedules_exactly_one_background_task(
    client, monkeypatch, patch_auth, mock_image_dir, captured_tasks
):
    record = make_record(result_gemini=PHASE1_DONE)
    monkeypatch.setattr(item, "get_dish_image_query_by_id", lambda _id: record)
    confirm_calls = _patch_confirm(monkeypatch, returns="confirmed")

    res = client.post("/api/item/1/confirm-identification", json=CONFIRM_BODY)

    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["nutrition_in_progress"] is True

    # The atomic CRUD ran exactly once with the user's payload
    assert len(confirm_calls) == 1
    assert confirm_calls[0]["confirmed_dish_name"] == "Beef Burger"
    assert confirm_calls[0]["confirmed_components"][0]["component_name"] == "Beef Burger"

    # And exactly one Phase-2 task got scheduled
    assert len(captured_tasks) == 1


def test_returns_409_on_duplicate_and_does_not_schedule_task(
    client, monkeypatch, patch_auth, mock_image_dir, captured_tasks
):
    record = make_record(result_gemini={**PHASE1_DONE, "identification_confirmed": True})
    monkeypatch.setattr(item, "get_dish_image_query_by_id", lambda _id: record)
    _patch_confirm(monkeypatch, returns="duplicate")

    res = client.post("/api/item/1/confirm-identification", json=CONFIRM_BODY)

    assert res.status_code == 409
    assert "already" in res.json()["detail"].lower()
    # Critical: the loser of the race must NOT enqueue a second Phase-2 task.
    assert captured_tasks == []


def test_returns_400_when_step1_not_yet_done(
    client, monkeypatch, patch_auth, mock_image_dir, captured_tasks
):
    record = make_record(result_gemini={"phase": 0, "identification_data": None})
    monkeypatch.setattr(item, "get_dish_image_query_by_id", lambda _id: record)
    _patch_confirm(monkeypatch, returns="no_step1")

    res = client.post("/api/item/1/confirm-identification", json=CONFIRM_BODY)

    assert res.status_code == 400
    assert captured_tasks == []


def test_returns_404_when_atomic_crud_finds_nothing(
    client, monkeypatch, patch_auth, mock_image_dir, captured_tasks
):
    # The pre-flight read found a record (e.g. row visible in a stale view)
    # but the locked SELECT inside confirm_identification_atomic did not. Surface
    # that as 404 rather than scheduling a doomed background task.
    record = make_record(result_gemini=PHASE1_DONE)
    monkeypatch.setattr(item, "get_dish_image_query_by_id", lambda _id: record)
    _patch_confirm(monkeypatch, returns="not_found")

    res = client.post("/api/item/1/confirm-identification", json=CONFIRM_BODY)

    assert res.status_code == 404
    assert captured_tasks == []


# ---------------------------------------------------------------------------
# Stage 4 — Phase 1.2 enrichment of personalized_food_descriptions
# ---------------------------------------------------------------------------


MULTI_COMPONENT_BODY = {
    "selected_dish_name": "Hainanese Chicken Rice",
    "components": [
        {
            "component_name": "Grilled Chicken",
            "selected_serving_size": "3 oz",
            "number_of_servings": 0.5,
        },
        {
            "component_name": "White Rice",
            "selected_serving_size": "1 cup",
            "number_of_servings": 1.0,
        },
        {
            "component_name": "Cucumber",
            "selected_serving_size": "1/2 cup",
            "number_of_servings": 1.5,
        },
    ],
}


def _patch_enrichment(monkeypatch, *, returns=None, raises=None):
    calls = []

    def _update(**kwargs):
        calls.append(kwargs)
        if raises is not None:
            raise raises
        return returns

    monkeypatch.setattr(item.crud_personalized_food, "update_confirmed_fields", _update)
    return calls


def _patch_tokenize(monkeypatch, *, return_value=None):
    seen = []

    def _tokenize(text):
        seen.append(text)
        return return_value if return_value is not None else text.lower().split()

    monkeypatch.setattr(item.personalized_food_index, "tokenize", _tokenize)
    return seen


def test_enrichment_calls_update_confirmed_fields_with_tokenized_dish_name(
    client, monkeypatch, patch_auth, mock_image_dir, captured_tasks
):
    record = make_record(result_gemini=PHASE1_DONE)
    monkeypatch.setattr(item, "get_dish_image_query_by_id", lambda _id: record)
    _patch_confirm(monkeypatch, returns="confirmed")
    enrichment_calls = _patch_enrichment(monkeypatch, returns=object())
    tokenized = _patch_tokenize(monkeypatch, return_value=["hainanese", "chicken", "rice"])

    res = client.post("/api/item/1/confirm-identification", json=MULTI_COMPONENT_BODY)

    assert res.status_code == 200
    assert tokenized == ["Hainanese Chicken Rice"]
    assert len(enrichment_calls) == 1
    call = enrichment_calls[0]
    assert call["query_id"] == 1
    assert call["confirmed_dish_name"] == "Hainanese Chicken Rice"
    assert call["confirmed_tokens"] == ["hainanese", "chicken", "rice"]


def test_enrichment_confirmed_portions_sums_multiple_components(
    client, monkeypatch, patch_auth, mock_image_dir, captured_tasks
):
    record = make_record(result_gemini=PHASE1_DONE)
    monkeypatch.setattr(item, "get_dish_image_query_by_id", lambda _id: record)
    _patch_confirm(monkeypatch, returns="confirmed")
    enrichment_calls = _patch_enrichment(monkeypatch, returns=object())
    _patch_tokenize(monkeypatch)

    res = client.post("/api/item/1/confirm-identification", json=MULTI_COMPONENT_BODY)

    assert res.status_code == 200
    # 0.5 + 1.0 + 1.5 == 3.0
    assert enrichment_calls[0]["confirmed_portions"] == pytest.approx(3.0)


def test_enrichment_called_before_background_task_dispatch(
    client, monkeypatch, patch_auth, mock_image_dir
):
    order = []

    record = make_record(result_gemini=PHASE1_DONE)
    monkeypatch.setattr(item, "get_dish_image_query_by_id", lambda _id: record)
    _patch_confirm(monkeypatch, returns="confirmed")

    def _update(**_kwargs):
        order.append("enrichment")
        return object()

    monkeypatch.setattr(item.crud_personalized_food, "update_confirmed_fields", _update)
    _patch_tokenize(monkeypatch)

    from fastapi import BackgroundTasks  # pylint: disable=import-outside-toplevel

    def _add_task(_self, _fn, *_a, **_kw):
        order.append("background_task")

    monkeypatch.setattr(BackgroundTasks, "add_task", _add_task)

    res = client.post("/api/item/1/confirm-identification", json=CONFIRM_BODY)

    assert res.status_code == 200
    assert order == ["enrichment", "background_task"]


def test_enrichment_swallows_none_return_and_still_schedules_phase2(
    client, monkeypatch, patch_auth, mock_image_dir, captured_tasks, caplog
):
    record = make_record(result_gemini=PHASE1_DONE)
    monkeypatch.setattr(item, "get_dish_image_query_by_id", lambda _id: record)
    _patch_confirm(monkeypatch, returns="confirmed")
    _patch_enrichment(monkeypatch, returns=None)
    _patch_tokenize(monkeypatch)

    with caplog.at_level("WARNING"):
        res = client.post("/api/item/1/confirm-identification", json=CONFIRM_BODY)

    assert res.status_code == 200
    # Phase 2 still scheduled despite the row-missing case.
    assert len(captured_tasks) == 1
    # WARN log names the query_id.
    assert any(
        "Stage 4 enrichment skipped" in rec.message and "query_id=1" in rec.message
        for rec in caplog.records
    )


def test_enrichment_swallows_exception_and_still_schedules_phase2(
    client, monkeypatch, patch_auth, mock_image_dir, captured_tasks, caplog
):
    record = make_record(result_gemini=PHASE1_DONE)
    monkeypatch.setattr(item, "get_dish_image_query_by_id", lambda _id: record)
    _patch_confirm(monkeypatch, returns="confirmed")
    _patch_enrichment(monkeypatch, raises=RuntimeError("db down"))
    _patch_tokenize(monkeypatch)

    with caplog.at_level("WARNING"):
        res = client.post("/api/item/1/confirm-identification", json=CONFIRM_BODY)

    assert res.status_code == 200
    assert len(captured_tasks) == 1
    assert any(
        "Stage 4 enrichment failed" in rec.message and "db down" in rec.message
        for rec in caplog.records
    )


def test_enrichment_not_called_on_duplicate_outcome(
    client, monkeypatch, patch_auth, mock_image_dir, captured_tasks
):
    record = make_record(result_gemini={**PHASE1_DONE, "identification_confirmed": True})
    monkeypatch.setattr(item, "get_dish_image_query_by_id", lambda _id: record)
    _patch_confirm(monkeypatch, returns="duplicate")
    enrichment_calls = _patch_enrichment(monkeypatch, returns=object())
    _patch_tokenize(monkeypatch)

    res = client.post("/api/item/1/confirm-identification", json=CONFIRM_BODY)

    assert res.status_code == 409
    assert not enrichment_calls
    assert captured_tasks == []


def test_enrichment_not_called_on_no_step1_outcome(
    client, monkeypatch, patch_auth, mock_image_dir, captured_tasks
):
    record = make_record(result_gemini={"phase": 0, "identification_data": None})
    monkeypatch.setattr(item, "get_dish_image_query_by_id", lambda _id: record)
    _patch_confirm(monkeypatch, returns="no_step1")
    enrichment_calls = _patch_enrichment(monkeypatch, returns=object())
    _patch_tokenize(monkeypatch)

    res = client.post("/api/item/1/confirm-identification", json=CONFIRM_BODY)

    assert res.status_code == 400
    assert not enrichment_calls
    assert captured_tasks == []


def test_enrichment_not_called_on_not_found_outcome(
    client, monkeypatch, patch_auth, mock_image_dir, captured_tasks
):
    record = make_record(result_gemini=PHASE1_DONE)
    monkeypatch.setattr(item, "get_dish_image_query_by_id", lambda _id: record)
    _patch_confirm(monkeypatch, returns="not_found")
    enrichment_calls = _patch_enrichment(monkeypatch, returns=object())
    _patch_tokenize(monkeypatch)

    res = client.post("/api/item/1/confirm-identification", json=CONFIRM_BODY)

    assert res.status_code == 404
    assert not enrichment_calls
    assert captured_tasks == []
