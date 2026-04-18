"""
CRUD operations for the per-user food-description index.

Backs `PersonalizedFoodDescription` — one row per `DishImageQuery` owned
by a user. Stage 0 ships the four calls that later stages bind to:

- `insert_description_row` — Stage 2 (Phase 1.1.1) writes the caption row.
- `update_confirmed_fields` — Stage 4 (Phase 1.2) enriches after Step 1
  confirmation.
- `update_corrected_step2_data` — Stage 8 (Phase 2.4) stores user
  nutrient corrections for future retrieval.
- `get_all_rows_for_user` — Stage 2/6 read the user's corpus; the index
  service calls this to build BM25 on the fly.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.database import SessionLocal
from src.models import PersonalizedFoodDescription


def insert_description_row(
    user_id: int,
    query_id: int,
    *,
    image_url: Optional[str] = None,
    description: Optional[str] = None,
    tokens: Optional[List[str]] = None,
    similarity_score_on_insert: Optional[float] = None,
) -> PersonalizedFoodDescription:
    """
    Insert a new personalization row for a dish upload.

    Args:
        user_id (int): Owner of the row
        query_id (int): DishImageQuery the row indexes; must be unique
        image_url (Optional[str]): Mirror of DishImageQuery.image_url
        description (Optional[str]): Fast-caption text
        tokens (Optional[List[str]]): Tokenized description
        similarity_score_on_insert (Optional[float]): Top-1 score at insert

    Returns:
        PersonalizedFoodDescription: Freshly inserted row

    Raises:
        Exception: If insert fails (e.g. unique violation on query_id)
    """
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        row = PersonalizedFoodDescription(
            user_id=user_id,
            query_id=query_id,
            image_url=image_url,
            description=description,
            tokens=tokens,
            similarity_score_on_insert=similarity_score_on_insert,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def update_confirmed_fields(
    query_id: int,
    *,
    confirmed_dish_name: str,
    confirmed_portions: float,
    confirmed_tokens: List[str],
) -> Optional[PersonalizedFoodDescription]:
    """
    Fill the user-confirmed fields after Step 1 confirmation.

    Args:
        query_id (int): Target row's query_id
        confirmed_dish_name (str): User-verified dish name
        confirmed_portions (float): Sum of confirmed component servings
        confirmed_tokens (List[str]): Tokenized confirmed_dish_name

    Returns:
        Optional[PersonalizedFoodDescription]: Updated row, or None if the
        row does not exist. Missing rows are not treated as an error — the
        caller (Stage 4) logs and moves on.
    """
    db = SessionLocal()
    try:
        row = (
            db.query(PersonalizedFoodDescription)
            .filter(PersonalizedFoodDescription.query_id == query_id)
            .first()
        )
        if row is None:
            return None
        row.confirmed_dish_name = confirmed_dish_name
        row.confirmed_portions = confirmed_portions
        row.confirmed_tokens = confirmed_tokens
        row.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(row)
        return row
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def update_corrected_step2_data(
    query_id: int,
    payload: Dict[str, Any],
) -> Optional[PersonalizedFoodDescription]:
    """
    Store a user manual correction payload from the Step 2 review UI.

    Args:
        query_id (int): Target row's query_id
        payload (Dict[str, Any]): Step 2 correction body; stored as JSON

    Returns:
        Optional[PersonalizedFoodDescription]: Updated row, or None if the
        row does not exist.
    """
    db = SessionLocal()
    try:
        row = (
            db.query(PersonalizedFoodDescription)
            .filter(PersonalizedFoodDescription.query_id == query_id)
            .first()
        )
        if row is None:
            return None
        row.corrected_step2_data = payload
        row.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(row)
        return row
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_row_by_query_id(query_id: int) -> Optional[PersonalizedFoodDescription]:
    """
    Return the single personalization row for a given dish query, or None.

    Stage 2's retry-idempotency probe. The `uq_personalized_food_descriptions_query_id`
    unique index guarantees at most one row per query_id, so a direct filter
    is sufficient.

    Args:
        query_id (int): DishImageQuery id to look up.

    Returns:
        Optional[PersonalizedFoodDescription]: The row, or None if absent.
    """
    db = SessionLocal()
    try:
        return (
            db.query(PersonalizedFoodDescription)
            .filter(PersonalizedFoodDescription.query_id == query_id)
            .first()
        )
    finally:
        db.close()


def get_all_rows_for_user(
    user_id: int,
    *,
    exclude_query_id: Optional[int] = None,
) -> List[PersonalizedFoodDescription]:
    """
    Return every personalization row the user owns, in stable order.

    Args:
        user_id (int): Owner to scope by
        exclude_query_id (Optional[int]): If set, drop the row whose
            `query_id` matches; used by Stage 2's write-after-read path so
            the current upload cannot match itself.

    Returns:
        List[PersonalizedFoodDescription]: Rows ordered by `id ASC` for
        deterministic test behavior.
    """
    db = SessionLocal()
    try:
        query = db.query(PersonalizedFoodDescription).filter(
            PersonalizedFoodDescription.user_id == user_id
        )
        if exclude_query_id is not None:
            query = query.filter(PersonalizedFoodDescription.query_id != exclude_query_id)
        return query.order_by(PersonalizedFoodDescription.id.asc()).all()
    finally:
        db.close()
