"""
API routes for individual item detail views.

This module provides detailed view functionality for individual dish
image query records, showing analysis results from Flow 2 (OpenAI)
and Flow 3 (Gemini).
"""

import logging

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

from src.auth import authenticate_user_from_request
from src.crud.crud_food_image_query import get_dish_image_query_by_id

logger = logging.getLogger(__name__)

# Create router for item detail endpoints
router = APIRouter(
    prefix='/api/item',
    tags=['item']
)


@router.get("/{record_id}")
async def item_detail(
    record_id: int,
    request: Request
) -> JSONResponse:
    """
    Get detailed information for a specific dish image query record.

    This endpoint returns analysis results for a single dish image query,
    including results from Flow 2 (OpenAI) and Flow 3 (Gemini).
    Users can only view their own records.

    Args:
        record_id (int): The ID of the dish image query record
        request (Request): FastAPI request object

    Returns:
        JSONResponse: JSON data with analysis results

    Raises:
        HTTPException: 401 if not authenticated, 404 if record not found
    """
    logger.info(f"Item detail request for record_id={record_id}")

    # Authentication
    user = authenticate_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Get the specific query record
    query_record = get_dish_image_query_by_id(record_id)

    if not query_record:
        raise HTTPException(status_code=404, detail="Record not found")

    # Check if the record belongs to the authenticated user
    if query_record.user_id != user.id:
        raise HTTPException(status_code=404, detail="Record not found")

    # Prepare response data
    item_data = {
        'id': query_record.id,
        'image_url': query_record.image_url,
        'meal_type': query_record.meal_type,
        'created_at': query_record.created_at.isoformat() if (
            query_record.created_at
        ) else None,
        'target_date': query_record.target_date.isoformat() if (
            query_record.target_date
        ) else None,
        'result_openai': query_record.result_openai,
        'result_gemini': query_record.result_gemini,
        'has_openai_result': query_record.result_openai is not None,
        'has_gemini_result': query_record.result_gemini is not None
    }

    return JSONResponse(content=item_data)

