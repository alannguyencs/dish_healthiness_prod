"""
Endpoint tests for POST /api/item/{record_id}/retry-nutrition and /retry-identification.
"""

# pylint: disable=missing-class-docstring,missing-function-docstring
# pylint: disable=redefined-outer-name,unused-argument

from pathlib import Path

import pytest

from src.api import item_retry
from tests.conftest import make_record


CONFIRMED = {
    "phase": 1,
    "identification_confirmed": True,
    "confirmed_dish_name": "Beef Burger",
    "confirmed_components": [
        {
            "component_name": "Beef Burger",
            "selected_serving_size": "5 oz",
            "number_of_servings": 1.0,
        }
    ],
    "nutrition_data": None,
    "nutrition_error": {
        "error_type": "api_error",
        "message": "...",
        "occurred_at": "2026-04-18T12:00:00+00:00",
        "retry_count": 0,
    },
}


@pytest.fixture()
def mock_image_dir(tmp_path, monkeypatch):
    """Point IMAGE_DIR at a tmp dir and create the expected image file."""
    image_dir = tmp_path / "images"
    image_dir.mkdir()
    monkeypatch.setattr(item_retry, "IMAGE_DIR", image_dir)
    image_file = image_dir / "240418_120000_dish1.jpg"
    image_file.write_bytes(b"fake-jpeg")
    return image_dir


@pytest.fixture()
def patch_auth(monkeypatch, fake_user):
    """Default to authenticated as fake_user. Override per-test by re-patching."""
    monkeypatch.setattr(item_retry, "authenticate_user_from_request", lambda _r: fake_user)


@pytest.fixture()
def captured_tasks(monkeypatch):
    """Capture BackgroundTasks.add_task invocations on the retry endpoint."""
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
    monkeypatch.setattr(item_retry, "authenticate_user_from_request", lambda _r: None)
    res = client.post("/api/item/1/retry-nutrition")
    assert res.status_code == 401


def test_returns_404_for_other_users_record(client, monkeypatch, patch_auth, fake_user):
    other_record = make_record(user_id=fake_user.id + 1, result_gemini=CONFIRMED)
    monkeypatch.setattr(item_retry, "get_dish_image_query_by_id", lambda _id: other_record)
    res = client.post("/api/item/1/retry-nutrition")
    assert res.status_code == 404


def test_returns_404_when_record_missing(client, monkeypatch, patch_auth):
    monkeypatch.setattr(item_retry, "get_dish_image_query_by_id", lambda _id: None)
    res = client.post("/api/item/1/retry-nutrition")
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# 400 guards
# ---------------------------------------------------------------------------


def test_400_when_step1_not_confirmed(client, monkeypatch, patch_auth):
    rg = {**CONFIRMED, "identification_confirmed": False}
    record = make_record(result_gemini=rg)
    monkeypatch.setattr(item_retry, "get_dish_image_query_by_id", lambda _id: record)
    res = client.post("/api/item/1/retry-nutrition")
    assert res.status_code == 400
    assert "Step 1" in res.json()["detail"]


def test_400_when_step2_already_complete(client, monkeypatch, patch_auth):
    rg = {**CONFIRMED, "nutrition_data": {"calories_kcal": 600}}
    record = make_record(result_gemini=rg)
    monkeypatch.setattr(item_retry, "get_dish_image_query_by_id", lambda _id: record)
    res = client.post("/api/item/1/retry-nutrition")
    assert res.status_code == 400
    assert "already complete" in res.json()["detail"]


def test_400_when_no_prior_error(client, monkeypatch, patch_auth):
    rg = {**CONFIRMED}
    rg = {k: v for k, v in rg.items() if k != "nutrition_error"}
    record = make_record(result_gemini=rg)
    monkeypatch.setattr(item_retry, "get_dish_image_query_by_id", lambda _id: record)
    res = client.post("/api/item/1/retry-nutrition")
    assert res.status_code == 400
    assert "No prior error" in res.json()["detail"]


def test_404_when_image_file_missing(client, monkeypatch, patch_auth, tmp_path):
    monkeypatch.setattr(item_retry, "IMAGE_DIR", tmp_path / "no-such-dir")
    record = make_record(result_gemini=CONFIRMED)
    monkeypatch.setattr(item_retry, "get_dish_image_query_by_id", lambda _id: record)
    res = client.post("/api/item/1/retry-nutrition")
    assert res.status_code == 404
    assert "Image file no longer exists" in res.json()["detail"]


# ---------------------------------------------------------------------------
# Success path
# ---------------------------------------------------------------------------


def test_success_clears_error_and_schedules_task(
    client, monkeypatch, patch_auth, mock_image_dir, captured_tasks, captured_writes
):
    record = make_record(result_gemini=dict(CONFIRMED))
    writes, capture = captured_writes

    monkeypatch.setattr(item_retry, "get_dish_image_query_by_id", lambda _id: record)
    monkeypatch.setattr(item_retry, "update_dish_image_query_results", capture)

    res = client.post("/api/item/1/retry-nutrition")

    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["retry_count"] == 1
    assert body["nutrition_in_progress"] is True

    # The error was cleared in the optimistic write
    assert len(writes) == 1
    assert "nutrition_error" not in writes[0]["result_gemini"]

    # And one background task was scheduled with the right args
    assert len(captured_tasks) == 1
    args = captured_tasks[0]["args"]
    assert args[0] == 1  # record_id
    assert isinstance(args[1], Path)
    assert args[2] == "Beef Burger"
    assert args[3] == CONFIRMED["confirmed_components"]
    assert args[4] == 1  # new retry_count


def test_increments_retry_count_from_prior_value(
    client, monkeypatch, patch_auth, mock_image_dir, captured_tasks, captured_writes
):
    rg = {**CONFIRMED, "nutrition_error": {**CONFIRMED["nutrition_error"], "retry_count": 4}}
    record = make_record(result_gemini=rg)
    _, capture = captured_writes

    monkeypatch.setattr(item_retry, "get_dish_image_query_by_id", lambda _id: record)
    monkeypatch.setattr(item_retry, "update_dish_image_query_results", capture)

    res = client.post("/api/item/1/retry-nutrition")
    assert res.status_code == 200
    assert res.json()["retry_count"] == 5
    assert captured_tasks[0]["args"][4] == 5


# ===========================================================================
# POST /api/item/{id}/retry-identification
# ===========================================================================


PHASE1_FAILED = {
    "phase": 0,
    "identification_data": None,
    "identification_error": {
        "error_type": "api_error",
        "message": "...",
        "occurred_at": "2026-04-18T12:00:00+00:00",
        "retry_count": 0,
    },
}


# ---- auth + ownership ----------------------------------------------------


def test_retry_identification_returns_401_when_not_authenticated(client, monkeypatch):
    monkeypatch.setattr(item_retry, "authenticate_user_from_request", lambda _r: None)
    res = client.post("/api/item/1/retry-identification")
    assert res.status_code == 401


def test_retry_identification_returns_404_for_other_users_record(
    client, monkeypatch, patch_auth, fake_user
):
    other_record = make_record(user_id=fake_user.id + 1, result_gemini=PHASE1_FAILED)
    monkeypatch.setattr(item_retry, "get_dish_image_query_by_id", lambda _id: other_record)
    res = client.post("/api/item/1/retry-identification")
    assert res.status_code == 404


# ---- 400 guards ----------------------------------------------------------


def test_retry_identification_400_when_step1_already_complete(client, monkeypatch, patch_auth):
    rg = {**PHASE1_FAILED, "identification_data": {"dish_predictions": []}}
    record = make_record(result_gemini=rg)
    monkeypatch.setattr(item_retry, "get_dish_image_query_by_id", lambda _id: record)
    res = client.post("/api/item/1/retry-identification")
    assert res.status_code == 400
    assert "already complete" in res.json()["detail"]


def test_retry_identification_400_when_no_prior_error(client, monkeypatch, patch_auth):
    rg = {k: v for k, v in PHASE1_FAILED.items() if k != "identification_error"}
    record = make_record(result_gemini=rg)
    monkeypatch.setattr(item_retry, "get_dish_image_query_by_id", lambda _id: record)
    res = client.post("/api/item/1/retry-identification")
    assert res.status_code == 400
    assert "No prior error" in res.json()["detail"]


def test_retry_identification_404_when_image_file_missing(client, monkeypatch, patch_auth, tmp_path):
    monkeypatch.setattr(item_retry, "IMAGE_DIR", tmp_path / "no-such-dir")
    record = make_record(result_gemini=PHASE1_FAILED)
    monkeypatch.setattr(item_retry, "get_dish_image_query_by_id", lambda _id: record)
    res = client.post("/api/item/1/retry-identification")
    assert res.status_code == 404


# ---- success -------------------------------------------------------------


def test_retry_identification_success_clears_error_and_schedules_task(
    client, monkeypatch, patch_auth, mock_image_dir, captured_tasks, captured_writes
):
    record = make_record(result_gemini=dict(PHASE1_FAILED))
    writes, capture = captured_writes

    monkeypatch.setattr(item_retry, "get_dish_image_query_by_id", lambda _id: record)
    monkeypatch.setattr(item_retry, "update_dish_image_query_results", capture)

    res = client.post("/api/item/1/retry-identification")

    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["retry_count"] == 1
    assert body["identification_in_progress"] is True

    assert "identification_error" not in writes[0]["result_gemini"]

    assert len(captured_tasks) == 1
    args = captured_tasks[0]["args"]
    assert args[0] == 1  # record_id
    assert isinstance(args[1], str)  # file_path str
    assert args[2] == 1  # new retry_count


def test_retry_identification_increments_retry_count(
    client, monkeypatch, patch_auth, mock_image_dir, captured_tasks, captured_writes
):
    rg = {**PHASE1_FAILED, "identification_error": {**PHASE1_FAILED["identification_error"], "retry_count": 4}}
    record = make_record(result_gemini=rg)
    _, capture = captured_writes

    monkeypatch.setattr(item_retry, "get_dish_image_query_by_id", lambda _id: record)
    monkeypatch.setattr(item_retry, "update_dish_image_query_results", capture)

    res = client.post("/api/item/1/retry-identification")
    assert res.status_code == 200
    assert res.json()["retry_count"] == 5
    assert captured_tasks[0]["args"][2] == 5
