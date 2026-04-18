"""
Tests for scripts/seed/load_nutrition_db.py.

Runs the per-source row-builders against tiny CSV fixtures written to a
temp dir, then exercises the SQLite-backed CRUD upsert path used by
`test_crud_nutrition.py` to verify the end-to-end seed pipeline lands
the right rows. Variation expansion in `searchable_document` is checked
on a known fixture.
"""

# pylint: disable=missing-function-docstring,redefined-outer-name
# pylint: disable=unused-argument,protected-access,wrong-import-order

import csv
from pathlib import Path
from typing import Dict, List

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.crud import crud_nutrition
from src.database import Base

from scripts.seed import load_nutrition_db as seed


@pytest.fixture()
def sqlite_session(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    test_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    monkeypatch.setattr(crud_nutrition, "SessionLocal", test_session)
    yield test_session


def _write_csv(path: Path, rows: List[Dict[str, object]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def test_searchable_document_expands_malaysian_variations(tmp_path):
    csv_path = tmp_path / "malaysian_food_calories.csv"
    _write_csv(
        csv_path,
        [
            {
                "food_item": "Nasi Lemak",
                "category": "Traditional Malaysian Kuih",
                "calories": "180.0",
                "rice_bowl_equivalent": "0.9",
                "portion_size": "1 plate",
                "source": "test",
                "source_file": "nasi_lemak.json",
            }
        ],
    )
    rows = seed._load_malaysian(csv_path)
    assert len(rows) == 1
    doc = rows[0]["searchable_document"]
    # Variations from `_SYNONYM_MAP`: nasi -> rice; lemak -> coconut/coconut milk
    assert "nasi" in doc
    assert "rice" in doc
    assert "coconut" in doc
    assert rows[0]["calories"] == pytest.approx(180.0)
    assert rows[0]["serving_unit"] == "1 plate"
    assert rows[0]["source_food_id"] == "nasi_lemak"


def test_anuvaad_loader_pulls_macros(tmp_path):
    csv_path = tmp_path / "anuvaad.csv"
    _write_csv(
        csv_path,
        [
            {
                "food_code": "ASC500",
                "food_name": "Daal Tadka",
                "primarysource": "asc_manual",
                "energy_kcal": "120.5",
                "carb_g": "10.0",
                "protein_g": "5.5",
                "fat_g": "3.2",
                "fibre_g": "2.1",
                "servings_unit": "katori",
            }
        ],
    )
    rows = seed._load_anuvaad(csv_path)
    assert len(rows) == 1
    row = rows[0]
    assert row["calories"] == pytest.approx(120.5)
    assert row["protein_g"] == pytest.approx(5.5)
    assert row["fiber_g"] == pytest.approx(2.1)
    assert row["serving_unit"] == "katori"
    assert "daal" in row["searchable_document"]


def test_ciqual_loader_uses_english_name(tmp_path):
    csv_path = tmp_path / "ciqual.csv"
    _write_csv(
        csv_path,
        [
            {
                "food_code": "25000",
                "food_name": "Quiche lorraine",
                "food_name_eng": "Quiche Lorraine",
                "food_name_sci": "",
                "food_group_code": "1",
                "food_group_name": "starters and dishes",
                "food_subgroup_code": "101",
                "food_subgroup_name": "mixed salads",
                "food_subsubgroup_code": "0",
                "food_subsubgroup_name": "-",
                "source_file": "ciqual_2020.csv",
                "Energy, Regulation EU No 1169/2011 (kJ/100g)": "",
                "Energy, Regulation EU No 1169/2011 (kcal/100g)": "260",
                "Carbohydrate (g/100g)": "23.0",
                "Protein (g/100g)": "11.0",
                "Fat (g/100g)": "14.0",
                "Fibres (g/100g)": "1.5",
            }
        ],
    )
    rows = seed._load_ciqual(csv_path)
    assert len(rows) == 1
    row = rows[0]
    assert row["food_name_eng"] == "Quiche Lorraine"
    assert row["calories"] == pytest.approx(260.0)
    assert row["category"] == "starters and dishes"
    assert "quiche" in row["searchable_document"]


def test_myfcd_basic_join_pulls_calories_from_nutrients(tmp_path):
    nutrients_path = tmp_path / "myfcd_nutrients.csv"
    _write_csv(
        nutrients_path,
        [
            {
                "ndb_id": "R101061",
                "nutrient_name": "Energy",
                "value_per_100g": "457.0",
                "value_per_serving": "60.0",
                "unit": "Kcal",
                "category": "Proximates",
            },
            {
                "ndb_id": "R101061",
                "nutrient_name": "Protein",
                "value_per_100g": "8.3",
                "value_per_serving": "1.08",
                "unit": "g",
                "category": "Proximates",
            },
        ],
    )
    nutrient_rows, nutrient_lookup = seed._load_myfcd_nutrients(nutrients_path)
    assert len(nutrient_rows) == 2
    assert "R101061" in nutrient_lookup
    assert nutrient_lookup["R101061"]["Energy"]["value_per_serving"] == pytest.approx(60.0)

    basic_path = tmp_path / "myfcd_basic.csv"
    _write_csv(
        basic_path,
        [
            {
                "ndb_id": "R101061",
                "food_name": "BISCUIT, COCONUT",
                "serving_unit": "1 piece",
                "serving_size_grams": "13.02",
                "source_file": "R101061.json",
                "categories": '["Proximates"]',
                "total_nutrients": "13",
            }
        ],
    )
    basic_rows = seed._load_myfcd_basic(basic_path, nutrient_lookup)
    assert len(basic_rows) == 1
    row = basic_rows[0]
    assert row["calories"] == pytest.approx(60.0)
    assert row["protein_g"] == pytest.approx(1.08)
    assert row["serving_size_grams"] == pytest.approx(13.02)


def test_myfcd_basic_falls_back_to_per_100g_when_per_serving_missing(tmp_path):
    nutrients_path = tmp_path / "myfcd_nutrients.csv"
    _write_csv(
        nutrients_path,
        [
            {
                "ndb_id": "R200000",
                "nutrient_name": "Energy",
                "value_per_100g": "200.0",
                "value_per_serving": "",
                "unit": "Kcal",
                "category": "Proximates",
            },
        ],
    )
    _, nutrient_lookup = seed._load_myfcd_nutrients(nutrients_path)

    basic_path = tmp_path / "myfcd_basic.csv"
    _write_csv(
        basic_path,
        [
            {
                "ndb_id": "R200000",
                "food_name": "PLACEHOLDER",
                "serving_unit": "1 cup",
                "serving_size_grams": "50.0",
                "source_file": "R200000.json",
                "categories": "[]",
                "total_nutrients": "1",
            }
        ],
    )
    rows = seed._load_myfcd_basic(basic_path, nutrient_lookup)
    # Falls back to per_100g * 50/100 = 100.0
    assert rows[0]["calories"] == pytest.approx(100.0)


def test_seed_end_to_end_against_sqlite(sqlite_session, tmp_path):
    csv_path = tmp_path / "anuvaad.csv"
    _write_csv(
        csv_path,
        [
            {
                "food_code": "ASC001",
                "food_name": "Hot tea",
                "primarysource": "asc_manual",
                "energy_kcal": "16.14",
                "carb_g": "2.58",
                "protein_g": "0.39",
                "fat_g": "0.53",
                "fibre_g": "0.0",
                "servings_unit": "tea cup",
            }
        ],
    )
    rows = seed._load_anuvaad(csv_path)
    inserted = crud_nutrition.bulk_upsert_foods(rows)
    assert inserted == 1

    # Re-run is idempotent — no second insert, just an update
    crud_nutrition.bulk_upsert_foods(rows)
    grouped = crud_nutrition.get_all_foods_grouped_by_source()
    assert len(grouped["anuvaad"]) == 1
    assert grouped["anuvaad"][0].calories == pytest.approx(16.14)


def test_coerce_empty_to_none_handles_blank_and_nan():
    assert seed._coerce_empty_to_none("") is None
    assert seed._coerce_empty_to_none("   ") is None
    assert seed._coerce_empty_to_none("nan") is None
    assert seed._coerce_empty_to_none("NaN") is None
    assert seed._coerce_empty_to_none("hello") == "hello"
    assert seed._coerce_empty_to_none(None) is None
    assert seed._coerce_empty_to_none("0") == "0"


def test_to_float_returns_none_for_missing_values():
    assert seed._to_float("") is None
    assert seed._to_float("nan") is None
    assert seed._to_float("not a number") is None
    assert seed._to_float("3.14") == pytest.approx(3.14)
    assert seed._to_float("0") == pytest.approx(0.0)


def test_verify_csvs_raises_when_files_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(seed, "DATABASE_DIR", tmp_path)
    with pytest.raises(FileNotFoundError):
        seed._verify_csvs()
