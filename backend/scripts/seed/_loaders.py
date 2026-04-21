"""
Per-source CSV → row-dict loaders for the nutrition seed script.

Extracted from `load_nutrition_db.py` so the orchestrator stays
under the line-count limit. Each loader reads one of the source CSVs
and emits a list of row dicts ready for `crud_nutrition.bulk_upsert_foods`.

The MyFCD basic loader joins against the nutrients lookup that
`_load_myfcd_nutrients` returns, so direct macro columns
(`calories`, `carbs_g`, ...) are populated from the per-serving (or
fallback per-100g × serving_size_grams / 100) values.
"""

# pylint: disable=wrong-import-order
import csv
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.service.nutrition_db import _normalize_text

from scripts.seed._variations import (
    extract_clean_terms_from_anuvaad,
    extract_clean_terms_from_myfcd,
    generate_food_variations,
)


_CIQUAL_KCAL_COL = "Energy, Regulation EU No 1169/2011 (kcal/100g)"
_CIQUAL_CARBS_COL = "Carbohydrate (g/100g)"
_CIQUAL_PROTEIN_COL = "Protein (g/100g)"
_CIQUAL_FAT_COL = "Fat (g/100g)"
_CIQUAL_FIBER_COL = "Fibres (g/100g)"


def coerce_empty_to_none(value: Any) -> Optional[str]:
    """Treat '', whitespace, and 'nan' (case-insensitive) as missing."""
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    return text


def to_float(value: Any) -> Optional[float]:
    """Best-effort coerce to float; missing / unparsable -> None."""
    text = coerce_empty_to_none(value)
    if text is None:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def read_csv(path: Path) -> List[Dict[str, Any]]:
    """Read a CSV via stdlib DictReader, coercing '' to None per cell."""
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        return [{k: coerce_empty_to_none(v) for k, v in row.items()} for row in reader]


def build_searchable_document(parts: List[Optional[str]]) -> str:
    """Normalize + concatenate searchable parts into a BM25 corpus document."""
    normalized = [_normalize_text(str(p)) for p in parts if p]
    return " ".join(seg for seg in normalized if seg)


def load_malaysian(path: Path) -> List[Dict[str, Any]]:
    """Build nutrition_foods rows from the Malaysian CSV."""
    rows = []
    for source_row in read_csv(path):
        food_name = source_row.get("food_item") or "Unknown"
        category = source_row.get("category")
        source_file = source_row.get("source_file") or ""
        source_food_id = Path(source_file).stem or food_name.lower().replace(" ", "_")

        parts = [food_name, category]
        parts.extend(generate_food_variations(food_name))
        rows.append(
            {
                "source": "malaysian_food_calories",
                "source_food_id": source_food_id,
                "food_name": food_name,
                "food_name_eng": None,
                "category": category,
                "searchable_document": build_searchable_document(parts),
                "calories": to_float(source_row.get("calories")),
                "carbs_g": None,
                "protein_g": None,
                "fat_g": None,
                "fiber_g": None,
                "serving_size_grams": None,
                "serving_unit": source_row.get("portion_size"),
                "raw_data": source_row,
            }
        )
    return rows


def load_anuvaad(path: Path) -> List[Dict[str, Any]]:
    """Build nutrition_foods rows from the Anuvaad CSV."""
    rows = []
    for source_row in read_csv(path):
        food_name = source_row.get("food_name") or "Unknown"
        food_code = source_row.get("food_code") or food_name

        parts = [food_name, food_code]
        parts.extend(extract_clean_terms_from_anuvaad(food_name))
        parts.extend(generate_food_variations(food_name))
        rows.append(
            {
                "source": "anuvaad",
                "source_food_id": food_code,
                "food_name": food_name,
                "food_name_eng": None,
                "category": None,
                "searchable_document": build_searchable_document(parts),
                "calories": to_float(source_row.get("energy_kcal")),
                "carbs_g": to_float(source_row.get("carb_g")),
                "protein_g": to_float(source_row.get("protein_g")),
                "fat_g": to_float(source_row.get("fat_g")),
                "fiber_g": to_float(source_row.get("fibre_g")),
                "serving_size_grams": None,
                "serving_unit": source_row.get("servings_unit"),
                "raw_data": source_row,
            }
        )
    return rows


def load_ciqual(path: Path) -> List[Dict[str, Any]]:
    """Build nutrition_foods rows from the CIQUAL CSV."""
    rows = []
    for source_row in read_csv(path):
        food_name = source_row.get("food_name") or "Unknown"
        food_name_eng = source_row.get("food_name_eng")
        food_code = source_row.get("food_code") or food_name
        food_group = source_row.get("food_group_name")
        food_subgroup = source_row.get("food_subgroup_name")

        primary_name = food_name_eng or food_name
        parts = [primary_name, food_group, food_subgroup]
        parts.extend(generate_food_variations(primary_name))
        rows.append(
            {
                "source": "ciqual",
                "source_food_id": food_code,
                "food_name": food_name,
                "food_name_eng": food_name_eng,
                "category": food_group,
                "searchable_document": build_searchable_document(parts),
                "calories": to_float(source_row.get(_CIQUAL_KCAL_COL)),
                "carbs_g": to_float(source_row.get(_CIQUAL_CARBS_COL)),
                "protein_g": to_float(source_row.get(_CIQUAL_PROTEIN_COL)),
                "fat_g": to_float(source_row.get(_CIQUAL_FAT_COL)),
                "fiber_g": to_float(source_row.get(_CIQUAL_FIBER_COL)),
                "serving_size_grams": None,
                "serving_unit": None,
                "raw_data": source_row,
            }
        )
    return rows


def load_myfcd_nutrients(
    path: Path,
) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Dict[str, Any]]]]:
    """
    Read `myfcd_nutrients.csv`.

    Returns (rows ready for bulk_upsert_myfcd_nutrients,
    {ndb_id: {nutrient_name: nutrient_dict}} lookup so the basic-row
    pass can populate direct macro columns from the join).
    """
    rows: List[Dict[str, Any]] = []
    lookup: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for source_row in read_csv(path):
        ndb_id = source_row.get("ndb_id")
        nutrient_name = source_row.get("nutrient_name")
        if not ndb_id or not nutrient_name:
            continue
        nutrient = {
            "ndb_id": ndb_id,
            "nutrient_name": nutrient_name,
            "value_per_100g": to_float(source_row.get("value_per_100g")),
            "value_per_serving": to_float(source_row.get("value_per_serving")),
            "unit": source_row.get("unit"),
            "category": source_row.get("category"),
        }
        rows.append(nutrient)
        lookup.setdefault(ndb_id, {})[nutrient_name] = nutrient
    return rows, lookup


def _myfcd_macro(
    nutrients: Dict[str, Dict[str, Any]],
    name: str,
    serving_size_grams: Optional[float],
) -> Optional[float]:
    """Pull a macro from the MyFCD nutrient dict; prefer per-serving."""
    nutrient = nutrients.get(name)
    if not nutrient:
        return None
    per_serving = nutrient.get("value_per_serving")
    if per_serving is not None:
        return per_serving
    per_100g = nutrient.get("value_per_100g")
    if per_100g is not None and serving_size_grams:
        return per_100g * serving_size_grams / 100.0
    return per_100g


def load_myfcd_basic(
    path: Path, nutrients_lookup: Dict[str, Dict[str, Dict[str, Any]]]
) -> List[Dict[str, Any]]:
    """Build nutrition_foods rows for MyFCD by joining basic + nutrients."""
    rows = []
    for source_row in read_csv(path):
        ndb_id = source_row.get("ndb_id")
        food_name = source_row.get("food_name") or "Unknown"
        if not ndb_id:
            continue
        per_food_nutrients = nutrients_lookup.get(ndb_id, {})
        serving_size_grams = to_float(source_row.get("serving_size_grams"))

        parts = [food_name]
        parts.extend(extract_clean_terms_from_myfcd(food_name))
        rows.append(
            {
                "source": "myfcd",
                "source_food_id": ndb_id,
                "food_name": food_name,
                "food_name_eng": None,
                "category": None,
                "searchable_document": build_searchable_document(parts),
                "calories": _myfcd_macro(per_food_nutrients, "Energy", serving_size_grams),
                "carbs_g": _myfcd_macro(per_food_nutrients, "Carbohydrate", serving_size_grams),
                "protein_g": _myfcd_macro(per_food_nutrients, "Protein", serving_size_grams),
                "fat_g": _myfcd_macro(per_food_nutrients, "Fat", serving_size_grams),
                "fiber_g": _myfcd_macro(
                    per_food_nutrients, "Total dietary fibre", serving_size_grams
                ),
                "serving_size_grams": serving_size_grams,
                "serving_unit": source_row.get("serving_unit"),
                "raw_data": source_row,
            }
        )
    return rows
