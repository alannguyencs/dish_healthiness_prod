"""
Background tasks for item API endpoints.

This module contains async background task functions for Step 2 analysis,
plus helpers that classify and persist Step 2 failures into result_gemini.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any

from src.crud.crud_food_image_query import (
    get_dish_image_query_by_id,
    update_dish_image_query_results,
)
from src.service.llm.gemini_analyzer import analyze_step2_nutritional_analysis_async
from src.service.llm.prompts import get_step2_nutritional_analysis_prompt

logger = logging.getLogger(__name__)


# Error classification buckets surfaced to the frontend via result_gemini.step2_error.
ERROR_USER_MESSAGE = {
    "config_error": (
        "An internal configuration issue is preventing analysis. Please try again later."
    ),
    "image_missing": "The dish image is no longer available. Please re-upload the meal.",
    "parse_error": ("The AI response could not be parsed. Try again — this is usually transient."),
    "api_error": "The nutrition service is temporarily unavailable. Try again in a moment.",
    "unknown": "Something went wrong while calculating nutrition. Try again.",
}


def _classify_step2_error(exc: Exception) -> str:
    """Bucket an exception into one of the error_type values used in step2_error."""
    msg = str(exc).lower()
    if "gemini_api_key" in msg or "api key" in msg:
        return "config_error"
    if "filenotfound" in msg or ("image" in msg and "not found" in msg):
        return "image_missing"
    if "parse" in msg or "validation" in msg or "schema" in msg:
        return "parse_error"
    if any(token in msg for token in ("503", "429", "timeout", "connection")):
        return "api_error"
    return "unknown"


def _persist_step2_error(query_id: int, exc: Exception, retry_count: int) -> None:
    """Write a step2_error block into result_gemini for the given query."""
    record = get_dish_image_query_by_id(query_id)
    if not record or not record.result_gemini:
        return

    error_type = _classify_step2_error(exc)
    result_gemini = record.result_gemini.copy()
    result_gemini["step2_error"] = {
        "error_type": error_type,
        "message": ERROR_USER_MESSAGE[error_type],
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "retry_count": retry_count,
    }
    update_dish_image_query_results(
        query_id=query_id, result_openai=None, result_gemini=result_gemini
    )


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
        # Get Step 2 prompt with confirmed data
        step2_prompt = get_step2_nutritional_analysis_prompt(
            dish_name=dish_name, components=components
        )

        # Run Step 2: Nutritional Analysis
        step2_result = await analyze_step2_nutritional_analysis_async(
            image_path=image_path,
            analysis_prompt=step2_prompt,
            gemini_model="gemini-2.5-pro",
            thinking_budget=-1,
        )

        # Get current query record
        query_record = get_dish_image_query_by_id(query_id)
        if not query_record or not query_record.result_gemini:
            logger.error("Query %s not found or missing result_gemini", query_id)
            return

        # Update result_gemini with Step 2 data
        result_gemini = query_record.result_gemini.copy()
        result_gemini["step"] = 2
        result_gemini["step2_data"] = step2_result
        result_gemini["step1_confirmed"] = True
        # Clear any prior error now that we have a successful result.
        result_gemini.pop("step2_error", None)

        # Add/update current iteration with Step 2 data
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

        # Update the query with Step 2 result
        update_dish_image_query_results(
            query_id=query_id, result_openai=None, result_gemini=result_gemini
        )
        logger.info("Query %s Step 2 completed successfully", query_id)

    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.error("Failed Step 2 analysis for query %s: %s", query_id, exc, exc_info=True)
        _persist_step2_error(query_id, exc, retry_count)
