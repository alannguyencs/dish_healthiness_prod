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
from src.models import MealType
from src.service.llm.high_level_api import analyze_dish_parallel_async

logger = logging.getLogger(__name__)

# Create router for date endpoints
router = APIRouter(
    prefix='/api/date',
    tags=['date']
)

# Meal types
MEAL_TYPES = [MealType.BREAKFAST.value, MealType.LUNCH.value,
              MealType.DINNER.value, MealType.SNACK.value]


async def analyze_image_background(query_id: int, file_path: str):
    """
    Background task to analyze food image with Flow 2 & 3.

    Args:
        query_id: ID of the DishImageQuery to update
        file_path: Path to the image file
    """
    logger.info(f"Starting background analysis for query {query_id}")

    try:
        # Run parallel analysis (Flow 2: OpenAI, Flow 3: Gemini)
        results = await analyze_dish_parallel_async(
            image_path=file_path,
            openai_model="gpt-5-low",
            gemini_model="gemini-2.5-pro",
            gemini_thinking_budget=-1
        )

        # Update the query with both results
        update_dish_image_query_results(
            query_id=query_id,
            result_openai=results.get("OpenAI"),
            result_gemini=results.get("Gemini")
        )
        logger.info(f"Query {query_id} updated successfully")

    except Exception as e:
        logger.error(f"Failed to analyze image: {e}", exc_info=True)


def _serialize_query(query) -> Dict[str, Any]:
    """Serialize a query object to dict."""
    return {
        'id': query.id,
        'image_url': query.image_url,
        'meal_type': query.meal_type,
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

    # Organize queries by meal type
    meal_data = {}
    for meal_type in MEAL_TYPES:
        meal_queries = [q for q in date_queries if q.meal_type == meal_type]
        meal_data[meal_type] = [
            _serialize_query(q) for q in meal_queries
        ]

    return JSONResponse(
        content={
            "target_date": target_date.isoformat(),
            "formatted_date": target_date.strftime('%B %d, %Y'),
            "meal_data": meal_data,
            "meal_types": MEAL_TYPES,
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
    meal_type: str = Form(...),
    file: UploadFile = File(...)
) -> JSONResponse:
    """
    Handle image upload for a specific date and meal type.

    Args:
        background_tasks: FastAPI background tasks
        request (Request): FastAPI request object
        year (int): Year
        month (int): Month
        day (int): Day
        meal_type (str): Meal type
        file (UploadFile): Uploaded image

    Returns:
        JSONResponse: Success response with created query data

    Raises:
        HTTPException: 401 if not authenticated, 400 if invalid data
    """
    user = authenticate_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if meal_type not in MEAL_TYPES:
        raise HTTPException(status_code=400, detail="Invalid meal type")

    try:
        meal_date = datetime(year, month, day).date()
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail="Invalid date"
        ) from exc

    # Generate filename
    timestamp = datetime.now(timezone.utc).strftime("%y%m%d_%H%M%S")
    filename = f"{timestamp}_{meal_type}.jpg"
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
        meal_type=meal_type
    )

    logger.info(
        f"Created query ID={query.id} for user {user.id}, "
        f"meal_type={meal_type}, target_date={target_datetime}"
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

