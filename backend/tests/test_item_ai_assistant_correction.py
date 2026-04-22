"""
Endpoint tests for POST /api/item/{record_id}/ai-assistant-correction (Stage 10).

Covers: auth + ownership, state guards (step2_data required, empty prompt),
Pydantic validation, happy-path dual write with `ai_assistant_prompt` stamped,
and Gemini-call failure surfacing as 502.
"""

# pylint: disable=missing-class-docstring,missing-function-docstring
# pylint: disable=redefined-outer-name,unused-argument

import pytest

from src.api import item_correction
from tests.conftest import make_record


VALID_BODY = {
    "prompt": "Portions are smaller than the AI estimated — ~200 kcal per serving.",
}


REVISED_PAYLOAD = {
    "dish_name": "Chicken Rice",
    "healthiness_score": 60,
    "healthiness_score_rationale": "Revised per user hint: smaller portion.",
    "calories_kcal": 420,
    "fiber_g": 2,
    "carbs_g": 35,
    "protein_g": 28,
    "fat_g": 12,
    "micronutrients": ["Iron"],
}


PHASE2_DONE = {
    "phase": 2,
    "identification_data": {"dish_predictions": [{"name": "Chicken Rice"}]},
    "nutrition_data": {
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


@pytest.fixture()
def patch_revise_ok(monkeypatch):
    async def _fake_revise(record_id, user_hint):
        return dict(REVISED_PAYLOAD)

    monkeypatch.setattr(item_correction, "revise_nutrition_with_hint", _fake_revise)


@pytest.fixture()
def patch_revise_raises(monkeypatch):
    async def _fake_revise(record_id, user_hint):
        raise RuntimeError("gemini down")

    monkeypatch.setattr(item_correction, "revise_nutrition_with_hint", _fake_revise)


def _patch_update_personalization(monkeypatch, *, returns=None, raises=None):
    calls = []

    def _update(**kwargs):
        calls.append(kwargs)
        if raises is not None:
            raise raises
        return returns

    monkeypatch.setattr(
        item_correction.crud_personalized_food, "update_corrected_nutrition_data", _update
    )
    return calls


# ---------------------------------------------------------------------------
# Auth + ownership
# ---------------------------------------------------------------------------


def test_returns_401_when_not_authenticated(client, monkeypatch):
    monkeypatch.setattr(item_correction, "authenticate_user_from_request", lambda _r: None)
    res = client.post("/api/item/1/ai-assistant-correction", json=VALID_BODY)
    assert res.status_code == 401


def test_returns_404_for_other_users_record(client, monkeypatch, patch_auth, fake_user):
    other = make_record(user_id=fake_user.id + 1, result_gemini=PHASE2_DONE)
    monkeypatch.setattr(item_correction, "get_dish_image_query_by_id", lambda _id: other)
    res = client.post("/api/item/1/ai-assistant-correction", json=VALID_BODY)
    assert res.status_code == 404


def test_returns_404_when_record_missing(client, monkeypatch, patch_auth):
    monkeypatch.setattr(item_correction, "get_dish_image_query_by_id", lambda _id: None)
    res = client.post("/api/item/1/ai-assistant-correction", json=VALID_BODY)
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# State guards
# ---------------------------------------------------------------------------


def test_returns_400_when_step2_data_missing(client, monkeypatch, patch_auth):
    record = make_record(result_gemini={"phase": 1, "identification_data": {}})
    monkeypatch.setattr(item_correction, "get_dish_image_query_by_id", lambda _id: record)
    res = client.post("/api/item/1/ai-assistant-correction", json=VALID_BODY)
    assert res.status_code == 400


def test_returns_400_when_result_gemini_null(client, monkeypatch, patch_auth):
    record = make_record(result_gemini=None)
    monkeypatch.setattr(item_correction, "get_dish_image_query_by_id", lambda _id: record)
    res = client.post("/api/item/1/ai-assistant-correction", json=VALID_BODY)
    assert res.status_code == 400


# ---------------------------------------------------------------------------
# Pydantic validation
# ---------------------------------------------------------------------------


def test_returns_422_when_prompt_empty(client, monkeypatch, patch_auth):
    record = make_record(result_gemini=PHASE2_DONE)
    monkeypatch.setattr(item_correction, "get_dish_image_query_by_id", lambda _id: record)
    res = client.post("/api/item/1/ai-assistant-correction", json={"prompt": ""})
    assert res.status_code == 422


def test_returns_422_when_prompt_whitespace(client, monkeypatch, patch_auth, patch_revise_ok):
    record = make_record(result_gemini=PHASE2_DONE)
    monkeypatch.setattr(item_correction, "get_dish_image_query_by_id", lambda _id: record)
    res = client.post("/api/item/1/ai-assistant-correction", json={"prompt": "   "})
    # Pydantic min_length=1 accepts "   " so the endpoint's strip-check catches it as 422
    assert res.status_code == 422


def test_returns_422_when_prompt_too_long(client, monkeypatch, patch_auth):
    record = make_record(result_gemini=PHASE2_DONE)
    monkeypatch.setattr(item_correction, "get_dish_image_query_by_id", lambda _id: record)
    res = client.post("/api/item/1/ai-assistant-correction", json={"prompt": "x" * 2001})
    assert res.status_code == 422


# ---------------------------------------------------------------------------
# Happy path + dual-write
# ---------------------------------------------------------------------------


def test_happy_path_writes_step2_corrected_with_ai_prompt(
    client, monkeypatch, patch_auth, patch_revise_ok, captured_writes
):
    record = make_record(result_gemini=PHASE2_DONE)
    writes, capture = captured_writes
    monkeypatch.setattr(item_correction, "get_dish_image_query_by_id", lambda _id: record)
    monkeypatch.setattr(item_correction, "update_dish_image_query_results", capture)
    _patch_update_personalization(monkeypatch, returns=object())

    res = client.post("/api/item/1/ai-assistant-correction", json=VALID_BODY)

    assert res.status_code == 200
    assert len(writes) == 1
    written = writes[0]["result_gemini"]
    corrected = written["nutrition_corrected"]
    # Revised macros landed from Gemini
    assert corrected["calories_kcal"] == 420
    assert corrected["dish_name"] == "Chicken Rice"
    # ai_assistant_prompt stamped with the submitted hint (stripped)
    assert corrected["ai_assistant_prompt"] == VALID_BODY["prompt"]
    # Original step2_data preserved for audit
    assert written["nutrition_data"]["calories_kcal"] == 600


def test_happy_path_mirrors_personalization_row(
    client, monkeypatch, patch_auth, patch_revise_ok, captured_writes
):
    record = make_record(result_gemini=PHASE2_DONE)
    _, capture = captured_writes
    monkeypatch.setattr(item_correction, "get_dish_image_query_by_id", lambda _id: record)
    monkeypatch.setattr(item_correction, "update_dish_image_query_results", capture)
    calls = _patch_update_personalization(monkeypatch, returns=object())

    res = client.post("/api/item/1/ai-assistant-correction", json=VALID_BODY)

    assert res.status_code == 200
    assert len(calls) == 1
    assert calls[0]["query_id"] == 1
    # The payload that went to the personalization row includes ai_assistant_prompt
    assert calls[0]["payload"]["ai_assistant_prompt"] == VALID_BODY["prompt"]
    assert calls[0]["payload"]["calories_kcal"] == 420


def test_happy_path_preserves_other_result_gemini_keys(
    client, monkeypatch, patch_auth, patch_revise_ok, captured_writes
):
    record = make_record(result_gemini=PHASE2_DONE)
    _, capture = captured_writes
    monkeypatch.setattr(item_correction, "get_dish_image_query_by_id", lambda _id: record)
    monkeypatch.setattr(item_correction, "update_dish_image_query_results", capture)
    _patch_update_personalization(monkeypatch, returns=object())

    res = client.post("/api/item/1/ai-assistant-correction", json=VALID_BODY)
    assert res.status_code == 200

    written, _ = captured_writes
    final = written[-1]["result_gemini"]
    assert "nutrition_db_matches" in final
    assert "personalized_matches" in final
    assert "identification_data" in final


def test_response_body_carries_step2_corrected(
    client, monkeypatch, patch_auth, patch_revise_ok, captured_writes
):
    record = make_record(result_gemini=PHASE2_DONE)
    _, capture = captured_writes
    monkeypatch.setattr(item_correction, "get_dish_image_query_by_id", lambda _id: record)
    monkeypatch.setattr(item_correction, "update_dish_image_query_results", capture)
    _patch_update_personalization(monkeypatch, returns=object())

    res = client.post("/api/item/1/ai-assistant-correction", json=VALID_BODY)

    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["record_id"] == 1
    assert body["nutrition_corrected"]["ai_assistant_prompt"] == VALID_BODY["prompt"]


# ---------------------------------------------------------------------------
# Gemini failure surface
# ---------------------------------------------------------------------------


def test_returns_502_when_revise_raises(
    client, monkeypatch, patch_auth, patch_revise_raises, captured_writes
):
    record = make_record(result_gemini=PHASE2_DONE)
    _, capture = captured_writes
    monkeypatch.setattr(item_correction, "get_dish_image_query_by_id", lambda _id: record)
    monkeypatch.setattr(item_correction, "update_dish_image_query_results", capture)
    _patch_update_personalization(monkeypatch, returns=object())

    res = client.post("/api/item/1/ai-assistant-correction", json=VALID_BODY)

    assert res.status_code == 502
    # No write happened
    writes, _ = captured_writes
    assert writes == []
