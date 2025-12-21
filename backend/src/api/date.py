"""
API routes for date-specific functionality.

This module provides endpoints for viewing and uploading dishes for a
specific date.
"""

import io
import logging
from datetime import datetime, timezone
from typing import Dict, Any

from fastapi import (
    APIRouter,
    Request,
    File,
    UploadFile,
    Form,
    HTTPException,
    BackgroundTasks,
)
from fastapi.responses import JSONResponse
from PIL import Image

from src.auth import authenticate_user_from_request
from src.configs import IMAGE_DIR
from src.crud.crud_food_image_query import (
    get_dish_image_queries_by_user_and_date,
    create_dish_image_query,
    update_dish_image_query_results,
)
from src.service.llm.gemini_analyzer import analyze_step1_component_identification_async
from src.service.llm.prompts import get_step1_component_identification_prompt

logger = logging.getLogger(__name__)

# Create router for date endpoints
router = APIRouter(prefix="/api/date", tags=["date"])

# Number of dishes per date
MAX_DISHES_PER_DATE = 5


async def analyze_image_background(query_id: int, file_path: str):
    """
    Background task to analyze food image with Gemini (Step 1 only).

    This performs Step 1: Component Identification
    - Predicts dish names
    - Identifies major nutrition components
    - Provides component-level serving size predictions

    Step 2 (nutritional analysis) is triggered separately after user confirmation.

    Args:
        query_id: ID of the DishImageQuery to update
        file_path: Path to the image file
    """
    logger.info("Starting Step 1 background analysis for query %s", query_id)

    try:
        # Run Step 1: Component Identification with Gemini
        step1_prompt = get_step1_component_identification_prompt()
        step1_result = await analyze_step1_component_identification_async(
            image_path=file_path,
            analysis_prompt=step1_prompt,
            gemini_model="gemini-2.5-pro",
            thinking_budget=-1,
        )

        # Wrap Step 1 result in iteration structure
        # Format: { "step": 1, "step1_data": {...}, "step2_data": null, "step1_confirmed": false }
        result_gemini = {
            "step": 1,
            "step1_data": step1_result,
            "step2_data": None,
            "step1_confirmed": False,
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

        # Update the query with Step 1 result
        update_dish_image_query_results(
            query_id=query_id, result_openai=None, result_gemini=result_gemini
        )
        logger.info("Query %s Step 1 completed successfully", query_id)

    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Failed to analyze image (Step 1): %s", e, exc_info=True)


def _serialize_query(query) -> Dict[str, Any]:
    """Serialize a query object to dict."""
    return {
        "id": query.id,
        "image_url": query.image_url,
        "dish_position": query.dish_position,
        "created_at": query.created_at.isoformat() if (query.created_at) else None,
        "target_date": query.target_date.isoformat() if (query.target_date) else None,
        "result_openai": query.result_openai,
        "result_gemini": query.result_gemini,
    }


@router.get("/{year}/{month}/{day}")
async def get_date(request: Request, year: int, month: int, day: int) -> JSONResponse:
    """
    Get analysis data for a specific date.

    Args:
        request (Request): FastAPI request object
        year (int): Year
        month (int): Month
        day (int): Day

    Returns:
        JSONResponse: Date analysis data

    Raises:
        HTTPException: 401 if not authenticated, 400 if invalid date
    """
    user = authenticate_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        target_date = datetime(year, month, day).date()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid date") from exc

    logger.info("Getting date data for user %s, date %s", user.id, target_date)

    date_queries = get_dish_image_queries_by_user_and_date(user.id, target_date)

    # Organize queries by dish position (1-5)
    dish_data = {}
    for position in range(1, MAX_DISHES_PER_DATE + 1):
        position_query = next((q for q in date_queries if q.dish_position == position), None)
        dish_data[f"dish_{position}"] = {
            "has_data": position_query is not None,
            "record_id": position_query.id if position_query else None,
            "image_url": position_query.image_url if position_query else None,
        }

    return JSONResponse(
        content={
            "target_date": target_date.isoformat(),
            "formatted_date": target_date.strftime("%B %d, %Y"),
            "dish_data": dish_data,
            "max_dishes": MAX_DISHES_PER_DATE,
            "year": year,
            "month": month,
            "day": day,
        }
    )


@router.post("/{year}/{month}/{day}/upload")
async def upload_dish(  # pylint: disable=too-many-locals
    background_tasks: BackgroundTasks,
    request: Request,
    year: int,
    month: int,
    day: int,
    *,
    dish_position: int = Form(...),
    file: UploadFile = File(...),
) -> JSONResponse:
    """
    Handle image upload for a specific date and dish position.

    Args:
        background_tasks: FastAPI background tasks
        request (Request): FastAPI request object
        year (int): Year
        month (int): Month
        day (int): Day
        dish_position (int): Dish position (1-5)
        file (UploadFile): Uploaded image

    Returns:
        JSONResponse: Success response with created query data

    Raises:
        HTTPException: 401 if not authenticated, 400 if invalid data
    """
    user = authenticate_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if dish_position < 1 or dish_position > MAX_DISHES_PER_DATE:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid dish position. Must be between 1 and {MAX_DISHES_PER_DATE}",
        )

    try:
        meal_date = datetime(year, month, day).date()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid date") from exc

    # Generate filename
    timestamp = datetime.now(timezone.utc).strftime("%y%m%d_%H%M%S")
    filename = f"{timestamp}_dish{dish_position}.jpg"
    file_path = IMAGE_DIR / filename

    # Process image
    content = await file.read()
    img = Image.open(io.BytesIO(content))

    # Rescale to max 384px
    max_size = 384
    if img.width > max_size or img.height > max_size:
        img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

    # Convert to RGB
    if img.mode == "RGBA":
        rgb_img = Image.new("RGB", img.size, (255, 255, 255))
        rgb_img.paste(img, mask=img.split()[-1])
        img = rgb_img
    elif img.mode != "RGB":
        img = img.convert("RGB")

    img.save(file_path, "JPEG")

    # Create query record
    target_datetime = datetime.combine(meal_date, datetime.min.time()).replace(tzinfo=timezone.utc)

    query = create_dish_image_query(
        user_id=user.id,
        image_url=f"/images/{filename}",
        result_openai=None,
        result_gemini=None,
        created_at=datetime.now(timezone.utc),
        target_date=target_datetime,
        dish_position=dish_position,
    )

    logger.info(
        "Created query ID=%s for user %s, dish_position=%s, target_date=%s",
        query.id,
        user.id,
        dish_position,
        target_datetime,
    )

    # Schedule analysis in background
    background_tasks.add_task(analyze_image_background, query.id, str(file_path))

    return JSONResponse(
        content={
            "success": True,
            "message": "Image uploaded. Analysis in progress...",
            "query": _serialize_query(query),
        }
    )
