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
    APIRouter, Request, Query, File, UploadFile, Form,
    HTTPException, BackgroundTasks
)
from fastapi.responses import JSONResponse
from PIL import Image

from src.auth import authenticate_user_from_request
from src.configs import IMAGE_DIR
from src.crud.crud_food_image_query import (
    get_dish_image_queries_by_user_and_date,
    create_dish_image_query,
    update_dish_image_query_results,
    get_dish_image_query_by_id
)
from src.service.llm.gemini_analyzer import analyze_with_gemini_async
from src.service.llm.prompts import get_analysis_prompt

logger = logging.getLogger(__name__)

# Create router for date endpoints
router = APIRouter(
    prefix='/api/date',
    tags=['date']
)

# Number of dishes per date
MAX_DISHES_PER_DATE = 5


async def analyze_image_background(query_id: int, file_path: str):
    """
    Background task to analyze food image with Gemini.

    Args:
        query_id: ID of the DishImageQuery to update
        file_path: Path to the image file
    """
    logger.info(f"Starting background analysis for query {query_id}")

    try:
        # Run Gemini analysis only
        analysis_prompt = get_analysis_prompt()
        gemini_result = await analyze_with_gemini_async(
            image_path=file_path,
            analysis_prompt=analysis_prompt,
            gemini_model="gemini-2.5-pro",
            thinking_budget=-1
        )

        # Update the query with Gemini result only
        update_dish_image_query_results(
            query_id=query_id,
            result_openai=None,
            result_gemini=gemini_result
        )
        logger.info(f"Query {query_id} updated successfully")

    except Exception as e:
        logger.error(f"Failed to analyze image: {e}", exc_info=True)


def _serialize_query(query) -> Dict[str, Any]:
    """Serialize a query object to dict."""
    return {
        'id': query.id,
        'image_url': query.image_url,
        'dish_position': query.dish_position,
        'created_at': query.created_at.isoformat() if (
            query.created_at
        ) else None,
        'target_date': query.target_date.isoformat() if (
            query.target_date
        ) else None,
        'result_openai': query.result_openai,
        'result_gemini': query.result_gemini
    }


@router.get("/{year}/{month}/{day}")
async def get_date(
    request: Request,
    year: int,
    month: int,
    day: int
) -> JSONResponse:
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
        raise HTTPException(
            status_code=400, detail="Invalid date"
        ) from exc

    logger.info(f"Getting date data for user {user.id}, date {target_date}")
    
    date_queries = get_dish_image_queries_by_user_and_date(
        user.id, target_date
    )

    # Organize queries by dish position (1-5)
    dish_data = {}
    for position in range(1, MAX_DISHES_PER_DATE + 1):
        position_query = next(
            (q for q in date_queries if q.dish_position == position),
            None
        )
        dish_data[f"dish_{position}"] = {
            "has_data": position_query is not None,
            "record_id": position_query.id if position_query else None,
            "image_url": position_query.image_url if position_query else None
        }

    return JSONResponse(
        content={
            "target_date": target_date.isoformat(),
            "formatted_date": target_date.strftime('%B %d, %Y'),
            "dish_data": dish_data,
            "max_dishes": MAX_DISHES_PER_DATE,
            "year": year,
            "month": month,
            "day": day
        }
    )


@router.post("/{year}/{month}/{day}/upload")
async def upload_dish(
    background_tasks: BackgroundTasks,
    request: Request,
    year: int,
    month: int,
    day: int,
    dish_position: int = Form(...),
    file: UploadFile = File(...)
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
            detail=f"Invalid dish position. Must be between 1 and {MAX_DISHES_PER_DATE}"
        )

    try:
        meal_date = datetime(year, month, day).date()
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail="Invalid date"
        ) from exc

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
    if img.mode == 'RGBA':
        rgb_img = Image.new('RGB', img.size, (255, 255, 255))
        rgb_img.paste(img, mask=img.split()[-1])
        img = rgb_img
    elif img.mode != 'RGB':
        img = img.convert('RGB')

    img.save(file_path, "JPEG")

    # Create query record
    target_datetime = datetime.combine(
        meal_date,
        datetime.min.time()
    ).replace(tzinfo=timezone.utc)

    query = create_dish_image_query(
        user_id=user.id,
        image_url=f"/images/{filename}",
        result_openai=None,
        result_gemini=None,
        created_at=datetime.now(timezone.utc),
        target_date=target_datetime,
        dish_position=dish_position
    )

    logger.info(
        f"Created query ID={query.id} for user {user.id}, "
        f"dish_position={dish_position}, target_date={target_datetime}"
    )

    # Schedule analysis in background
    background_tasks.add_task(
        analyze_image_background,
        query.id,
        str(file_path)
    )

    return JSONResponse(
        content={
            "success": True,
            "message": "Image uploaded. Analysis in progress...",
            "query": _serialize_query(query)
        }
    )

