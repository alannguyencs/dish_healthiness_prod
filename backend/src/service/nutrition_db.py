"""
BM25-backed nutrition lookup over the four source databases.

Loads the full corpus from `nutrition_foods` (+ `nutrition_myfcd_nutrients`
for MyFCD's nested nutrient detail) into memory exactly once per
process, builds four per-source BM25 indices, and answers
`_search_dishes_direct` / `search_nutrition_database_enhanced` calls
in the verbatim row shape the consolidation prompt expects.

Stage 1 ships this as library code only — no pipeline call sites yet.
Stage 5 wires it into the Phase 2 background task; Stage 9 benchmarks
it against the 846-query NDCG eval set.

The confidence formula constants live in `_nutrition_scoring.py`. They
are a verbatim port of the reference project at
`/Volumes/wd/projects/dish_healthiness/src/service/collect_from_nutrition_db.py`
which measured NDCG@10 = 0.7744 on the eval set. Editing them
invalidates the Stage 9 regression gate.
"""

import logging
import re
import threading
import unicodedata
from typing import Any, Dict, List, Optional, Set

from rank_bm25 import BM25Okapi

from src.crud import crud_nutrition
from src.service._nutrition_collect import (
    collect_from_nutrition_db as _collect_from_nutrition_db,
)
from src.service._nutrition_scoring import direct_bm25_search

logger = logging.getLogger(__name__)


_NORMALIZE_PUNCT_RE = re.compile(r"[^\w\s]")
_NORMALIZE_WS_RE = re.compile(r"\s+")


class NutritionCollectionError(Exception):
    """Base exception for nutrition collection operations."""


class NutritionDBEmptyError(NutritionCollectionError):
    """Raised on first-use when `nutrition_foods` is empty."""


def _normalize_text(text: str) -> str:
    """
    NFKD-fold + casefold + strip punctuation + collapse whitespace.

    Used at runtime on the user query, and at seed time inside the
    seed script to build the persisted `searchable_document`. Same
    transform on both sides so corpus and query share a vocabulary.
    """
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text).casefold()
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = _NORMALIZE_PUNCT_RE.sub(" ", text)
    text = _NORMALIZE_WS_RE.sub(" ", text).strip()
    return text


def _materialize_food(row) -> Dict[str, Any]:
    """
    Convert an ORM `NutritionFood` row into the dict shape the
    BM25 reader expects (preserves the source-CSV field names downstream
    consumers / prompts already reference).
    """
    raw = dict(row.raw_data or {})
    raw.setdefault("food_name", row.food_name)
    if row.source == "malaysian_food_calories":
        raw.setdefault("food_item", row.food_name)
        raw.setdefault("category", row.category)
        raw.setdefault("calories", row.calories)
    elif row.source == "ciqual":
        raw.setdefault("food_name_eng", row.food_name_eng)
    return raw


class NutritionCollectionService:  # pylint: disable=too-many-instance-attributes
    """
    Per-source BM25 retrieval over the seeded nutrition corpus.

    The constructor pays the index-build cost once per instance.
    Use `get_nutrition_service()` for the lazy singleton; only
    instantiate the class directly in tests where a fresh corpus
    is wanted.
    """

    def __init__(self) -> None:
        grouped = crud_nutrition.get_all_foods_grouped_by_source()
        if not any(grouped.values()):
            raise NutritionDBEmptyError(
                "nutrition_foods is empty. Run "
                "`python -m scripts.seed.load_nutrition_db` from backend/."
            )

        myfcd_nutrients = crud_nutrition.get_myfcd_nutrients_grouped_by_ndb_id()

        self.malaysian_foods = [_materialize_food(r) for r in grouped["malaysian_food_calories"]]
        self.myfcd_foods = self._materialize_myfcd(grouped["myfcd"], myfcd_nutrients)
        self.anuvaad_foods = [_materialize_food(r) for r in grouped["anuvaad"]]
        self.ciqual_foods = [_materialize_food(r) for r in grouped["ciqual"]]

        self._malaysian_docs = [
            (row.searchable_document or "").split() for row in grouped["malaysian_food_calories"]
        ]
        self._myfcd_docs = [(row.searchable_document or "").split() for row in grouped["myfcd"]]
        self._anuvaad_docs = [
            (row.searchable_document or "").split() for row in grouped["anuvaad"]
        ]
        self._ciqual_docs = [(row.searchable_document or "").split() for row in grouped["ciqual"]]

        self.malaysian_bm25 = BM25Okapi(self._malaysian_docs) if self._malaysian_docs else None
        self.myfcd_bm25 = BM25Okapi(self._myfcd_docs) if self._myfcd_docs else None
        self.anuvaad_bm25 = BM25Okapi(self._anuvaad_docs) if self._anuvaad_docs else None
        self.ciqual_bm25 = BM25Okapi(self._ciqual_docs) if self._ciqual_docs else None

        self._current_dish_tokens: Optional[Set[str]] = None

        logger.info(
            "Nutrition service ready: %d malaysian, %d myfcd, %d anuvaad, %d ciqual",
            len(self.malaysian_foods),
            len(self.myfcd_foods),
            len(self.anuvaad_foods),
            len(self.ciqual_foods),
        )

    @staticmethod
    def _materialize_myfcd(myfcd_rows, nutrients_by_ndb) -> List[Dict[str, Any]]:
        """Re-attach MyFCD's long-format nutrients onto each food row."""
        out = []
        for row in myfcd_rows:
            food = _materialize_food(row)
            nested: Dict[str, Dict[str, Any]] = {}
            for n in nutrients_by_ndb.get(row.source_food_id, []):
                nested[n.nutrient_name] = {
                    "value_per_100g": n.value_per_100g,
                    "value_per_serving": n.value_per_serving,
                    "unit": n.unit,
                    "category": n.category,
                }
            food["ndb_id"] = row.source_food_id
            food["serving_size_grams"] = row.serving_size_grams
            food["serving_unit"] = row.serving_unit
            food["nutrients"] = nested
            out.append(food)
        return out

    def _per_source_indices(self):
        """Yield (bm25, metadata, source_name) for the four sources."""
        return (
            (self.malaysian_bm25, self.malaysian_foods, "malaysian_food_calories"),
            (self.myfcd_bm25, self.myfcd_foods, "myfcd"),
            (self.anuvaad_bm25, self.anuvaad_foods, "anuvaad"),
            (self.ciqual_bm25, self.ciqual_foods, "ciqual"),
        )

    def _search_dishes_direct(
        self,
        user_input: str,
        top_k: int = 10,
        min_confidence: float = 0.1,
    ) -> List[Dict[str, Any]]:
        """
        Cross-source BM25 search of `user_input` against all four indices.

        Returns up to `top_k` rows with `confidence >= min_confidence`,
        sorted by confidence descending.
        """
        input_tokens = _normalize_text(user_input).split()
        if not input_tokens:
            return []

        results: List[Dict[str, Any]] = []
        for bm25, metadata, db_type in self._per_source_indices():
            if bm25 is None:
                continue
            results.extend(
                direct_bm25_search(
                    input_tokens, bm25, metadata, db_type, top_k, self._current_dish_tokens
                )
            )

        results.sort(key=lambda hit: hit["confidence"], reverse=True)
        return [hit for hit in results if hit["confidence"] >= min_confidence][:top_k]

    def collect_from_nutrition_db(
        self,
        text: str,
        min_confidence: int = 70,
        deduplicate: bool = True,
    ) -> Dict[str, Any]:
        """
        Stage-7-compatible full-shape lookup. Thin delegator to
        `_nutrition_collect.collect_from_nutrition_db` to keep this module
        under the 300-line cap. See that module for details.
        """
        return _collect_from_nutrition_db(self, text, min_confidence, deduplicate)

    def search_nutrition_database_enhanced(
        self,
        dish_name: str,
        related_keywords: str,
        estimated_quantity: str,
        top_k: int = 10,
    ) -> Dict[str, Any]:
        """
        Dish-name-priority + descriptor-keyword search.

        `dish_name` tokens are weighted as core; `related_keywords`
        (comma-separated) become descriptors. Sets
        `self._current_dish_tokens` for the duration of the call so
        the scoring formula weights core matches over descriptors.
        """
        keywords = [k.strip().lower() for k in (related_keywords or "").split(",") if k.strip()]
        keywords = list(dict.fromkeys(keywords))

        dish_name_tokens = set(_normalize_text(dish_name or "").split())
        descriptor_tokens: Set[str] = set()
        for kw in keywords:
            descriptor_tokens.update(_normalize_text(kw).split())
        descriptor_tokens -= dish_name_tokens
        all_tokens = list(dish_name_tokens | descriptor_tokens)

        prior = self._current_dish_tokens
        self._current_dish_tokens = dish_name_tokens
        try:
            all_matches: List[Dict[str, Any]] = []
            for bm25, metadata, db_type in self._per_source_indices():
                if bm25 is None:
                    continue
                all_matches.extend(
                    direct_bm25_search(
                        all_tokens, bm25, metadata, db_type, top_k, dish_name_tokens
                    )
                )
        finally:
            self._current_dish_tokens = prior

        all_matches.sort(
            key=lambda hit: (hit["confidence"], hit["raw_bm25_score"]),
            reverse=True,
        )

        return {
            "matches": all_matches[:top_k],
            "search_strategy": "OR logic - match ANY keyword",
            "keywords_used": keywords,
            "total_matches": len(all_matches[:top_k]),
            "dish_name": dish_name,
            "estimated_quantity": estimated_quantity,
        }


_INSTANCE: Optional[NutritionCollectionService] = None
_INSTANCE_LOCK = threading.Lock()


def get_nutrition_service() -> NutritionCollectionService:
    """
    Lazy thread-safe singleton accessor.

    Pays the corpus-load + four-index-build cost on the first call.
    Subsequent callers (within the same process) get the same instance.
    """
    global _INSTANCE  # pylint: disable=global-statement
    if _INSTANCE is not None:
        return _INSTANCE
    with _INSTANCE_LOCK:
        if _INSTANCE is None:
            _INSTANCE = NutritionCollectionService()
    return _INSTANCE


def _reset_singleton_for_tests() -> None:
    """Test-only hook so per-test fixtures get a fresh instance."""
    global _INSTANCE  # pylint: disable=global-statement
    _INSTANCE = None
