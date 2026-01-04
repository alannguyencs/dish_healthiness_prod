"""API routes for date-specific functionality."""

import io
import logging
import os
from datetime import datetime, timezone
from typing import Dict, Any

import httpx
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
from pydantic import BaseModel

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
router = APIRouter(prefix="/api/date", tags=["date"])
MAX_DISHES_PER_DATE = 5


async def analyze_image_background(query_id: int, file_path: str):
    """Background task to analyze food image with Gemini (Step 1: Component Identification)."""
    logger.info("Starting Step 1 background analysis for query %s", query_id)

    try:
        step1_prompt = get_step1_component_identification_prompt()
        step1_result = await analyze_step1_component_identification_async(
            image_path=file_path,
            analysis_prompt=step1_prompt,
            gemini_model="gemini-2.5-pro",
            thinking_budget=-1,
        )

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


def _process_and_save_image(content: bytes, file_path: str) -> Image.Image:
    """Process image content: resize and convert to RGB, then save as JPEG."""
    img = Image.open(io.BytesIO(content))
    max_size = 384
    if img.width > max_size or img.height > max_size:
        img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
    if img.mode == "RGBA":
        rgb_img = Image.new("RGB", img.size, (255, 255, 255))
        rgb_img.paste(img, mask=img.split()[-1])
        img = rgb_img
    elif img.mode != "RGB":
        img = img.convert("RGB")
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    img.save(file_path, "JPEG")
    return img


@router.get("/{year}/{month}/{day}")
async def get_date(request: Request, year: int, month: int, day: int) -> JSONResponse:
    """Get analysis data for a specific date."""
    user = authenticate_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        target_date = datetime(year, month, day).date()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid date") from exc

    logger.info("Getting date data for user %s, date %s", user.id, target_date)

    date_queries = get_dish_image_queries_by_user_and_date(user.id, target_date)

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
async def upload_dish(
    background_tasks: BackgroundTasks,
    request: Request,
    year: int,
    month: int,
    day: int,
    *,
    dish_position: int = Form(...),
    file: UploadFile = File(...),
) -> JSONResponse:
    """Handle image upload for a specific date and dish position."""
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

    timestamp = datetime.now(timezone.utc).strftime("%y%m%d_%H%M%S")
    filename = f"{timestamp}_dish{dish_position}.jpg"
    file_path = IMAGE_DIR / filename
    content = await file.read()
    _process_and_save_image(content, str(file_path))
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

    background_tasks.add_task(analyze_image_background, query.id, str(file_path))
    return JSONResponse(
        content={
            "success": True,
            "message": "Image uploaded. Analysis in progress...",
            "query": _serialize_query(query),
        }
    )


class ImageUrlUploadRequest(BaseModel):
    """Request model for URL-based image upload."""

    dish_position: int
    image_url: str


@router.post("/{year}/{month}/{day}/upload-url")
async def upload_dish_from_url(
    background_tasks: BackgroundTasks,
    request: Request,
    year: int,
    month: int,
    day: int,
    body: ImageUrlUploadRequest,
) -> JSONResponse:
    """Handle image upload from URL for a specific date and dish position."""
    user = authenticate_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    dish_position = body.dish_position
    image_url = body.image_url

    if dish_position < 1 or dish_position > MAX_DISHES_PER_DATE:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid dish position. Must be between 1 and {MAX_DISHES_PER_DATE}",
        )

    try:
        meal_date = datetime(year, month, day).date()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid date") from exc

    # Download image from URL
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(image_url)
            response.raise_for_status()
            content = response.content
    except httpx.HTTPError as exc:
        logger.error("Failed to download image from URL %s: %s", image_url, exc)
        raise HTTPException(
            status_code=400, detail=f"Failed to download image from URL: {exc}"
        ) from exc

    # Generate filename and process image
    timestamp = datetime.now(timezone.utc).strftime("%y%m%d_%H%M%S")
    filename = f"{timestamp}_dish{dish_position}.jpg"
    file_path = IMAGE_DIR / filename

    try:
        _process_and_save_image(content, str(file_path))
    except Exception as exc:
        logger.error("Failed to process image from URL %s: %s", image_url, exc)
        raise HTTPException(status_code=400, detail="Invalid image format") from exc

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
        "Created query ID=%s from URL for user %s, dish_position=%s, target_date=%s",
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
            "message": "Image uploaded from URL. Analysis in progress...",
            "query": _serialize_query(query),
        }
    )
