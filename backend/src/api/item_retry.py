"""
Retry endpoints for failed Phase 1 (Component Identification) and Phase 2
(Nutritional Analysis) runs.

Lives in its own module to keep `backend/src/api/item.py` under the 300-line
file cap enforced by pre-commit.
"""

import logging
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import JSONResponse

from src.api.item_identification_tasks import analyze_image_background
from src.api.item_tasks import trigger_nutrition_analysis_background
from src.auth import authenticate_user_from_request
from src.configs import IMAGE_DIR
from src.crud.crud_food_image_query import (
    get_dish_image_query_by_id,
    update_dish_image_query_results,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/item", tags=["item"])


@router.post("/{record_id}/retry-nutrition")
async def retry_nutrition_analysis(
    record_id: int,
    request: Request,
    background_tasks: BackgroundTasks,
) -> JSONResponse:
    """
    Re-run Step 2 nutritional analysis after a prior failure.

    Clears `result_gemini.nutrition_error`, increments retry_count, and
    re-schedules `trigger_nutrition_analysis_background` using the
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
    if not result_gemini.get("identification_confirmed"):
        raise HTTPException(status_code=400, detail="Step 1 has not been confirmed")
    if result_gemini.get("nutrition_data"):
        raise HTTPException(status_code=400, detail="Step 2 is already complete")
    if not result_gemini.get("nutrition_error"):
        raise HTTPException(status_code=400, detail="No prior error to retry")

    if not record.image_url:
        raise HTTPException(status_code=400, detail="No image found for this record")

    image_path = IMAGE_DIR / Path(record.image_url).name
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Image file no longer exists on disk")

    prior_retry = int(result_gemini["nutrition_error"].get("retry_count", 0))
    new_retry_count = prior_retry + 1

    cleared = result_gemini.copy()
    cleared.pop("nutrition_error", None)
    update_dish_image_query_results(query_id=record_id, result_openai=None, result_gemini=cleared)

    background_tasks.add_task(
        trigger_nutrition_analysis_background,
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
            "nutrition_in_progress": True,
        }
    )


@router.post("/{record_id}/retry-identification")
async def retry_identification_analysis(
    record_id: int,
    request: Request,
    background_tasks: BackgroundTasks,
) -> JSONResponse:
    """
    Re-run Phase 1 (Component Identification) after a prior failure.

    Clears `result_gemini.identification_error`, increments retry_count, and
    re-schedules `analyze_image_background` against the existing image file.
    """
    logger.info("Step 1 retry request for record_id=%s", record_id)

    user = authenticate_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    record = get_dish_image_query_by_id(record_id)
    if not record or record.user_id != user.id:
        raise HTTPException(status_code=404, detail="Record not found")

    result_gemini = record.result_gemini or {}
    if result_gemini.get("identification_data"):
        raise HTTPException(status_code=400, detail="Step 1 is already complete")
    if not result_gemini.get("identification_error"):
        raise HTTPException(status_code=400, detail="No prior error to retry")

    if not record.image_url:
        raise HTTPException(status_code=400, detail="No image found for this record")

    image_path = IMAGE_DIR / Path(record.image_url).name
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Image file no longer exists on disk")

    prior_retry = int(result_gemini["identification_error"].get("retry_count", 0))
    new_retry_count = prior_retry + 1

    cleared = result_gemini.copy()
    cleared.pop("identification_error", None)
    update_dish_image_query_results(query_id=record_id, result_openai=None, result_gemini=cleared)

    background_tasks.add_task(
        analyze_image_background, record_id, str(image_path), new_retry_count
    )

    return JSONResponse(
        content={
            "success": True,
            "message": "Step 1 analysis re-scheduled.",
            "record_id": record_id,
            "retry_count": new_retry_count,
            "identification_in_progress": True,
        }
    )
