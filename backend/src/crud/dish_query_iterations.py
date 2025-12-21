"""
Iteration management for dish image queries.

This module handles the iteration structure for tracking multiple
analysis versions with user feedback and metadata changes.
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from sqlalchemy.orm.attributes import flag_modified
from src.database import SessionLocal
from src.models import DishImageQuery
from src.crud.dish_query_basic import get_dish_image_query_by_id


def initialize_iterations_structure(
    analysis_result: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Initialize iteration structure for first analysis.

    Args:
        analysis_result (Dict[str, Any]): The analysis result from LLM
        metadata (Optional[Dict[str, Any]]): Optional metadata for iteration

    Returns:
        Dict[str, Any]: Iterations structure with first iteration
    """
    # Initialize default metadata if not provided
    if metadata is None:
        metadata = {
            "selected_dish": analysis_result.get("dish_name", "Unknown"),
            "selected_serving_size": None,
            "number_of_servings": 1.0,
            "metadata_modified": False,
        }

    return {
        "iterations": [
            {
                "iteration_number": 1,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "user_feedback": None,
                "metadata": metadata,
                "analysis": analysis_result,
            }
        ],
        "current_iteration": 1,
    }


def get_current_iteration(record: DishImageQuery) -> Optional[Dict[str, Any]]:
    """
    Get the current iteration from result_gemini.

    Args:
        record (DishImageQuery): The query record

    Returns:
        Optional[Dict[str, Any]]: Current iteration data, or None if not found
    """
    if not record.result_gemini:
        return None

    # Handle legacy format (direct analysis without iterations)
    if "iterations" not in record.result_gemini:
        # Convert to iterations format on-the-fly
        return {
            "iteration_number": 1,
            "created_at": (
                record.created_at.isoformat()
                if record.created_at
                else datetime.now(timezone.utc).isoformat()
            ),
            "user_feedback": None,
            "metadata": {
                "selected_dish": record.result_gemini.get("dish_name", "Unknown"),
                "selected_serving_size": None,
                "number_of_servings": 1.0,
                "metadata_modified": False,
            },
            "analysis": record.result_gemini,
        }

    # Get current iteration from iterations array
    current_idx = record.result_gemini.get("current_iteration", 1) - 1
    iterations = record.result_gemini.get("iterations", [])

    if 0 <= current_idx < len(iterations):
        return iterations[current_idx]

    return None


def add_metadata_reanalysis_iteration(
    query_id: int, analysis_result: Dict[str, Any], metadata: Dict[str, Any]
) -> Optional[DishImageQuery]:
    """
    Add new iteration after metadata-based re-analysis.

    Args:
        query_id (int): ID of the query
        analysis_result (Dict[str, Any]): New analysis from LLM
        metadata (Dict[str, Any]): User-selected metadata

    Returns:
        Optional[DishImageQuery]: Updated query object if successful, None otherwise

    Raises:
        Exception: If update fails
    """
    db = SessionLocal()
    try:
        query = db.query(DishImageQuery).filter(DishImageQuery.id == query_id).first()

        if not query:
            return None

        # Ensure result_gemini has iterations structure
        if not query.result_gemini or "iterations" not in query.result_gemini:
            # Initialize iterations structure with existing data
            existing_analysis = query.result_gemini or {}
            query.result_gemini = initialize_iterations_structure(existing_analysis)

        # Create new iteration
        new_iteration_number = len(query.result_gemini["iterations"]) + 1
        new_iteration = {
            "iteration_number": new_iteration_number,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "user_feedback": None,
            "metadata": {**metadata, "metadata_modified": True},
            "analysis": analysis_result,
        }

        # Append new iteration
        query.result_gemini["iterations"].append(new_iteration)
        query.result_gemini["current_iteration"] = new_iteration_number

        # Mark as modified for SQLAlchemy to detect change
        flag_modified(query, "result_gemini")

        db.commit()
        db.refresh(query)
        return query
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def update_metadata(
    query_id: int,
    selected_dish: str,
    selected_serving_size: str,
    number_of_servings: float,
) -> bool:
    """
    Update metadata for current iteration.

    Args:
        query_id (int): ID of the query
        selected_dish (str): Selected or custom dish name
        selected_serving_size (str): Selected or custom serving size
        number_of_servings (float): Number of servings consumed

    Returns:
        bool: True if successful, False otherwise

    Raises:
        Exception: If update fails
    """
    db = SessionLocal()
    try:
        query = db.query(DishImageQuery).filter(DishImageQuery.id == query_id).first()

        if not query or not query.result_gemini:
            return False

        # Ensure iterations structure exists
        if "iterations" not in query.result_gemini:
            query.result_gemini = initialize_iterations_structure(query.result_gemini)

        # Get current iteration index
        current_idx = query.result_gemini.get("current_iteration", 1) - 1
        iterations = query.result_gemini.get("iterations", [])

        if 0 <= current_idx < len(iterations):
            # Update metadata
            iterations[current_idx]["metadata"].update(
                {
                    "selected_dish": selected_dish,
                    "selected_serving_size": selected_serving_size,
                    "number_of_servings": number_of_servings,
                    "metadata_modified": True,
                }
            )

            # Mark as modified for SQLAlchemy
            flag_modified(query, "result_gemini")

            db.commit()
            return True

        return False
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_latest_iterations(record_id: int, limit: int = 3) -> List[Dict[str, Any]]:
    """
    Get most recent iterations for display.

    Args:
        record_id (int): ID of the query record
        limit (int): Maximum number of iterations to return

    Returns:
        List[Dict[str, Any]]: List of iteration objects (most recent first)
    """
    query = get_dish_image_query_by_id(record_id)

    if not query or not query.result_gemini:
        return []

    # Handle legacy format
    if "iterations" not in query.result_gemini:
        # Return single iteration
        return [
            {
                "iteration_number": 1,
                "created_at": (
                    query.created_at.isoformat()
                    if query.created_at
                    else datetime.now(timezone.utc).isoformat()
                ),
                "user_feedback": None,
                "metadata": {
                    "selected_dish": query.result_gemini.get("dish_name", "Unknown"),
                    "selected_serving_size": None,
                    "number_of_servings": 1.0,
                    "metadata_modified": False,
                },
                "analysis": query.result_gemini,
            }
        ]

    # Get iterations (most recent first)
    iterations = query.result_gemini.get("iterations", [])
    return list(reversed(iterations[-limit:]))
