"""
Nutrition aggregation helpers for Phase 2.1 (Stage 5).

Ported from reference project `collect_from_nutrition_db.py`. Kept in a
sibling module to `_nutrition_scoring.py` so `nutrition_db.py` stays focused
on retrieval. All public functions are module-level — no class — so callers
(`NutritionCollectionService.collect_from_nutrition_db`, plus any future
consumers) can import what they need.

Per-source nutrition extraction shapes:
  - malaysian_food_calories: `nutrition_data.calories` per-serving
  - myfcd: `nutrients.{Energy,Protein,Carbohydrate,Fat}.value_per_serving`
  - anuvaad: `energy_kcal / protein_g / carb_g / fat_g` scaled x 1.5
    (reference's 150 g-serving assumption)
  - ciqual: per-100 g macros read from the source's verbatim column names
    (no serving scale; Stage 7 prompt will reconcile servings)
"""

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


_HIGH_CONFIDENCE_THRESHOLD = 0.90
_ANUVAAD_SERVING_SCALE = 1.5

_CIQUAL_CALORIES_KEY = "Energy, Regulation EU No 1169/2011 (kcal/100g)"
_CIQUAL_PROTEIN_KEY = "Protein (g/100g)"
_CIQUAL_CARBS_KEY = "Carbohydrate (g/100g)"
_CIQUAL_FAT_KEY = "Fat (g/100g)"


def deduplicate_matches(matches: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Drop duplicate matches by `matched_food_name`, keeping the highest
    confidence. BM25 raw score breaks ties.
    """
    seen: Dict[str, Dict[str, Any]] = {}
    for match in matches:
        food_name = match["matched_food_name"]
        existing = seen.get(food_name)
        if (
            not existing
            or match["confidence"] > existing["confidence"]
            or (
                match["confidence"] == existing["confidence"]
                and match.get("raw_bm25_score", 0) > existing.get("raw_bm25_score", 0)
            )
        ):
            seen[food_name] = match
    return list(seen.values())


def _coerce_numeric(value: Any) -> float:
    """Return a non-negative float, or 0.0 when `value` isn't numeric."""
    if isinstance(value, (int, float)) and value > 0:
        return float(value)
    return 0.0


def _extract_myfcd_nutrient(nutrients: Dict[str, Any], key: str) -> float:
    entry = nutrients.get(key) or {}
    value = entry.get("value_per_serving")
    return _coerce_numeric(value)


def extract_single_match_nutrition(match: Dict[str, Any]) -> Dict[str, Any]:
    """
    Pull macros for a single match, source-aware. Returns the shape
    Stage 7's prompt consumes (`total_calories`, `total_protein_g`,
    `total_carbohydrates_g`, `total_fat_g`, `foods_included`, `disclaimer`).
    """
    nutrition_data = match.get("nutrition_data") or {}
    source = match.get("source")
    food_name = match["matched_food_name"]

    calories = proteins = carbs = fats = 0.0

    if source == "malaysian_food_calories":
        calories = _coerce_numeric(nutrition_data.get("calories"))

    elif source == "myfcd":
        nutrients = nutrition_data.get("nutrients") or {}
        calories = _extract_myfcd_nutrient(nutrients, "Energy")
        proteins = _extract_myfcd_nutrient(nutrients, "Protein")
        carbs = _extract_myfcd_nutrient(nutrients, "Carbohydrate")
        fats = _extract_myfcd_nutrient(nutrients, "Fat")

    elif source == "anuvaad":
        calories = _coerce_numeric(nutrition_data.get("energy_kcal")) * _ANUVAAD_SERVING_SCALE
        proteins = _coerce_numeric(nutrition_data.get("protein_g")) * _ANUVAAD_SERVING_SCALE
        carbs = _coerce_numeric(nutrition_data.get("carb_g")) * _ANUVAAD_SERVING_SCALE
        fats = _coerce_numeric(nutrition_data.get("fat_g")) * _ANUVAAD_SERVING_SCALE

    elif source == "ciqual":
        calories = _coerce_numeric(nutrition_data.get(_CIQUAL_CALORIES_KEY))
        proteins = _coerce_numeric(nutrition_data.get(_CIQUAL_PROTEIN_KEY))
        carbs = _coerce_numeric(nutrition_data.get(_CIQUAL_CARBS_KEY))
        fats = _coerce_numeric(nutrition_data.get(_CIQUAL_FAT_KEY))

    return {
        "total_calories": round(calories, 2),
        "total_protein_g": round(proteins, 2),
        "total_carbohydrates_g": round(carbs, 2),
        "total_fat_g": round(fats, 2),
        "foods_included": [food_name],
        "disclaimer": (
            f"Nutritional values for {food_name} based on high-confidence "
            f"database match ({source}). Values scaled to typical serving size."
        ),
    }


def aggregate_nutrition(matches: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Sum macros across `matches`, source-aware."""
    if not matches:
        return {}

    total_calories = total_proteins = total_carbs = total_fats = 0.0
    foods_counted: List[str] = []

    for match in matches:
        contribution = extract_single_match_nutrition(match)
        if (
            contribution["total_calories"]
            or contribution["total_protein_g"]
            or contribution["total_carbohydrates_g"]
            or contribution["total_fat_g"]
        ):
            total_calories += contribution["total_calories"]
            total_proteins += contribution["total_protein_g"]
            total_carbs += contribution["total_carbohydrates_g"]
            total_fats += contribution["total_fat_g"]
            foods_counted.append(match["matched_food_name"])

    return {
        "total_calories": round(total_calories, 2),
        "total_protein_g": round(total_proteins, 2),
        "total_carbohydrates_g": round(total_carbs, 2),
        "total_fat_g": round(total_fats, 2),
        "foods_included": foods_counted,
        "disclaimer": ("Nutritional values are approximate and based on standard serving sizes"),
    }


def calculate_optimal_nutrition(matches: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Prefer the top match's nutrition when it is a high-confidence exact
    match (>= 0.90 AND more than one candidate). Otherwise aggregate.
    """
    if not matches:
        return {}

    best_match = matches[0]
    if best_match["confidence"] >= _HIGH_CONFIDENCE_THRESHOLD and len(matches) > 1:
        single = extract_single_match_nutrition(best_match)
        single["aggregation_strategy"] = "single_high_confidence_match"
        single["best_match_confidence"] = best_match["confidence"]
        single["total_matches_available"] = len(matches)
        return single

    aggregated = aggregate_nutrition(matches)
    aggregated["aggregation_strategy"] = "multiple_items_aggregated"
    aggregated["best_match_confidence"] = best_match["confidence"]
    return aggregated


def generate_recommendations(nutrition_data: Dict[str, Any]) -> List[str]:
    """Deterministic tips from calorie + macro thresholds."""
    if not nutrition_data:
        return ["Consider adding more nutritious foods to your meal"]

    total_calories = nutrition_data.get("total_calories", 0)
    total_protein = nutrition_data.get("total_protein_g", 0)
    total_carbs = nutrition_data.get("total_carbohydrates_g", 0)
    foods_included = nutrition_data.get("foods_included", [])

    recommendations: List[str] = []

    if total_calories > 800:
        recommendations.append(
            "This is a high-calorie meal. Consider balancing with lighter "
            "meals throughout the day."
        )
    elif total_calories < 200:
        recommendations.append(
            "This is a light meal. Consider adding protein or healthy fats for better satiety."
        )

    if total_protein > 0 and total_carbs > 0:
        protein_ratio = total_protein / (total_protein + total_carbs)
        if protein_ratio < 0.2:
            recommendations.append(
                "Consider adding more protein sources for better muscle health and satiety."
            )

    if len(foods_included) == 1:
        recommendations.append("Try to include a variety of foods for better nutritional balance.")

    if not recommendations:
        recommendations.append("Maintain a balanced diet with variety in your food choices.")

    return recommendations
