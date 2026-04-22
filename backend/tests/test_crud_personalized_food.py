"""
Tests for src/crud/crud_personalized_food.py.

Uses an in-memory SQLite engine so CRUD logic (INSERT/UPDATE/SELECT +
unique-index enforcement) is exercised against a real SQLAlchemy session
without depending on Postgres. `SessionLocal` in the CRUD module is
monkeypatched onto the SQLite-backed sessionmaker per test.
"""

# pylint: disable=missing-class-docstring,missing-function-docstring
# pylint: disable=redefined-outer-name,unused-argument

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from src.crud import crud_personalized_food
from src.database import Base
from src.models import DishImageQuery, PersonalizedFoodDescription, Users


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

    seed = test_session()
    try:
        seed.add(Users(id=1, username="alice", hashed_password="x"))
        seed.add(Users(id=2, username="bob", hashed_password="x"))
        seed.flush()
        for qid in (10, 11, 12, 20, 21):
            seed.add(
                DishImageQuery(
                    id=qid,
                    user_id=1 if qid < 20 else 2,
                    created_at=datetime.now(timezone.utc),
                )
            )
        seed.commit()
    finally:
        seed.close()

    yield test_session


def test_insert_description_row_persists_expected_columns(sqlite_session):
    row = crud_personalized_food.insert_description_row(
        user_id=1,
        query_id=10,
        image_url="/images/abc.jpg",
        description="chicken rice hainanese style",
        tokens=["chicken", "rice", "hainanese", "style"],
        similarity_score_on_insert=0.73,
    )
    assert row.id is not None
    assert row.user_id == 1
    assert row.query_id == 10
    assert row.image_url == "/images/abc.jpg"
    assert row.description == "chicken rice hainanese style"
    assert row.tokens == ["chicken", "rice", "hainanese", "style"]
    assert row.similarity_score_on_insert == pytest.approx(0.73)
    assert row.confirmed_dish_name is None
    assert row.confirmed_portions is None
    assert row.confirmed_tokens is None
    assert row.corrected_nutrition_data is None
    assert row.created_at is not None
    assert row.updated_at is not None
    assert row.created_at == row.updated_at


def test_insert_description_row_rejects_duplicate_query_id(sqlite_session):
    crud_personalized_food.insert_description_row(
        user_id=1, query_id=10, description="one", tokens=["one"]
    )
    with pytest.raises(IntegrityError):
        crud_personalized_food.insert_description_row(
            user_id=1, query_id=10, description="two", tokens=["two"]
        )


def test_update_confirmed_fields_sets_fields_and_bumps_updated_at(sqlite_session):
    inserted = crud_personalized_food.insert_description_row(
        user_id=1, query_id=10, description="pho bo", tokens=["pho", "bo"]
    )
    original_updated_at = inserted.updated_at

    updated = crud_personalized_food.update_confirmed_fields(
        query_id=10,
        confirmed_dish_name="Pho Bo",
        confirmed_portions=1.5,
        confirmed_tokens=["pho", "bo"],
    )
    assert updated is not None
    assert updated.confirmed_dish_name == "Pho Bo"
    assert updated.confirmed_portions == pytest.approx(1.5)
    assert updated.confirmed_tokens == ["pho", "bo"]
    assert updated.updated_at >= original_updated_at


def test_update_confirmed_fields_returns_none_for_missing_query_id(sqlite_session):
    result = crud_personalized_food.update_confirmed_fields(
        query_id=9999,
        confirmed_dish_name="nope",
        confirmed_portions=1.0,
        confirmed_tokens=["nope"],
    )
    assert result is None


def test_update_corrected_nutrition_data_persists_payload(sqlite_session):
    crud_personalized_food.insert_description_row(
        user_id=1, query_id=11, description="sushi roll", tokens=["sushi", "roll"]
    )
    payload = {
        "healthiness": "moderate",
        "calories_kcal": 420,
        "fat_g": 12,
        "micronutrients": ["Iron", "Folate"],
    }
    updated = crud_personalized_food.update_corrected_nutrition_data(query_id=11, payload=payload)
    assert updated is not None
    assert updated.corrected_nutrition_data == payload


def test_update_corrected_nutrition_data_returns_none_for_missing_query_id(sqlite_session):
    assert crud_personalized_food.update_corrected_nutrition_data(9999, {"a": 1}) is None


def test_get_row_by_query_id_returns_row(sqlite_session):
    inserted = crud_personalized_food.insert_description_row(
        user_id=1,
        query_id=10,
        description="chicken rice",
        tokens=["chicken", "rice"],
    )
    row = crud_personalized_food.get_row_by_query_id(10)
    assert row is not None
    assert row.id == inserted.id
    assert row.query_id == 10
    assert row.description == "chicken rice"


def test_get_row_by_query_id_returns_none_for_missing(sqlite_session):
    assert crud_personalized_food.get_row_by_query_id(9999) is None


def test_get_all_rows_for_user_scopes_and_excludes(sqlite_session):
    crud_personalized_food.insert_description_row(
        user_id=1, query_id=10, description="a", tokens=["a"]
    )
    crud_personalized_food.insert_description_row(
        user_id=1, query_id=11, description="b", tokens=["b"]
    )
    crud_personalized_food.insert_description_row(
        user_id=1, query_id=12, description="c", tokens=["c"]
    )
    crud_personalized_food.insert_description_row(
        user_id=2, query_id=20, description="x", tokens=["x"]
    )
    crud_personalized_food.insert_description_row(
        user_id=2, query_id=21, description="y", tokens=["y"]
    )

    user1_rows = crud_personalized_food.get_all_rows_for_user(1)
    assert [r.query_id for r in user1_rows] == [10, 11, 12]

    user1_excluded = crud_personalized_food.get_all_rows_for_user(1, exclude_query_id=11)
    assert [r.query_id for r in user1_excluded] == [10, 12]

    user2_rows = crud_personalized_food.get_all_rows_for_user(2)
    assert [r.query_id for r in user2_rows] == [20, 21]

    assert all(isinstance(r, PersonalizedFoodDescription) for r in user1_rows)
