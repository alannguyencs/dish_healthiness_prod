"""
Per-user BM25 retrieval over the `personalized_food_descriptions` table.

Stage 0 foundation: exposes two functions that Stages 2, 4, 6 call into
without further modification. The index is built on the fly from the
user's rows (no persistence, no module-level cache) so there is no
stored artefact to invalidate when the tokenizer or scoring scheme is
later refined.

Ranking uses BM25 so IDF-common terms (e.g. "rice", "curry") get
down-weighted. The exposed `similarity_score` is a Jaccard overlap on
the token sets (|query ∩ doc| / |query ∪ doc|) — an absolute [0, 1]
measure that the callers' threshold constants (0.25 / 0.30 / 0.35) gate
on meaningfully.
"""

import re
import unicodedata
from typing import Any, Dict, List, Optional

from rank_bm25 import BM25Okapi

from src.crud import crud_personalized_food


_TOKEN_STRIP_RE = re.compile(r"[^a-z0-9\s]+")


def tokenize(text: str) -> List[str]:
    """
    Normalize and tokenize a caption for BM25.

    NFKD decomposition drops diacritics into combining marks, which the
    non-alphanumeric strip then removes. Casefold gives locale-insensitive
    lowercasing. Empty / whitespace-only input returns [].

    Args:
        text (str): Input caption or dish name

    Returns:
        List[str]: Token list, lowercase ASCII, whitespace-split
    """
    if not text:
        return []
    nfkd = unicodedata.normalize("NFKD", text)
    folded = nfkd.casefold()
    ascii_only = _TOKEN_STRIP_RE.sub(" ", folded)
    return ascii_only.split()


def search_for_user(
    user_id: int,
    query_tokens: List[str],
    *,
    top_k: int = 1,
    min_similarity: float = 0.0,
    exclude_query_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Build a BM25 index from the user's rows and return the top matches.

    Each result dict has the fixed shape Stages 2/4/6/8 bind to:
        {
            "query_id": int,
            "image_url": str | None,
            "description": str | None,
            "similarity_score": float,
            "row": PersonalizedFoodDescription,
        }

    Scoring: rows are ranked by BM25 (IDF-aware), but `similarity_score`
    is a Jaccard overlap on token sets — an absolute [0, 1] measure the
    callers' thresholds gate on meaningfully. Zero-overlap rows are
    dropped regardless of `min_similarity`. Ties break on `query_id DESC`
    so more recent uploads win.

    Args:
        user_id (int): Owner whose corpus to search
        query_tokens (List[str]): Tokenized query; empty returns []
        top_k (int): Max hits to return
        min_similarity (float): Drop hits whose Jaccard is below this
        exclude_query_id (Optional[int]): Exclude this query's own row so
            write-after-read callers cannot match themselves

    Returns:
        List[Dict[str, Any]]: Up to `top_k` hits, highest first
    """
    if not query_tokens:
        return []

    rows = crud_personalized_food.get_all_rows_for_user(user_id, exclude_query_id=exclude_query_id)
    corpus_rows = [row for row in rows if row.tokens]
    if not corpus_rows:
        return []

    corpus_tokens = [list(row.tokens) for row in corpus_rows]
    bm25 = BM25Okapi(corpus_tokens)
    bm25_scores = bm25.get_scores(list(query_tokens))

    query_set = set(query_tokens)
    scored: List[Dict[str, Any]] = []
    for row, doc_tokens, bm25_score in zip(corpus_rows, corpus_tokens, bm25_scores):
        doc_set = set(doc_tokens)
        union = query_set | doc_set
        similarity = (len(query_set & doc_set) / len(union)) if union else 0.0
        if similarity <= 0.0 or similarity < min_similarity:
            continue
        scored.append(
            {
                "query_id": row.query_id,
                "image_url": row.image_url,
                "description": row.description,
                "similarity_score": similarity,
                "row": row,
                "_bm25": float(bm25_score),
            }
        )

    scored.sort(key=lambda hit: (-hit["_bm25"], -hit["similarity_score"], -hit["query_id"]))
    for hit in scored:
        hit.pop("_bm25", None)
    return scored[:top_k]
