"""
Stage 8 — POST /api/item/{record_id}/correction.

Persists a user correction of the Step 2 nutritional analysis. Lives in
its own module so `backend/src/api/item.py` stays under the 300-line file
cap (parallel to `item_retry.py` / `item_step1_tasks.py`).

Dual write:
  1. `DishImageQuery.result_gemini.step2_corrected` — the user override,
     preserving `step2_data` untouched for audit.
  2. `personalized_food_descriptions.corrected_step2_data` — same payload
     written onto the personalization row via Stage 0's CRUD so future
     Phase 2.2 retrieval surfaces the user-verified nutrients.

The personalization half is wrapped in try/except-swallow-log: the user's
primary intent (save correction) succeeds even if the enrichment fails.
Matches Stage 4's pattern.
"""

import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from src.api.item_schemas import Step2CorrectionRequest
from src.auth import authenticate_user_from_request
from src.crud import crud_personalized_food
from src.crud.crud_food_image_query import (
    get_dish_image_query_by_id,
    update_dish_image_query_results,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/item", tags=["item"])


def _enrich_personalization_corrected_data(record_id: int, payload: Dict[str, Any]) -> None:
    """
    Stage 8: mirror the user correction onto the personalization row.

    Fire-and-forget — failures must not bounce the user since the main
    `result_gemini.step2_corrected` write already landed.
    """
    try:
        updated_row = crud_personalized_food.update_corrected_step2_data(
            query_id=record_id,
            payload=payload,
        )
        if updated_row is None:
            logger.warning(
                "Stage 8 enrichment skipped: no personalized_food_descriptions "
                "row for query_id=%s",
                record_id,
            )
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.warning("Stage 8 enrichment failed for query_id=%s: %s", record_id, exc)


@router.post("/{record_id}/correction")
async def save_step2_correction(
    record_id: int,
    request: Request,
    correction: Step2CorrectionRequest,
) -> JSONResponse:
    """
    Save a user correction of the Step 2 nutritional analysis.

    Writes `result_gemini.step2_corrected` (preserving `step2_data` for
    audit) and best-effort mirrors the payload onto
    `personalized_food_descriptions.corrected_step2_data`.
    """
    logger.info("Step 2 correction request for record_id=%s", record_id)

    user = authenticate_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    record = get_dish_image_query_by_id(record_id)
    if not record or record.user_id != user.id:
        raise HTTPException(status_code=404, detail="Record not found")

    if not record.result_gemini:
        raise HTTPException(
            status_code=400,
            detail="Step 2 analysis has not completed; nothing to correct.",
        )

    payload = correction.model_dump()

    new_blob = dict(record.result_gemini)
    new_blob["step2_corrected"] = payload
    update_dish_image_query_results(
        query_id=record_id,
        result_openai=None,
        result_gemini=new_blob,
    )

    _enrich_personalization_corrected_data(record_id, payload)

    return JSONResponse(
        content={
            "success": True,
            "record_id": record_id,
            "step2_corrected": payload,
        }
    )
