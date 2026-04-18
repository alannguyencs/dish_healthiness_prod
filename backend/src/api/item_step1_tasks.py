"""
Background task for Phase 1 (Component Identification).

Lives in its own module so `backend/src/api/date.py` stays under the 300-line
file cap and so the Phase 1 + Phase 2 backgrounds tasks have parallel homes
(`item_step1_tasks.py` ↔ `item_tasks.py`).
"""

import logging
from datetime import datetime, timezone

from src.api._phase_errors import persist_phase_error
from src.crud import crud_personalized_food
from src.crud.crud_food_image_query import (
    get_dish_image_query_by_id,
    update_dish_image_query_results,
)
from src.service.llm.gemini_analyzer import analyze_step1_component_identification_async
from src.service.llm.prompts import get_step1_component_identification_prompt
from src.service.personalized_reference import resolve_reference_for_upload

logger = logging.getLogger(__name__)


async def analyze_image_background(query_id: int, file_path: str, retry_count: int = 0) -> None:
    """
    Background task to analyze a meal image with Gemini (Step 1: Component Identification).

    Runs Phase 1.1.1 (fast-caption + personalized reference retrieval) first
    and persists `result_gemini.reference_image` before invoking Phase 1.1.2
    (the Step 1 Pro call). The two phases persist independently so a
    Phase 1.1.2 failure does not destroy Phase 1.1.1's output, and a
    retry short-circuit does not overwrite a prior attempt's reference.
    """
    logger.info(
        "Starting Step 1 background analysis for query %s (retry_count=%s)",
        query_id,
        retry_count,
    )

    # Phase 1.1.1 — fast caption + personalized reference retrieval.
    record_pre = get_dish_image_query_by_id(query_id)
    user_id = record_pre.user_id if record_pre else None

    # Capture retry state before invoking the orchestrator: if a personalization
    # row already exists for this query_id we are on a retry and must NOT
    # overwrite whatever reference_image a prior run already persisted.
    is_retry_short_circuit = (
        user_id is not None and crud_personalized_food.get_row_by_query_id(query_id) is not None
    )

    if user_id is not None and not is_retry_short_circuit:
        reference = await resolve_reference_for_upload(
            user_id=user_id,
            query_id=query_id,
            image_path=file_path,
        )
        # Persist reference_image immediately, before the Pro call, so a
        # Phase 1.1.2 failure does not wipe Phase 1.1.1's output. Seed with
        # the same `{"step": 0, "step1_data": None}` defaults persist_phase_error
        # uses so the frontend's step-branching logic stays consistent on
        # a subsequent failure.
        pre_blob = (
            (record_pre.result_gemini or {"step": 0, "step1_data": None}).copy()
            if record_pre
            else {"step": 0, "step1_data": None}
        )
        pre_blob["reference_image"] = reference
        update_dish_image_query_results(
            query_id=query_id, result_openai=None, result_gemini=pre_blob
        )
    elif is_retry_short_circuit:
        logger.info("Phase 1.1.1 skipped on retry for query_id=%s", query_id)

    try:
        step1_prompt = get_step1_component_identification_prompt()
        step1_result = await analyze_step1_component_identification_async(
            image_path=file_path,
            analysis_prompt=step1_prompt,
            gemini_model="gemini-2.5-pro",
            thinking_budget=-1,
        )

        # Re-read so we merge onto whatever Phase 1.1.1 wrote (including
        # reference_image) without clobbering it.
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
