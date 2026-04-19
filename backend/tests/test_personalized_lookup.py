"""
Tests for backend/src/service/personalized_lookup.py.

`search_for_user` is patched at the module boundary so no BM25 corpus is
built. `get_dish_image_query_by_id` is patched to return canned records
so tests don't touch the DB.
"""

# pylint: disable=missing-class-docstring,missing-function-docstring
# pylint: disable=redefined-outer-name,unused-argument

from types import SimpleNamespace

import pytest

from src.service import personalized_lookup
from src.service.personalized_lookup import (
    _build_query_tokens,
    lookup_personalization,
)


def _hit(
    query_id,
    *,
    image_url=None,
    description=None,
    similarity_score=0.9,
    corrected_step2_data=None,
):
    return {
        "query_id": query_id,
        "image_url": image_url,
        "description": description,
        "similarity_score": similarity_score,
        "row": SimpleNamespace(corrected_step2_data=corrected_step2_data),
    }


# ---------------------------------------------------------------------------
# _build_query_tokens
# ---------------------------------------------------------------------------


def test_build_query_tokens_unions_description_and_dish_name():
    tokens = _build_query_tokens("chicken rice", "Hainanese Chicken Rice")
    assert set(tokens) == {"chicken", "rice", "hainanese"}


def test_build_query_tokens_handles_none_description():
    tokens = _build_query_tokens(None, "Pho Bo")
    assert set(tokens) == {"pho", "bo"}


def test_build_query_tokens_empty_on_both_empty():
    assert not _build_query_tokens(None, "")
    assert not _build_query_tokens("", "")


# ---------------------------------------------------------------------------
# lookup_personalization
# ---------------------------------------------------------------------------


def test_lookup_personalization_cold_start_returns_empty(monkeypatch):
    monkeypatch.setattr(
        personalized_lookup.personalized_food_index,
        "search_for_user",
        lambda *_a, **_kw: [],
    )
    out = lookup_personalization(
        user_id=1, query_id=100, description="chicken rice", confirmed_dish_name="Chicken Rice"
    )
    assert not out


def test_lookup_personalization_populates_prior_step2_data_from_referenced_record(monkeypatch):
    hit = _hit(
        42, image_url="/images/prior.jpg", description="chicken rice", similarity_score=0.88
    )
    monkeypatch.setattr(
        personalized_lookup.personalized_food_index,
        "search_for_user",
        lambda *_a, **_kw: [hit],
    )

    referenced = SimpleNamespace(
        result_gemini={"step2_data": {"calories_kcal": 500, "dish_name": "Chicken Rice"}}
    )
    monkeypatch.setattr(personalized_lookup, "get_dish_image_query_by_id", lambda _id: referenced)

    out = lookup_personalization(
        user_id=1, query_id=100, description="chicken rice", confirmed_dish_name="Chicken Rice"
    )
    assert len(out) == 1
    assert out[0]["query_id"] == 42
    assert out[0]["image_url"] == "/images/prior.jpg"
    assert out[0]["similarity_score"] == pytest.approx(0.88)
    assert out[0]["prior_step2_data"]["calories_kcal"] == 500
    assert out[0]["corrected_step2_data"] is None


def test_lookup_personalization_prior_step2_data_null_when_referenced_has_no_step2(
    monkeypatch,
):
    hit = _hit(42)
    monkeypatch.setattr(
        personalized_lookup.personalized_food_index,
        "search_for_user",
        lambda *_a, **_kw: [hit],
    )
    referenced = SimpleNamespace(result_gemini={"step2_data": None})
    monkeypatch.setattr(personalized_lookup, "get_dish_image_query_by_id", lambda _id: referenced)

    out = lookup_personalization(1, 100, "c", "Chicken Rice")
    assert out[0]["prior_step2_data"] is None


def test_lookup_personalization_passes_corrected_step2_data_from_row(monkeypatch):
    corrected = {"calories_kcal": 420, "healthiness": "moderate"}
    hit = _hit(42, corrected_step2_data=corrected)
    monkeypatch.setattr(
        personalized_lookup.personalized_food_index,
        "search_for_user",
        lambda *_a, **_kw: [hit],
    )
    monkeypatch.setattr(
        personalized_lookup,
        "get_dish_image_query_by_id",
        lambda _id: SimpleNamespace(result_gemini={"step2_data": {"x": 1}}),
    )

    out = lookup_personalization(1, 100, "c", "Chicken Rice")
    assert out[0]["corrected_step2_data"] == corrected


def test_lookup_personalization_calls_search_for_user_with_exclude_query_id(monkeypatch):
    captured = {}

    def _fake(user_id, query_tokens, *, top_k, min_similarity, exclude_query_id):
        captured["user_id"] = user_id
        captured["exclude_query_id"] = exclude_query_id
        captured["top_k"] = top_k
        captured["min_similarity"] = min_similarity
        return []

    monkeypatch.setattr(personalized_lookup.personalized_food_index, "search_for_user", _fake)

    lookup_personalization(user_id=7, query_id=42, description="x", confirmed_dish_name="Y")
    assert captured["user_id"] == 7
    assert captured["exclude_query_id"] == 42
    # Defaults from the plan
    assert captured["top_k"] == 5
    assert captured["min_similarity"] == pytest.approx(0.30)


def test_lookup_personalization_drops_row_key_from_output(monkeypatch):
    hit = _hit(42)
    monkeypatch.setattr(
        personalized_lookup.personalized_food_index,
        "search_for_user",
        lambda *_a, **_kw: [hit],
    )
    monkeypatch.setattr(
        personalized_lookup,
        "get_dish_image_query_by_id",
        lambda _id: SimpleNamespace(result_gemini={"step2_data": {}}),
    )
    out = lookup_personalization(1, 100, "c", "Dish")
    assert "row" not in out[0]


def test_lookup_personalization_empty_tokens_skips_search(monkeypatch):
    search_calls = {"count": 0}

    def _counted(*_a, **_kw):
        search_calls["count"] += 1
        return []

    monkeypatch.setattr(personalized_lookup.personalized_food_index, "search_for_user", _counted)
    out = lookup_personalization(user_id=1, query_id=100, description=None, confirmed_dish_name="")
    assert not out
    assert search_calls["count"] == 0


def test_lookup_personalization_handles_missing_referenced_record(monkeypatch):
    """Referenced DishImageQuery lookup returns None → prior_step2_data=None."""
    hit = _hit(42)
    monkeypatch.setattr(
        personalized_lookup.personalized_food_index,
        "search_for_user",
        lambda *_a, **_kw: [hit],
    )
    monkeypatch.setattr(personalized_lookup, "get_dish_image_query_by_id", lambda _id: None)
    out = lookup_personalization(1, 100, "c", "Dish")
    assert len(out) == 1
    assert out[0]["prior_step2_data"] is None
