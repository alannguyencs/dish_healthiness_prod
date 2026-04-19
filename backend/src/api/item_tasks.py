"""
Background tasks for Phase 2 (Nutritional Analysis).

Error classification + persistence helpers live in `src.api._phase_errors`
and are shared with the Phase 1 background task in `src.api.item_step1_tasks`.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List

from src.api._phase_errors import persist_phase_error
from src.crud.crud_food_image_query import (
    get_dish_image_query_by_id,
    update_dish_image_query_results,
)
from src.service.llm.gemini_analyzer import analyze_step2_nutritional_analysis_async
from src.service.llm.prompts import get_step2_nutritional_analysis_prompt
from src.service.nutrition_lookup import extract_and_lookup_nutrition

logger = logging.getLogger(__name__)


def _persist_nutrition_db_matches(query_id: int, nutrition_db_matches: Dict[str, Any]) -> None:
    """
    Stage 5: write `nutrition_db_matches` onto result_gemini BEFORE the
    Gemini Pro call, so a Step 2 failure cannot destroy the lookup.

    Best-effort: if the record read races with a concurrent write or
    result_gemini is None (Phase 1 never landed), we simply skip the
    write and Stage 7 sees no nutrition_db_matches for that query.
    """
    record = get_dish_image_query_by_id(query_id)
    if not record or record.result_gemini is None:
        logger.warning(
            "Phase 2.1 skipped pre-Pro persist for query_id=%s (no result_gemini)",
            query_id,
        )
        return
    pre_blob = dict(record.result_gemini)
    pre_blob["nutrition_db_matches"] = nutrition_db_matches
    update_dish_image_query_results(query_id=query_id, result_openai=None, result_gemini=pre_blob)


async def trigger_step2_analysis_background(
    query_id: int,
    image_path: Path,
    dish_name: str,
    components: List[Dict[str, Any]],
    retry_count: int = 0,
):
    """
    Background task to run Step 2 nutritional analysis.

    Args:
        query_id: ID of the DishImageQuery to update
        image_path: Path to the image file
        dish_name: User-confirmed dish name
        components: List of confirmed components with serving sizes
        retry_count: How many times this query has been retried (0 on first run)
    """
    logger.info(
        "Starting Step 2 background analysis for query %s (retry_count=%s)",
        query_id,
        retry_count,
    )

    try:
        # Stage 5 — Phase 2.1 nutrition DB lookup. Runs synchronously before
        # the Pro call (in-process BM25, <50 ms once the singleton is warm)
        # and is persisted first so a Step 2 failure cannot wipe it.
        nutrition_db_matches = extract_and_lookup_nutrition(dish_name, components)
        _persist_nutrition_db_matches(query_id, nutrition_db_matches)

        step2_prompt = get_step2_nutritional_analysis_prompt(
            dish_name=dish_name, components=components
        )

        step2_result = await analyze_step2_nutritional_analysis_async(
            image_path=image_path,
            analysis_prompt=step2_prompt,
            gemini_model="gemini-2.5-pro",
            thinking_budget=-1,
        )

        query_record = get_dish_image_query_by_id(query_id)
        if not query_record or not query_record.result_gemini:
            logger.error("Query %s not found or missing result_gemini", query_id)
            return

        result_gemini = query_record.result_gemini.copy()
        result_gemini["step"] = 2
        result_gemini["step2_data"] = step2_result
        result_gemini["step1_confirmed"] = True
        # Clear any prior error now that we have a successful result.
        result_gemini.pop("step2_error", None)

        if "iterations" in result_gemini and len(result_gemini["iterations"]) > 0:
            current_iter_idx = result_gemini.get("current_iteration", 1) - 1
            if 0 <= current_iter_idx < len(result_gemini["iterations"]):
                result_gemini["iterations"][current_iter_idx]["step"] = 2
                result_gemini["iterations"][current_iter_idx]["step2_data"] = step2_result
                result_gemini["iterations"][current_iter_idx]["metadata"][
                    "confirmed_dish_name"
                ] = dish_name
                result_gemini["iterations"][current_iter_idx]["metadata"][
                    "confirmed_components"
                ] = components

        update_dish_image_query_results(
            query_id=query_id, result_openai=None, result_gemini=result_gemini
        )
        logger.info("Query %s Step 2 completed successfully", query_id)

    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.error("Failed Step 2 analysis for query %s: %s", query_id, exc, exc_info=True)
        persist_phase_error(query_id, exc, retry_count, "step2_error")
