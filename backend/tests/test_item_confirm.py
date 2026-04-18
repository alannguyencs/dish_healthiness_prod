"""
Endpoint tests for POST /api/item/{record_id}/confirm-step1.

Focus: idempotency. A double-tapped Confirm must NOT enqueue two Phase-2
background tasks. The atomic CRUD `confirm_step1_atomic` enforces a single
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
    "step": 1,
    "step1_data": {"dish_predictions": [{"name": "Beef Burger", "confidence": 0.9}]},
    "step2_data": None,
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
    res = client.post("/api/item/1/confirm-step1", json=CONFIRM_BODY)
    assert res.status_code == 401


def test_returns_404_for_other_users_record(client, monkeypatch, patch_auth, fake_user):
    other = make_record(user_id=fake_user.id + 1, result_gemini=PHASE1_DONE)
    monkeypatch.setattr(item, "get_dish_image_query_by_id", lambda _id: other)
    res = client.post("/api/item/1/confirm-step1", json=CONFIRM_BODY)
    assert res.status_code == 404


def test_returns_404_when_record_missing(client, monkeypatch, patch_auth):
    monkeypatch.setattr(item, "get_dish_image_query_by_id", lambda _id: None)
    res = client.post("/api/item/1/confirm-step1", json=CONFIRM_BODY)
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# Image guards (run before the atomic CRUD touches the row)
# ---------------------------------------------------------------------------


def test_400_when_no_image_url(client, monkeypatch, patch_auth):
    record = make_record(image_url=None, result_gemini=PHASE1_DONE)
    monkeypatch.setattr(item, "get_dish_image_query_by_id", lambda _id: record)
    res = client.post("/api/item/1/confirm-step1", json=CONFIRM_BODY)
    assert res.status_code == 400


def test_404_when_image_file_missing(client, monkeypatch, patch_auth, tmp_path):
    monkeypatch.setattr(item, "IMAGE_DIR", tmp_path / "no-such-dir")
    record = make_record(result_gemini=PHASE1_DONE)
    monkeypatch.setattr(item, "get_dish_image_query_by_id", lambda _id: record)
    res = client.post("/api/item/1/confirm-step1", json=CONFIRM_BODY)
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

    monkeypatch.setattr(item, "confirm_step1_atomic", _confirm)
    return calls


def test_success_schedules_exactly_one_background_task(
    client, monkeypatch, patch_auth, mock_image_dir, captured_tasks
):
    record = make_record(result_gemini=PHASE1_DONE)
    monkeypatch.setattr(item, "get_dish_image_query_by_id", lambda _id: record)
    confirm_calls = _patch_confirm(monkeypatch, returns="confirmed")

    res = client.post("/api/item/1/confirm-step1", json=CONFIRM_BODY)

    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["step2_in_progress"] is True

    # The atomic CRUD ran exactly once with the user's payload
    assert len(confirm_calls) == 1
    assert confirm_calls[0]["confirmed_dish_name"] == "Beef Burger"
    assert confirm_calls[0]["confirmed_components"][0]["component_name"] == "Beef Burger"

    # And exactly one Phase-2 task got scheduled
    assert len(captured_tasks) == 1


def test_returns_409_on_duplicate_and_does_not_schedule_task(
    client, monkeypatch, patch_auth, mock_image_dir, captured_tasks
):
    record = make_record(result_gemini={**PHASE1_DONE, "step1_confirmed": True})
    monkeypatch.setattr(item, "get_dish_image_query_by_id", lambda _id: record)
    _patch_confirm(monkeypatch, returns="duplicate")

    res = client.post("/api/item/1/confirm-step1", json=CONFIRM_BODY)

    assert res.status_code == 409
    assert "already" in res.json()["detail"].lower()
    # Critical: the loser of the race must NOT enqueue a second Phase-2 task.
    assert captured_tasks == []


def test_returns_400_when_step1_not_yet_done(
    client, monkeypatch, patch_auth, mock_image_dir, captured_tasks
):
    record = make_record(result_gemini={"step": 0, "step1_data": None})
    monkeypatch.setattr(item, "get_dish_image_query_by_id", lambda _id: record)
    _patch_confirm(monkeypatch, returns="no_step1")

    res = client.post("/api/item/1/confirm-step1", json=CONFIRM_BODY)

    assert res.status_code == 400
    assert captured_tasks == []


def test_returns_404_when_atomic_crud_finds_nothing(
    client, monkeypatch, patch_auth, mock_image_dir, captured_tasks
):
    # The pre-flight read found a record (e.g. row visible in a stale view)
    # but the locked SELECT inside confirm_step1_atomic did not. Surface
    # that as 404 rather than scheduling a doomed background task.
    record = make_record(result_gemini=PHASE1_DONE)
    monkeypatch.setattr(item, "get_dish_image_query_by_id", lambda _id: record)
    _patch_confirm(monkeypatch, returns="not_found")

    res = client.post("/api/item/1/confirm-step1", json=CONFIRM_BODY)

    assert res.status_code == 404
    assert captured_tasks == []
