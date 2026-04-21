"""
Tests for src/service/personalized_reference.py.

Uses the same in-memory SQLite harness as test_crud_personalized_food.py so
`crud_personalized_food.*`, `get_dish_image_query_by_id`, and the BM25
`search_for_user` call all run against a real SQLAlchemy session. The
Gemini fast-caption call is monkeypatched at the boundary.
"""

# pylint: disable=missing-class-docstring,missing-function-docstring
# pylint: disable=redefined-outer-name,unused-argument

import asyncio
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from src.crud import crud_personalized_food, dish_query_basic
from src.database import Base
from src.models import DishImageQuery, Users
from src.service import personalized_food_index, personalized_reference


@pytest.fixture()
def sqlite_session(monkeypatch):
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_connection, _):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    test_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    monkeypatch.setattr(crud_personalized_food, "SessionLocal", test_session)
    monkeypatch.setattr(dish_query_basic, "SessionLocal", test_session)

    seed = test_session()
    try:
        seed.add(Users(id=1, username="alice", hashed_password="x"))
        seed.add(Users(id=2, username="bob", hashed_password="x"))
        seed.flush()
        for qid, uid in ((10, 1), (11, 1), (20, 2), (30, 1), (31, 1)):
            seed.add(
                DishImageQuery(
                    id=qid,
                    user_id=uid,
                    image_url=f"/images/q{qid}.jpg",
                    result_gemini=None,
                    created_at=datetime.now(timezone.utc),
                )
            )
        seed.commit()
    finally:
        seed.close()

    yield test_session


@pytest.fixture()
def caption_spy(monkeypatch):
    calls = {"count": 0}

    async def fake(_image_path):
        calls["count"] += 1
        return calls.get("return_value", "chicken rice hainanese")

    monkeypatch.setattr(personalized_reference, "generate_fast_caption_async", fake)
    return calls


def _set_caption(calls, text):
    calls["return_value"] = text


def _set_caption_raises(monkeypatch, exc):
    async def fake(_image_path):
        raise exc

    monkeypatch.setattr(personalized_reference, "generate_fast_caption_async", fake)


def test_resolve_reference_cold_start_returns_caption_and_null_reference(
    sqlite_session, caption_spy
):
    _set_caption(caption_spy, "chicken rice")
    result = asyncio.run(
        personalized_reference.resolve_reference_for_upload(
            user_id=1, query_id=10, image_path="/tmp/q10.jpg"
        )
    )
    assert result == {"flash_caption": "chicken rice", "reference_image": None}
    row = crud_personalized_food.get_row_by_query_id(10)
    assert row is not None
    assert row.description == "chicken rice"
    assert row.tokens == ["chicken", "rice"]
    assert row.similarity_score_on_insert is None
    assert row.image_url == "/images/q10.jpg"


def test_resolve_reference_warm_user_returns_reference(sqlite_session, caption_spy):
    # Seed a prior row for user 1 and give its DishImageQuery a step1_data
    crud_personalized_food.insert_description_row(
        user_id=1,
        query_id=10,
        image_url="/images/q10.jpg",
        description="chicken rice hainanese style",
        tokens=["chicken", "rice", "hainanese", "style"],
        similarity_score_on_insert=None,
    )
    dish_query_basic.update_dish_image_query_results(
        query_id=10,
        result_openai=None,
        result_gemini={"step1_data": {"dish_predictions": [{"name": "Chicken Rice"}]}},
    )

    _set_caption(caption_spy, "chicken rice with cucumber")
    result = asyncio.run(
        personalized_reference.resolve_reference_for_upload(
            user_id=1, query_id=11, image_path="/tmp/q11.jpg"
        )
    )
    assert result is not None
    assert result["flash_caption"] == "chicken rice with cucumber"
    ref = result["reference_image"]
    assert ref is not None
    assert ref["query_id"] == 10
    assert ref["similarity_score"] >= 0.25
    assert ref["image_url"] == "/images/q10.jpg"
    assert ref["prior_step1_data"] == {"dish_predictions": [{"name": "Chicken Rice"}]}

    # New row for query_id=11 inserted with similarity_score_on_insert set
    row11 = crud_personalized_food.get_row_by_query_id(11)
    assert row11 is not None
    assert row11.similarity_score_on_insert is not None


def test_resolve_reference_excludes_self(sqlite_session, monkeypatch, caption_spy):
    # The exclude_query_id contract prevents self-matching even if the
    # orchestrator somehow runs when the row already exists. Simulate a
    # degenerate caller by monkey-patching the retry short-circuit probe off.
    crud_personalized_food.insert_description_row(
        user_id=1,
        query_id=10,
        description="chicken rice",
        tokens=["chicken", "rice"],
    )
    _set_caption(caption_spy, "chicken rice")
    # Bypass the retry short-circuit by tricking the probe to return None
    monkeypatch.setattr(crud_personalized_food, "get_row_by_query_id", lambda _qid: None)
    # The insert will later fail with IntegrityError but the orchestrator
    # swallows it. We only care that the returned reference_image does NOT
    # have query_id == 10 (self). Since exclude_query_id=10 is passed to
    # the search, and no other matching row exists, reference_image is None.
    result = asyncio.run(
        personalized_reference.resolve_reference_for_upload(
            user_id=1, query_id=10, image_path="/tmp/q10.jpg"
        )
    )
    assert result == {"flash_caption": "chicken rice", "reference_image": None}


def test_resolve_reference_below_threshold_returns_null_reference_but_inserts_row(
    sqlite_session, monkeypatch, caption_spy
):
    # Force every BM25 normalized score below the 0.25 threshold.
    monkeypatch.setattr(
        personalized_food_index,
        "search_for_user",
        lambda *_a, **_kw: [],
    )
    crud_personalized_food.insert_description_row(
        user_id=1, query_id=10, description="pho bo", tokens=["pho", "bo"]
    )
    _set_caption(caption_spy, "chocolate cookie")
    result = asyncio.run(
        personalized_reference.resolve_reference_for_upload(
            user_id=1, query_id=11, image_path="/tmp/q11.jpg"
        )
    )
    assert result == {"flash_caption": "chocolate cookie", "reference_image": None}
    assert crud_personalized_food.get_row_by_query_id(11) is not None


def test_resolve_reference_retry_short_circuits_when_row_exists(sqlite_session, caption_spy):
    crud_personalized_food.insert_description_row(
        user_id=1, query_id=10, description="prior", tokens=["prior"]
    )
    _set_caption(caption_spy, "should-not-be-called")
    result = asyncio.run(
        personalized_reference.resolve_reference_for_upload(
            user_id=1, query_id=10, image_path="/tmp/q10.jpg"
        )
    )
    assert result is None
    assert caption_spy["count"] == 0
    # Row untouched
    row = crud_personalized_food.get_row_by_query_id(10)
    assert row.description == "prior"


def test_resolve_reference_graceful_degrade_on_caption_failure(sqlite_session, monkeypatch):
    _set_caption_raises(monkeypatch, ValueError("Gemini down"))
    result = asyncio.run(
        personalized_reference.resolve_reference_for_upload(
            user_id=1, query_id=10, image_path="/tmp/q10.jpg"
        )
    )
    assert result == {"flash_caption": None, "reference_image": None}
    # No row inserted on caption failure
    assert crud_personalized_food.get_row_by_query_id(10) is None


def test_resolve_reference_graceful_degrade_on_image_missing(sqlite_session, monkeypatch):
    _set_caption_raises(monkeypatch, FileNotFoundError("no image"))
    result = asyncio.run(
        personalized_reference.resolve_reference_for_upload(
            user_id=1, query_id=10, image_path="/nope.jpg"
        )
    )
    assert result == {"flash_caption": None, "reference_image": None}
    assert crud_personalized_food.get_row_by_query_id(10) is None


def test_resolve_reference_handles_prior_step1_data_missing(sqlite_session, caption_spy):
    crud_personalized_food.insert_description_row(
        user_id=1,
        query_id=10,
        image_url="/images/q10.jpg",
        description="chicken rice",
        tokens=["chicken", "rice"],
    )
    # Leave DishImageQuery.result_gemini as None (Phase 1.1.2 never completed)
    _set_caption(caption_spy, "chicken rice")
    result = asyncio.run(
        personalized_reference.resolve_reference_for_upload(
            user_id=1, query_id=11, image_path="/tmp/q11.jpg"
        )
    )
    assert result is not None
    ref = result["reference_image"]
    assert ref is not None
    assert ref["query_id"] == 10
    assert ref["prior_step1_data"] is None


def test_resolve_reference_cross_user_isolation(sqlite_session, caption_spy):
    crud_personalized_food.insert_description_row(
        user_id=2,
        query_id=20,
        image_url="/images/q20.jpg",
        description="chicken rice",
        tokens=["chicken", "rice"],
    )
    _set_caption(caption_spy, "chicken rice")
    # User 1 (alice) searches — must not surface user 2 (bob)'s row.
    result = asyncio.run(
        personalized_reference.resolve_reference_for_upload(
            user_id=1, query_id=10, image_path="/tmp/q10.jpg"
        )
    )
    assert result == {"flash_caption": "chicken rice", "reference_image": None}
    # Alice's row inserted
    assert crud_personalized_food.get_row_by_query_id(10) is not None
    # Bob's row untouched
    bob = crud_personalized_food.get_row_by_query_id(20)
    assert bob.description == "chicken rice"


def test_resolve_reference_empty_tokens_inserts_row_without_search(
    sqlite_session, monkeypatch, caption_spy
):
    search_calls = {"count": 0}

    def _counted(*_a, **_kw):
        search_calls["count"] += 1
        return []

    monkeypatch.setattr(personalized_food_index, "search_for_user", _counted)
    _set_caption(caption_spy, "...")
    result = asyncio.run(
        personalized_reference.resolve_reference_for_upload(
            user_id=1, query_id=10, image_path="/tmp/q10.jpg"
        )
    )
    assert result == {"flash_caption": "...", "reference_image": None}
    assert search_calls["count"] == 0
    row = crud_personalized_food.get_row_by_query_id(10)
    assert row is not None
    assert row.tokens == []
