# Personalized Food Index — Technical Design

[< Prev: Nutritional Analysis](./nutritional_analysis.md) | [Parent](./index.md) | [Next: Nutrition DB >](./nutrition_db.md)

## Related Docs

- Discussion: [docs/discussion/260418_food_db.md](../../discussion/260418_food_db.md) — end-to-end workflow diagram this foundation unblocks
- Plan: [docs/plan/260418_stage0_personalized_food_index.md](../../plan/260418_stage0_personalized_food_index.md)

## Architecture

Per-user retrieval of prior food uploads. Scoped strictly by `user_id` at the SQL layer; the service layer cannot return rows owned by another user. The index (BM25) is rebuilt on the fly per request — no persistence, no module-level cache. Stage 0 ships only the foundation; Phase 1.1.1, Phase 1.2, Phase 2.2, and Phase 2.4 (arriving in Stages 2, 4, 6, 8 of the end-to-end workflow) are the downstream consumers.

```
+-----------------------+       +----------------------------+
|  Background tasks     | ----> |  crud_personalized_food    |
|  (Phase 1.1.1 / 1.2 / |       |  insert / update / read    |
|   2.2 / 2.4, future)  |       +--------------+-------------+
+-----------------------+                      |
            |                                  v
            |                        +---------------------+
            +----------------------> |  personalized_food_ |
                                     |  descriptions table |
                                     +---------------------+
            |
            v
+-------------------------------+
|  personalized_food_index      |
|    .tokenize(text)            |
|    .search_for_user(user_id,  |
|        query_tokens, ...)     |
+-------------------------------+
```

## Data Model

**`PersonalizedFoodDescription`** — `backend/src/models.py`. Table `personalized_food_descriptions`.

| Column | Type | Nullable | Writer stage | Purpose |
|---|---|---|---|---|
| `id` | SERIAL PK | no | Stage 0 | surrogate key |
| `user_id` | INT FK → `users.id` | no | Stage 0 | scope; `idx_personalized_food_descriptions_user_id` |
| `query_id` | INT FK → `dish_image_query_prod_dev.id` | no | Stage 0 | 1:1 join back to `DishImageQuery`; `uq_personalized_food_descriptions_query_id` unique index; `ON DELETE CASCADE` |
| `image_url` | VARCHAR | yes | Stage 2 | mirrors `DishImageQuery.image_url` |
| `description` | TEXT | yes | Stage 2 | Gemini 2.0 Flash caption |
| `tokens` | JSONB | yes | Stage 2 | tokens used as the BM25 corpus document |
| `similarity_score_on_insert` | FLOAT | yes | Stage 2 | top-1 score vs prior corpus at insert time (debug/audit) |
| `confirmed_dish_name` | TEXT | yes | Stage 4 | user-confirmed dish name |
| `confirmed_portions` | FLOAT | yes | Stage 4 | sum of confirmed component servings |
| `confirmed_tokens` | JSONB | yes | Stage 4 | tokenized `confirmed_dish_name`; Stage 6 queries are the union of `tokens` + `confirmed_tokens` |
| `corrected_nutrition_data` | JSONB | yes | Stage 8 | user manual nutrient corrections, ground truth for Stage 6 lookups |
| `created_at` | TIMESTAMP | no | Stage 0 | set on insert |
| `updated_at` | TIMESTAMP | no | Stage 0 | bumped on every write |

## Pipeline

```
caller (Phase 1.1.1 / 2.2, later)
  │
  ▼
search_for_user(user_id, query_tokens, top_k, min_similarity, exclude_query_id)
  │
  ├── crud_personalized_food.get_all_rows_for_user(user_id, exclude_query_id)
  │       │
  │       └── SELECT * FROM personalized_food_descriptions
  │             WHERE user_id = ? [AND query_id != ?]
  │             ORDER BY id ASC
  │
  ├── drop rows with empty tokens
  ├── BM25Okapi(corpus_tokens).get_scores(query_tokens)
  │       └── if max score ≤ 0 → fall back to token-overlap ratio
  ├── normalize by max-in-batch → [0, 1]
  ├── filter by min_similarity
  └── sort by (-similarity_score, -query_id), take top_k
  │
  ▼
[{query_id, image_url, description, similarity_score, row}, ...]
```

## Algorithms

### `tokenize(text) -> List[str]`

- `unicodedata.normalize("NFKD", text)` — decompose accented characters into base + combining marks.
- `.casefold()` — locale-insensitive lowercase.
- `re.sub(r"[^a-z0-9\s]+", " ", ...)` — strip combining marks and punctuation together.
- `.split()` — whitespace tokens.
- Empty / whitespace-only input returns `[]`.
- Deterministic: the same input produces the same token list on every call.

### `search_for_user(...) -> List[Dict]`

- Corpus source is `crud_personalized_food.get_all_rows_for_user`, always scoped to the caller-supplied `user_id`. Rows with `tokens is None` or `tokens == []` are skipped.
- Primary scoring: `rank_bm25.BM25Okapi` over the row-token lists.
- Fallback scoring: when BM25's top raw score is ≤ 0 (IDF collapse on 1–2 row corpora, or no term overlap), each row scores `len(doc ∩ query) / len(query)` — a bounded [0, 1] lexical-overlap ratio. This keeps cold-start users from silently receiving no results when they actually have a matching prior upload.
- Normalization: divide every row's raw score by the batch maximum so the top hit is always `1.0`. Rows with negative BM25 scores are clamped to `0` before normalization.
- Filter: drop any result below `min_similarity`.
- Tiebreak: `query_id DESC` — recent uploads win.
- Return shape is stable. Stages 2/4/6/8 bind against these exact keys: `query_id, image_url, description, similarity_score, row`.

## Backend — Service Layer

| Function | File | Purpose |
|---|---|---|
| `tokenize(text: str) -> List[str]` | `backend/src/service/personalized_food_index.py` | NFKD + casefold + strip + split |
| `search_for_user(user_id, query_tokens, *, top_k, min_similarity, exclude_query_id) -> List[Dict]` | same | Build per-request BM25, score, filter, sort |

No class. Module-level functions so later callers (Stages 2, 4, 6) can import directly without instantiation.

## Backend — CRUD Layer

`backend/src/crud/crud_personalized_food.py`:

| Function | Purpose |
|---|---|
| `insert_description_row(user_id, query_id, *, image_url, description, tokens, similarity_score_on_insert)` | Stage 2 write path. Raises `IntegrityError` on duplicate `query_id`. Sets `created_at == updated_at` at insert. |
| `update_confirmed_fields(query_id, *, confirmed_dish_name, confirmed_portions, confirmed_tokens)` | Stage 4 write. Returns `None` if the row does not exist (Stage 4 logs and moves on). |
| `update_corrected_nutrition_data(query_id, payload)` | Stage 8 write. Returns `None` on missing row. |
| `get_all_rows_for_user(user_id, *, exclude_query_id)` | Used by `search_for_user` to build the per-request corpus. Deterministic `id ASC` order. `exclude_query_id` is how Stage 2's write-after-read contract prevents self-matching. |

The module is deliberately **not** re-exported from the `crud_food_image_query.py` facade: that facade is scoped to `DishImageQuery` concerns. Callers import the new module directly.

## External Integrations

None. `rank-bm25` is an in-process Python library, added to `requirements.txt` at the repo root.

## Constraints & Edge Cases

- **Empty corpus.** `search_for_user` returns `[]` when the user has no rows (cold-start) or when all rows were excluded.
- **Empty query tokens.** Short-circuits to `[]` before touching the DB.
- **Single-row corpus / BM25 IDF collapse.** BM25 returns 0 for every row when `df/N` is degenerate. The service falls back to token-overlap ratio so retrieval still works; callers should not assume `similarity_score` is a BM25-quality number.
- **`similarity_score` is a ranking signal, not an absolute quality number.** The top hit is always 1.0. Downstream stages (thresholds like `THRESHOLD_PHASE_1_1_1_SIMILARITY = 0.25`) must treat this as "top of the batch" and rely on the prompt framing ("reference is a hint, not ground truth") for quality control. Absolute-quality scoring will be revisited in Stage 2 once real user data is available.
- **Self-matching is the caller's responsibility.** Stage 0 provides `exclude_query_id`; it is on the Phase 1.1.1 orchestrator to pass its own in-flight `query_id` so the current upload cannot match itself. Stage 2 implements the write-after-read insertion order as the belt-and-suspenders guarantee: the orchestrator calls `search_for_user(..., exclude_query_id=query_id)` (filter) AND inserts the new row only after the search returns (order). Either alone would suffice under current assumptions; both together tolerate a future refactor that re-orders steps or drops `exclude_query_id` without silently re-introducing self-matches.
- **Row deletion cascades with the dish.** FK `ON DELETE CASCADE` means purging a `DishImageQuery` also removes its personalization row. Matches GDPR-style "delete my data" semantics.
- **Tokenizer is ASCII-folding.** Works for EN / FR / MS / VI romanized captions. CJK captions produce empty token lists and are therefore invisible to retrieval; revisit before onboarding CJK users. Swapping the tokenizer later does not invalidate any stored artefact because the index is rebuilt per request.

## Component Checklist

- [x] `personalized_food_descriptions` table — `backend/sql/create_tables.sql`
- [x] `idx_personalized_food_descriptions_user_id` B-tree index
- [x] `uq_personalized_food_descriptions_query_id` unique index
- [x] `PersonalizedFoodDescription` ORM class — `backend/src/models.py`
- [x] CRUD `insert_description_row` — `backend/src/crud/crud_personalized_food.py`
- [x] CRUD `update_confirmed_fields`
- [x] CRUD `update_corrected_nutrition_data`
- [x] CRUD `get_all_rows_for_user` with `exclude_query_id`
- [x] Service `tokenize` — `backend/src/service/personalized_food_index.py`
- [x] Service `search_for_user` with max-in-batch normalization + token-overlap fallback
- [x] `rank-bm25` dependency — `requirements.txt`
- [x] Unit tests CRUD — `backend/tests/test_crud_personalized_food.py`
- [x] Unit tests index — `backend/tests/test_personalized_food_index.py`
- [x] Stage 2 (Phase 1.1.1): fast-caption + retrieval wired into `analyze_image_background` (see [component_identification.md](./component_identification.md#phase-111--fast-caption--reference-retrieval))
- [x] Stage 4 (Phase 1.2): `update_confirmed_fields` called from `confirm_identification_and_trigger_nutrition` (see [user_customization.md](./user_customization.md#personalization-enrichment-stage-4))
- [x] Stage 6 (Phase 2.2): `search_for_user` called from `service/personalized_lookup.py::lookup_personalization`, gathered in parallel with Phase 2.1 inside `trigger_nutrition_analysis_background` (see [nutritional_analysis.md § Phase 2.2](./nutritional_analysis.md#phase-22--personalization-lookup-stage-6))
- [x] Stage 7 (Phase 2.3): Nutritional Analysis prompt reads `result_gemini.personalized_matches` via `__PERSONALIZED_BLOCK__` placeholder; gated on `similarity_score >= 0.30` for text block, `>= 0.35` for image-B attach. See [nutritional_analysis.md § Phase 2.3](./nutritional_analysis.md#phase-23--reference-assisted-prompt-stage-7).
- [x] Stage 8 (Phase 2.4): `update_corrected_nutrition_data` called from `POST /api/item/{record_id}/correction` (see [nutritional_analysis.md § Phase 2.4](./nutritional_analysis.md#phase-24--user-review--correction-stage-8)). Stage 6's `lookup_personalization` surfaces the written `corrected_nutrition_data` on each match so Stage 8's PersonalizationMatches panel renders the user-verified nutrients with a badge.

---

[< Prev: Nutritional Analysis](./nutritional_analysis.md) | [Parent](./index.md) | [Next: Nutrition DB >](./nutrition_db.md)
