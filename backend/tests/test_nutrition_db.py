"""
Tests for src/service/nutrition_db.py.

The service's only DB dependency is `crud_nutrition.get_all_foods_grouped_by_source`
and `get_myfcd_nutrients_grouped_by_ndb_id`. Both are patched per test
to return hand-crafted ORM-like row objects so the tests are pure
in-process: BM25 indices are built on the fixture corpus and the
verbatim row-output shape is asserted.

Manual smoke check (not in CI — requires a populated dev DB):
    from src.service.nutrition_db import get_nutrition_service
    svc = get_nutrition_service()
    assert svc._search_dishes_direct("chicken rice", top_k=5)[0]["confidence"] > 0.5
"""

# pylint: disable=missing-function-docstring,redefined-outer-name,protected-access
# pylint: disable=unused-argument

from types import SimpleNamespace
from typing import Any, Dict, Optional

import pytest

from src.service import nutrition_db


def _food_row(
    *,
    source: str,
    source_food_id: str,
    food_name: str,
    searchable_document: str,
    food_name_eng: Optional[str] = None,
    category: Optional[str] = None,
    raw_data: Optional[Dict[str, Any]] = None,
    serving_size_grams: Optional[float] = None,
    serving_unit: Optional[str] = None,
    calories: Optional[float] = None,
):
    return SimpleNamespace(
        source=source,
        source_food_id=source_food_id,
        food_name=food_name,
        food_name_eng=food_name_eng,
        category=category,
        searchable_document=searchable_document,
        calories=calories,
        carbs_g=None,
        protein_g=None,
        fat_g=None,
        fiber_g=None,
        serving_size_grams=serving_size_grams,
        serving_unit=serving_unit,
        raw_data=raw_data or {"food_name": food_name},
    )


def _myfcd_nutrient(
    *, ndb_id, nutrient_name, value_per_100g=None, value_per_serving=None, unit=None, category=None
):
    return SimpleNamespace(
        ndb_id=ndb_id,
        nutrient_name=nutrient_name,
        value_per_100g=value_per_100g,
        value_per_serving=value_per_serving,
        unit=unit,
        category=category,
    )


@pytest.fixture(autouse=True)
def reset_singleton():
    nutrition_db._reset_singleton_for_tests()
    yield
    nutrition_db._reset_singleton_for_tests()


@pytest.fixture()
def patch_corpus(monkeypatch):
    """Replace the two CRUD reads with canned-rows factories."""

    def _set(*, foods_by_source=None, myfcd_nutrients=None):
        sources = ("malaysian_food_calories", "myfcd", "anuvaad", "ciqual")
        grouped = {src: [] for src in sources}
        for src, rows in (foods_by_source or {}).items():
            grouped[src] = list(rows)
        nutrients = {}
        for n in myfcd_nutrients or []:
            nutrients.setdefault(n.ndb_id, []).append(n)

        monkeypatch.setattr(
            nutrition_db.crud_nutrition,
            "get_all_foods_grouped_by_source",
            lambda: grouped,
        )
        monkeypatch.setattr(
            nutrition_db.crud_nutrition,
            "get_myfcd_nutrients_grouped_by_ndb_id",
            lambda: nutrients,
        )

    return _set


def test_service_raises_on_empty_db(patch_corpus):
    patch_corpus()
    with pytest.raises(nutrition_db.NutritionDBEmptyError) as exc:
        nutrition_db.NutritionCollectionService()
    assert "scripts.seed.load_nutrition_db" in str(exc.value)


def test_service_builds_four_indices(patch_corpus):
    patch_corpus(
        foods_by_source={
            "malaysian_food_calories": [
                _food_row(
                    source="malaysian_food_calories",
                    source_food_id="m1",
                    food_name="Nasi Lemak",
                    searchable_document="nasi lemak rice coconut milk",
                )
            ],
            "myfcd": [
                _food_row(
                    source="myfcd",
                    source_food_id="R101061",
                    food_name="BISCUIT, COCONUT",
                    searchable_document="biscuit coconut",
                )
            ],
            "anuvaad": [
                _food_row(
                    source="anuvaad",
                    source_food_id="ASC001",
                    food_name="Daal Tadka",
                    searchable_document="daal tadka dal lentil curry",
                )
            ],
            "ciqual": [
                _food_row(
                    source="ciqual",
                    source_food_id="25001",
                    food_name="Quiche lorraine",
                    food_name_eng="Quiche lorraine",
                    searchable_document="quiche lorraine starters",
                )
            ],
        }
    )
    svc = nutrition_db.NutritionCollectionService()
    assert len(svc.malaysian_foods) == 1
    assert len(svc.myfcd_foods) == 1
    assert len(svc.anuvaad_foods) == 1
    assert len(svc.ciqual_foods) == 1
    assert svc.malaysian_bm25 is not None
    assert svc.myfcd_bm25 is not None
    assert svc.anuvaad_bm25 is not None
    assert svc.ciqual_bm25 is not None


@pytest.fixture()
def four_source_corpus(patch_corpus):
    """
    Per-source corpora large enough that BM25 IDF stays positive
    (BM25Okapi reduces to 0 when df = N/2 in a tiny corpus). Production
    has 4,493 rows so this collapse is impossible there; fixture is
    sized to avoid it artificially.
    """
    patch_corpus(
        foods_by_source={
            "malaysian_food_calories": [
                _food_row(
                    source="malaysian_food_calories",
                    source_food_id="ayam_goreng",
                    food_name="Ayam Goreng",
                    searchable_document="ayam goreng chicken fried",
                ),
                _food_row(
                    source="malaysian_food_calories",
                    source_food_id="chicken_rice",
                    food_name="Chicken Rice",
                    searchable_document="chicken rice nasi ayam hainanese",
                ),
                _food_row(
                    source="malaysian_food_calories",
                    source_food_id="apple_red",
                    food_name="Apple, Red",
                    searchable_document="apple red fruits",
                ),
                _food_row(
                    source="malaysian_food_calories",
                    source_food_id="banana",
                    food_name="Banana",
                    searchable_document="banana fruits",
                ),
                _food_row(
                    source="malaysian_food_calories",
                    source_food_id="laksa",
                    food_name="Laksa",
                    searchable_document="laksa noodles soup spicy",
                ),
            ],
            "myfcd": [
                _food_row(
                    source="myfcd",
                    source_food_id="R101061",
                    food_name="BISCUIT, COCONUT",
                    searchable_document="biscuit coconut",
                ),
                _food_row(
                    source="myfcd",
                    source_food_id="R101069",
                    food_name="BISCUIT, LEMON PUFF",
                    searchable_document="biscuit lemon puff",
                ),
                _food_row(
                    source="myfcd",
                    source_food_id="R101081",
                    food_name="CROISSANT",
                    searchable_document="croissant bread pastry",
                ),
                _food_row(
                    source="myfcd",
                    source_food_id="R101094",
                    food_name="BUN, CHEESE",
                    searchable_document="bun cheese bread",
                ),
            ],
            "anuvaad": [
                _food_row(
                    source="anuvaad",
                    source_food_id="ASC500",
                    food_name="Daal Tadka",
                    searchable_document="daal tadka dal lentil curry",
                ),
                _food_row(
                    source="anuvaad",
                    source_food_id="ASC600",
                    food_name="Aloo Paratha",
                    searchable_document="aloo paratha bread potato roti",
                ),
                _food_row(
                    source="anuvaad",
                    source_food_id="ASC700",
                    food_name="Chicken Biryani",
                    searchable_document="chicken biryani rice spices murgh",
                ),
                _food_row(
                    source="anuvaad",
                    source_food_id="ASC800",
                    food_name="Paneer Tikka",
                    searchable_document="paneer tikka cheese cottage grilled",
                ),
            ],
            "ciqual": [
                _food_row(
                    source="ciqual",
                    source_food_id="25001",
                    food_name="Quiche Lorraine",
                    food_name_eng="Quiche Lorraine",
                    searchable_document="quiche lorraine starters dishes",
                ),
                _food_row(
                    source="ciqual",
                    source_food_id="25500",
                    food_name="Salade verte",
                    food_name_eng="Green salad",
                    searchable_document="green salad vegetables",
                ),
                _food_row(
                    source="ciqual",
                    source_food_id="25600",
                    food_name="Tabbouleh",
                    food_name_eng="Tabbouleh",
                    searchable_document="tabbouleh starters mixed",
                ),
                _food_row(
                    source="ciqual",
                    source_food_id="25700",
                    food_name="Soupe à l'oignon",
                    food_name_eng="Onion soup",
                    searchable_document="onion soup starters",
                ),
            ],
        }
    )


def test_search_returns_top_1_from_expected_source(four_source_corpus):
    svc = nutrition_db.NutritionCollectionService()
    cases = [
        ("ayam goreng", {"malaysian_food_calories", "anuvaad"}),
        ("daal tadka", {"anuvaad"}),
        ("quiche lorraine", {"ciqual"}),
    ]
    for query, allowed_sources in cases:
        hits = svc._search_dishes_direct(query, top_k=3, min_confidence=0.5)
        assert hits, f"no results for {query!r}"
        assert (
            hits[0]["source"] in allowed_sources
        ), f"{query!r} expected source in {allowed_sources}, got {hits[0]['source']}"
        assert hits[0]["confidence"] > 0.5


def test_search_chicken_rice_above_confidence_floor(four_source_corpus):
    svc = nutrition_db.NutritionCollectionService()
    hits = svc._search_dishes_direct("chicken rice", top_k=5)
    assert hits
    assert hits[0]["confidence"] > 0.5


def test_search_returns_row_output_shape(four_source_corpus):
    svc = nutrition_db.NutritionCollectionService()
    hits = svc._search_dishes_direct("chicken rice", top_k=2)
    expected_keys = {
        "matched_food_name",
        "source",
        "confidence",
        "confidence_score",
        "nutrition_data",
        "search_method",
        "raw_bm25_score",
        "matched_keywords",
        "total_keywords",
    }
    for hit in hits:
        assert set(hit.keys()) == expected_keys
        assert hit["search_method"] == "Direct BM25"
        assert 0.50 <= hit["confidence"] <= 0.95


def test_search_filters_below_min_confidence(four_source_corpus):
    svc = nutrition_db.NutritionCollectionService()
    assert svc._search_dishes_direct("zzz unrelated query", top_k=3, min_confidence=0.85) == []


def test_search_caps_at_top_k(four_source_corpus):
    svc = nutrition_db.NutritionCollectionService()
    hits = svc._search_dishes_direct("chicken rice", top_k=2)
    assert len(hits) <= 2


def test_search_empty_query_returns_empty(four_source_corpus):
    svc = nutrition_db.NutritionCollectionService()
    assert svc._search_dishes_direct("   ", top_k=5) == []
    assert svc._search_dishes_direct("", top_k=5) == []


def test_enhanced_search_weights_dish_tokens(four_source_corpus):
    svc = nutrition_db.NutritionCollectionService()
    result = svc.search_nutrition_database_enhanced(
        dish_name="chicken rice",
        related_keywords="hainanese,steamed",
        estimated_quantity="1 plate",
        top_k=3,
    )
    assert result["dish_name"] == "chicken rice"
    assert result["search_strategy"].startswith("OR logic")
    assert "hainanese" in result["keywords_used"]
    assert result["matches"]
    top = result["matches"][0]
    assert top["source"] == "malaysian_food_calories"


def test_get_nutrition_service_is_singleton(four_source_corpus):
    a = nutrition_db.get_nutrition_service()
    b = nutrition_db.get_nutrition_service()
    assert a is b


def test_myfcd_row_carries_nested_nutrients(patch_corpus):
    nutrients = [
        _myfcd_nutrient(
            ndb_id="R101061",
            nutrient_name="Energy",
            value_per_100g=457.0,
            value_per_serving=60.0,
            unit="Kcal",
            category="Proximates",
        ),
        _myfcd_nutrient(
            ndb_id="R101061",
            nutrient_name="Protein",
            value_per_100g=8.3,
            value_per_serving=1.08,
            unit="g",
            category="Proximates",
        ),
        _myfcd_nutrient(
            ndb_id="R101061",
            nutrient_name="Fat",
            value_per_100g=17.4,
            value_per_serving=2.27,
            unit="g",
            category="Proximates",
        ),
    ]
    patch_corpus(
        foods_by_source={
            "myfcd": [
                _food_row(
                    source="myfcd",
                    source_food_id="R101061",
                    food_name="BISCUIT, COCONUT",
                    searchable_document="biscuit coconut",
                    serving_size_grams=13.02,
                    serving_unit="1 piece",
                )
            ]
        },
        myfcd_nutrients=nutrients,
    )
    svc = nutrition_db.NutritionCollectionService()
    food = svc.myfcd_foods[0]
    assert food["ndb_id"] == "R101061"
    assert food["serving_size_grams"] == pytest.approx(13.02)
    assert food["serving_unit"] == "1 piece"
    assert set(food["nutrients"].keys()) == {"Energy", "Protein", "Fat"}
    energy = food["nutrients"]["Energy"]
    assert energy["value_per_serving"] == pytest.approx(60.0)
    assert energy["value_per_100g"] == pytest.approx(457.0)
    assert energy["unit"] == "Kcal"


def test_normalize_text_strips_diacritics_and_punctuation():
    cases = [
        ("Chicken Rice", "chicken rice"),
        ("café — au lait", "cafe au lait"),
        ("ARROZ com FRANGO", "arroz com frango"),
        ("", ""),
        ("   ", ""),
    ]
    for raw, expected in cases:
        assert nutrition_db._normalize_text(raw) == expected
