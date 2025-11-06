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
from src.models import DishImageQuery, MealType


def create_dish_image_query(
    user_id: int,
    image_url: Optional[str] = None,
    result_openai: Optional[Dict[str, Any]] = None,
    result_gemini: Optional[Dict[str, Any]] = None,
    meal_type: str = MealType.LUNCH.value,
    created_at: Optional[datetime] = None,
    target_date: Optional[datetime] = None
) -> DishImageQuery:
    """
    Create a new dish image query.

    Args:
        user_id (int): ID of the user making the query
        image_url (Optional[str]): URL of the uploaded image
        result_openai (Optional[Dict[str, Any]]): OpenAI analysis result
        result_gemini (Optional[Dict[str, Any]]): Gemini analysis result
        meal_type (str): Type of meal (breakfast, lunch, dinner, snack)
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
            meal_type=meal_type,
            created_at=created_at or datetime.now(timezone.utc),
            target_date=target_date
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
        return db.query(DishImageQuery).filter(
            DishImageQuery.id == query_id
        ).first()
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
        return db.query(DishImageQuery).filter(
            DishImageQuery.user_id == user_id
        ).order_by(DishImageQuery.created_at.desc()).all()
    finally:
        db.close()


def get_dish_image_queries_by_user_and_date(
    user_id: int,
    query_date,
    meal_type: Optional[str] = None
) -> List[DishImageQuery]:
    """
    Get all dish image queries for a specific user and date.

    Args:
        user_id (int): ID of the user
        query_date: Date to filter queries for
        meal_type (Optional[str]): Optional meal type filter

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
                    func.date(DishImageQuery.target_date) == query_date
                ),
                # Fallback: Use created_at if target_date is NULL
                and_(
                    DishImageQuery.target_date.is_(None),
                    func.date(DishImageQuery.created_at) == query_date
                )
            )
        ]
        
        # Add meal type filter if specified
        if meal_type is not None:
            filters.append(DishImageQuery.meal_type == meal_type)
        
        return db.query(DishImageQuery).filter(*filters).order_by(
            DishImageQuery.target_date.desc().nulls_last(),
            DishImageQuery.created_at.desc()
        ).all()
    finally:
        db.close()


def get_single_dish_by_user_date_meal(
    user_id: int,
    query_date,
    meal_type: str
) -> Optional[DishImageQuery]:
    """
    Get single dish for a specific user, date, and meal type.
    
    Args:
        user_id (int): ID of the user
        query_date: Date to filter queries for
        meal_type (str): Meal type to filter for

    Returns:
        Optional[DishImageQuery]: Single dish for the meal slot, or None
    """
    db = SessionLocal()
    try:
        result = db.query(DishImageQuery).filter(
            DishImageQuery.user_id == user_id,
            DishImageQuery.meal_type == meal_type,
            or_(
                # Primary: Use target_date if it exists
                and_(
                    DishImageQuery.target_date.isnot(None),
                    func.date(DishImageQuery.target_date) == query_date
                ),
                # Fallback: Use created_at if target_date is NULL
                and_(
                    DishImageQuery.target_date.is_(None),
                    func.date(DishImageQuery.created_at) == query_date
                )
            )
        ).order_by(
            DishImageQuery.target_date.desc().nulls_last(),
            DishImageQuery.created_at.desc()
        ).first()
        
        return result
    finally:
        db.close()


def update_dish_image_query_results(
    query_id: int,
    result_openai: Optional[Dict[str, Any]] = None,
    result_gemini: Optional[Dict[str, Any]] = None
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
        query = db.query(DishImageQuery).filter(
            DishImageQuery.id == query_id
        ).first()
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
        query = db.query(DishImageQuery).filter(
            DishImageQuery.id == query_id
        ).first()
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


def get_calendar_data(
    user_id: int,
    year: int,
    month: int
) -> Dict[str, int]:
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
        queries = db.query(
            func.date(
                func.coalesce(
                    DishImageQuery.target_date,
                    DishImageQuery.created_at
                )
            ).label('date'),
            func.count(DishImageQuery.id).label('count')
        ).filter(
            DishImageQuery.user_id == user_id,
            func.extract('year', func.coalesce(
                DishImageQuery.target_date,
                DishImageQuery.created_at
            )) == year,
            func.extract('month', func.coalesce(
                DishImageQuery.target_date,
                DishImageQuery.created_at
            )) == month
        ).group_by('date').all()
        
        # Convert to dictionary
        result = {}
        for query in queries:
            date_str = query.date.strftime('%Y-%m-%d')
            result[date_str] = query.count
        
        return result
    finally:
        db.close()

