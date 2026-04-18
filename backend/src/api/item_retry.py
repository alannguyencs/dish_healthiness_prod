"""
Retry endpoint for failed Step 2 (nutritional analysis) runs.

Lives in its own module to keep `backend/src/api/item.py` under the 300-line
file cap enforced by pre-commit.
"""

import logging
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import JSONResponse

from src.api.item_tasks import trigger_step2_analysis_background
from src.auth import authenticate_user_from_request
from src.configs import IMAGE_DIR
from src.crud.crud_food_image_query import (
    get_dish_image_query_by_id,
    update_dish_image_query_results,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/item", tags=["item"])


@router.post("/{record_id}/retry-step2")
async def retry_step2_analysis(
    record_id: int,
    request: Request,
    background_tasks: BackgroundTasks,
) -> JSONResponse:
    """
    Re-run Step 2 nutritional analysis after a prior failure.

    Clears `result_gemini.step2_error`, increments retry_count, and
    re-schedules `trigger_step2_analysis_background` using the
    confirmed dish name and components stored on the record.
    """
    logger.info("Step 2 retry request for record_id=%s", record_id)

    user = authenticate_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    record = get_dish_image_query_by_id(record_id)
    if not record or record.user_id != user.id:
        raise HTTPException(status_code=404, detail="Record not found")

    result_gemini = record.result_gemini or {}
    if not result_gemini.get("step1_confirmed"):
        raise HTTPException(status_code=400, detail="Step 1 has not been confirmed")
    if result_gemini.get("step2_data"):
        raise HTTPException(status_code=400, detail="Step 2 is already complete")
    if not result_gemini.get("step2_error"):
        raise HTTPException(status_code=400, detail="No prior error to retry")

    if not record.image_url:
        raise HTTPException(status_code=400, detail="No image found for this record")

    image_path = IMAGE_DIR / Path(record.image_url).name
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Image file no longer exists on disk")

    prior_retry = int(result_gemini["step2_error"].get("retry_count", 0))
    new_retry_count = prior_retry + 1

    cleared = result_gemini.copy()
    cleared.pop("step2_error", None)
    update_dish_image_query_results(query_id=record_id, result_openai=None, result_gemini=cleared)

    background_tasks.add_task(
        trigger_step2_analysis_background,
        record_id,
        image_path,
        result_gemini["confirmed_dish_name"],
        result_gemini["confirmed_components"],
        new_retry_count,
    )

    return JSONResponse(
        content={
            "success": True,
            "message": "Step 2 analysis re-scheduled.",
            "record_id": record_id,
            "retry_count": new_retry_count,
            "step2_in_progress": True,
        }
    )
