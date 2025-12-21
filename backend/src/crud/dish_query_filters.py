"""
Query and filter operations for dish image queries.

This module provides filtered query operations for finding dishes
by date, position, and calendar data.
"""

from typing import Dict, List, Optional

from sqlalchemy import func, or_, and_
from src.database import SessionLocal
from src.models import DishImageQuery


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
        # pylint: disable=not-callable
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
        # pylint: enable=not-callable

        return (
            db.query(DishImageQuery)
            .filter(*filters)
            .order_by(
                DishImageQuery.dish_position.asc().nulls_last(),
                DishImageQuery.created_at.desc(),
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
        # pylint: disable=not-callable
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
                DishImageQuery.target_date.desc().nulls_last(),
                DishImageQuery.created_at.desc(),
            )
            .first()
        )
        # pylint: enable=not-callable

        return result
    finally:
        db.close()


def get_calendar_data(user_id: int, year: int, month: int) -> Dict[str, int]:
    """
    Get calendar data showing count of dishes per day for a month.

    Args:
        user_id (int): ID of the user
        year (int): Year to query
        month (int): Month to query (1-12)

    Returns:
        Dict[str, int]: Dictionary mapping date strings (YYYY-MM-DD) to dish counts
    """
    db = SessionLocal()
    try:
        # Query to get count of dishes per day for the specified month/year
        # pylint: disable=not-callable
        results = (
            db.query(
                func.count(DishImageQuery.id).label("count"),
                func.extract("day", DishImageQuery.target_date).label("day"),
            )
            .filter(
                DishImageQuery.user_id == user_id,
                func.extract("year", DishImageQuery.target_date) == year,
                func.extract("month", DishImageQuery.target_date) == month,
            )
            .group_by(func.extract("day", DishImageQuery.target_date))
            .all()
        )
        # pylint: enable=not-callable

        # Convert to dictionary with date strings as keys
        calendar_data = {}
        for count, day in results:
            date_str = f"{year}-{month:02d}-{int(day):02d}"
            calendar_data[date_str] = count

        return calendar_data
    finally:
        db.close()
