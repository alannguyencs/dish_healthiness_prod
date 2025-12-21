"""
API routes for individual item detail views.

This module provides detailed view functionality for individual dish
image query records, showing analysis results from Gemini, as well as
metadata update and re-analysis endpoints.
"""

import logging
from pathlib import Path

from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse

from src.api.item_schemas import Step1ConfirmationRequest
from src.api.item_tasks import trigger_step2_analysis_background
from src.auth import authenticate_user_from_request
from src.crud.crud_food_image_query import (
    get_dish_image_query_by_id,
    get_current_iteration,
    update_metadata,
    update_dish_image_query_results,
)
from src.schemas import MetadataUpdate
from src.configs import IMAGE_DIR

logger = logging.getLogger(__name__)

# Create router for item detail endpoints
router = APIRouter(prefix="/api/item", tags=["item"])


@router.get("/{record_id}")
async def item_detail(record_id: int, request: Request) -> JSONResponse:
    """
    Get detailed information for a specific dish image query record.

    This endpoint returns analysis results for a single dish image query,
    including results from Gemini.
    Users can only view their own records.

    Args:
        record_id (int): The ID of the dish image query record
        request (Request): FastAPI request object

    Returns:
        JSONResponse: JSON data with analysis results

    Raises:
        HTTPException: 401 if not authenticated, 404 if record not found
    """
    logger.info("Item detail request for record_id=%s", record_id)

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

    # Extract iterations data
    iterations = []
    current_iteration = 1
    total_iterations = 1

    if query_record.result_gemini:
        if "iterations" in query_record.result_gemini:
            # New format with iterations
            iterations = query_record.result_gemini.get("iterations", [])
            current_iteration = query_record.result_gemini.get("current_iteration", 1)
            total_iterations = len(iterations)
        else:
            # Legacy format - convert to iterations format on-the-fly
            current_iter = get_current_iteration(query_record)
            if current_iter:
                iterations = [current_iter]

    # Prepare response data (Gemini only with iterations support)
    item_data = {
        "id": query_record.id,
        "image_url": query_record.image_url,
        "dish_position": query_record.dish_position,
        "created_at": query_record.created_at.isoformat() if (query_record.created_at) else None,
        "target_date": (
            query_record.target_date.isoformat() if (query_record.target_date) else None
        ),
        "result_gemini": query_record.result_gemini,
        "has_gemini_result": query_record.result_gemini is not None,
        "iterations": iterations,
        "current_iteration": current_iteration,
        "total_iterations": total_iterations,
    }

    return JSONResponse(content=item_data)


@router.patch("/{record_id}/metadata")
async def update_item_metadata(
    record_id: int, request: Request, metadata: MetadataUpdate
) -> JSONResponse:
    """
    Update metadata (dish, serving size, servings count) for current iteration.

    This endpoint allows users to update the dish name, serving size, and
    number of servings for their food analysis. The metadata is stored in
    the current iteration and marked as modified.

    Args:
        record_id (int): The ID of the dish image query record
        request (Request): FastAPI request object
        metadata (MetadataUpdate): Metadata to update

    Returns:
        JSONResponse: Success status and metadata_modified flag

    Raises:
        HTTPException: 401 if not authenticated, 404 if record not found,
                      400 if validation fails
    """
    logger.info("Metadata update request for record_id=%s", record_id)
    logger.info("Metadata: %s", metadata.model_dump())

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

    # Update metadata
    try:
        success = update_metadata(
            record_id,
            metadata.selected_dish,
            metadata.selected_serving_size,
            metadata.number_of_servings,
        )

        if not success:
            raise HTTPException(status_code=400, detail="Failed to update metadata")

        return JSONResponse(
            content={
                "success": True,
                "message": "Metadata updated successfully",
                "metadata_modified": True,
            }
        )

    except Exception as e:
        logger.error("Error updating metadata: %s", e)
        raise HTTPException(status_code=500, detail=f"Error updating metadata: {str(e)}") from e


@router.post("/{record_id}/confirm-step1")
async def confirm_step1_and_trigger_step2(
    record_id: int,
    request: Request,
    background_tasks: BackgroundTasks,
    confirmation: Step1ConfirmationRequest,
) -> JSONResponse:
    """
    Confirm Step 1 data and trigger Step 2 nutritional analysis.

    This endpoint receives user-confirmed dish name and components,
    then triggers Step 2 (nutritional analysis) in the background.

    Args:
        record_id (int): The ID of the dish image query record
        request (Request): FastAPI request object
        background_tasks (BackgroundTasks): FastAPI background tasks
        confirmation (Step1ConfirmationRequest): Confirmed Step 1 data

    Returns:
        JSONResponse: Success response with confirmation status

    Raises:
        HTTPException: 401 if not authenticated, 404 if record not found,
                      400 if Step 1 not completed
    """
    logger.info("Step 1 confirmation request for record_id=%s", record_id)
    logger.info("Confirmed dish: %s", confirmation.selected_dish_name)
    logger.info("Confirmed components: %s", [c.component_name for c in confirmation.components])

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

    # Verify Step 1 is completed
    if not query_record.result_gemini:
        raise HTTPException(status_code=400, detail="Step 1 analysis not completed yet")

    result_gemini = query_record.result_gemini
    if result_gemini.get("step") != 1:
        raise HTTPException(status_code=400, detail="Step 1 must be completed before confirmation")

    # Verify image exists
    if not query_record.image_url:
        raise HTTPException(status_code=400, detail="No image found for this record")

    image_path = IMAGE_DIR / Path(query_record.image_url).name

    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Image file not found")

    # Convert confirmation data to dict for background task
    components_data = [comp.model_dump() for comp in confirmation.components]

    # Mark Step 1 as confirmed (optimistic update)
    result_gemini_updated = result_gemini.copy()
    result_gemini_updated["step1_confirmed"] = True
    result_gemini_updated["confirmed_dish_name"] = confirmation.selected_dish_name
    result_gemini_updated["confirmed_components"] = components_data

    update_dish_image_query_results(
        query_id=record_id, result_openai=None, result_gemini=result_gemini_updated
    )

    # Schedule Step 2 analysis in background
    background_tasks.add_task(
        trigger_step2_analysis_background,
        record_id,
        image_path,
        confirmation.selected_dish_name,
        components_data,
    )

    return JSONResponse(
        content={
            "success": True,
            "message": "Step 1 confirmed. Step 2 analysis in progress...",
            "record_id": record_id,
            "confirmed_dish_name": confirmation.selected_dish_name,
            "step2_in_progress": True,
        }
    )
