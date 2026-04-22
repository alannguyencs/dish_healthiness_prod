"""
Phase 2.4 AI Assistant Edit revision service.

Loads the current effective Step 2 payload from `result_gemini` (prefers
`nutrition_corrected` when present, falls back to `nutrition_data`), builds a
revision prompt from `backend/resources/prompts/nutrition_assistant_correction.md`
with the trimmed baseline JSON + user hint substituted, and calls Gemini
2.5 Pro with the query image attached. Returns the revised
`NutritionalAnalysis` payload.

Persistence is the endpoint's job — this service only produces the
revised numbers. Mirrors the Phase 2.3 Gemini wrapper pattern so retries,
thinking budget, and response schema stay consistent across Phase 2.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict

from src.configs import IMAGE_DIR, RESOURCE_DIR
from src.crud.crud_food_image_query import get_dish_image_query_by_id
from src.service.llm.nutrition_analyzer import analyze_nutritional_analysis_async

logger = logging.getLogger(__name__)

_BASELINE_PLACEHOLDER = "{{BASELINE_JSON}}"
_HINT_PLACEHOLDER = "{{USER_HINT}}"

_TRIMMED_FIELDS = (
    "dish_name",
    "healthiness_score",
    "healthiness_score_rationale",
    "calories_kcal",
    "fiber_g",
    "carbs_g",
    "protein_g",
    "fat_g",
    "micronutrients",
    "reasoning_sources",
    "reasoning_calories",
    "reasoning_protein",
    "reasoning_carbs",
    "reasoning_fat",
    "reasoning_fiber",
    "reasoning_micronutrients",
)


def _trim_baseline_for_prompt(baseline: Dict[str, Any]) -> Dict[str, Any]:
    """
    Keep only the semantic fields the prompt needs. Drops engineering
    metadata (model, price_usd, analysis_time, input_token, output_token)
    and the audit-only `ai_assistant_prompt` field so the LLM is not
    confused by a prior hint when producing the new revision.
    """
    return {k: baseline[k] for k in _TRIMMED_FIELDS if k in baseline}


def _render_assistant_prompt(trimmed_baseline: Dict[str, Any], user_hint: str) -> str:
    prompt_path = RESOURCE_DIR / "prompts" / "nutrition_assistant_correction.md"
    if not prompt_path.exists():
        raise FileNotFoundError(f"AI Assistant Edit prompt template not found: {prompt_path}")

    with open(prompt_path, "r", encoding="utf-8") as handle:
        template = handle.read()

    baseline_json = json.dumps(trimmed_baseline, indent=2, default=str)
    return template.replace(_BASELINE_PLACEHOLDER, baseline_json).replace(
        _HINT_PLACEHOLDER, user_hint
    )


async def revise_nutrition_with_hint(record_id: int, user_hint: str) -> Dict[str, Any]:
    """
    Produce a revised `NutritionalAnalysis` payload for the given
    record, driven by the user's free-text hint.

    Baseline selection: current effective payload — `nutrition_corrected` if
    present, else `nutrition_data`. Stacked edits are supported by design.

    Multi-modal: the query image is attached so Gemini can cross-check
    the hint against what is actually visible on the plate.
    """
    record = get_dish_image_query_by_id(record_id)
    if not record or not record.result_gemini:
        raise ValueError(f"Record {record_id} has no result_gemini payload")

    result_gemini = record.result_gemini
    baseline = result_gemini.get("nutrition_corrected") or result_gemini.get("nutrition_data")
    if not baseline:
        raise ValueError(
            f"Record {record_id} has no nutrition_data/nutrition_corrected baseline to revise"
        )

    image_url = record.image_url
    if not image_url:
        raise ValueError(f"Record {record_id} has no image_url")

    image_path = IMAGE_DIR / Path(image_url).name
    if not image_path.exists():
        raise FileNotFoundError(f"Query image missing on disk: {image_path}")

    trimmed = _trim_baseline_for_prompt(baseline)
    prompt = _render_assistant_prompt(trimmed, user_hint)

    logger.info(
        "AI Assistant Edit: revising record_id=%s (baseline source=%s, hint_len=%s)",
        record_id,
        "nutrition_corrected" if result_gemini.get("nutrition_corrected") else "nutrition_data",
        len(user_hint),
    )

    return await analyze_nutritional_analysis_async(
        image_path=image_path,
        analysis_prompt=prompt,
        gemini_model="gemini-2.5-pro",
        thinking_budget=-1,
    )
