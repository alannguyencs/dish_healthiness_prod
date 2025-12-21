"""
Basic CRUD operations for dish image queries.

This module provides Create, Read, Update, Delete operations.
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from src.database import SessionLocal
from src.models import DishImageQuery


def create_dish_image_query(
    user_id: int,
    *,
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
        List[DishImageQuery]: List of query objects for the user
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


def update_dish_image_query_results(
    query_id: int,
    result_openai: Optional[Dict[str, Any]] = None,
    result_gemini: Optional[Dict[str, Any]] = None,
) -> Optional[DishImageQuery]:
    """
    Update analysis results for a query.

    Args:
        query_id (int): ID of the query to update
        result_openai (Optional[Dict[str, Any]]): OpenAI analysis result
        result_gemini (Optional[Dict[str, Any]]): Gemini analysis result

    Returns:
        Optional[DishImageQuery]: Updated query object if found, None otherwise

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

        return None
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

        if query:
            db.delete(query)
            db.commit()
            return True

        return False
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
