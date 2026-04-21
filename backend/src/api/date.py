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

from src.api.item_step1_tasks import analyze_image_background
from src.auth import authenticate_user_from_request
from src.configs import IMAGE_DIR
from src.crud.crud_food_image_query import (
    get_dish_image_queries_by_user_and_date,
    replace_slot_atomic,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/date", tags=["date"])
MAX_DISHES_PER_DATE = 5


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


def _build_image_filename(user_id: int, dish_position: int) -> str:
    """
    Filename pattern: `{yymmdd_HHMMSS}_u{user_id}_dish{N}.jpg`.

    Including `user_id` prevents cross-user collisions when two accounts
    upload to slot N within the same second; including `dish_position`
    prevents same-user collisions across slots in the same second.
    """
    timestamp = datetime.now(timezone.utc).strftime("%y%m%d_%H%M%S")
    return f"{timestamp}_u{user_id}_dish{dish_position}.jpg"


def _delete_old_image_files(image_urls: list) -> None:
    """Best-effort cleanup of orphaned image files from a slot replacement."""
    for url in image_urls:
        if not url:
            continue
        old_path = IMAGE_DIR / os.path.basename(url)
        try:
            old_path.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("Failed to remove orphaned image %s: %s", old_path, exc)


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

    filename = _build_image_filename(user.id, dish_position)
    file_path = IMAGE_DIR / filename
    content = await file.read()
    _process_and_save_image(content, str(file_path))
    target_datetime = datetime.combine(meal_date, datetime.min.time()).replace(tzinfo=timezone.utc)

    query, old_image_urls = replace_slot_atomic(
        user_id=user.id,
        target_date=target_datetime,
        dish_position=dish_position,
        image_url=f"/images/{filename}",
    )
    _delete_old_image_files(old_image_urls)

    logger.info(
        "Created query ID=%s for user %s, dish_position=%s, target_date=%s "
        "(replaced %s prior row(s))",
        query.id,
        user.id,
        dish_position,
        target_datetime,
        len(old_image_urls),
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
    filename = _build_image_filename(user.id, dish_position)
    file_path = IMAGE_DIR / filename

    try:
        _process_and_save_image(content, str(file_path))
    except Exception as exc:
        logger.error("Failed to process image from URL %s: %s", image_url, exc)
        raise HTTPException(status_code=400, detail="Invalid image format") from exc

    # Create query record
    target_datetime = datetime.combine(meal_date, datetime.min.time()).replace(tzinfo=timezone.utc)

    query, old_image_urls = replace_slot_atomic(
        user_id=user.id,
        target_date=target_datetime,
        dish_position=dish_position,
        image_url=f"/images/{filename}",
    )
    _delete_old_image_files(old_image_urls)

    logger.info(
        "Created query ID=%s from URL for user %s, dish_position=%s, target_date=%s "
        "(replaced %s prior row(s))",
        query.id,
        user.id,
        dish_position,
        target_datetime,
        len(old_image_urls),
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
