"""
Phase 2.3 prompt-block renderers for the Nutrition Analysis Gemini call.

Trimmed JSON payloads — only the fields the prompt needs — keep the
outbound Gemini prompt readable in backend.log and reduce token cost.
Returns empty string when the block's gate fails so the caller's
placeholder-strip regex removes the line cleanly.

Static prose for each block lives under
`backend/resources/prompts/blocks/` (`nutrition_db_block.md` and
`personalized_block.md`); this module loads those templates and
substitutes the trimmed JSON payload at the `{{PAYLOAD_JSON}}` slot.
"""

import json
from typing import Any, Dict, List, Optional

from src.configs import RESOURCE_DIR, THRESHOLD_DB_INCLUDE, THRESHOLD_PERSONALIZATION_INCLUDE
from src.service._nutrition_aggregation import extract_single_match_nutrition


TOP_K = 5

_BLOCKS_DIR = RESOURCE_DIR / "prompts" / "blocks"
_PAYLOAD_PLACEHOLDER = "{{PAYLOAD_JSON}}"


def _load_block_template(filename: str) -> str:
    """Load a prompt-block template from `backend/resources/prompts/blocks/`."""
    path = _BLOCKS_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Prompt block template not found: {path}")
    # rstrip trailing newlines only — preserve all internal whitespace.
    return path.read_text(encoding="utf-8").rstrip("\n")


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


def _trim_prior_nutrition(
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
        # For corrected_nutrition_data only — keep the user's rationale so Pro
        # can read their intent alongside the numbers.
        trimmed["healthiness_score_rationale"] = prior.get("healthiness_score_rationale")
    return trimmed


def _trim_personalization_match(match: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "description": match.get("description"),
        "similarity_score": match.get("similarity_score"),
        "prior_nutrition_data": _trim_prior_nutrition(match.get("prior_nutrition_data")),
        "corrected_nutrition_data": _trim_prior_nutrition(
            match.get("corrected_nutrition_data"), include_user_context=True
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
    template = _load_block_template("nutrition_db_block.md")
    return template.replace(_PAYLOAD_PLACEHOLDER, payload)


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
    template = _load_block_template("personalized_block.md")
    return template.replace(_PAYLOAD_PLACEHOLDER, payload)
