"""
Tests for src/crud/crud_nutrition.py.

Uses an in-memory SQLite engine so the upsert + read paths are
exercised against a real SQLAlchemy session without depending on
Postgres. The CRUD module's `SessionLocal` is monkeypatched to a
SQLite-backed sessionmaker per test, and `_insert_for` is dialect-aware
so the same `on_conflict_do_update` call site works for both.
"""

# pylint: disable=missing-function-docstring,redefined-outer-name,unused-argument

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.crud import crud_nutrition
from src.database import Base


@pytest.fixture()
def sqlite_session(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    test_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    monkeypatch.setattr(crud_nutrition, "SessionLocal", test_session)
    yield test_session


def _food_row(source: str, source_food_id: str, *, food_name: str = "Sample", **overrides):
    base = {
        "source": source,
        "source_food_id": source_food_id,
        "food_name": food_name,
        "food_name_eng": None,
        "category": None,
        "searchable_document": food_name.lower(),
        "calories": 100.0,
        "carbs_g": 10.0,
        "protein_g": 5.0,
        "fat_g": 2.0,
        "fiber_g": 1.0,
        "serving_size_grams": None,
        "serving_unit": None,
        "raw_data": {"food_name": food_name},
    }
    base.update(overrides)
    return base


def test_bulk_upsert_foods_inserts_new_rows(sqlite_session):
    crud_nutrition.bulk_upsert_foods(
        [_food_row("anuvaad", "ASC001"), _food_row("ciqual", "12345")]
    )
    counts = crud_nutrition.count_foods_by_source()
    assert counts["anuvaad"] == 1
    assert counts["ciqual"] == 1
    assert counts["myfcd"] == 0
    assert counts["malaysian_food_calories"] == 0


def test_bulk_upsert_foods_updates_on_conflict(sqlite_session):
    crud_nutrition.bulk_upsert_foods([_food_row("anuvaad", "ASC001", food_name="First")])
    crud_nutrition.bulk_upsert_foods(
        [_food_row("anuvaad", "ASC001", food_name="Second", calories=999.0)]
    )
    grouped = crud_nutrition.get_all_foods_grouped_by_source()
    assert len(grouped["anuvaad"]) == 1
    row = grouped["anuvaad"][0]
    assert row.food_name == "Second"
    assert row.calories == pytest.approx(999.0)


def test_bulk_upsert_foods_returns_input_count(sqlite_session):
    n = crud_nutrition.bulk_upsert_foods([_food_row("anuvaad", f"A{i}") for i in range(5)])
    assert n == 5


def test_bulk_upsert_foods_handles_empty_input(sqlite_session):
    assert crud_nutrition.bulk_upsert_foods([]) == 0


def test_bulk_upsert_myfcd_nutrients_inserts_then_updates(sqlite_session):
    crud_nutrition.bulk_upsert_myfcd_nutrients(
        [
            {
                "ndb_id": "R101061",
                "nutrient_name": "Energy",
                "value_per_100g": 457.0,
                "value_per_serving": 60.0,
                "unit": "Kcal",
                "category": "Proximates",
            }
        ]
    )
    crud_nutrition.bulk_upsert_myfcd_nutrients(
        [
            {
                "ndb_id": "R101061",
                "nutrient_name": "Energy",
                "value_per_100g": 999.0,
                "value_per_serving": 120.0,
                "unit": "Kcal",
                "category": "Proximates",
            }
        ]
    )
    grouped = crud_nutrition.get_myfcd_nutrients_grouped_by_ndb_id()
    assert list(grouped.keys()) == ["R101061"]
    assert grouped["R101061"][0].value_per_100g == pytest.approx(999.0)
    assert grouped["R101061"][0].value_per_serving == pytest.approx(120.0)


def test_get_all_foods_grouped_by_source_partitions(sqlite_session):
    crud_nutrition.bulk_upsert_foods(
        [
            _food_row("anuvaad", "A1"),
            _food_row("anuvaad", "A2"),
            _food_row("ciqual", "C1"),
            _food_row("malaysian_food_calories", "M1"),
            _food_row("myfcd", "MY1"),
            _food_row("myfcd", "MY2"),
        ]
    )
    grouped = crud_nutrition.get_all_foods_grouped_by_source()
    assert {k: len(v) for k, v in grouped.items()} == {
        "anuvaad": 2,
        "ciqual": 1,
        "malaysian_food_calories": 1,
        "myfcd": 2,
    }


def test_get_myfcd_nutrients_groups_per_ndb_id(sqlite_session):
    crud_nutrition.bulk_upsert_myfcd_nutrients(
        [
            {
                "ndb_id": "X1",
                "nutrient_name": "Energy",
                "value_per_100g": 100.0,
                "value_per_serving": 10.0,
                "unit": "Kcal",
                "category": "P",
            },
            {
                "ndb_id": "X1",
                "nutrient_name": "Protein",
                "value_per_100g": 5.0,
                "value_per_serving": 0.5,
                "unit": "g",
                "category": "P",
            },
            {
                "ndb_id": "X2",
                "nutrient_name": "Energy",
                "value_per_100g": 200.0,
                "value_per_serving": 20.0,
                "unit": "Kcal",
                "category": "P",
            },
        ]
    )
    grouped = crud_nutrition.get_myfcd_nutrients_grouped_by_ndb_id()
    assert sorted(grouped.keys()) == ["X1", "X2"]
    assert {n.nutrient_name for n in grouped["X1"]} == {"Energy", "Protein"}
    assert len(grouped["X2"]) == 1


def test_count_foods_reports_zero_for_unseen_sources(sqlite_session):
    crud_nutrition.bulk_upsert_foods([_food_row("malaysian_food_calories", "M1")])
    counts = crud_nutrition.count_foods_by_source()
    assert counts == {
        "malaysian_food_calories": 1,
        "myfcd": 0,
        "anuvaad": 0,
        "ciqual": 0,
    }
