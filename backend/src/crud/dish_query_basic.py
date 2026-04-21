"""
Basic CRUD operations for dish image queries.

This module provides Create, Read, Update, Delete operations.
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

from sqlalchemy import and_, func, or_

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


def replace_slot_atomic(
    *,
    user_id: int,
    target_date: datetime,
    dish_position: int,
    image_url: str,
) -> Tuple[DishImageQuery, List[str]]:
    """
    Atomically replace any existing row(s) for `(user_id, date(target_date),
    dish_position)` with a single new row.

    A re-upload to the same slot used to leak an orphan row that the GET
    endpoint silently hid but `get_calendar_data` overcounted. This locks the
    matching slot rows, deletes them, and inserts the new row in one
    transaction so concurrent uploads can't both create new rows for the same
    slot (combined with the partial UNIQUE index in `create_tables.sql`).

    Returns:
        (new_query, [old_image_urls]) — the caller is expected to delete the
        old image files from disk after the transaction commits.
    """
    target_day = target_date.date()
    db = SessionLocal()
    try:
        # pylint: disable=not-callable
        existing = (
            db.query(DishImageQuery)
            .filter(
                DishImageQuery.user_id == user_id,
                DishImageQuery.dish_position == dish_position,
                or_(
                    and_(
                        DishImageQuery.target_date.isnot(None),
                        func.date(DishImageQuery.target_date) == target_day,
                    ),
                    and_(
                        DishImageQuery.target_date.is_(None),
                        func.date(DishImageQuery.created_at) == target_day,
                    ),
                ),
            )
            .with_for_update()
            .all()
        )
        # pylint: enable=not-callable

        old_image_urls = [row.image_url for row in existing if row.image_url]
        for row in existing:
            db.delete(row)

        new_row = DishImageQuery(
            user_id=user_id,
            image_url=image_url,
            result_openai=None,
            result_gemini=None,
            dish_position=dish_position,
            created_at=datetime.now(timezone.utc),
            target_date=target_date,
        )
        db.add(new_row)
        db.commit()
        db.refresh(new_row)
        return new_row, old_image_urls
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def confirm_step1_atomic(
    query_id: int,
    *,
    confirmed_dish_name: str,
    confirmed_components: List[Dict[str, Any]],
) -> str:
    """
    Atomically mark Step 1 as confirmed for a query.

    Acquires a row-level lock (SELECT ... FOR UPDATE) so that two concurrent
    requests cannot both pass the `step1_confirmed=False` check and each
    schedule a Step-2 background task.

    Returns:
        "confirmed"   — this call set step1_confirmed=True (caller should
                        schedule the background task).
        "duplicate"   — step1_confirmed was already True (caller should not
                        re-schedule; respond 409).
        "not_found"   — no record exists with that id.
        "no_step1"    — Step 1 has not produced a result yet (step != 1).
    """
    db = SessionLocal()
    try:
        query = (
            db.query(DishImageQuery)
            .filter(DishImageQuery.id == query_id)
            .with_for_update()
            .first()
        )

        if not query:
            return "not_found"

        result_gemini = dict(query.result_gemini or {})
        if result_gemini.get("step") != 1:
            return "no_step1"
        if result_gemini.get("step1_confirmed"):
            return "duplicate"

        result_gemini["step1_confirmed"] = True
        result_gemini["confirmed_dish_name"] = confirmed_dish_name
        result_gemini["confirmed_components"] = confirmed_components
        query.result_gemini = result_gemini

        db.commit()
        return "confirmed"
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
