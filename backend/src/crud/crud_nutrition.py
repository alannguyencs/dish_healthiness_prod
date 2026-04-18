"""
CRUD operations for the nutrition database tables.

Backs `NutritionFood` and `NutritionMyfcdNutrient` — the unified
four-source corpus that `service/nutrition_db.py` searches with BM25.

The five public functions divide cleanly between the seed script (which
bulk-upserts) and the runtime service (which reads everything once at
first use):

- `bulk_upsert_foods`, `bulk_upsert_myfcd_nutrients` — seed-script writes.
  Idempotent on the unique indices defined in `backend/sql/create_tables.sql`.
- `get_all_foods_grouped_by_source`,
  `get_myfcd_nutrients_grouped_by_ndb_id` — service reads. Each issues
  one SELECT and groups in Python, since the service rebuilds in-memory
  BM25 indices from the full corpus at first use.
- `count_foods_by_source` — used by the seed script's re-run summary.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from src.database import SessionLocal
from src.models import NutritionFood, NutritionMyfcdNutrient


_FOOD_SOURCES = ("malaysian_food_calories", "myfcd", "anuvaad", "ciqual")
_BULK_CHUNK = 500


def _chunked(rows: List[Dict[str, Any]], size: int):
    """Yield successive `size`-sized slices from `rows`."""
    for start in range(0, len(rows), size):
        yield rows[start : start + size]


def _insert_for(bind) -> Any:
    """
    Pick the dialect-specific `insert` whose `.on_conflict_do_update` we need.

    Both Postgres and SQLite support `INSERT ... ON CONFLICT DO UPDATE`
    via their respective dialect modules (with identical Python APIs),
    so production (Postgres) and unit tests (SQLite) share one code
    path.
    """
    name = bind.dialect.name if bind is not None else "postgresql"
    if name == "sqlite":
        return sqlite_insert
    return pg_insert


def bulk_upsert_foods(rows: List[Dict[str, Any]]) -> int:
    """
    Bulk-upsert `nutrition_foods` rows on (source, source_food_id).

    Each row dict must carry every required column except `created_at`
    and `updated_at`, which this function sets. On conflict, every
    mutable column is overwritten and `updated_at` is bumped.

    Args:
        rows (List[Dict[str, Any]]): Rows to insert/update

    Returns:
        int: Number of rows processed (Postgres does not cleanly expose
        insert-vs-update split via SQLAlchemy Core; we report the input
        size, which is the seed script's own count anyway).
    """
    if not rows:
        return 0

    now = datetime.now(timezone.utc)
    payload = [{**row, "created_at": now, "updated_at": now} for row in rows]

    db = SessionLocal()
    try:
        insert_ = _insert_for(db.get_bind())
        excluded = insert_(NutritionFood).excluded
        update_cols = {
            "food_name": excluded.food_name,
            "food_name_eng": excluded.food_name_eng,
            "category": excluded.category,
            "searchable_document": excluded.searchable_document,
            "calories": excluded.calories,
            "carbs_g": excluded.carbs_g,
            "protein_g": excluded.protein_g,
            "fat_g": excluded.fat_g,
            "fiber_g": excluded.fiber_g,
            "serving_size_grams": excluded.serving_size_grams,
            "serving_unit": excluded.serving_unit,
            "raw_data": excluded.raw_data,
            "updated_at": excluded.updated_at,
        }
        for chunk in _chunked(payload, _BULK_CHUNK):
            stmt = insert_(NutritionFood).values(chunk)
            stmt = stmt.on_conflict_do_update(
                index_elements=["source", "source_food_id"],
                set_=update_cols,
            )
            db.execute(stmt)
        db.commit()
        return len(payload)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def bulk_upsert_myfcd_nutrients(rows: List[Dict[str, Any]]) -> int:
    """
    Bulk-upsert `nutrition_myfcd_nutrients` rows on (ndb_id, nutrient_name).

    Args:
        rows (List[Dict[str, Any]]): Rows to insert/update

    Returns:
        int: Number of input rows processed
    """
    if not rows:
        return 0

    db = SessionLocal()
    try:
        insert_ = _insert_for(db.get_bind())
        excluded = insert_(NutritionMyfcdNutrient).excluded
        update_cols = {
            "value_per_100g": excluded.value_per_100g,
            "value_per_serving": excluded.value_per_serving,
            "unit": excluded.unit,
            "category": excluded.category,
        }
        for chunk in _chunked(rows, _BULK_CHUNK):
            stmt = insert_(NutritionMyfcdNutrient).values(chunk)
            stmt = stmt.on_conflict_do_update(
                index_elements=["ndb_id", "nutrient_name"],
                set_=update_cols,
            )
            db.execute(stmt)
        db.commit()
        return len(rows)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_all_foods_grouped_by_source() -> Dict[str, List[NutritionFood]]:
    """
    Read every nutrition_foods row and group in Python by source.

    Returns:
        Dict[str, List[NutritionFood]]: Dict keyed by every source name
        in `_FOOD_SOURCES`. Sources with no rows return [] (no raise);
        the service is responsible for treating an entirely-empty corpus
        as an error.
    """
    db = SessionLocal()
    try:
        rows = db.query(NutritionFood).order_by(NutritionFood.id.asc()).all()
        # Detach from session so the service can close the call without
        # losing access to the column values during BM25 index build.
        for row in rows:
            db.expunge(row)
    finally:
        db.close()

    grouped: Dict[str, List[NutritionFood]] = {src: [] for src in _FOOD_SOURCES}
    for row in rows:
        if row.source in grouped:
            grouped[row.source].append(row)
    return grouped


def get_myfcd_nutrients_grouped_by_ndb_id() -> Dict[str, List[NutritionMyfcdNutrient]]:
    """
    Read every nutrition_myfcd_nutrients row and group by ndb_id.

    Returns:
        Dict[str, List[NutritionMyfcdNutrient]]: ndb_id -> nutrient rows
    """
    db = SessionLocal()
    try:
        rows = db.query(NutritionMyfcdNutrient).order_by(NutritionMyfcdNutrient.id.asc()).all()
        for row in rows:
            db.expunge(row)
    finally:
        db.close()

    grouped: Dict[str, List[NutritionMyfcdNutrient]] = {}
    for row in rows:
        grouped.setdefault(row.ndb_id, []).append(row)
    return grouped


def count_foods_by_source() -> Dict[str, int]:
    """
    Return a per-source count of nutrition_foods rows.

    Returns:
        Dict[str, int]: Always includes every source name in
        `_FOOD_SOURCES`; sources with no rows report 0.
    """
    db = SessionLocal()
    try:
        rows = db.query(NutritionFood.source).all()
    finally:
        db.close()

    counts: Dict[str, int] = {src: 0 for src in _FOOD_SOURCES}
    for (source,) in rows:
        if source in counts:
            counts[source] = counts.get(source, 0) + 1
    return counts
