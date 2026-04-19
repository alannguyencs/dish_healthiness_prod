"""
Endpoint tests for POST /api/item/{record_id}/correction (Stage 8).

Covers: auth + ownership guards, Pydantic validation (422 paths), the
dual write onto `result_gemini.step2_corrected` + personalization row,
and the Stage-4-style swallow-log when the personalization half fails.
"""

# pylint: disable=missing-class-docstring,missing-function-docstring
# pylint: disable=redefined-outer-name,unused-argument

import pytest

from src.api import item_correction
from tests.conftest import make_record


VALID_PAYLOAD = {
    "healthiness_score": 70,
    "healthiness_score_rationale": "Corrected rationale",
    "calories_kcal": 450,
    "fiber_g": 2,
    "carbs_g": 40,
    "protein_g": 30,
    "fat_g": 15,
    "micronutrients": ["Iron", "Magnesium"],
}


PHASE2_DONE = {
    "step": 2,
    "step1_data": {"dish_predictions": [{"name": "Chicken Rice"}]},
    "step2_data": {
        "dish_name": "Chicken Rice",
        "calories_kcal": 600,
        "healthiness_score": 50,
    },
    "nutrition_db_matches": {"nutrition_matches": [{"matched_food_name": "Chicken Rice"}]},
    "personalized_matches": [],
}


@pytest.fixture()
def patch_auth(monkeypatch, fake_user):
    monkeypatch.setattr(item_correction, "authenticate_user_from_request", lambda _r: fake_user)


def _patch_update_personalization(monkeypatch, *, returns=None, raises=None):
    calls = []

    def _update(**kwargs):
        calls.append(kwargs)
        if raises is not None:
            raise raises
        return returns

    monkeypatch.setattr(
        item_correction.crud_personalized_food, "update_corrected_step2_data", _update
    )
    return calls


# ---------------------------------------------------------------------------
# Auth + ownership
# ---------------------------------------------------------------------------


def test_returns_401_when_not_authenticated(client, monkeypatch):
    monkeypatch.setattr(item_correction, "authenticate_user_from_request", lambda _r: None)
    res = client.post("/api/item/1/correction", json=VALID_PAYLOAD)
    assert res.status_code == 401


def test_returns_404_for_other_users_record(client, monkeypatch, patch_auth, fake_user):
    other = make_record(user_id=fake_user.id + 1, result_gemini=PHASE2_DONE)
    monkeypatch.setattr(item_correction, "get_dish_image_query_by_id", lambda _id: other)
    res = client.post("/api/item/1/correction", json=VALID_PAYLOAD)
    assert res.status_code == 404


def test_returns_404_when_record_missing(client, monkeypatch, patch_auth):
    monkeypatch.setattr(item_correction, "get_dish_image_query_by_id", lambda _id: None)
    res = client.post("/api/item/1/correction", json=VALID_PAYLOAD)
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# Pydantic validation
# ---------------------------------------------------------------------------


def test_returns_422_when_calories_negative(client, monkeypatch, patch_auth):
    record = make_record(result_gemini=PHASE2_DONE)
    monkeypatch.setattr(item_correction, "get_dish_image_query_by_id", lambda _id: record)
    body = {**VALID_PAYLOAD, "calories_kcal": -50}
    res = client.post("/api/item/1/correction", json=body)
    assert res.status_code == 422


def test_returns_422_when_healthiness_score_out_of_range(client, monkeypatch, patch_auth):
    record = make_record(result_gemini=PHASE2_DONE)
    monkeypatch.setattr(item_correction, "get_dish_image_query_by_id", lambda _id: record)
    body = {**VALID_PAYLOAD, "healthiness_score": 150}
    res = client.post("/api/item/1/correction", json=body)
    assert res.status_code == 422


def test_returns_400_when_result_gemini_missing(client, monkeypatch, patch_auth):
    record = make_record(result_gemini=None)
    monkeypatch.setattr(item_correction, "get_dish_image_query_by_id", lambda _id: record)
    res = client.post("/api/item/1/correction", json=VALID_PAYLOAD)
    assert res.status_code == 400


# ---------------------------------------------------------------------------
# Happy path + dual-write + swallow-log
# ---------------------------------------------------------------------------


def test_happy_path_writes_step2_corrected_preserving_step2_data(
    client, monkeypatch, patch_auth, captured_writes
):
    record = make_record(result_gemini=PHASE2_DONE)
    writes, capture = captured_writes
    monkeypatch.setattr(item_correction, "get_dish_image_query_by_id", lambda _id: record)
    monkeypatch.setattr(item_correction, "update_dish_image_query_results", capture)
    _patch_update_personalization(monkeypatch, returns=object())

    res = client.post("/api/item/1/correction", json=VALID_PAYLOAD)

    assert res.status_code == 200
    assert len(writes) == 1
    written = writes[0]["result_gemini"]
    # step2_corrected landed
    assert written["step2_corrected"]["calories_kcal"] == 450
    assert written["step2_corrected"]["micronutrients"] == ["Iron", "Magnesium"]
    # step2_data preserved
    assert written["step2_data"]["calories_kcal"] == 600
    assert written["step2_data"]["dish_name"] == "Chicken Rice"


def test_happy_path_calls_update_corrected_step2_data(
    client, monkeypatch, patch_auth, captured_writes
):
    record = make_record(result_gemini=PHASE2_DONE)
    _, capture = captured_writes
    monkeypatch.setattr(item_correction, "get_dish_image_query_by_id", lambda _id: record)
    monkeypatch.setattr(item_correction, "update_dish_image_query_results", capture)
    calls = _patch_update_personalization(monkeypatch, returns=object())

    res = client.post("/api/item/1/correction", json=VALID_PAYLOAD)

    assert res.status_code == 200
    assert len(calls) == 1
    assert calls[0]["query_id"] == 1
    assert calls[0]["payload"]["healthiness_score"] == 70


def test_personalization_row_missing_swallow_and_log_warn(
    client, monkeypatch, patch_auth, captured_writes, caplog
):
    record = make_record(result_gemini=PHASE2_DONE)
    _, capture = captured_writes
    monkeypatch.setattr(item_correction, "get_dish_image_query_by_id", lambda _id: record)
    monkeypatch.setattr(item_correction, "update_dish_image_query_results", capture)
    _patch_update_personalization(monkeypatch, returns=None)

    with caplog.at_level("WARNING"):
        res = client.post("/api/item/1/correction", json=VALID_PAYLOAD)

    assert res.status_code == 200
    assert any(
        "Stage 8 enrichment skipped" in rec.message and "query_id=1" in rec.message
        for rec in caplog.records
    )


def test_personalization_crud_exception_swallow_and_log_warn(
    client, monkeypatch, patch_auth, captured_writes, caplog
):
    record = make_record(result_gemini=PHASE2_DONE)
    _, capture = captured_writes
    monkeypatch.setattr(item_correction, "get_dish_image_query_by_id", lambda _id: record)
    monkeypatch.setattr(item_correction, "update_dish_image_query_results", capture)
    _patch_update_personalization(monkeypatch, raises=RuntimeError("db down"))

    with caplog.at_level("WARNING"):
        res = client.post("/api/item/1/correction", json=VALID_PAYLOAD)

    assert res.status_code == 200
    assert any(
        "Stage 8 enrichment failed" in rec.message and "db down" in rec.message
        for rec in caplog.records
    )


def test_response_body_carries_step2_corrected_payload(
    client, monkeypatch, patch_auth, captured_writes
):
    record = make_record(result_gemini=PHASE2_DONE)
    _, capture = captured_writes
    monkeypatch.setattr(item_correction, "get_dish_image_query_by_id", lambda _id: record)
    monkeypatch.setattr(item_correction, "update_dish_image_query_results", capture)
    _patch_update_personalization(monkeypatch, returns=object())

    res = client.post("/api/item/1/correction", json=VALID_PAYLOAD)

    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["record_id"] == 1
    assert body["step2_corrected"]["calories_kcal"] == 450


def test_saves_correction_does_not_destroy_other_result_gemini_keys(
    client, monkeypatch, patch_auth, captured_writes
):
    record = make_record(result_gemini=PHASE2_DONE)
    _, capture = captured_writes
    monkeypatch.setattr(item_correction, "get_dish_image_query_by_id", lambda _id: record)
    monkeypatch.setattr(item_correction, "update_dish_image_query_results", capture)
    _patch_update_personalization(monkeypatch, returns=object())

    res = client.post("/api/item/1/correction", json=VALID_PAYLOAD)
    assert res.status_code == 200

    written, _ = captured_writes
    final = written[-1]["result_gemini"]
    # nutrition_db_matches preserved
    assert "nutrition_db_matches" in final
    # personalized_matches preserved
    assert "personalized_matches" in final
    # step1_data preserved
    assert "step1_data" in final
