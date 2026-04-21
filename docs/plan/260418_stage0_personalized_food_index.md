# Stage 0 — Per-User Food-Description Index (Foundation)

**Feature**: Ship the shared foundation for per-user food-description retrieval — a new `personalized_food_descriptions` table, its CRUD surface, and a BM25 search module that later stages (Phase 1.1.1, Phase 1.2, Phase 2.2, Phase 2.4) consume. No user-visible change on its own.
**Plan Created:** 2026-04-18
**Status:** Plan
**Reference**:
- [Issues — 260415, Stage 0](../issues/260415.md)
- [Discussion — Food DB investigation & end-to-end redesign](../discussion/260418_food_db.md)
- [Abstract — Dish Analysis](../abstract/dish_analysis/index.md)
- [Technical — Dish Analysis](../technical/dish_analysis/index.md)
- [Technical — Component Identification](../technical/dish_analysis/component_identification.md)
- [Technical — Nutritional Analysis](../technical/dish_analysis/nutritional_analysis.md)

---

## Problem Statement

1. The end-to-end redesign in `docs/discussion/260418_food_db.md` introduces per-user personalization at four distinct points:
   - **Phase 1.1.1** (Stage 2): fast-caption + BM25 lookup against the user's prior uploads to pick a reference image.
   - **Phase 1.2** (Stage 4): on Step 1 confirmation, enrich the matching row with the user-verified dish name and portion count.
   - **Phase 2.2** (Stage 6): retrieve the top-K historical rows to feed the consolidation prompt.
   - **Phase 2.4** (Stage 8): write user nutrient corrections back to the same row so future lookups return verified nutrients.
2. All four touchpoints share the same store and the same BM25 retrieval logic. Shipping them sequentially without a shared foundation forces every stage to carry schema + retrieval code that the next one partially overwrites.
3. Today the project has no place to persist per-user food history beyond `DishImageQuery.result_gemini` (which is per-query, not an index), and `rank-bm25` is not installed.
4. Stage 0 unblocks Stages 2, 4, 6, and 8. It ships exactly three things — a new table, a CRUD module, and a BM25 index module — and deliberately produces no user-visible behavior change.

---

## Proposed Solution

Land the three artifacts in a single PR, all behind a module that nothing yet calls:

1. **`personalized_food_descriptions` table.** One row per dish upload, scoped by `user_id`, joined to `DishImageQuery` by `query_id`. Created with the full column set specified in the issue (including the `confirmed_*` and `corrected_step2_data` columns that Stages 4 and 8 will populate later). Full-table-now means Stages 2/4/6/8 only ever read and write existing columns — no `ALTER TABLE` churn.
2. **`crud_personalized_food.py` CRUD module.** Four functions matching the issue's public contract: `insert_description_row`, `update_confirmed_fields`, `update_corrected_step2_data`, `get_all_rows_for_user`. Each opens and closes its own `SessionLocal`, mirroring the existing `dish_query_basic.py` style.
3. **`personalized_food_index.py` service module.** Exposes `tokenize(text)` (NFKD normalize + lowercase + strip punctuation) and `search_for_user(user_id, query_tokens, top_k, min_similarity)`. The index is built on the fly per request from the user's rows (no persistence, no cache). A `rank-bm25` dependency is added to `requirements.txt` at repo root (the project has no separate `backend/requirements.txt`).

The shape that later stages need is fixed here so they have a stable interface to wire against:

```
personalized_food_descriptions (per-user BM25 corpus)
  │
  ▼
personalized_food_index.search_for_user(...)  returns rows like:
  { query_id, image_url, description, similarity_score, row }
```

Stage 0 deliberately does **not** touch the upload / confirmation / analysis pipelines. The only runtime code that can exercise the new table is its own unit tests.

---

## Current Implementation Analysis

### What Exists (keep as-is)

| Component | File | Status |
|-----------|------|--------|
| `DishImageQuery` model and table | `backend/src/models.py`, `backend/sql/create_tables.sql` | Keep — foreign key target for the new table; unchanged. |
| `Users` model and table | `backend/src/models.py`, `backend/src/database.py` | Keep — foreign key target for `user_id`; unchanged. |
| CRUD facade `crud_food_image_query.py` | `backend/src/crud/crud_food_image_query.py` | Keep — unrelated; the new CRUD module is a sibling, not an extension. |
| `Base` declarative and `SessionLocal` | `backend/src/database.py` | Keep — reused by the new CRUD. |
| `RESOURCE_DIR` constant | `backend/src/configs.py` | Keep — Stage 1 will add `DATABASE_DIR` off this; Stage 0 does not. |
| Existing test harness (`conftest.py`, pytest config) | `backend/tests/conftest.py`, `backend/pytest.ini` | Keep — new tests plug in through the same harness. |
| Existing requirements stack | `requirements.txt` (repo root) | Keep — appended, not rewritten. |

### What Changes

| Component | Current | Proposed |
|-----------|---------|----------|
| Schema (`backend/sql/create_tables.sql`) | Only `dish_image_query_prod_dev` + its indices/constraints. | Adds `personalized_food_descriptions` table with indices on `user_id` and `query_id`, and a `uq_personalized_food_descriptions_query_id` unique index so each `DishImageQuery` has at most one row. |
| ORM (`backend/src/models.py`) | Only `Users` and `DishImageQuery`. | Adds `PersonalizedFoodDescription` SQLAlchemy class mirroring the new table, following the `to_dict()` / `__repr__` style already established. |
| CRUD (`backend/src/crud/`) | Only dish-query CRUD. | Adds `crud_personalized_food.py` with `insert_description_row`, `update_confirmed_fields`, `update_corrected_step2_data`, `get_all_rows_for_user`. |
| Services (`backend/src/service/`) | Only the `llm/` submodule today. | Adds top-level `personalized_food_index.py` with `tokenize` and `search_for_user` (BM25 built per request, no module-level cache — that is a Stage 1 concern, not Stage 0). |
| Requirements | `requirements.txt` has no retrieval library. | Adds `rank-bm25` under the `# others` block. |
| Tests | No tests for personalization. | Adds `test_crud_personalized_food.py` and `test_personalized_food_index.py` covering the "done when" criteria. |

---

## Implementation Plan

### Key Workflow

Stage 0 introduces no runtime flow — nothing in the app calls `personalized_food_index.search_for_user` yet. The only exercised paths are:

```
Unit test (CRUD)
  │
  ▼
insert_description_row(user_id, query_id, image_url, description, tokens, ...)
  │
  ▼
get_all_rows_for_user(user_id, exclude_query_id=<current>)
  │
  ▼
[expected rows]
```

```
Unit test (index)
  │
  ▼
tokenize("Chicken rice, Hainanese style")  → ["chicken", "rice", "hainanese", "style"]
  │
  ▼
search_for_user(user_id, query_tokens, top_k=1, min_similarity=THRESHOLD)
  │
  ├── load rows via get_all_rows_for_user(user_id, exclude_query_id)
  ├── build BM25 over row.tokens
  ├── score query_tokens
  └── filter by similarity ≥ min_similarity, take top_k
  │
  ▼
[{ query_id, image_url, description, similarity_score, row }]
```

The contract frozen here is what Stages 2, 4, 6, and 8 will bind against. Concretely:

- Rows are scoped strictly by `user_id`. Cross-user retrieval is impossible by construction.
- The index is **read-then-insert** at the call-site in Stage 2 (not here) — Stage 0 simply offers an `exclude_query_id` filter so the caller can guarantee self-exclusion regardless of insertion order.
- `similarity_score` is the raw normalized BM25 output in `[0, 1]`. Threshold constants live in `configs.py` and are owned by their consuming stage; Stage 0 does not define any threshold.

#### To Delete

None.

#### To Update

None — the three artifacts are additive. The only files modified in-place are `backend/sql/create_tables.sql` (append a `CREATE TABLE IF NOT EXISTS`), `backend/src/models.py` (append a class), and `requirements.txt` (append one line).

#### To Add New

- The workflow above is fully implemented by the new CRUD module and the new index module. No callers exist yet.

---

### Database Schema

All schema lives in the single-file `backend/sql/create_tables.sql` (this project has no `scripts/sql/` migration runner — the file is executed wholesale on startup, so every statement must be `IF [NOT] EXISTS` idempotent). The DDL below is appended to that file.

```sql
-- Table: personalized_food_descriptions
-- Per-user food upload index. One row per DishImageQuery owned by a user,
-- keyed on query_id so later stages can join back to the dish record and
-- its result_gemini blob without duplicating JSON payloads here.
CREATE TABLE IF NOT EXISTS personalized_food_descriptions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    query_id INTEGER NOT NULL REFERENCES dish_image_query_prod_dev(id) ON DELETE CASCADE,
    image_url VARCHAR,
    description TEXT,
    tokens JSONB,
    similarity_score_on_insert FLOAT,
    confirmed_dish_name TEXT,
    confirmed_portions FLOAT,
    confirmed_tokens JSONB,
    corrected_step2_data JSONB,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);

-- Lookup by owner (Stage 2 / Stage 6 primary access path)
CREATE INDEX IF NOT EXISTS idx_personalized_food_descriptions_user_id
    ON personalized_food_descriptions(user_id);

-- Lookup by dish query (Stage 4 / Stage 8 update path; also enforces 1:1)
CREATE UNIQUE INDEX IF NOT EXISTS uq_personalized_food_descriptions_query_id
    ON personalized_food_descriptions(query_id);
```

Column notes (for the ORM and for Stages 2/4/8 readers):

| Column | Type | Nullable | Writer stage | Purpose |
|---|---|---|---|---|
| `id` | SERIAL PK | no | Stage 0 | surrogate key |
| `user_id` | INT FK → users | no | Stage 0 | scope; joined `user_id` index |
| `query_id` | INT FK → dish_image_query_prod_dev | no | Stage 0 | 1:1 join back to `DishImageQuery`; `ON DELETE CASCADE` so purging a dish purges its index row |
| `image_url` | VARCHAR | yes | Stage 2 | mirrors `DishImageQuery.image_url` for fast retrieval without a join |
| `description` | TEXT | yes | Stage 2 | Gemini 2.0 Flash caption (written in Stage 2) |
| `tokens` | JSONB | yes | Stage 2 | caption tokens used to build the BM25 index |
| `similarity_score_on_insert` | FLOAT | yes | Stage 2 | raw top-1 BM25 score against the user's prior corpus at insert time (debug/audit) |
| `confirmed_dish_name` | TEXT | yes | Stage 4 | user-confirmed dish name |
| `confirmed_portions` | FLOAT | yes | Stage 4 | sum of confirmed per-component servings |
| `confirmed_tokens` | JSONB | yes | Stage 4 | tokenized `confirmed_dish_name`; union with `tokens` is the Stage 6 query |
| `corrected_step2_data` | JSONB | yes | Stage 8 | user manual nutrient corrections, used by Stage 6 lookups as ground truth |
| `created_at`, `updated_at` | TIMESTAMP | no | Stage 0 | maintained by CRUD |

SQLAlchemy model (appended to `backend/src/models.py`):

```python
class PersonalizedFoodDescription(Base):
    __tablename__ = "personalized_food_descriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    query_id = Column(
        Integer,
        ForeignKey("dish_image_query_prod_dev.id", ondelete="CASCADE"),
        nullable=False,
    )
    image_url = Column(String, nullable=True, default=None)
    description = Column(String, nullable=True, default=None)
    tokens = Column(JSON, nullable=True, default=None)
    similarity_score_on_insert = Column(Float, nullable=True, default=None)
    confirmed_dish_name = Column(String, nullable=True, default=None)
    confirmed_portions = Column(Float, nullable=True, default=None)
    confirmed_tokens = Column(JSON, nullable=True, default=None)
    corrected_step2_data = Column(JSON, nullable=True, default=None)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
```

`Float` is added to the existing `sqlalchemy` import line.

#### To Delete

None.

#### To Update

- `backend/sql/create_tables.sql` — append the `CREATE TABLE IF NOT EXISTS personalized_food_descriptions` block and two indices shown above.
- `backend/src/models.py` — append the `PersonalizedFoodDescription` class; extend the SQLAlchemy import to include `Float`.

#### To Add New

- None as a standalone file — no migration runner exists in this project; all schema lives in `backend/sql/create_tables.sql`.

---

### CRUD

New module `backend/src/crud/crud_personalized_food.py`. All functions open and close their own `SessionLocal`, matching `dish_query_basic.py`. `updated_at` is set to `datetime.now(timezone.utc)` on every write. `created_at` is set only on insert.

```python
def insert_description_row(
    user_id: int,
    query_id: int,
    *,
    image_url: str,
    description: str,
    tokens: List[str],
    similarity_score_on_insert: Optional[float] = None,
) -> PersonalizedFoodDescription: ...

def update_confirmed_fields(
    query_id: int,
    *,
    confirmed_dish_name: str,
    confirmed_portions: float,
    confirmed_tokens: List[str],
) -> Optional[PersonalizedFoodDescription]: ...

def update_corrected_step2_data(
    query_id: int,
    payload: Dict[str, Any],
) -> Optional[PersonalizedFoodDescription]: ...

def get_all_rows_for_user(
    user_id: int,
    *,
    exclude_query_id: Optional[int] = None,
) -> List[PersonalizedFoodDescription]: ...
```

Behavior:

- `insert_description_row` — INSERT; rely on the `uq_personalized_food_descriptions_query_id` unique index to reject a duplicate row for the same `query_id` (caller is expected to catch `IntegrityError` if the invariant is broken).
- `update_confirmed_fields` / `update_corrected_step2_data` — UPDATE by `query_id`; return `None` if no row exists (Stage 4/8 will treat this as "Phase 1.1.1 never wrote a row for this query" and log, not raise).
- `get_all_rows_for_user` — returns ORM objects (not dicts). `exclude_query_id` is `WHERE query_id != :x` when provided; None returns every row. Ordering is by `id ASC` so tests are deterministic.

#### To Delete

None.

#### To Update

None.

#### To Add New

- `backend/src/crud/crud_personalized_food.py` — the four functions above plus module-level docstring matching the existing CRUD style.
- (Intentionally **not** re-exported from `crud_food_image_query.py`.) That facade is scoped to `DishImageQuery` concerns; callers import the new module directly via `from src.crud import crud_personalized_food`.

---

### Services

New module `backend/src/service/personalized_food_index.py`. No class — two module-level functions.

```python
def tokenize(text: str) -> List[str]:
    """
    NFKD-normalize, lowercase, strip non-alphanumeric, split on whitespace.
    Returns a list of tokens suitable for BM25 corpus + query use.
    Empty / whitespace-only input returns [].
    """

def search_for_user(
    user_id: int,
    query_tokens: List[str],
    *,
    top_k: int = 1,
    min_similarity: float = 0.0,
    exclude_query_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Build a BM25 index from the user's rows on the fly and return the top
    matches for `query_tokens`. Each result dict has the fixed shape:
      {
        "query_id": int,
        "image_url": str | None,
        "description": str | None,
        "similarity_score": float,
        "row": PersonalizedFoodDescription,
      }
    If the user has no rows (or none after exclusion), or if `query_tokens`
    is empty, returns [].
    """
```

Key implementation details the later stages depend on:

- **`tokenize`** — `unicodedata.normalize("NFKD", text)`, `.casefold()`, `re.sub(r"[^a-z0-9\s]+", " ", ...)` (post-casefold), `.split()`. Deterministic; the same text on two users must produce identical tokens so Stage 2 can store them and Stage 6 can reuse them.
- **Corpus source** — `crud_personalized_food.get_all_rows_for_user(user_id, exclude_query_id=exclude_query_id)`. Rows with `tokens is None` or `tokens == []` are skipped for the corpus (they would be empty BM25 documents).
- **Token column preference** — `row.tokens` is the canonical corpus token list. Stage 4 later populates `row.confirmed_tokens`; Stage 6 unions them at the query side, not the corpus side, so Stage 0 does not need to decide precedence here.
- **Similarity scaling** — `rank-bm25`'s raw score is unbounded. Normalize within each query by dividing by the max raw score in the result batch (guard divide-by-zero when max is 0). Scores land in `[0, 1]`. This matches the scheme the Stage 1 `nutrition_db.py` confidence formula will later apply at the DB side, so the two pieces speak the same scale.
- **No module-level caching.** The index is rebuilt per call. Stages 2/6 measure latency; if a cache is warranted it is a later optimization and must not change the return shape.
- **Dependency** — `from rank_bm25 import BM25Okapi`.

#### To Delete

None.

#### To Update

- `requirements.txt` (repo root) — append `rank-bm25` under the `# others` section. No version pin (matches the project convention of loose pinning for non-critical deps).

#### To Add New

- `backend/src/service/personalized_food_index.py` — module with `tokenize` and `search_for_user`.

---

### API Endpoints

None. Stage 0 exposes no HTTP surface. Endpoint changes begin at Stage 2 (which silently adds a key to `result_gemini` via the upload path; no new route).

#### To Delete

None.

#### To Update

None.

#### To Add New

None.

---

### Testing

Test location: `backend/tests/`. Tests use the existing `conftest.py` harness. Follow the style of `test_item_step1_tasks.py` (direct function calls, no HTTP client, SQLAlchemy sessions cleaned in fixtures).

**Unit tests — CRUD (`backend/tests/test_crud_personalized_food.py`):**

- `test_insert_description_row_persists_expected_columns` — insert, then query and assert every column landed with the expected type and value; `created_at` and `updated_at` are set; `updated_at == created_at` at insert time.
- `test_insert_description_row_rejects_duplicate_query_id` — two inserts with the same `query_id` raises `IntegrityError` (proves the unique index is active).
- `test_update_confirmed_fields_sets_fields_and_bumps_updated_at` — insert, then update, assert `confirmed_dish_name / confirmed_portions / confirmed_tokens` set and `updated_at > created_at`.
- `test_update_confirmed_fields_returns_none_for_missing_query_id` — update against an unknown `query_id` returns `None` and does not raise.
- `test_update_corrected_step2_data_persists_payload` — arbitrary dict round-trips through JSONB.
- `test_get_all_rows_for_user_scopes_and_excludes` — seed rows for two users; assert only owner's rows return; `exclude_query_id` removes the matching row; deterministic ordering by `id ASC`.

**Unit tests — Index (`backend/tests/test_personalized_food_index.py`):**

- `test_tokenize_normalizes_and_strips` — table-driven: `"Chicken Rice"`, `"  hainanese   style  "`, `"café — au lait"`, `"ARROZ com FRANGO"`, `""`, `"  "`. Asserts expected token lists (lowercased, NFKD-folded, punctuation removed, no empties).
- `test_tokenize_is_deterministic` — same input across two calls yields the exact same list.
- `test_search_for_user_empty_corpus_returns_empty_list` — no rows for the user → `[]`.
- `test_search_for_user_empty_query_tokens_returns_empty_list` — rows exist but `query_tokens=[]` → `[]`.
- `test_search_for_user_returns_top_1_above_threshold` — 3-row fixture (hand-crafted: "chicken rice hainanese", "beef noodle soup", "chocolate chip cookie"); query tokens `["chicken", "rice"]`; `top_k=1, min_similarity=0.1` returns the chicken-rice row with `similarity_score > 0.1`. **This is the `Done when` fixture check from the issue.**
- `test_search_for_user_filters_below_threshold` — same fixture; query `["unrelated", "zzz"]`, `min_similarity=0.5` → `[]`.
- `test_search_for_user_respects_exclude_query_id` — two near-identical rows for the user; excluding the nominally-best `query_id` returns the second-best.
- `test_search_for_user_scopes_to_user_id` — seed rows under user A and B; a user-A search never surfaces user-B rows.
- `test_search_for_user_return_shape_is_stable` — each result dict has exactly the keys `{query_id, image_url, description, similarity_score, row}`; `similarity_score` is a float in `[0, 1]`; `row` is a `PersonalizedFoodDescription` instance. (Stages 2/6 bind against this shape — do not change it without updating them.)

**Pre-commit loop** (mandatory per skill rules):

1. `source venv/bin/activate && pre-commit run --all-files`.
2. Fix any issues (e.g. lint errors, Python line-count violations).
3. Re-run pre-commit — Prettier may reformat fixes and push files back over the line limit (300 lines per frontend file; no frontend files land in Stage 0 so this is a no-op, but still run the loop). If so, fix durably (extract a helper, not a cosmetic shuffle).
4. Repeat until pre-commit passes cleanly on a full re-run with zero new failures.

**Acceptance check from the issue's "done when":**

- Table exists on dev DB after `create_tables.sql` runs.
- CRUD insert/update/read-for-user have the unit coverage above.
- `test_search_for_user_returns_top_1_above_threshold` passes against the hand-crafted 3-row fixture.

#### To Delete

None.

#### To Update

None (existing tests are untouched).

#### To Add New

- `backend/tests/test_crud_personalized_food.py` — CRUD test cases listed above.
- `backend/tests/test_personalized_food_index.py` — tokenize + search test cases listed above.

---

### Frontend

None. Stage 0 ships no UI.

#### To Delete

None.

#### To Update

None.

#### To Add New

None.

---

### Documentation

Stage 0 is a hidden foundation with no user-facing behavior, but it introduces a new table and two new modules that future stages will document against. Capture the foundation now so Stages 2/4/6/8 extend — not introduce — the documentation.

#### Abstract (`docs/abstract/`)

No changes needed — Stage 0 has zero user-visible behavior change. The user-facing narrative (Phase 1 reference retrieval, Phase 2 personalization, user correction) lands with Stages 2, 6, and 8 respectively. Adding abstract copy now would describe behavior that does not yet exist.

#### Technical (`docs/technical/`)

- **Update** `docs/technical/dish_analysis/index.md` — extend the section outline to announce the new foundation page (see below). One new row in the index table.
- **Update** `docs/technical/dish_analysis/component_identification.md` — add a short "Personalization Store" sub-section under Data Model that links to the new foundation page and explains that Phase 1.1.1 (arriving in Stage 2) will read from it. Two-line forward reference only; no pipeline change is documented here yet.
- **Add new** `docs/technical/dish_analysis/personalized_food_index.md` — the canonical technical page for the table + CRUD + service module:
  - **Architecture** section: per-user BM25 corpus, scoped strictly by `user_id`, built per-request, no module-level cache.
  - **Data Model** section: `PersonalizedFoodDescription` class, column-by-column table mirroring the one in this plan, constraints (`uq_personalized_food_descriptions_query_id`, `ON DELETE CASCADE` from `DishImageQuery`).
  - **Pipeline** section: minimal vertical ASCII diagram showing `search_for_user` as a standalone call — callers arrive in Stages 2/6.
  - **Backend — Service Layer** section: signatures of `tokenize` and `search_for_user`, return shape, normalization rules.
  - **Backend — CRUD Layer** section: signatures of the four CRUD functions; note the `exclude_query_id` contract that Stage 2's write-after-read flow depends on.
  - **Constraints & Edge Cases**: empty corpus, empty query tokens, identical-score ties (break on `query_id DESC` so recent uploads win), ScoreScale = normalized-by-max-in-batch.
  - **Component Checklist** (per the docs-hierarchy rule): boxes for table + unique index + ORM class + CRUD funcs + service funcs + unit tests. Stage 0 ships all checked; the page exists so that Stages 2/4/6/8 can append their own checklist rows in-place rather than creating new pages for what is fundamentally the same infrastructure.
- **Update navigation** on the three affected pages: the new page sits after `nutritional_analysis.md` in `docs/technical/dish_analysis/index.md` order, so `nutritional_analysis.md`'s bottom nav gains a `Next: Personalized Food Index >` link, and the new page has `< Prev: Nutritional Analysis` / `Parent` / (no Next, last page) nav at both top and bottom per the documentation-hierarchy rules.

#### API Documentation (`docs/api_doc/`)

No changes needed — Stage 0 adds no API endpoints. (The project does not appear to have a `docs/api_doc/` tree yet; no seeding is required for this stage.)

#### To Delete

None.

#### To Update

- `docs/technical/dish_analysis/index.md` — add row 4 `[Personalized Food Index](./personalized_food_index.md)` and adjust neighbouring Prev/Next links.
- `docs/technical/dish_analysis/component_identification.md` — two-line forward-reference block under Data Model.
- `docs/technical/dish_analysis/nutritional_analysis.md` — update bottom navigation to include a `Next: Personalized Food Index >` link.

#### To Add New

- `docs/technical/dish_analysis/personalized_food_index.md` — full per-feature technical page per the template in `documentation_hierarchy.md`.

---

### Chrome Claude Extension Execution

**Skipped for Stage 0.** Per the user clarification in the planning phase: Stage 0 ships no UI and no observable HTTP behavior, so the Chrome Claude Extension E2E harness has nothing to click. The first stage that changes user-visible state is Stage 2 (adds `result_gemini.reference_image` after upload) — Chrome tests resume there.

If a Chrome spec is wanted regardless (e.g. for a smoke login check that the new migration did not break the app), the user can request `/webapp-dev:chrome-test-generate` directly; it would write a single sign-in smoke test under `docs/chrome_test/`. Default is to skip.

#### To Delete

None.

#### To Update

None.

#### To Add New

None.

---

## Dependencies

- **External library:** `rank-bm25` (added to root `requirements.txt`).
- **Existing tables:** `users` and `dish_image_query_prod_dev` — both already present; the new table foreign-keys to them.
- **Existing ORM:** `Base` declarative and `SessionLocal` in `backend/src/database.py`.
- **No downstream code consumes the new modules yet** — Stages 2, 4, 6, and 8 are the first consumers and are explicitly blocked on this PR landing.

## Resolved Decisions

- **Token normalization** — NFKD ASCII-fold + casefold + strip-non-alphanumeric + whitespace split (Option A, confirmed 2026-04-18). Aggressive ASCII folding is acceptable for the current target populations (EN / FR / MS / VI romanized captions). CJK captions will produce empty token lists and silently disable personalization for those users; re-open this decision before onboarding CJK users, at which point Stage 2 can swap in a script-aware tokenizer without changing the `List[str]` contract (the corpus is rebuilt per request, so no stored artefact to invalidate).
- **Similarity scaling** — max-in-batch normalization (Option A, confirmed 2026-04-18). `similarity_score = top_raw / max_raw` with a divide-by-zero guard. This is a **relative ranking signal only**: `similarity_score = 1.0` means "top of this batch", not "good match", and a single-row corpus always scores `1.0` regardless of overlap. Document this explicitly in the new technical page's "Constraints & Edge Cases" section so Stages 2 and 6 don't assume the threshold gate is load-bearing on its own. Re-open the decision when Stage 2 ships real threshold numbers (e.g. add a token-overlap multiplier, or calibrate a fixed BM25 ceiling against labeled data).
- **`on_delete` behavior for the `query_id` FK** — `ON DELETE CASCADE` (confirmed 2026-04-18). Purging a `DishImageQuery` row takes its personalization row with it, matching GDPR-style "delete my data" semantics and avoiding orphaned rows. The `user_id` FK keeps SQLAlchemy's default (no cascade); user deletion is a separate concern handled outside this stage.

## Open Questions

None — all decisions resolved 2026-04-18. Ready for implementation.
