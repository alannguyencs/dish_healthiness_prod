"""
Stage 7 prompt-block renderers for the Step 2 Gemini call.

Trimmed JSON payloads — only the fields the prompt needs — keep the
outbound Gemini prompt readable in backend.log and reduce token cost.
Returns empty string when the block's gate fails so the caller's
placeholder-strip regex removes the line cleanly.
"""

import json
from typing import Any, Dict, List, Optional

from src.configs import THRESHOLD_DB_INCLUDE, THRESHOLD_PERSONALIZATION_INCLUDE
from src.service._nutrition_aggregation import extract_single_match_nutrition


TOP_K = 5


def _trim_db_match(match: Dict[str, Any]) -> Dict[str, Any]:
    """Keep only the fields the prompt needs; compute source-aware macros."""
    macros = extract_single_match_nutrition(match)
    return {
        "matched_food_name": match.get("matched_food_name"),
        "source": match.get("source"),
        "confidence_score": match.get("confidence_score"),
        "calories_kcal": macros["total_calories"],
        "protein_g": macros["total_protein_g"],
        "carbs_g": macros["total_carbohydrates_g"],
        "fat_g": macros["total_fat_g"],
        "fiber_g": 0,
    }


def _trim_prior_step2(
    prior: Optional[Dict[str, Any]],
    *,
    include_user_context: bool = False,
) -> Optional[Dict[str, Any]]:
    if not prior:
        return None
    trimmed: Dict[str, Any] = {
        "calories_kcal": prior.get("calories_kcal"),
        "protein_g": prior.get("protein_g"),
        "carbs_g": prior.get("carbs_g"),
        "fat_g": prior.get("fat_g"),
        "fiber_g": prior.get("fiber_g"),
        "micronutrients": prior.get("micronutrients"),
    }
    if include_user_context:
        # For corrected_step2_data only — keep the user's rationale so Pro
        # can read their intent alongside the numbers.
        trimmed["healthiness_score_rationale"] = prior.get("healthiness_score_rationale")
    return trimmed


def _trim_personalization_match(match: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "description": match.get("description"),
        "similarity_score": match.get("similarity_score"),
        "prior_step2_data": _trim_prior_step2(match.get("prior_step2_data")),
        "corrected_step2_data": _trim_prior_step2(
            match.get("corrected_step2_data"), include_user_context=True
        ),
    }


def render_nutrition_db_block(nutrition_db_matches: Optional[Dict[str, Any]]) -> str:
    """
    Render the DB block when gate passes, else return "" so the caller's
    strip regex removes the placeholder line.

    Gate: top match's `confidence_score` >= THRESHOLD_DB_INCLUDE (80).
    """
    if not nutrition_db_matches:
        return ""
    matches = nutrition_db_matches.get("nutrition_matches") or []
    if not matches:
        return ""
    top_confidence = matches[0].get("confidence_score") or 0
    if top_confidence < THRESHOLD_DB_INCLUDE:
        return ""

    trimmed = [_trim_db_match(m) for m in matches[:TOP_K]]
    payload = json.dumps(trimmed, indent=2, default=str)
    return (
        "## Nutrition Database Matches (top 5, with confidence_score)\n"
        "\n"
        "The following matches were retrieved from a curated nutrition database "
        "(Malaysian / MyFCD / Anuvaad / CIQUAL). Treat them as strong evidence "
        "for `reasoning_*` citations when they align with the query image's "
        "dish. Use them to calibrate your macro estimates; do not copy blindly.\n"
        "\n"
        "```json\n"
        f"{payload}\n"
        "```"
    )


def render_personalized_block(
    personalized_matches: Optional[List[Dict[str, Any]]],
) -> str:
    """
    Render the personalization block when gate passes, else return "".

    Gate: top match's `similarity_score` >= THRESHOLD_PERSONALIZATION_INCLUDE (0.30).
    """
    if not personalized_matches:
        return ""
    top_similarity = personalized_matches[0].get("similarity_score") or 0.0
    if top_similarity < THRESHOLD_PERSONALIZATION_INCLUDE:
        return ""

    trimmed = [_trim_personalization_match(m) for m in personalized_matches[:TOP_K]]
    payload = json.dumps(trimmed, indent=2, default=str)
    return (
        "## Personalization Matches (top 5, this user's prior dishes)\n"
        "\n"
        "The following are previous uploads by the same user whose caption or "
        "confirmed dish name overlaps this query. Treat `prior_step2_data` as "
        "weaker evidence than the Nutrition Database above — the user's prior "
        "analysis may itself have been uncertain.\n"
        "\n"
        "**When `corrected_step2_data` is present, it is the user's "
        "hand-corrected nutrients — treat it as AUTHORITATIVE for the query "
        "image's dish.** Specifically:\n"
        "\n"
        "1. Derive the user's per-portion profile by dividing the corrected "
        "macros by the number of servings you estimate from the **user's** "
        "prior image (look at the match's `description` for context). Apply "
        "that per-portion profile to your estimate of the current image's "
        "portion count.\n"
        "2. Preserve the user's `micronutrients` list verbatim unless the "
        "query image clearly shows different ingredients. If the user added "
        "a nutrient (e.g. Vitamin D) you do not recognize from the photo, "
        "keep it anyway — the user likely has context you cannot see.\n"
        "3. If the user's `healthiness_score_rationale` reflects a durable "
        "preference (portion size, cooking method, ingredient swap), echo "
        "that reasoning in your own `healthiness_score_rationale` rather "
        "than describing the photo generically.\n"
        "4. Cite the correction explicitly in `reasoning_sources` using the "
        'phrase "user-corrected" so downstream reviewers can tell.\n'
        "\n"
        "```json\n"
        f"{payload}\n"
        "```"
    )
