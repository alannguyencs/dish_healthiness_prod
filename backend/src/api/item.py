"""
API routes for individual item detail views.

This module provides detailed view functionality for individual dish
image query records, showing analysis results from Gemini, as well as
metadata update and re-analysis endpoints.
"""

import logging
from pathlib import Path

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

from src.auth import authenticate_user_from_request
from src.crud.crud_food_image_query import (
    get_dish_image_query_by_id,
    get_current_iteration,
    update_metadata,
    add_metadata_reanalysis_iteration,
    get_latest_iterations
)
from src.schemas import MetadataUpdate
from src.service.llm.gemini_analyzer import analyze_with_gemini_brief_async
from src.service.llm.prompts import get_brief_analysis_prompt
from src.configs import IMAGE_DIR

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
        'id': query_record.id,
        'image_url': query_record.image_url,
        'dish_position': query_record.dish_position,
        'created_at': query_record.created_at.isoformat() if (
            query_record.created_at
        ) else None,
        'target_date': query_record.target_date.isoformat() if (
            query_record.target_date
        ) else None,
        'result_gemini': query_record.result_gemini,
        'has_gemini_result': query_record.result_gemini is not None,
        'iterations': iterations,
        'current_iteration': current_iteration,
        'total_iterations': total_iterations
    }

    return JSONResponse(content=item_data)


@router.patch("/{record_id}/metadata")
async def update_item_metadata(
    record_id: int,
    request: Request,
    metadata: MetadataUpdate
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
    logger.info(f"Metadata update request for record_id={record_id}")
    logger.info(f"Metadata: {metadata.model_dump()}")

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
            metadata.number_of_servings
        )

        if not success:
            raise HTTPException(
                status_code=400,
                detail="Failed to update metadata"
            )

        return JSONResponse(content={
            "success": True,
            "message": "Metadata updated successfully",
            "metadata_modified": True
        })

    except Exception as e:
        logger.error(f"Error updating metadata: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error updating metadata: {str(e)}"
        )


@router.post("/{record_id}/reanalyze")
async def reanalyze_item(
    record_id: int,
    request: Request
) -> JSONResponse:
    """
    Trigger re-analysis with current metadata using FoodHealthAnalysisBrief.

    This endpoint performs a new analysis using the user-selected metadata
    (dish, serving size, servings count) from the current iteration. It uses
    the lighter FoodHealthAnalysisBrief model to save 20-30% token usage.

    Args:
        record_id (int): The ID of the dish image query record
        request (Request): FastAPI request object

    Returns:
        JSONResponse: New iteration data with analysis results

    Raises:
        HTTPException: 401 if not authenticated, 404 if record not found,
                      400 if re-analysis fails
    """
    logger.info(f"Re-analysis request for record_id={record_id}")

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

    # Get current iteration to extract metadata
    current_iter = get_current_iteration(query_record)

    if not current_iter or "metadata" not in current_iter:
        raise HTTPException(
            status_code=400,
            detail="No metadata found for re-analysis"
        )

    metadata = current_iter["metadata"]
    selected_dish = metadata.get("selected_dish")
    selected_serving_size = metadata.get("selected_serving_size")
    number_of_servings = metadata.get("number_of_servings", 1.0)

    if not selected_dish or not selected_serving_size:
        raise HTTPException(
            status_code=400,
            detail="Incomplete metadata for re-analysis"
        )

    # Load image path
    if not query_record.image_url:
        raise HTTPException(
            status_code=400,
            detail="No image found for this record"
        )

    image_path = IMAGE_DIR / Path(query_record.image_url).name

    if not image_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Image file not found"
        )

    # Perform re-analysis using brief model
    try:
        logger.info(f"Starting re-analysis with metadata: {metadata}")

        brief_prompt = get_brief_analysis_prompt()

        analysis_result = await analyze_with_gemini_brief_async(
            image_path=image_path,
            analysis_prompt=brief_prompt,
            selected_dish=selected_dish,
            selected_serving_size=selected_serving_size,
            number_of_servings=number_of_servings,
            gemini_model="gemini-2.5-pro",
            thinking_budget=-1
        )

        logger.info(f"Re-analysis complete: {analysis_result}")

        # Add new iteration
        updated_record = add_metadata_reanalysis_iteration(
            query_id=record_id,
            analysis_result=analysis_result,
            metadata={
                "selected_dish": selected_dish,
                "selected_serving_size": selected_serving_size,
                "number_of_servings": number_of_servings
            }
        )

        if not updated_record:
            raise HTTPException(
                status_code=500,
                detail="Failed to save re-analysis results"
            )

        # Get the new iteration
        new_iteration = get_current_iteration(updated_record)

        return JSONResponse(content={
            "success": True,
            "iteration_id": record_id,
            "iteration_number": updated_record.result_gemini.get("current_iteration"),
            "analysis_data": analysis_result,
            "created_at": new_iteration.get("created_at") if new_iteration else None
        })

    except Exception as e:
        logger.error(f"Error during re-analysis: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error during re-analysis: {str(e)}"
        )

