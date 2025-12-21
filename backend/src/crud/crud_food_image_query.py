"""
CRUD operations for dish image queries.

This module provides Create, Read, Update, Delete operations for
DishImageQuery model with database session management.
Simplified version supporting only Flow 2 (OpenAI) and Flow 3 (Gemini).
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from sqlalchemy import func, or_, and_
from src.database import SessionLocal
from src.models import DishImageQuery


def create_dish_image_query(
    user_id: int,
    image_url: Optional[str] = None,
    result_openai: Optional[Dict[str, Any]] = None,
    result_gemini: Optional[Dict[str, Any]] = None,
    dish_position: Optional[int] = None,
    created_at: Optional[datetime] = None,
    target_date: Optional[datetime] = None,
) -> DishImageQuery:
    """
    Create a new dish image query.

    Args:
        user_id (int): ID of the user making the query
        image_url (Optional[str]): URL of the uploaded image
        result_openai (Optional[Dict[str, Any]]): OpenAI analysis result
        result_gemini (Optional[Dict[str, Any]]): Gemini analysis result
        dish_position (Optional[int]): Position of dish (1-5)
        created_at (Optional[datetime]): Creation timestamp
        target_date (Optional[datetime]): Date when dish was consumed

    Returns:
        DishImageQuery: Created dish image query object

    Raises:
        Exception: If query creation fails
    """
    db = SessionLocal()
    try:
        db_query = DishImageQuery(
            user_id=user_id,
            image_url=image_url,
            result_openai=result_openai,
            result_gemini=result_gemini,
            dish_position=dish_position,
            created_at=created_at or datetime.now(timezone.utc),
            target_date=target_date,
        )
        db.add(db_query)
        db.commit()
        db.refresh(db_query)
        return db_query
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_dish_image_query_by_id(query_id: int) -> Optional[DishImageQuery]:
    """
    Get a dish image query by ID.

    Args:
        query_id (int): ID of the query to retrieve

    Returns:
        Optional[DishImageQuery]: Query object if found, None otherwise
    """
    db = SessionLocal()
    try:
        return db.query(DishImageQuery).filter(DishImageQuery.id == query_id).first()
    finally:
        db.close()


def get_dish_image_queries_by_user(user_id: int) -> List[DishImageQuery]:
    """
    Get all dish image queries for a specific user.

    Args:
        user_id (int): ID of the user

    Returns:
        List[DishImageQuery]: List of user's queries ordered by creation date
    """
    db = SessionLocal()
    try:
        return (
            db.query(DishImageQuery)
            .filter(DishImageQuery.user_id == user_id)
            .order_by(DishImageQuery.created_at.desc())
            .all()
        )
    finally:
        db.close()


def get_dish_image_queries_by_user_and_date(user_id: int, query_date) -> List[DishImageQuery]:
    """
    Get all dish image queries for a specific user and date.

    Args:
        user_id (int): ID of the user
        query_date: Date to filter queries for

    Returns:
        List[DishImageQuery]: List of queries for the specified date
    """
    db = SessionLocal()
    try:
        # Build base filters
        filters = [
            DishImageQuery.user_id == user_id,
            or_(
                # Primary: Use target_date if it exists
                and_(
                    DishImageQuery.target_date.isnot(None),
                    func.date(DishImageQuery.target_date) == query_date,
                ),
                # Fallback: Use created_at if target_date is NULL
                and_(
                    DishImageQuery.target_date.is_(None),
                    func.date(DishImageQuery.created_at) == query_date,
                ),
            ),
        ]

        return (
            db.query(DishImageQuery)
            .filter(*filters)
            .order_by(
                DishImageQuery.dish_position.asc().nulls_last(), DishImageQuery.created_at.desc()
            )
            .all()
        )
    finally:
        db.close()


def get_single_dish_by_user_date_position(
    user_id: int, query_date, dish_position: int
) -> Optional[DishImageQuery]:
    """
    Get single dish for a specific user, date, and position.

    Args:
        user_id (int): ID of the user
        query_date: Date to filter queries for
        dish_position (int): Dish position (1-5)

    Returns:
        Optional[DishImageQuery]: Single dish for the position, or None
    """
    db = SessionLocal()
    try:
        result = (
            db.query(DishImageQuery)
            .filter(
                DishImageQuery.user_id == user_id,
                DishImageQuery.dish_position == dish_position,
                or_(
                    # Primary: Use target_date if it exists
                    and_(
                        DishImageQuery.target_date.isnot(None),
                        func.date(DishImageQuery.target_date) == query_date,
                    ),
                    # Fallback: Use created_at if target_date is NULL
                    and_(
                        DishImageQuery.target_date.is_(None),
                        func.date(DishImageQuery.created_at) == query_date,
                    ),
                ),
            )
            .order_by(
                DishImageQuery.target_date.desc().nulls_last(), DishImageQuery.created_at.desc()
            )
            .first()
        )

        return result
    finally:
        db.close()


def update_dish_image_query_results(
    query_id: int,
    result_openai: Optional[Dict[str, Any]] = None,
    result_gemini: Optional[Dict[str, Any]] = None,
) -> Optional[DishImageQuery]:
    """
    Update analysis results for an existing dish image query.

    Args:
        query_id (int): ID of the query to update
        result_openai (Optional[Dict[str, Any]]): OpenAI results
        result_gemini (Optional[Dict[str, Any]]): Gemini results

    Returns:
        Optional[DishImageQuery]: Updated query object if found, None

    Raises:
        Exception: If update fails
    """
    db = SessionLocal()
    try:
        query = db.query(DishImageQuery).filter(DishImageQuery.id == query_id).first()
        if query:
            if result_openai is not None:
                query.result_openai = result_openai
            if result_gemini is not None:
                query.result_gemini = result_gemini
            db.commit()
            db.refresh(query)
        return query
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def delete_dish_image_query_by_id(query_id: int) -> bool:
    """
    Delete a single dish image query by its ID.

    Args:
        query_id (int): ID of the query to delete

    Returns:
        bool: True if a record was deleted, False if not found

    Raises:
        Exception: If deletion fails
    """
    db = SessionLocal()
    try:
        query = db.query(DishImageQuery).filter(DishImageQuery.id == query_id).first()
        if not query:
            return False
        db.delete(query)
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_calendar_data(user_id: int, year: int, month: int) -> Dict[str, int]:
    """
    Get record count for each day in a month.

    Args:
        user_id (int): ID of the user
        year (int): Year
        month (int): Month

    Returns:
        Dict[str, int]: Dictionary with dates as keys and counts as values
    """
    db = SessionLocal()
    try:
        # Query all records for the month
        queries = (
            db.query(
                func.date(
                    func.coalesce(DishImageQuery.target_date, DishImageQuery.created_at)
                ).label("date"),
                func.count(DishImageQuery.id).label("count"),
            )
            .filter(
                DishImageQuery.user_id == user_id,
                func.extract(
                    "year", func.coalesce(DishImageQuery.target_date, DishImageQuery.created_at)
                )
                == year,
                func.extract(
                    "month", func.coalesce(DishImageQuery.target_date, DishImageQuery.created_at)
                )
                == month,
            )
            .group_by("date")
            .all()
        )

        # Convert to dictionary
        result = {}
        for query in queries:
            date_str = query.date.strftime("%Y-%m-%d")
            result[date_str] = query.count

        return result
    finally:
        db.close()


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
        from sqlalchemy.orm.attributes import flag_modified

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
    query_id: int, selected_dish: str, selected_serving_size: str, number_of_servings: float
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
            from sqlalchemy.orm.attributes import flag_modified

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
