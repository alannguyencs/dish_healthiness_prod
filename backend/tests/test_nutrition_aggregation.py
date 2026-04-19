"""
Tests for backend/src/service/_nutrition_aggregation.py.

Pure unit tests — no DB, no network. Each function is exercised against
hand-crafted match dicts in the same shape `direct_bm25_search` produces.
"""

# pylint: disable=missing-class-docstring,missing-function-docstring
# pylint: disable=redefined-outer-name,unused-argument

import pytest

from src.service import _nutrition_aggregation as agg


def _match(
    name,
    source,
    confidence,
    *,
    nutrition_data=None,
    raw_bm25_score=1.0,
):
    return {
        "matched_food_name": name,
        "source": source,
        "confidence": confidence,
        "confidence_score": round(confidence * 100, 1),
        "nutrition_data": nutrition_data or {},
        "raw_bm25_score": raw_bm25_score,
        "matched_keywords": 1,
        "total_keywords": 1,
        "search_method": "Direct BM25",
    }


def test_deduplicate_matches_keeps_highest_confidence():
    matches = [
        _match("Chicken Rice", "myfcd", 0.75),
        _match("Chicken Rice", "anuvaad", 0.85),
        _match("Chicken Rice", "malaysian_food_calories", 0.65),
    ]
    result = agg.deduplicate_matches(matches)
    assert len(result) == 1
    assert result[0]["confidence"] == pytest.approx(0.85)
    assert result[0]["source"] == "anuvaad"


def test_deduplicate_matches_uses_bm25_as_tiebreaker():
    matches = [
        _match("Pho Bo", "myfcd", 0.75, raw_bm25_score=2.0),
        _match("Pho Bo", "anuvaad", 0.75, raw_bm25_score=5.0),
    ]
    result = agg.deduplicate_matches(matches)
    assert result[0]["raw_bm25_score"] == pytest.approx(5.0)


def test_extract_single_match_nutrition_malaysian():
    match = _match(
        "Nasi Lemak",
        "malaysian_food_calories",
        0.9,
        nutrition_data={"calories": 450},
    )
    out = agg.extract_single_match_nutrition(match)
    assert out["total_calories"] == pytest.approx(450)
    assert out["total_protein_g"] == 0
    assert out["foods_included"] == ["Nasi Lemak"]


def test_extract_single_match_nutrition_myfcd():
    nutrients = {
        "Energy": {"value_per_serving": 320},
        "Protein": {"value_per_serving": 18.5},
        "Carbohydrate": {"value_per_serving": 45.2},
        "Fat": {"value_per_serving": 10.3},
    }
    match = _match(
        "Chicken Rice",
        "myfcd",
        0.9,
        nutrition_data={"nutrients": nutrients},
    )
    out = agg.extract_single_match_nutrition(match)
    assert out["total_calories"] == pytest.approx(320)
    assert out["total_protein_g"] == pytest.approx(18.5)
    assert out["total_carbohydrates_g"] == pytest.approx(45.2)
    assert out["total_fat_g"] == pytest.approx(10.3)


def test_extract_single_match_nutrition_anuvaad_applies_serving_scale():
    match = _match(
        "Dal Tadka",
        "anuvaad",
        0.9,
        nutrition_data={
            "energy_kcal": 200,
            "protein_g": 8,
            "carb_g": 20,
            "fat_g": 6,
        },
    )
    out = agg.extract_single_match_nutrition(match)
    # 1.5 x scale
    assert out["total_calories"] == pytest.approx(300)
    assert out["total_protein_g"] == pytest.approx(12)
    assert out["total_carbohydrates_g"] == pytest.approx(30)
    assert out["total_fat_g"] == pytest.approx(9)


def test_extract_single_match_nutrition_ciqual_reads_per_100g_fields():
    match = _match(
        "Quiche Lorraine",
        "ciqual",
        0.9,
        nutrition_data={
            "Energy, Regulation EU No 1169/2011 (kcal/100g)": 280,
            "Protein (g/100g)": 10,
            "Carbohydrate (g/100g)": 15,
            "Fat (g/100g)": 20,
        },
    )
    out = agg.extract_single_match_nutrition(match)
    # No scale applied for CIQUAL
    assert out["total_calories"] == pytest.approx(280)
    assert out["total_protein_g"] == pytest.approx(10)
    assert out["total_carbohydrates_g"] == pytest.approx(15)
    assert out["total_fat_g"] == pytest.approx(20)


def test_aggregate_nutrition_sums_across_sources():
    matches = [
        _match(
            "Chicken Rice",
            "myfcd",
            0.8,
            nutrition_data={"nutrients": {"Energy": {"value_per_serving": 300}}},
        ),
        _match(
            "Nasi Lemak",
            "malaysian_food_calories",
            0.7,
            nutrition_data={"calories": 400},
        ),
    ]
    out = agg.aggregate_nutrition(matches)
    assert out["total_calories"] == pytest.approx(700)
    assert "Chicken Rice" in out["foods_included"]
    assert "Nasi Lemak" in out["foods_included"]


def test_calculate_optimal_nutrition_uses_single_match_when_top_is_high_confidence():
    matches = [
        _match(
            "Pad Thai",
            "myfcd",
            0.93,
            nutrition_data={"nutrients": {"Energy": {"value_per_serving": 500}}},
        ),
        _match(
            "Other Dish",
            "myfcd",
            0.6,
            nutrition_data={"nutrients": {"Energy": {"value_per_serving": 200}}},
        ),
    ]
    out = agg.calculate_optimal_nutrition(matches)
    assert out["foods_included"] == ["Pad Thai"]
    assert out["aggregation_strategy"] == "single_high_confidence_match"
    assert out["best_match_confidence"] == pytest.approx(0.93)


def test_calculate_optimal_nutrition_falls_back_to_aggregate():
    matches = [
        _match(
            "Chicken Rice",
            "myfcd",
            0.85,
            nutrition_data={"nutrients": {"Energy": {"value_per_serving": 300}}},
        ),
        _match(
            "Nasi Lemak",
            "malaysian_food_calories",
            0.7,
            nutrition_data={"calories": 400},
        ),
    ]
    out = agg.calculate_optimal_nutrition(matches)
    assert out["aggregation_strategy"] == "multiple_items_aggregated"
    assert out["total_calories"] == pytest.approx(700)


def test_generate_recommendations_high_calorie():
    out = agg.generate_recommendations(
        {"total_calories": 1000, "total_protein_g": 30, "total_carbohydrates_g": 100}
    )
    assert any("high-calorie" in r for r in out)


def test_generate_recommendations_low_calorie():
    out = agg.generate_recommendations(
        {"total_calories": 100, "total_protein_g": 5, "total_carbohydrates_g": 10}
    )
    assert any("light meal" in r for r in out)


def test_generate_recommendations_low_protein_ratio():
    out = agg.generate_recommendations(
        {"total_calories": 500, "total_protein_g": 5, "total_carbohydrates_g": 100}
    )
    assert any("protein" in r.lower() for r in out)


def test_generate_recommendations_fallback_default():
    out = agg.generate_recommendations(
        {
            "total_calories": 500,
            "total_protein_g": 30,
            "total_carbohydrates_g": 50,
            "foods_included": ["A", "B", "C"],
        }
    )
    assert any("balanced" in r.lower() for r in out)
