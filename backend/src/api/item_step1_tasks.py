"""
Background task for Phase 1 (Component Identification).

Lives in its own module so `backend/src/api/date.py` stays under the 300-line
file cap and so the Phase 1 + Phase 2 backgrounds tasks have parallel homes
(`item_step1_tasks.py` ↔ `item_tasks.py`).
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from src.api._phase_errors import persist_phase_error
from src.configs import IMAGE_DIR
from src.crud import crud_personalized_food
from src.crud.crud_food_image_query import (
    get_dish_image_query_by_id,
    update_dish_image_query_results,
)
from src.service.llm.gemini_analyzer import analyze_step1_component_identification_async
from src.service.llm.prompts import get_step1_component_identification_prompt
from src.service.personalized_reference import resolve_reference_for_upload

logger = logging.getLogger(__name__)


def _resolve_reference_inputs(
    reference: Optional[Dict[str, Any]],
) -> Tuple[Optional[bytes], Optional[Dict[str, Any]]]:
    """
    Turn a persisted result_gemini.reference_image dict into concrete
    (reference_image_bytes, reference) arguments for Phase 1.1.2.

    Returns (None, None) on any of the degrade paths:
      - reference is None (cold start / below-threshold / caption failure)
      - reference.image_url resolves to a missing file on disk
      - reference.prior_step1_data is None (Option B per 2026-04-18 decision)
      - reference.prior_step1_data is an empty dict (defensive)
    """
    if not reference:
        return None, None

    image_url = reference.get("image_url")
    if not image_url:
        return None, None
    disk_path = IMAGE_DIR / Path(image_url).name
    try:
        image_bytes = disk_path.read_bytes()
    except (FileNotFoundError, OSError) as exc:
        logger.warning(
            "Phase 1.1.2 reference image missing on disk (%s); degrading to single-image: %s",
            disk_path,
            exc,
        )
        return None, None

    prior = reference.get("prior_step1_data")
    if not prior:
        return None, None

    return image_bytes, reference


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
        phase111_out = await resolve_reference_for_upload(
            user_id=user_id,
            query_id=query_id,
            image_path=file_path,
        )
        # Persist flash_caption + reference_image immediately, before the
        # Pro call, so a Phase 1.1.2 failure does not wipe Phase 1.1.1's
        # output. Seed with the same `{"step": 0, "step1_data": None}`
        # defaults persist_phase_error uses so the frontend's
        # step-branching logic stays consistent on a subsequent failure.
        pre_blob = (
            (record_pre.result_gemini or {"step": 0, "step1_data": None}).copy()
            if record_pre
            else {"step": 0, "step1_data": None}
        )
        # `phase111_out` is None only on the retry short-circuit (which we
        # already excluded above); every other path returns a dict with
        # both keys present.
        pre_blob["flash_caption"] = (phase111_out or {}).get("flash_caption")
        pre_blob["reference_image"] = (phase111_out or {}).get("reference_image")
        update_dish_image_query_results(
            query_id=query_id, result_openai=None, result_gemini=pre_blob
        )
    elif is_retry_short_circuit:
        logger.info("Phase 1.1.1 skipped on retry for query_id=%s", query_id)

    try:
        # Re-read to pick up the reference_image Phase 1.1.1 just persisted
        # (or the prior attempt's value on the retry short-circuit path).
        record_pre_pro = get_dish_image_query_by_id(query_id)
        reference_from_blob = (
            (record_pre_pro.result_gemini or {}).get("reference_image") if record_pre_pro else None
        )
        reference_image_bytes, effective_reference = _resolve_reference_inputs(reference_from_blob)

        step1_prompt = get_step1_component_identification_prompt(reference=effective_reference)
        step1_result = await analyze_step1_component_identification_async(
            image_path=file_path,
            analysis_prompt=step1_prompt,
            gemini_model="gemini-2.5-pro",
            thinking_budget=-1,
            reference_image_bytes=reference_image_bytes,
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
