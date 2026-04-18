"""
Background task for Phase 1 (Component Identification).

Lives in its own module so `backend/src/api/date.py` stays under the 300-line
file cap and so the Phase 1 + Phase 2 backgrounds tasks have parallel homes
(`item_step1_tasks.py` ↔ `item_tasks.py`).
"""

import logging
from datetime import datetime, timezone

from src.api._phase_errors import persist_phase_error
from src.crud.crud_food_image_query import (
    get_dish_image_query_by_id,
    update_dish_image_query_results,
)
from src.service.llm.gemini_analyzer import analyze_step1_component_identification_async
from src.service.llm.prompts import get_step1_component_identification_prompt

logger = logging.getLogger(__name__)


async def analyze_image_background(query_id: int, file_path: str, retry_count: int = 0) -> None:
    """
    Background task to analyze a meal image with Gemini (Step 1: Component Identification).

    On success: writes the full Phase 1 payload into result_gemini and clears
    any prior step1_error. On failure: classifies the exception and persists
    a step1_error block via the shared `persist_phase_error` helper.
    """
    logger.info(
        "Starting Step 1 background analysis for query %s (retry_count=%s)",
        query_id,
        retry_count,
    )

    try:
        step1_prompt = get_step1_component_identification_prompt()
        step1_result = await analyze_step1_component_identification_async(
            image_path=file_path,
            analysis_prompt=step1_prompt,
            gemini_model="gemini-2.5-pro",
            thinking_budget=-1,
        )

        # Preserve any prior fields (e.g., from a partial earlier state); replace
        # step1_data, clear step1_error.
        record = get_dish_image_query_by_id(query_id)
        base = (record.result_gemini or {}).copy() if record else {}

        base.update(
            {
                "step": 1,
                "step1_data": step1_result,
                "step2_data": base.get("step2_data"),
                "step1_confirmed": base.get("step1_confirmed", False),
                "iterations": [
                    {
                        "iteration_number": 1,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "step": 1,
                        "step1_data": step1_result,
                        "step2_data": None,
                        "metadata": {},
                    }
                ],
                "current_iteration": 1,
            }
        )
        base.pop("step1_error", None)

        update_dish_image_query_results(query_id=query_id, result_openai=None, result_gemini=base)
        logger.info("Query %s Step 1 completed successfully", query_id)

    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.error("Failed Phase 1 for query %s: %s", query_id, exc, exc_info=True)
        persist_phase_error(query_id, exc, retry_count, "step1_error")
