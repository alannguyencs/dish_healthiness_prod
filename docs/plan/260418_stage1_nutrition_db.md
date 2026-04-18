# Stage 1 — Nutrition DB Service (Library Only, Postgres-Backed)

**Feature**: Port the reference project's `NutritionCollectionService` into this repo as pure library code, but back it with PostgreSQL tables (`nutrition_foods` + `nutrition_myfcd_nutrients`) seeded once from the four source CSVs already shipped under `backend/resources/database/`. No pipeline wiring; ships purely so Stage 5 has a service to import.
**Plan Created:** 2026-04-18
**Status:** Plan
**Reference**:
- [Issues — 260415, Stage 1](../issues/260415.md)
- [Discussion — Food DB investigation & end-to-end redesign](../discussion/260418_food_db.md)
- [Plan — Stage 0 Personalized Food Index](./260418_stage0_personalized_food_index.md) (precedent for "library only, hidden foundation" plan shape)
- [Abstract — Dish Analysis](../abstract/dish_analysis/index.md)
- [Technical — Dish Analysis](../technical/dish_analysis/index.md)
- [Technical — Nutritional Analysis](../technical/dish_analysis/nutritional_analysis.md)
- [Technical — Personalized Food Index](../technical/dish_analysis/personalized_food_index.md)

---

## Problem Statement

1. The end-to-end redesign in `docs/discussion/260418_food_db.md` adds a curated nutrition database lookup to the dish-analysis pipeline at four user-visible touchpoints (Phase 2.1 in Stage 5, Phase 2.3 in Stage 7, Phase 2.4 read-only panels in Stage 8, and the regression gate in Stage 9). All four touchpoints share the same retrieval service.
2. The reference project at `/Volumes/wd/projects/dish_healthiness/src/service/collect_from_nutrition_db.py` already has the tuned implementation (BM25 indices per source, the 0.85/0.15 keyword/descriptor split with +0.20/+0.15 bonuses, the 0.8/0.2 keyword-vs-BM25 mix, scaled into [0.50, 0.95]) that hit NDCG@10 = 0.7744 on an 846-query eval set. Re-deriving these constants would invalidate the benchmark.
3. The four source CSVs (Anuvaad, CIQUAL, Malaysian, MyFCD basic + nutrients) are **already shipped** under `backend/resources/database/`. What is missing is (a) a service module that loads them and answers BM25 lookups, (b) a place to put the data so the service does not pay the CSV-parse cost on every process, and (c) a smoke test asserting the indices return sane top-1 hits for known queries.
4. Shipping Stage 1 unwired (no pipeline call sites) keeps the change reviewable in isolation. Stage 5 (Phase 2.1 wiring) and Stage 9 (NDCG benchmark) are the first consumers and are explicitly blocked on this PR landing.
5. **User decision (2026-04-18):** the corpus must live in PostgreSQL rather than be re-parsed from CSVs at process start. This avoids paying the ~1 s CSV-parse + variation-expansion cost in every dev / test / prod process, and gives later stages a single source of truth that can be re-seeded without redeploying.

---

## Proposed Solution

Land four artifacts in a single PR, all behind modules that nothing yet calls:

1. **Two new tables.** `nutrition_foods` (one row per food across all four source DBs, with direct columns for the four macros + a `searchable_document` text column precomputed at seed time + a `raw_data JSONB` spillover for source-specific extras) and `nutrition_myfcd_nutrients` (long-format child for MyFCD's nested nutrient list). Indices on `(source)` and on `(source, source_food_id)` for upsert idempotency.
2. **One-shot seed script** `backend/scripts/seed/load_nutrition_db.py`. Reads the five CSVs, runs the reference project's variation / synonym expansions **once** to compute each row's `searchable_document`, and bulk-upserts. Idempotent on `(source, source_food_id)`. Manual run; no startup hook.
3. **`NutritionCollectionService` library** at `backend/src/service/nutrition_db.py`. Loads rows from the DB, rebuilds the four BM25 indices in memory at first use (lazy singleton), exposes `_search_dishes_direct(user_input, top_k, min_confidence)` and `search_nutrition_database_enhanced(dish_name, related_keywords, estimated_quantity, top_k)` — same row output shape Stage 7's consolidation prompt will substitute. The runtime never sees the CSVs.
4. **`get_nutrition_service()` accessor** so Stage 5 wiring imports a single function and pays the ~1 s index-build cost exactly once per process, on the first incoming request rather than at module import.

The shape Stage 5 (and the Stage 9 benchmark) will bind to is fixed here:

```
nutrition_foods + nutrition_myfcd_nutrients (DB)
       │
       ▼  (loaded once at first request, joined for MyFCD)
NutritionCollectionService
       │
       ▼
_search_dishes_direct(text, top_k, min_confidence)
       │
       ▼
[
  {
    "matched_food_name": str,
    "source": "malaysian_food_calories" | "myfcd" | "anuvaad" | "ciqual",
    "confidence": float in [0.50, 0.95],
    "confidence_score": float in [50.0, 95.0],
    "nutrition_data": dict,         # source-specific shape; MyFCD has nested .nutrients
    "search_method": "Direct BM25",
    "raw_bm25_score": float,
    "matched_keywords": int,
    "total_keywords": int,
  },
  ...
]
```

Stage 1 deliberately does **not** wire this into `item_tasks.py` or the prompts. The only runtime code that exercises it is the smoke test.

### Why precompute `searchable_document` at seed time

The reference project recomputes per-source variations (`_generate_food_variations`, `_extract_clean_terms_from_myfcd`, `_extract_clean_terms_from_anuvaad`, `_generate_indian_food_variations`) on every service init. These maps are static — they were tuned against the eval set and are not user-data-dependent. Computing them once at seed time and persisting the result as a `TEXT` column on `nutrition_foods` means:

- The runtime hot path drops three hundred lines of variation/synonym code.
- Re-tuning the maps becomes a deliberate "re-seed" event — no risk of subtle drift from "I edited the synonym map but production has yesterday's indices".
- BM25 documents become a simple `searchable_document.split()` at index-build time.

The trade-off: changing the variations requires re-running the seed script. Acceptable — the reference project has not changed these maps in months.

### Why a lazy first-use singleton

Test collection scans `backend/src/service/`. An eager init at module import (a) blocks `pytest` collection by ~1 s, (b) crashes the whole app on startup if the DB is empty (the seed script has not been run yet), and (c) makes it impossible to import the service from a script that does not need the indices. A lazy `get_nutrition_service()` accessor pays the cost on the first real request and keeps test imports cheap.

---

## Current Implementation Analysis

### What Exists (keep as-is)

| Component | File | Status |
|-----------|------|--------|
| Source CSVs (Anuvaad, CIQUAL, Malaysian, MyFCD basic + nutrients) | `backend/resources/database/*.csv` | Keep — seed script is the only consumer |
| `RESOURCE_DIR` constant | `backend/src/configs.py` | Keep — Stage 1 adds `DATABASE_DIR` next to it |
| `Base` declarative + `SessionLocal` | `backend/src/database.py` | Keep — new ORM classes and CRUD use these unchanged |
| `rank-bm25` dependency | `requirements.txt` (root) | Keep — added by Stage 0; reused here |
| Existing `create_tables.sql` blocks | `backend/sql/create_tables.sql` | Keep — append-only addition |
| Test harness (`conftest.py`) | `backend/tests/conftest.py` | Keep — new tests plug in via the same fixtures |
| Stage 0 personalization tables | `personalized_food_descriptions` | Keep — orthogonal feature; no FK between the two |

### What Changes

| Component | Current | Proposed |
|-----------|---------|----------|
| `backend/sql/create_tables.sql` | Has `dish_image_query_prod_dev` and `personalized_food_descriptions`. | Adds `nutrition_foods` + `nutrition_myfcd_nutrients` + their indices. Append-only; idempotent `IF NOT EXISTS`. |
| `backend/src/models.py` | Has `Users`, `DishImageQuery`, `PersonalizedFoodDescription`. | Adds `NutritionFood` and `NutritionMyfcdNutrient` classes. |
| `backend/src/crud/` | Has `crud_food_image_query`, `crud_user`, `crud_personalized_food`, etc. | Adds `crud_nutrition.py` with bulk-upsert + read-by-source helpers. |
| `backend/src/service/` | Has `personalized_food_index.py` and `llm/`. | Adds `nutrition_db.py` (the `NutritionCollectionService` class + `get_nutrition_service()` accessor + module-level errors). |
| `backend/src/configs.py` | Has `RESOURCE_DIR`. | Adds `DATABASE_DIR = RESOURCE_DIR / "database"`. |
| `backend/scripts/` | Does not exist as a Python package. | Adds `backend/scripts/seed/load_nutrition_db.py` (one-shot CLI). |
| `backend/tests/` | Has Stage 0 tests + existing API tests. | Adds `test_nutrition_db.py` (smoke test) and `test_crud_nutrition.py` (CRUD coverage). |
| `requirements.txt` | Has `rank-bm25`. | No change — the seed script uses the standard-library `csv` module, no `pandas` dependency added. |

---

## Implementation Plan

### Key Workflow

Stage 1 introduces no production-runtime flow — nothing in the FastAPI app calls into `nutrition_db.py` yet. The only exercised paths are the seed script and the smoke test:

```
Operator (manual, once)
  │
  ▼
python -m scripts.seed.load_nutrition_db   (run from backend/)
  │
  ├── reads backend/resources/database/{Anuvaad_INDB_2024,ciqual_2020,malaysian_food_calories}.csv
  ├── reads myfcd_basic.csv + myfcd_nutrients.csv (joined on ndb_id)
  ├── per row: compute searchable_document via the variation / synonym maps
  └── bulk-upsert into nutrition_foods + nutrition_myfcd_nutrients
                                  (ON CONFLICT (source, source_food_id) DO UPDATE)
  │
  ▼
DB now populated.

------------------------------------------------------------

Smoke test (pytest)
  │
  ▼
patch crud_nutrition.get_all_foods_grouped_by_source → fixture rows
  │
  ▼
NutritionCollectionService()  builds 4 BM25 indices in-memory
  │
  ▼
service._search_dishes_direct("chicken rice", top_k=5, min_confidence=0.5)
  │
  ▼
[{matched_food_name: "Chicken Rice", source: "malaysian_food_calories",
  confidence: 0.91, ...}, ...]
```

The contract frozen here is what Stage 5 will bind against. Concretely:

- `get_nutrition_service()` returns the same `NutritionCollectionService` instance for the lifetime of the process. Stage 5 imports the accessor, never the class directly.
- Each row in the result list carries the **superset** of fields the consolidation prompt (Stage 7) will read. Adding a field is safe; renaming or removing one is a breaking change.
- Confidence is **per call**: it is a function of the query, not a static rank. Re-querying with different tokens gives different confidences. Stage 7 thresholds (`THRESHOLD_DB_INCLUDE = 0.80`) bind against this exact `confidence` field.

#### To Delete

None.

#### To Update

None — all four artifacts are additive. The only files modified in-place are `backend/sql/create_tables.sql`, `backend/src/models.py`, and `backend/src/configs.py`.

#### To Add New

- The workflow above is fully implemented by the new tables, CRUD module, service module, and seed script. No callers exist yet.

---

### Database Schema

All schema lives in `backend/sql/create_tables.sql` (this project has no migration runner — the file is executed wholesale at boot, so every statement must be `IF [NOT] EXISTS` idempotent). The DDL below is appended to that file.

```sql
-- Table: nutrition_foods
-- Unified row table for the four source nutrition databases. One row per
-- food item across all sources. Direct columns for the four macros +
-- standard serving fields; raw_data JSONB stores source-specific
-- extras (full Anuvaad nutrient set, CIQUAL micros, Malaysian portion
-- description, etc.). searchable_document is precomputed at seed time
-- (variations + synonyms expanded once) so the runtime BM25 index build
-- is a simple split().
CREATE TABLE IF NOT EXISTS nutrition_foods (
    id SERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    source_food_id TEXT NOT NULL,
    food_name TEXT NOT NULL,
    food_name_eng TEXT,
    category TEXT,
    searchable_document TEXT NOT NULL,
    calories FLOAT,
    carbs_g FLOAT,
    protein_g FLOAT,
    fat_g FLOAT,
    fiber_g FLOAT,
    serving_size_grams FLOAT,
    serving_unit TEXT,
    raw_data JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);

-- Source filter (service partitions the corpus by source before BM25)
CREATE INDEX IF NOT EXISTS idx_nutrition_foods_source
    ON nutrition_foods(source);

-- Idempotent upsert key for the seed script
CREATE UNIQUE INDEX IF NOT EXISTS uq_nutrition_foods_source_food_id
    ON nutrition_foods(source, source_food_id);

-- Table: nutrition_myfcd_nutrients
-- Long-format MyFCD nutrient detail. Joined back to the parent
-- nutrition_foods row by (source='myfcd', source_food_id=ndb_id) so the
-- service can reconstruct the nested .nutrients dict that downstream
-- consumers expect.
CREATE TABLE IF NOT EXISTS nutrition_myfcd_nutrients (
    id SERIAL PRIMARY KEY,
    ndb_id TEXT NOT NULL,
    nutrient_name TEXT NOT NULL,
    value_per_100g FLOAT,
    value_per_serving FLOAT,
    unit TEXT,
    category TEXT
);

-- Lookup by parent food (service load path)
CREATE INDEX IF NOT EXISTS idx_nutrition_myfcd_nutrients_ndb_id
    ON nutrition_myfcd_nutrients(ndb_id);

-- Idempotent upsert key for the seed script
CREATE UNIQUE INDEX IF NOT EXISTS uq_nutrition_myfcd_nutrients_ndb_nutrient
    ON nutrition_myfcd_nutrients(ndb_id, nutrient_name);
```

Column notes for `nutrition_foods`:

| Column | Type | Nullable | Source-specific notes |
|---|---|---|---|
| `id` | SERIAL PK | no | Surrogate key |
| `source` | TEXT | no | One of `malaysian_food_calories`, `myfcd`, `anuvaad`, `ciqual`. Reference-project naming preserved so Stage 7 prompt strings stay verbatim. |
| `source_food_id` | TEXT | no | Anuvaad → `food_code` (e.g. `ASC001`); MyFCD → `ndb_id` (`R101061`); CIQUAL → `food_code`; Malaysian → derived from `source_file` filename (e.g. `ang_koo_kuih_mungbean`) since Malaysian CSV has no native ID column |
| `food_name` | TEXT | no | Native-language name. Malaysian → `food_item`; others → `food_name`. |
| `food_name_eng` | TEXT | yes | CIQUAL only. Used as primary display name when present (matches reference `_get_display_name`). |
| `category` | TEXT | yes | Malaysian → `category`; CIQUAL → `food_group_name`; others → `NULL` |
| `searchable_document` | TEXT | no | Precomputed at seed time: normalized food name + variations + synonyms + per-source clean terms. Service splits on whitespace to build the BM25 corpus. |
| `calories`, `carbs_g`, `protein_g`, `fat_g`, `fiber_g` | FLOAT | yes | Per-100g for Anuvaad/CIQUAL; per-serving for Malaysian/MyFCD. The consumer (Stage 5+) is responsible for portion scaling. |
| `serving_size_grams`, `serving_unit` | FLOAT, TEXT | yes | MyFCD has both; Malaysian has unit only (`portion_size`); Anuvaad has unit only (`servings_unit`); CIQUAL has neither |
| `raw_data` | JSONB | no | Full source row (every column from the CSV). Lets Stage 7 read source-specific extras (e.g. CIQUAL micros) without schema migration. |
| `created_at`, `updated_at` | TIMESTAMP | no | Set on insert; `updated_at` bumped on upsert. |

Column notes for `nutrition_myfcd_nutrients`:

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `id` | SERIAL PK | no | Surrogate key |
| `ndb_id` | TEXT | no | FK target — joined to `nutrition_foods.source_food_id` where `source = 'myfcd'`. **Soft join** (no DB-level FK) because the nutrient table only carries values for MyFCD rows; a hard FK would require `nutrition_foods.source_food_id` to be unique globally, which it is not (Anuvaad and CIQUAL share the `ASC###` numeric range). |
| `nutrient_name` | TEXT | no | e.g. `Energy`, `Protein`, `Carbohydrate` |
| `value_per_100g`, `value_per_serving` | FLOAT | yes | Direct from MyFCD CSV |
| `unit` | TEXT | yes | e.g. `Kcal`, `g`, `mg` |
| `category` | TEXT | yes | e.g. `Proximates`, `Minerals`, `Vitamins` |

SQLAlchemy models (appended to `backend/src/models.py`):

```python
class NutritionFood(Base):
    __tablename__ = "nutrition_foods"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String, nullable=False)
    source_food_id = Column(String, nullable=False)
    food_name = Column(String, nullable=False)
    food_name_eng = Column(String, nullable=True, default=None)
    category = Column(String, nullable=True, default=None)
    searchable_document = Column(String, nullable=False)
    calories = Column(Float, nullable=True, default=None)
    carbs_g = Column(Float, nullable=True, default=None)
    protein_g = Column(Float, nullable=True, default=None)
    fat_g = Column(Float, nullable=True, default=None)
    fiber_g = Column(Float, nullable=True, default=None)
    serving_size_grams = Column(Float, nullable=True, default=None)
    serving_unit = Column(String, nullable=True, default=None)
    raw_data = Column(JSON, nullable=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)


class NutritionMyfcdNutrient(Base):
    __tablename__ = "nutrition_myfcd_nutrients"

    id = Column(Integer, primary_key=True, index=True)
    ndb_id = Column(String, nullable=False, index=True)
    nutrient_name = Column(String, nullable=False)
    value_per_100g = Column(Float, nullable=True, default=None)
    value_per_serving = Column(Float, nullable=True, default=None)
    unit = Column(String, nullable=True, default=None)
    category = Column(String, nullable=True, default=None)
```

`Float` is added to the existing SQLAlchemy import block on `backend/src/models.py` if Stage 0 has not already done so.

#### To Delete

None.

#### To Update

- `backend/sql/create_tables.sql` — append the two `CREATE TABLE IF NOT EXISTS` blocks plus their four indices.
- `backend/src/models.py` — append the two ORM classes; ensure `Float` is in the `sqlalchemy` import.
- `backend/src/configs.py` — add `DATABASE_DIR = RESOURCE_DIR / "database"` directly under the existing `RESOURCE_DIR` block. Do not call `.mkdir(exist_ok=True)` on it — the directory already exists with the shipped CSVs, and a stray `mkdir` would mask "the operator deleted my CSVs by accident".

#### To Add New

- None as a standalone file — schema lives in `backend/sql/create_tables.sql`.

---

### CRUD

New module `backend/src/crud/crud_nutrition.py`. All functions open and close their own `SessionLocal`, matching `dish_query_basic.py` / `crud_personalized_food.py` style.

```python
def bulk_upsert_foods(rows: List[Dict[str, Any]]) -> int:
    """
    INSERT ... ON CONFLICT (source, source_food_id) DO UPDATE.

    Each row dict must carry every required column. Returns the number of
    rows processed (NOT differentiating insert vs update; Postgres does
    not expose this cleanly via SQLAlchemy Core).

    Sets created_at on first insert; bumps updated_at on every upsert.
    """

def bulk_upsert_myfcd_nutrients(rows: List[Dict[str, Any]]) -> int:
    """
    INSERT ... ON CONFLICT (ndb_id, nutrient_name) DO UPDATE.
    """

def get_all_foods_grouped_by_source() -> Dict[str, List[NutritionFood]]:
    """
    Single SELECT * grouped in Python by source. Returns:
        {
          "malaysian_food_calories": [NutritionFood, ...],
          "myfcd": [NutritionFood, ...],
          "anuvaad": [NutritionFood, ...],
          "ciqual": [NutritionFood, ...],
        }
    Sources missing from the DB return [] (do not raise).
    Used by NutritionCollectionService at first-use init.
    """

def get_myfcd_nutrients_grouped_by_ndb_id() -> Dict[str, List[NutritionMyfcdNutrient]]:
    """
    Single SELECT * grouped in Python by ndb_id. Returns a dict keyed
    by ndb_id with the list of long-format nutrient rows for each food.
    Used by NutritionCollectionService to reconstruct the nested
    .nutrients dict on each MyFCD food.
    """

def count_foods_by_source() -> Dict[str, int]:
    """
    SELECT source, COUNT(*) GROUP BY source.
    Used by the seed script's idempotent re-run summary.
    """
```

Behavior:

- Bulk-upserts use SQLAlchemy Core's `insert(...).on_conflict_do_update(...)` against the unique indices defined above. Reasonable batch size (`chunk=500`) for the ~4,500-row total.
- Reads (`get_all_foods_grouped_by_source`, `get_myfcd_nutrients_grouped_by_ndb_id`) issue exactly **one SELECT each** and group in Python. This is the right shape because the service rebuilds in-memory BM25 indices from the full corpus at first use; a per-source query loop would do four round-trips for no benefit.
- All reads return ORM objects (not dicts) — the service is allowed to reach into `row.searchable_document`, `row.food_name`, `row.raw_data`.

#### To Delete

None.

#### To Update

None.

#### To Add New

- `backend/src/crud/crud_nutrition.py` — the five functions above plus a module-level docstring.
- The module is **not** re-exported from any facade. Callers (the seed script and the service) import directly via `from src.crud import crud_nutrition`. Same convention as `crud_personalized_food` from Stage 0.

---

### Services

New module `backend/src/service/nutrition_db.py`. Class + module-level lazy accessor + module-level error types.

```python
class NutritionCollectionError(Exception):
    """Base exception for nutrition collection operations."""


class NutritionDBEmptyError(NutritionCollectionError):
    """Raised on first-use when the nutrition_foods table is empty."""


class NutritionCollectionService:
    """
    BM25-backed nutrition lookup over the four source DBs.

    Loads the full corpus from `nutrition_foods` (+ `nutrition_myfcd_nutrients`
    for MyFCD's nested nutrient detail) into memory exactly once per
    instance and builds four per-source BM25 indices. All public methods
    return rows in the verbatim shape Stage 7's consolidation prompt
    expects.
    """

    def __init__(self) -> None:
        grouped = crud_nutrition.get_all_foods_grouped_by_source()
        if not any(grouped.values()):
            raise NutritionDBEmptyError(
                "nutrition_foods is empty. Run "
                "`python -m scripts.seed.load_nutrition_db` from backend/."
            )

        myfcd_nutrients = crud_nutrition.get_myfcd_nutrients_grouped_by_ndb_id()

        self.malaysian_foods = self._materialize(grouped["malaysian_food_calories"])
        self.myfcd_foods = self._materialize_myfcd(grouped["myfcd"], myfcd_nutrients)
        self.anuvaad_foods = self._materialize(grouped["anuvaad"])
        self.ciqual_foods = self._materialize(grouped["ciqual"])

        self._build_bm25_indices()
        self._current_dish_tokens: Optional[Set[str]] = None

    def _search_dishes_direct(
        self,
        user_input: str,
        top_k: int = 10,
        min_confidence: float = 0.1,
    ) -> List[Dict[str, Any]]:
        """
        Direct token-vs-corpus BM25 search across all four indices.
        Returns rows in the row-output shape documented above.
        """

    def search_nutrition_database_enhanced(
        self,
        dish_name: str,
        related_keywords: str,
        estimated_quantity: str,
        top_k: int = 10,
    ) -> Dict[str, Any]:
        """
        Enhanced search using the dish_name as PRIORITY tokens and a
        comma-separated `related_keywords` string as descriptor tokens.
        Sets `self._current_dish_tokens` so the BM25 confidence formula
        weights core-dish-name matches over generic descriptors.
        """


def get_nutrition_service() -> NutritionCollectionService:
    """
    Lazy singleton accessor. Builds the service on first call; returns
    the same instance thereafter. Stage 5 imports this; never the class.
    """
```

Key implementation details Stage 5 / Stage 7 / Stage 9 will depend on:

- **Confidence formula — verbatim port from `_direct_bm25_search`.** Keep the constants exactly as in reference: 0.85 core-dish + 0.15 descriptors → +0.20 if matched ≥ 2 core tokens → +0.15 more if matched ≥ 3 → mix `0.8 × keyword_score + 0.2 × log(1+raw)/log(1+max_raw)` → final scale `0.50 + base × 0.45` capped at 0.95. Altering any constant invalidates the Stage 9 NDCG benchmark.
- **`_get_display_name` mapping.** Preserved exactly: CIQUAL prefers `food_name_eng`; Malaysian uses `food_name` (was `food_item` in the source CSV — the seed script renames at load time so the runtime sees a uniform field); Anuvaad and MyFCD use `food_name`.
- **Per-source BM25 indices, not unified.** Each source has its own vocabulary (Malaysian + romanized Malay; Anuvaad + Hindi-derived terms; CIQUAL + French; MyFCD + clinical descriptors). A unified BM25 would dilute the term-frequency signal. The reference proved per-source on the 846-query benchmark — keep it.
- **Dish-token weighting** lives in `_current_dish_tokens` (instance attribute set inside `search_nutrition_database_enhanced`, read inside `_direct_bm25_search`). When unset (i.e. when `_search_dishes_direct` is called directly), `_direct_bm25_search` falls back to "all input tokens are dish tokens" — same as reference.
- **Logging.** Use the standard `logging` module (`logger = logging.getLogger(__name__)`) for INFO-level "indices built, N rows per source" once-per-process. Drop the reference's `print("[BM25 DEBUG] ...")` per-search noise — that was development scaffolding and would spam production logs at every Phase 2.1 call in Stage 5.
- **Lazy singleton.** `get_nutrition_service()` holds a module-level `_INSTANCE: Optional[NutritionCollectionService] = None` and a `threading.Lock()` to make first-call init thread-safe (FastAPI may handle two near-simultaneous requests during process warm-up). Subsequent calls do an unlocked `if _INSTANCE is not None: return _INSTANCE` fast path.
- **Error contract on empty DB.** `NutritionDBEmptyError` carries a message that names the seed command (`python -m scripts.seed.load_nutrition_db`). Stage 5's wiring should let this propagate as a 500 the first time it happens — that is the deploy-time signal that the seed step was missed.

#### To Delete

None.

#### To Update

None.

#### To Add New

- `backend/src/service/nutrition_db.py` — class, lazy accessor, module-level errors.
- `backend/src/configs.py` — `DATABASE_DIR = RESOURCE_DIR / "database"` (already covered above; called out again here because it is the only configs change Stage 1 ships).

---

### Seed Script

New script `backend/scripts/seed/load_nutrition_db.py`. CLI entry point; creates `backend/scripts/__init__.py` and `backend/scripts/seed/__init__.py` so `python -m scripts.seed.load_nutrition_db` works from `backend/`.

The script's responsibilities:

1. **Verify CSVs.** Check all five paths under `DATABASE_DIR` exist; raise `FileNotFoundError` with the missing-path list if not.
2. **Load each source.** Use the standard-library `csv.DictReader` per file. Coerce `''` and `'nan'` cell strings to `None`. Coerce numeric columns (`calories`, `carbs_g`, etc.) to `float` after the empty-string check; non-numeric source rows skip the column rather than raise.
3. **Per-row variation expansion (one-shot).** Run the full reference-project chain in the seed script (and only here):
   - `_normalize_text` → NFKD + lowercase + strip.
   - `_create_searchable_document(food_dict, source)` → emits the variation list per source (Malaysian + Anuvaad call `_generate_food_variations`; MyFCD calls `_extract_clean_terms_from_myfcd`; Anuvaad also calls `_extract_clean_terms_from_anuvaad` + `_generate_indian_food_variations`; CIQUAL emits the English name + group + subgroup).
   - Concatenate, normalize, and store as the `searchable_document` column.
4. **Map source columns onto the unified row.** Per source:
   - **Malaysian** — `source_food_id = source_file.replace('.json','')`, `food_name = food_item`, `category = category`, `calories = calories`, `serving_unit = portion_size`, `raw_data = full row`.
   - **Anuvaad** — `source_food_id = food_code`, `food_name = food_name`, `calories = energy_kcal`, `carbs_g = carb_g`, `protein_g = protein_g`, `fat_g = fat_g`, `fiber_g = fibre_g`, `serving_unit = servings_unit`, `raw_data = full row` (the raw row carries every micronutrient column for Stage 7's micronutrient surfacing).
   - **CIQUAL** — `source_food_id = food_code`, `food_name = food_name`, `food_name_eng = food_name_eng`, `category = food_group_name`, `calories = "Energy, Regulation EU No 1169/2011 (kcal/100g)"`, `carbs_g = "Carbohydrate (g/100g)"`, `protein_g = "Protein (g/100g)"`, `fat_g = "Fat (g/100g)"`, `fiber_g = "Fibres (g/100g)"`, `raw_data = full row`.
   - **MyFCD** — `source_food_id = ndb_id`, `food_name = food_name`, `serving_size_grams = serving_size_grams`, `serving_unit = serving_unit`, `raw_data = basic row`. Direct macro columns are populated from the joined `nutrition_myfcd_nutrients` rows where available (Energy → `calories`, Carbohydrate → `carbs_g`, Protein → `protein_g`, Fat → `fat_g`, "Total dietary fibre" → `fiber_g`), reading `value_per_serving` first and falling back to `value_per_100g` × `serving_size_grams / 100`.
5. **Bulk-upsert.** Call `crud_nutrition.bulk_upsert_foods(...)` and `crud_nutrition.bulk_upsert_myfcd_nutrients(...)`. Idempotent — re-running the script leaves the DB in the same state.
6. **Print a one-line summary** (`stdout`) per source: `malaysian_food_calories: 60 rows`, `myfcd: 233 rows (+1,247 nutrient rows)`, `anuvaad: 1014 rows`, `ciqual: 3186 rows` — exact numbers come from `count_foods_by_source` after the upsert.

`stdlib csv` is intentional. `pandas` is the reference's choice but only because `pd.read_csv + df.where(pd.notna(df), None)` is convenient for NaN coercion. The five CSVs in this repo are well-formed (4,493 rows total — small enough for pure-Python parsing); a 30-line per-source loader plus a `_coerce_empty_to_none(value)` helper covers what `pandas` does, without adding a 50 MB dependency that no other module in this codebase needs. Decision recorded in **Resolved Decisions** below.

#### To Delete

None.

#### To Update

None.

#### To Add New

- `backend/scripts/__init__.py` — empty package marker.
- `backend/scripts/seed/__init__.py` — empty package marker.
- `backend/scripts/seed/load_nutrition_db.py` — the CLI entry point + per-source loaders + variation/synonym helpers (verbatim from reference; comment-block at the top of each helper noting "DO NOT EDIT WITHOUT RE-SEEDING + RE-RUNNING STAGE 9 BENCHMARK").

---

### API Endpoints

None. Stage 1 exposes no HTTP surface. Endpoint changes begin at Stage 5 (`item_tasks.py` adds an inline call to `extract_and_lookup_nutrition`) and Stage 7 (prompt rewrite). No new routes anywhere in the chain.

#### To Delete

None.

#### To Update

None.

#### To Add New

None.

---

### Testing

Test location: `backend/tests/`. Tests use the existing `conftest.py` harness. Follow the style of `test_personalized_food_index.py` (patch the CRUD layer with hand-crafted rows; service is exercised purely in-process; no real DB hit).

**Unit tests — Service (`backend/tests/test_nutrition_db.py`):**

- `test_service_raises_on_empty_db` — patch `crud_nutrition.get_all_foods_grouped_by_source` to return `{src: [] for src in 4 sources}`. Constructing `NutritionCollectionService()` raises `NutritionDBEmptyError`; the message contains `python -m scripts.seed.load_nutrition_db`.
- `test_service_builds_four_indices` — patch CRUD with one fixture row per source. Service initializes; `len(service.malaysian_foods) == 1`, same for the other three. (Smoke that the four-source split survives the DB round-trip.)
- `test_search_returns_top_1_from_expected_source` — table-driven, three cases:
   - query `"ayam goreng"` → top-1 source is `malaysian_food_calories` or `anuvaad`, confidence > 0.5
   - query `"daal tadka"` → top-1 source is `anuvaad`, confidence > 0.5
   - query `"quiche lorraine"` → top-1 source is `ciqual`, confidence > 0.5
   Hand-crafted fixture has 1–2 rows per source carrying these dish names with appropriate `searchable_document` values. **This is the issue's "done when" smoke check.**
- `test_search_chicken_rice_above_confidence_floor` — fixture has a `Chicken Rice` row in `malaysian_food_calories`. `service._search_dishes_direct("chicken rice", top_k=5)` returns at least one row; the top result has `confidence > 0.5`. **This is the issue's stronger acceptance line.**
- `test_search_returns_row_output_shape` — every result dict has exactly the keys `{matched_food_name, source, confidence, confidence_score, nutrition_data, search_method, raw_bm25_score, matched_keywords, total_keywords}`. `search_method == "Direct BM25"`. (Stage 7 binds against this shape — do not change without updating Stage 7's prompt placeholders.)
- `test_search_filters_below_min_confidence` — query that no fixture row matches; `min_confidence=0.85` → `[]`. `min_confidence=0.0` → top results returned.
- `test_search_caps_at_top_k` — fixture with 10 rows, `top_k=3` → exactly 3 results.
- `test_enhanced_search_weights_dish_tokens_over_descriptors` — two fixtures: row A matches dish-name tokens; row B matches only descriptor tokens. `search_nutrition_database_enhanced("nasi goreng", "rice,fried", "1 plate")` ranks A above B because `_current_dish_tokens` weighting kicks in.
- `test_get_nutrition_service_is_singleton` — two calls to `get_nutrition_service()` return the same `id(...)`. (Use `monkeypatch` to reset the module-level `_INSTANCE` between tests so this does not leak.)
- `test_myfcd_row_carries_nested_nutrients` — fixture has one MyFCD `nutrition_foods` row + 3 `nutrition_myfcd_nutrients` rows for that ndb_id. `service.myfcd_foods[0]['nutrients']` is a dict keyed by `nutrient_name`, each value carrying `value_per_100g / value_per_serving / unit / category` — exactly the shape Stage 5's nutrition aggregator expects.

**Unit tests — CRUD (`backend/tests/test_crud_nutrition.py`):**

- `test_bulk_upsert_foods_inserts_then_updates_on_conflict` — first call inserts; second call with the same `(source, source_food_id)` updates `food_name` and bumps `updated_at`.
- `test_bulk_upsert_myfcd_nutrients_inserts_then_updates_on_conflict` — same shape against `(ndb_id, nutrient_name)`.
- `test_get_all_foods_grouped_by_source_partitions_correctly` — seed 2 rows per source; assert dict keys cover all four sources and each list has the right length.
- `test_get_myfcd_nutrients_grouped_by_ndb_id_returns_per_food_lists` — seed 2 ndb_ids × 3 nutrients each; assert two top-level keys, each with three nutrient rows.
- `test_count_foods_by_source_reports_zero_for_unseen_sources` — seed only Malaysian; the returned dict still includes `myfcd: 0`, `anuvaad: 0`, `ciqual: 0`. (Lets the seed script print a stable summary even on a partial load.)

**Unit tests — Seed script (`backend/tests/test_seed_load_nutrition_db.py`):**

- `test_searchable_document_includes_variations` — feed a single Malaysian fixture (`food_item="Nasi Lemak"`); the precomputed `searchable_document` includes `nasi`, `lemak`, `rice` (synonym), `coconut milk` (synonym).
- `test_myfcd_basic_and_nutrients_join` — feed a one-row basic + three-row nutrients fixture; the upserted `nutrition_foods.calories` is populated from the `Energy` nutrient's `value_per_serving`.
- `test_idempotent_rerun` — call the loader twice with the same input; total row counts are identical and `updated_at > created_at` on the second pass.

**Smoke / integration test (manual, not in CI):**

- After running the seed script against a dev DB, the operator runs:
  ```python
  from src.service.nutrition_db import get_nutrition_service
  svc = get_nutrition_service()
  assert svc._search_dishes_direct("chicken rice", top_k=5)[0]["confidence"] > 0.5
  ```
  This is the acceptance line from the issue. Do **not** add it as an automated test (it would require a populated dev DB in the CI runner); document it in the test file's module docstring as the "manual smoke check post-seed".

**Pre-commit loop** (mandatory per skill rules):

1. `source venv/bin/activate && pre-commit run --all-files`.
2. Fix any issues (e.g. lint errors, Python line-count violations — `nutrition_db.py` will hover near the 300-line cap; if it crosses, extract `_direct_bm25_search` into a sibling private module rather than papering with cosmetic line shuffling).
3. Re-run pre-commit — Prettier may reformat fixes and push files back over the line limit (300 lines per frontend file; no frontend files land in Stage 1, but still run the loop). If so, fix durably (extract helpers, not pylint disables).
4. Repeat until pre-commit passes cleanly on a full re-run with zero new failures.

**Acceptance check from the issue's "done when":**

- The dev DB has 4,493 rows in `nutrition_foods` after the one-shot seed.
- `from src.service.nutrition_db import get_nutrition_service; get_nutrition_service()._search_dishes_direct("chicken rice", top_k=5)` returns results with the top hit at `confidence > 0.5`.
- The smoke test (`test_search_returns_top_1_from_expected_source`) passes locally and in CI (DB-free, fixture-driven).

#### To Delete

None.

#### To Update

None (existing tests are untouched).

#### To Add New

- `backend/tests/test_nutrition_db.py` — service tests above.
- `backend/tests/test_crud_nutrition.py` — CRUD tests above.
- `backend/tests/test_seed_load_nutrition_db.py` — seed-script tests above.

---

### Frontend

None. Stage 1 ships no UI. The first stage that changes the React surface is Stage 8 (Phase 2.4 review panels).

#### To Delete

None.

#### To Update

None.

#### To Add New

None.

---

### Documentation

Stage 1 is a hidden foundation with no user-facing behavior, but it introduces two new tables, a CRUD module, a service singleton, and a seed script that future stages will document against. Capture the foundation now so Stages 5/7/9 extend — not introduce — the documentation.

#### Abstract (`docs/abstract/`)

No changes needed — Stage 1 has zero user-visible behavior change. The user-facing narrative for the curated nutrition database (Phase 2.1 evidence chip row, Phase 2.3 reasoning citing DB matches, Phase 2.4 top-5 panel) lands with Stages 5, 7, and 8 respectively. Adding abstract copy now would describe behavior that does not yet exist. Same rationale applied in Stage 0.

#### Technical (`docs/technical/`)

- **Add new** `docs/technical/dish_analysis/nutrition_db.md` — the canonical technical page for the two tables + CRUD + service module + seed script:
  - **Architecture** — per-source BM25 corpus loaded from PostgreSQL into memory at first request; lazy `get_nutrition_service()` singleton; precomputed `searchable_document` keeps the runtime hot path off the variation / synonym maps.
  - **Data Model** — `NutritionFood` and `NutritionMyfcdNutrient` ORM classes, full column tables mirroring the ones in this plan, indices (`idx_nutrition_foods_source`, `uq_nutrition_foods_source_food_id`, `idx_nutrition_myfcd_nutrients_ndb_id`, `uq_nutrition_myfcd_nutrients_ndb_nutrient`), the soft-FK rationale.
  - **Pipeline** — vertical ASCII diagram showing operator → seed script → DB → first request → singleton init → BM25 indices → caller. Arriving callers (Stage 5, Stage 9) are placeholder boxes with forward links.
  - **Algorithms** — bullet list of the confidence formula constants (0.85/0.15, +0.20/+0.15, 0.8/0.2, 0.50–0.95 scale) with the explicit "DO NOT EDIT WITHOUT RE-RUNNING STAGE 9 BENCHMARK" note.
  - **Backend — Service Layer** — signatures of `_search_dishes_direct`, `search_nutrition_database_enhanced`, `get_nutrition_service`; return-row shape; thread-safety note for the singleton.
  - **Backend — CRUD Layer** — signatures of the five CRUD functions.
  - **External Integrations** — none (rank-bm25 is in-process; CSVs are local).
  - **Constraints & Edge Cases** — empty DB raises `NutritionDBEmptyError`; first request takes ~1 s; per-source partitioning is intentional; `searchable_document` precomputation means variation-map edits require re-seed.
  - **Component Checklist** — boxes for both tables + indices + ORM classes + CRUD funcs + service class + accessor + seed script + tests. Stage 1 ships all checked; future stages append rows in-place rather than creating new pages.
- **Update** `docs/technical/dish_analysis/index.md` — add row 5 `[Nutrition DB](./nutrition_db.md)` after the existing Personalized Food Index row.
- **Update** `docs/technical/dish_analysis/personalized_food_index.md` — change the bottom navigation from `[< Prev: Nutritional Analysis](./nutritional_analysis.md) | [Parent](./index.md)` to `[< Prev: Nutritional Analysis](./nutritional_analysis.md) | [Parent](./index.md) | [Next: Nutrition DB >](./nutrition_db.md)` (top nav block too — both must match).
- **Update** `docs/technical/dish_analysis/nutritional_analysis.md` — no change required at Stage 1 (the consolidation prompt that consumes the DB matches arrives in Stage 7). Leave the existing Component Checklist unchanged.

#### API Documentation (`docs/api_doc/`)

No changes needed — Stage 1 adds no API endpoints. The project does not yet ship a `docs/api_doc/` tree; no seeding is required for this stage.

#### To Delete

None.

#### To Update

- `docs/technical/dish_analysis/index.md` — append row 5.
- `docs/technical/dish_analysis/personalized_food_index.md` — extend top + bottom nav with `Next: Nutrition DB >`.

#### To Add New

- `docs/technical/dish_analysis/nutrition_db.md` — full per-feature technical page per the template in `documentation_hierarchy.md`.

---

### Chrome Claude Extension Execution

**Skipped for Stage 1.** Same rationale as Stage 0: no UI, no observable HTTP behavior, so the Chrome Claude Extension E2E harness has nothing to click. The first stage that changes user-visible state for the nutrition-DB feature is Stage 5 (`result_gemini.nutrition_db_matches` becomes a key on the response payload). Chrome tests resume there.

If a Chrome spec is wanted regardless (e.g. to confirm the new tables and the seed script did not break the existing dish-analysis flow), the user can request `/webapp-dev:chrome-test-generate` directly to write a sign-in + upload smoke test under `docs/chrome_test/`. Default is to skip.

#### To Delete

None.

#### To Update

None.

#### To Add New

None.

---

## Dependencies

- **Stage 0** — Stage 1 reuses `rank-bm25` (added by Stage 0 to `requirements.txt`). It does not otherwise touch the `personalized_food_descriptions` schema.
- **Existing tables** — `users`, `dish_image_query_prod_dev`, `personalized_food_descriptions` are untouched. The two new tables FK nothing on the user / dish side; they are pure reference data.
- **Existing ORM** — `Base` declarative + `SessionLocal` in `backend/src/database.py`.
- **Source CSVs already present** — `backend/resources/database/{Anuvaad_INDB_2024,ciqual_2020,malaysian_food_calories,myfcd_basic,myfcd_nutrients}.csv`. Re-shipping is not in scope.
- **No downstream consumers yet** — Stage 5 (Phase 2.1 wiring) and Stage 9 (NDCG benchmark) are the first consumers and are explicitly blocked on this PR landing.

---

## Resolved Decisions

- **Storage backend — PostgreSQL, not in-memory CSV cache** (confirmed 2026-04-18). Reference project re-parses the CSVs at every service init; this project pays once at seed time, persists in DB, and the runtime issues two SELECTs per process. Trade-off: a deploy-time seed step (`python -m scripts.seed.load_nutrition_db`) becomes mandatory; missing-the-step is detected at first service call (`NutritionDBEmptyError`) so it cannot silently degrade.
- **Table shape — unified `nutrition_foods` row table + separate `nutrition_myfcd_nutrients` long-format child** (confirmed 2026-04-18, "Option C"). Direct columns for the four macros where the source has them; `raw_data JSONB` spillover for source-specific extras (CIQUAL micros, Anuvaad full nutrient set). Two tables instead of five; lets Stage 7 read either the direct columns OR the JSONB blob without changing the read path.
- **Singleton init mode — lazy first-use accessor `get_nutrition_service()`** (confirmed 2026-04-18). Eager-at-import would block test collection by ~1 s and crash on import when the DB is empty (which it always is during fresh-clone setup, before the seed script runs). Lazy init pays the cost on the first real request and keeps test imports cheap.
- **Seed script location — `backend/scripts/seed/load_nutrition_db.py`, manual one-shot** (confirmed 2026-04-18). Not a startup hook (would silently re-seed on every dev restart with no logs about partial loads); not a migration (project's `create_tables.sql` is DDL-only, no DML allowed). The script is invoked once after the DDL lands; idempotent on re-run.
- **CSV reader — stdlib `csv` module, no `pandas` dependency** (decision recorded by the planner; flag below). Pandas would mirror reference verbatim but adds a ~50 MB runtime dependency that no other module in this codebase needs. The five CSVs total 4,493 rows — small enough for pure-Python parsing. A `_coerce_empty_to_none(value)` helper covers what `df.where(pd.notna(df), None)` does in the reference. Re-open the decision if (a) the project later adopts pandas for analytics, OR (b) a future source DB ships in a format that materially benefits from pandas (e.g. multi-sheet xlsx).
- **`searchable_document` precomputation at seed time, not at service init** (decision recorded by the planner). Variations / synonyms in the reference are static and tuned against the eval set. Computing once at seed time drops three hundred lines of variation logic from the runtime hot path. Trade-off: editing the variation maps requires re-seeding. Acceptable — the maps have not changed in months.
- **Logging policy — `logging.getLogger(__name__)` for once-per-process INFO; drop `print("[BM25 DEBUG]")` per-search statements from the reference** (decision recorded by the planner). The reference's per-search prints were development scaffolding; in this project they would spam logs at every Phase 2.1 call (Stage 5).

## Open Questions

None — all decisions resolved 2026-04-18. Ready for implementation.
