"""
Seed `nutrition_foods` + `nutrition_myfcd_nutrients` from the four source CSVs.

Run from `backend/`:

    python -m scripts.seed.load_nutrition_db

Idempotent: re-running upserts on (source, source_food_id) and on
(ndb_id, nutrient_name), so it's safe to invoke after a partial load.

Reads from `backend/resources/database/`:
- Anuvaad_INDB_2024.csv
- ciqual_2020.csv
- malaysian_food_calories.csv
- myfcd_basic.csv + myfcd_nutrients.csv (joined on ndb_id)

Per-source loaders + variation/synonym expansion live in `_loaders.py`
and `_variations.py`. This module is the orchestrator only.
"""

import logging
import sys
from pathlib import Path
from typing import Dict

# Ensure `src` is importable when invoked as `python -m scripts.seed.load_nutrition_db`
BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# pylint: disable=wrong-import-position,wrong-import-order
from src.configs import DATABASE_DIR  # noqa: E402
from src.crud import crud_nutrition  # noqa: E402

from scripts.seed._loaders import (  # noqa: E402
    coerce_empty_to_none as _coerce_empty_to_none,
    load_anuvaad as _load_anuvaad,
    load_ciqual as _load_ciqual,
    load_malaysian as _load_malaysian,
    load_myfcd_basic as _load_myfcd_basic,
    load_myfcd_nutrients as _load_myfcd_nutrients,
    to_float as _to_float,
)

logger = logging.getLogger(__name__)


_CSV_FILES = {
    "anuvaad": "Anuvaad_INDB_2024.csv",
    "ciqual": "ciqual_2020.csv",
    "malaysian": "malaysian_food_calories.csv",
    "myfcd_basic": "myfcd_basic.csv",
    "myfcd_nutrients": "myfcd_nutrients.csv",
}


def _verify_csvs() -> Dict[str, Path]:
    """Ensure all five expected CSVs exist; return their resolved paths."""
    paths = {key: DATABASE_DIR / name for key, name in _CSV_FILES.items()}
    missing = [str(p) for p in paths.values() if not p.exists()]
    if missing:
        raise FileNotFoundError(f"Missing nutrition CSVs: {', '.join(missing)}")
    return paths


def main() -> int:
    """Run the seed end-to-end. Returns process exit code."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    paths = _verify_csvs()

    malaysian_rows = _load_malaysian(paths["malaysian"])
    anuvaad_rows = _load_anuvaad(paths["anuvaad"])
    ciqual_rows = _load_ciqual(paths["ciqual"])
    nutrient_rows, nutrient_lookup = _load_myfcd_nutrients(paths["myfcd_nutrients"])
    myfcd_rows = _load_myfcd_basic(paths["myfcd_basic"], nutrient_lookup)

    all_food_rows = malaysian_rows + anuvaad_rows + ciqual_rows + myfcd_rows
    food_count = crud_nutrition.bulk_upsert_foods(all_food_rows)
    nutrient_count = crud_nutrition.bulk_upsert_myfcd_nutrients(nutrient_rows)

    by_source = crud_nutrition.count_foods_by_source()
    print(f"nutrition_foods: {food_count} rows upserted")
    for src, count in sorted(by_source.items()):
        print(f"  {src}: {count} rows")
    print(f"nutrition_myfcd_nutrients: {nutrient_count} rows upserted")
    return 0


# Re-exports for tests and any external module that already binds to
# the old names (kept stable across the _loaders extraction refactor)
__all__ = [
    "_coerce_empty_to_none",
    "_load_anuvaad",
    "_load_ciqual",
    "_load_malaysian",
    "_load_myfcd_basic",
    "_load_myfcd_nutrients",
    "_to_float",
    "_verify_csvs",
    "main",
]


if __name__ == "__main__":
    sys.exit(main())
