"""
Background tasks for Phase 2 (Nutritional Analysis).

Error classification + persistence helpers live in `src.api._phase_errors`
and are shared with the Phase 1 background task in `src.api.item_step1_tasks`.
"""

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, List

from src.api._phase_errors import persist_phase_error
from src.crud.crud_food_image_query import (
    get_dish_image_query_by_id,
    update_dish_image_query_results,
)
from src.service import nutrition_lookup
from src.service.llm.gemini_analyzer import analyze_step2_nutritional_analysis_async
from src.service.llm.prompts import get_step2_nutritional_analysis_prompt
from src.service.nutrition_lookup import extract_and_lookup_nutrition
from src.service.personalized_lookup import lookup_personalization

logger = logging.getLogger(__name__)


def _persist_pre_pro_state(
    query_id: int,
    nutrition_db_matches: Dict[str, Any],
    personalized_matches: List[Dict[str, Any]],
) -> None:
    """
    Write both Stage 5 and Stage 6 pre-Pro keys in one update.

    Best-effort: if result_gemini is None (Phase 1 never landed), we skip
    the write and Stage 7 sees neither key for that query.
    """
    record = get_dish_image_query_by_id(query_id)
    if not record or record.result_gemini is None:
        logger.warning(
            "Phase 2 skipped pre-Pro persist for query_id=%s (no result_gemini)",
            query_id,
        )
        return
    pre_blob = dict(record.result_gemini)
    pre_blob["nutrition_db_matches"] = nutrition_db_matches
    pre_blob["personalized_matches"] = personalized_matches
    update_dish_image_query_results(query_id=query_id, result_openai=None, result_gemini=pre_blob)


def _safe_phase_2_1_result(result_or_exc: Any, dish_name: str, query_id: int) -> Dict[str, Any]:
    """Convert a gather exception into the Stage 5 empty-response shape."""
    if isinstance(result_or_exc, Exception):
        logger.warning(
            "Phase 2.1 raised inside gather for query_id=%s; substituting empty shape: %s",
            query_id,
            result_or_exc,
        )
        return nutrition_lookup._empty_response(  # pylint: disable=protected-access
            dish_name or "", reason="unexpected_exception"
        )
    return result_or_exc


def _safe_phase_2_2_result(result_or_exc: Any, query_id: int) -> List[Dict[str, Any]]:
    """Convert a gather exception into an empty personalization list."""
    if isinstance(result_or_exc, Exception):
        logger.warning(
            "Phase 2.2 raised inside gather for query_id=%s; substituting empty list: %s",
            query_id,
            result_or_exc,
        )
        return []
    return result_or_exc


async def _gather_pre_pro_lookups(
    query_id: int,
    dish_name: str,
    components: List[Dict[str, Any]],
):
    """
    Run Phase 2.1 and Phase 2.2 in parallel and convert any unexpected
    exceptions into their respective empty-shape fallbacks.

    Falls back to sequential Phase 2.1 only when we cannot resolve the
    user / reference description from the record (Phase 1 never landed).
    """
    record = get_dish_image_query_by_id(query_id)
    if not record or record.result_gemini is None:
        return extract_and_lookup_nutrition(dish_name, components), []

    user_id = record.user_id
    ref_description = (record.result_gemini.get("reference_image") or {}).get("description")

    nutrition_result, personalization_result = await asyncio.gather(
        asyncio.to_thread(extract_and_lookup_nutrition, dish_name, components),
        asyncio.to_thread(
            lookup_personalization,
            user_id,
            query_id,
            ref_description,
            dish_name,
        ),
        return_exceptions=True,
    )
    nutrition_db_matches = _safe_phase_2_1_result(nutrition_result, dish_name, query_id)
    personalized_matches = _safe_phase_2_2_result(personalization_result, query_id)
    return nutrition_db_matches, personalized_matches


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
        # Stage 5 Phase 2.1 (nutrition DB lookup) and Stage 6 Phase 2.2
        # (personalization lookup) run in parallel via asyncio.gather and
        # persist onto result_gemini BEFORE the Pro call so a Step 2 failure
        # cannot wipe either lookup. Each side is wrapped in to_thread
        # because both orchestrators are sync (BM25 + DB reads). Gather
        # uses return_exceptions=True so one side's failure does not kill
        # the other or the Pro call.
        nutrition_db_matches, personalized_matches = await _gather_pre_pro_lookups(
            query_id, dish_name, components
        )
        _persist_pre_pro_state(query_id, nutrition_db_matches, personalized_matches)

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
