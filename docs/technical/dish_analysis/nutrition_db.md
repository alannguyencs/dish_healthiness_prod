# Nutrition DB — Technical Design

[< Prev: Personalized Food Index](./personalized_food_index.md) | [Parent](./index.md)

## Related Docs

- Plan: [docs/plan/260418_stage1_nutrition_db.md](../../plan/260418_stage1_nutrition_db.md)
- Discussion: [docs/discussion/260418_food_db.md](../../discussion/260418_food_db.md) — end-to-end redesign this foundation unblocks
- Precedent: [docs/plan/260418_stage0_personalized_food_index.md](../../plan/260418_stage0_personalized_food_index.md) — same "library only, hidden foundation" pattern

## Architecture

Two PostgreSQL tables hold the curated nutrition corpus ported from the reference project's four source CSVs (Anuvaad INDB 2024, CIQUAL 2020, Malaysian Food Calories, MyFCD). A seed script (`scripts/seed/load_nutrition_db.py`) ingests the CSVs once and precomputes each row's `searchable_document`; the runtime `NutritionCollectionService` reads every row on first use, rebuilds four per-source BM25 indices in memory, and answers dish-name lookups with the verbatim row shape Stage 7's consolidation prompt expects.

```
+--------------------+         +----------------------------+
|  Operator (manual) | ----->  |  scripts/seed/             |
|  one-shot seed     |         |  load_nutrition_db.py      |
+--------------------+         +------------+---------------+
                                            |
                                            v
+-------------------------------------------+-----------------+
|  PostgreSQL                                                |
|   nutrition_foods (one row per food, 4 sources)            |
|   nutrition_myfcd_nutrients (long-format child)            |
+------------+-----------------------------------------------+
             |
             v
+------------+-----------------------------------------------+
|  src/service/nutrition_db.py                               |
|    NutritionCollectionService (lazy singleton)             |
|    _search_dishes_direct(user_input, top_k, min_confidence)|
|    search_nutrition_database_enhanced(dish_name, ...)      |
+------------------------------------------------------------+
             |
             v
   Future consumers (Stage 5 wiring, Stage 9 benchmark).
```

Stage 1 ships the tables, the CRUD, the service, and the seed script with zero runtime callers. The only path that exercises the pipeline is the smoke test (fixture-driven, no DB) plus the manual post-seed check.

## Data Model

### `NutritionFood` — `backend/src/models.py`

Table `nutrition_foods`. One row per food item across all four source DBs. Direct columns for the four macros where the source carries them; `raw_data JSONB` holds the full source row so Stage 7 can read source-specific extras (CIQUAL micros, Anuvaad full nutrient set).

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `id` | SERIAL PK | no | Surrogate key |
| `source` | TEXT | no | `malaysian_food_calories`, `myfcd`, `anuvaad`, `ciqual` |
| `source_food_id` | TEXT | no | Anuvaad `food_code`, MyFCD `ndb_id`, CIQUAL `food_code`, Malaysian filename stem |
| `food_name` | TEXT | no | Native-language name (for Malaysian: from `food_item`) |
| `food_name_eng` | TEXT | yes | CIQUAL only; preferred display name |
| `category` | TEXT | yes | Malaysian → `category`; CIQUAL → `food_group_name`; else NULL |
| `searchable_document` | TEXT | no | Precomputed BM25 document; seeded once |
| `calories` | FLOAT | yes | Per-100g for Anuvaad/CIQUAL; per-serving for Malaysian/MyFCD |
| `carbs_g`, `protein_g`, `fat_g`, `fiber_g` | FLOAT | yes | Same scale as `calories` |
| `serving_size_grams` | FLOAT | yes | MyFCD only |
| `serving_unit` | TEXT | yes | Source-specific serving label |
| `raw_data` | JSONB | no | Full source-row JSON |
| `created_at`, `updated_at` | TIMESTAMP | no | `updated_at` bumped on upsert |

Constraints:

- `UniqueConstraint(source, source_food_id)` — the seed script upserts on this key.
- `Index(source)` — B-tree for per-source partitioning at service-init time.

### `NutritionMyfcdNutrient` — `backend/src/models.py`

Table `nutrition_myfcd_nutrients`. Long-format nutrient child for MyFCD rows only.

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `id` | SERIAL PK | no | Surrogate key |
| `ndb_id` | TEXT | no | Soft FK to `nutrition_foods.source_food_id` where `source='myfcd'` |
| `nutrient_name` | TEXT | no | e.g. `Energy`, `Protein`, `Carbohydrate`, `Total dietary fibre` |
| `value_per_100g`, `value_per_serving` | FLOAT | yes | Direct from MyFCD CSV |
| `unit` | TEXT | yes | e.g. `Kcal`, `g`, `mg` |
| `category` | TEXT | yes | e.g. `Proximates`, `Minerals`, `Vitamins` |

Constraints:

- `UniqueConstraint(ndb_id, nutrient_name)` — the seed script upserts on this key.
- `Index(ndb_id)` — join path to parent food row.

The FK to `nutrition_foods` is **soft** (no DB-level foreign key). `nutrition_foods.source_food_id` is not globally unique (Anuvaad and CIQUAL share numeric ID ranges); only `(source, source_food_id)` is. A hard FK would need a composite that only applies to the `myfcd` source, which is awkward. The service treats missing parent rows as "skip this nutrient" rather than raising.

## Pipeline

```
Seed (one-shot, manual)
  │
  ▼
python -m scripts.seed.load_nutrition_db
  │
  ├── verify_csvs  → DATABASE_DIR / {Anuvaad_INDB_2024,ciqual_2020,
  │                                  malaysian_food_calories,
  │                                  myfcd_basic, myfcd_nutrients}.csv
  │
  ├── for each source:
  │     csv.DictReader → _coerce_empty_to_none per cell
  │     build searchable_document (variations + synonyms)
  │     map source columns → nutrition_foods row dict
  │
  ├── crud_nutrition.bulk_upsert_foods(rows)
  │     ON CONFLICT (source, source_food_id) DO UPDATE
  │
  └── crud_nutrition.bulk_upsert_myfcd_nutrients(nutrient_rows)
        ON CONFLICT (ndb_id, nutrient_name) DO UPDATE

Runtime (first request per process)
  │
  ▼
get_nutrition_service()   (lazy thread-safe singleton)
  │
  ├── crud_nutrition.get_all_foods_grouped_by_source  (one SELECT)
  ├── crud_nutrition.get_myfcd_nutrients_grouped_by_ndb_id  (one SELECT)
  ├── materialize rows into source-specific dicts
  ├── build four BM25Okapi indices (one per source)
  └── cache instance in module-level _INSTANCE

Runtime (every subsequent request)
  │
  ▼
service._search_dishes_direct(user_input, top_k, min_confidence)
  │
  ├── normalize_text(user_input) → tokens
  ├── for each source:
  │     BM25.get_scores(tokens) → top_k by raw score
  │     per-hit confidence formula (core/descriptor + BM25 quality)
  │     scale into [0.50, 0.95]
  ├── merge, sort by confidence desc
  └── filter by min_confidence, cap at top_k

→ [
    { matched_food_name, source, confidence, confidence_score,
      nutrition_data, search_method, raw_bm25_score,
      matched_keywords, total_keywords }, ...
  ]
```

## Algorithms

### Confidence formula (verbatim port — DO NOT EDIT WITHOUT RE-RUNNING STAGE 9 BENCHMARK)

- `core_dish_tokens = dish_tokens - quantity_words` (quantity = digits 1–9 + `small/large/medium/big/mini/wraps/pieces/servings`).
- `keyword_score = dish_match_ratio × 0.85 + descriptor_match_ratio × 0.15`.
- Add `+0.20` when `len(matched_dish) >= 2`; `+0.15` more when `>= 3`; cap at `1.0`.
- `bm25_quality = log(1 + raw_score) / log(1 + max_raw_in_batch)`.
- `base_confidence = 0.8 × keyword_score + 0.2 × bm25_quality`.
- `confidence = min(0.50 + base_confidence × 0.45, 0.95)`.

The 0.85/0.15 split, +0.20/+0.15 bonuses, 0.8/0.2 mix, and [0.50, 0.95] scale are tuned against the reference project's 846-query NDCG eval set (measured NDCG@10 = 0.7744 with BM25Okapi). Stage 9 guards future regressions.

### `searchable_document` construction (seed-time)

- Base: source-preferred name (English for CIQUAL, `food_item` for Malaysian, else `food_name`).
- Add: category / group / subgroup where the source carries them.
- Expand via `generate_food_variations` (shared synonym map: Malaysian + Indian basics).
- Additionally per source:
  - Malaysian → food_item + category + generic variations.
  - MyFCD → parenthetical extractions + food-keyword + Malaysian-term scan.
  - Anuvaad → Indian-term scan + split-on-separators + spelling/plural variations.
  - CIQUAL → English + French + group + subgroup + generic variations.
- Every part passes through `_normalize_text` (NFKD fold + casefold + strip punctuation + collapse whitespace) before concatenation.
- Result is stored as a single space-separated string; runtime BM25 splits it with `str.split()` to build the corpus document.

### Tokenization (runtime)

- `_normalize_text(user_input)` — same transform the seed script applies to corpus documents. Corpus and query share one vocabulary, so BM25 scoring is symmetric across the two sides.

### Lazy singleton

- `get_nutrition_service()` guards the module-level `_INSTANCE` with a `threading.Lock()`. First caller pays the full init cost (~1 s on 4,493-row production corpus); subsequent callers (same process) take the unlocked fast path.
- `_reset_singleton_for_tests()` is the only hook that drops the cache; conftest fixtures call it per-test so each test gets a fresh corpus.

## Backend — Service Layer

| Function / Class | File | Purpose |
|---|---|---|
| `NutritionCollectionService.__init__()` | `backend/src/service/nutrition_db.py` | Reads the full corpus via CRUD, joins MyFCD nutrients, builds four per-source `BM25Okapi` indices. Raises `NutritionDBEmptyError` when no rows exist. |
| `NutritionCollectionService._search_dishes_direct(user_input, top_k, min_confidence)` | same | Cross-source BM25 search; returns rows in the fixed row-output shape. |
| `NutritionCollectionService.search_nutrition_database_enhanced(dish_name, related_keywords, estimated_quantity, top_k)` | same | Dish-name-priority search; sets `_current_dish_tokens` so the confidence formula weights core dish matches. |
| `NutritionCollectionService._normalize_text(text)` (module-level `_normalize_text`) | same | NFKD + casefold + strip punctuation + collapse whitespace. Shared with the seed script. |
| `get_nutrition_service()` | same | Thread-safe lazy singleton accessor. Stage 5 wiring imports this, never the class directly. |
| `NutritionCollectionError`, `NutritionDBEmptyError` | same | Error contract. `NutritionDBEmptyError` message names the seed command. |

## Backend — CRUD Layer

`backend/src/crud/crud_nutrition.py`:

| Function | Purpose |
|---|---|
| `bulk_upsert_foods(rows)` | Dialect-aware `INSERT ... ON CONFLICT (source, source_food_id) DO UPDATE`. Chunks at 500 rows. Used by seed script. |
| `bulk_upsert_myfcd_nutrients(rows)` | Same shape on `(ndb_id, nutrient_name)`. |
| `get_all_foods_grouped_by_source()` | Single SELECT, grouped in Python; always returns all four source keys. |
| `get_myfcd_nutrients_grouped_by_ndb_id()` | Single SELECT, grouped by `ndb_id`. |
| `count_foods_by_source()` | Per-source count; always includes all four sources (zero for unseen). |

`_insert_for(bind)` picks `sqlalchemy.dialects.postgresql.insert` in production and `sqlalchemy.dialects.sqlite.insert` in tests. Both expose an identical `on_conflict_do_update(index_elements=..., set_=...)` API so the call site is portable.

## Seed Script

`backend/scripts/seed/load_nutrition_db.py`:

- Run from `backend/`: `python -m scripts.seed.load_nutrition_db`.
- Verifies the five source CSVs exist (raises `FileNotFoundError` on any missing).
- Reads each CSV with stdlib `csv.DictReader` (no `pandas` dependency).
- MyFCD reads both `myfcd_basic.csv` and `myfcd_nutrients.csv`, joins on `ndb_id`, and fills direct macro columns on the basic row (prefer `value_per_serving`; fall back to `value_per_100g × serving_size_grams / 100`).
- Precomputes every row's `searchable_document` via helpers in `scripts/seed/_variations.py`. Those helpers are a verbatim port of the reference project's variation / synonym maps and carry an explicit "DO NOT EDIT WITHOUT RE-SEEDING" block.
- Idempotent: second run upserts the same rows, bumps `updated_at`.
- Prints a per-source summary on stdout.

## Constraints & Edge Cases

- **Empty DB** — `NutritionCollectionService()` raises `NutritionDBEmptyError` whose message names the seed command (`python -m scripts.seed.load_nutrition_db`). Stage 5's orchestrator (`extract_and_lookup_nutrition`) catches this and returns the Stage-7-compatible empty-response shape with `match_summary.reason = "nutrition_db_empty"`; Phase 2 Gemini proceeds as today. The operator sees the WARN line in `backend.log` — that is the "seed step was missed" signal.

### Downstream consumers

- **Stage 5 — `service/nutrition_lookup.py::extract_and_lookup_nutrition`** — first caller of `collect_from_nutrition_db`. Runs per-component + dish_name queries at `min_confidence=70` and a combined-terms fallback at `min_confidence=60` when the best individual match scores below 0.75. Persists on `result_gemini.nutrition_db_matches` before the Gemini Pro call.
- **Stage 7 — Phase 2.3 prompt (not yet wired)** — will consume `nutrition_db_matches.nutrition_matches[]` with a threshold gate (`confidence_score >= THRESHOLD_DB_INCLUDE`) to decide whether to inject a "Nutrition Database Matches" block into the Pro prompt.
- **Stage 9 — regression gate** — `backend/tests/test_nutrition_retrieval_benchmark.py` runs the 846-query eval set through `_search_dishes_direct` and asserts aggregate NDCG@10 ≥ 0.75. See the "Regression gate (Stage 9)" sub-section below.
- **Tiny corpora** — `BM25Okapi` scores all docs as `0.0` when `df = N/2` in a 2-doc corpus (log(1.5) − log(1.5) = 0). Production has 4,493 rows so this collapse is impossible; fixture-based tests use ≥ 4 rows per source to avoid it.
- **First request is slow** — ~1 s on production data for the two SELECTs + four BM25 builds. Subsequent requests in the same process are sub-millisecond. Expected behavior; no cache-warming hook on startup (would re-introduce the import-time-crash-if-empty-DB problem the lazy singleton was designed to avoid).
- **Re-seeding required for variation edits** — `searchable_document` is materialized at seed time. Editing `scripts/seed/_variations.py` has no effect until the seed script is re-run.
- **Raw data JSONB spillover** — every source-CSV column is preserved in `raw_data`. Stage 7's consolidation prompt can read either the direct columns (typed) or JSON fields (untyped) depending on what the prompt template wants.
- **Soft MyFCD join** — `nutrition_myfcd_nutrients` has no DB-level FK to `nutrition_foods`. Deleting a MyFCD food row does not cascade-delete its nutrients. This is deliberate: re-seeding will overwrite on conflict; orphaned nutrient rows are inert because the service only reads nutrients whose `ndb_id` matches a loaded food row.
- **Thread safety of singleton** — `get_nutrition_service()` uses a `threading.Lock` to guard first-call init so two near-simultaneous FastAPI requests during warm-up do not race-build two instances.

### Regression gate (Stage 9)

`backend/tests/test_nutrition_retrieval_benchmark.py` + `backend/tests/data/retrieval_eval_dataset.csv` (846 queries, ~80 KB) enforce the retrieval-quality invariant that Stage 1's confidence-formula constants encode.

- **How to run.** The benchmark is gated behind `@pytest.mark.benchmark`; `backend/pytest.ini` excludes it by default via `addopts = -m "not benchmark"`. To run it explicitly:
  ```bash
  source venv/bin/activate
  cd backend
  pytest -m benchmark
  # or target the file directly:
  pytest backend/tests/test_nutrition_retrieval_benchmark.py -m benchmark
  ```
- **What it asserts.** For each of the 846 queries, runs `_search_dishes_direct(query, top_k=10, min_confidence=0.0)`, extracts each match's `source_food_id` (checks `ndb_id` → `food_code` → `source_food_id` in that order), computes per-query NDCG@10 against the labeled `relevant_dish_ids`/`relevance_scores`, and asserts `mean(ndcg) >= 0.75`.
- **Historical anchor.** The reference project measured NDCG@10 = 0.7744 on this eval set with the same BM25Okapi formula. The 0.75 floor gives 3% slack for small per-source materialization differences (CIQUAL, Malaysian ID formats) without constant false positives; a substantive drop (say to 0.72) still fires.
- **Empty DB.** When `nutrition_foods` is empty, the benchmark emits `pytest.skip` with a message naming the seed command. The benchmark is not a fast unit test — a missing seed is an operator concern, not a CI failure.
- **Fast-suite helpers.** Seven small unit tests in the same module (NDCG math, `_extract_match_id`, CSV loading) are NOT marked `benchmark` — they run on every pre-commit and protect the benchmark's scaffolding from silent bugs.
- **When to re-run.** Any change to the Stage 1 scoring formula (`_nutrition_scoring.py`), the seed script's variation / synonym maps (`scripts/seed/_variations.py`), or the `searchable_document` precomputation should be followed by a `pytest -m benchmark` run against a freshly-seeded dev DB. If the aggregate dips near the floor, raise the question deliberately rather than silently accepting drift.

## Component Checklist

- [x] `nutrition_foods` table — `backend/sql/create_tables.sql`
- [x] `nutrition_myfcd_nutrients` table
- [x] `idx_nutrition_foods_source` B-tree index
- [x] `uq_nutrition_foods_source_food_id` unique index
- [x] `idx_nutrition_myfcd_nutrients_ndb_id` B-tree index
- [x] `uq_nutrition_myfcd_nutrients_ndb_nutrient` unique index
- [x] `NutritionFood` ORM class — `backend/src/models.py`
- [x] `NutritionMyfcdNutrient` ORM class
- [x] CRUD `bulk_upsert_foods` — `backend/src/crud/crud_nutrition.py`
- [x] CRUD `bulk_upsert_myfcd_nutrients`
- [x] CRUD `get_all_foods_grouped_by_source`
- [x] CRUD `get_myfcd_nutrients_grouped_by_ndb_id`
- [x] CRUD `count_foods_by_source`
- [x] `NutritionCollectionService` — `backend/src/service/nutrition_db.py`
- [x] `get_nutrition_service` lazy singleton
- [x] `NutritionCollectionError` / `NutritionDBEmptyError`
- [x] `_search_dishes_direct` verbatim confidence formula
- [x] `search_nutrition_database_enhanced` dish-token weighting
- [x] Seed script `backend/scripts/seed/load_nutrition_db.py`
- [x] Variation helpers `backend/scripts/seed/_variations.py`
- [x] `DATABASE_DIR` constant — `backend/src/configs.py`
- [x] Unit tests CRUD — `backend/tests/test_crud_nutrition.py`
- [x] Unit tests service — `backend/tests/test_nutrition_db.py`
- [x] Unit tests seed — `backend/tests/test_seed_load_nutrition_db.py`
- [x] Stage 5 (Phase 2.1): `extract_and_lookup_nutrition` wired into `trigger_step2_analysis_background` (see [nutritional_analysis.md § Phase 2.1](./nutritional_analysis.md#phase-21--nutrition-db-lookup-stage-5))
- [x] Stage 5: `NutritionCollectionService.collect_from_nutrition_db(text, min_confidence, deduplicate)` method
- [x] Stage 5: `_nutrition_aggregation.py` helpers (`deduplicate_matches`, `aggregate_nutrition`, `calculate_optimal_nutrition`, `extract_single_match_nutrition`, `generate_recommendations`)
- [x] Stage 7 (Phase 2.3): Step 2 prompt reads `result_gemini.nutrition_db_matches` via `__NUTRITION_DB_BLOCK__` placeholder; gated on `confidence_score >= THRESHOLD_DB_INCLUDE (80)`. See [nutritional_analysis.md § Phase 2.3](./nutritional_analysis.md#phase-23--reference-assisted-prompt-stage-7).
- [x] Stage 9: NDCG@10 ≥ 0.75 regression gate against the 846-query eval set — `backend/tests/test_nutrition_retrieval_benchmark.py`, dataset at `backend/tests/data/retrieval_eval_dataset.csv`.

---

[< Prev: Personalized Food Index](./personalized_food_index.md) | [Parent](./index.md)
