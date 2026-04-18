"""
Per-user BM25 retrieval over the `personalized_food_descriptions` table.

Stage 0 foundation: exposes two functions that Stages 2, 4, 6 call into
without further modification. The index is built on the fly from the
user's rows (no persistence, no module-level cache) so there is no
stored artefact to invalidate when the tokenizer or scoring scheme is
later refined.

Similarity is a relative ranking signal: the top hit always scores 1.0.
See `docs/technical/dish_analysis/personalized_food_index.md` for the
"Constraints & Edge Cases" discussion.
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

    Scoring: raw BM25 scores are normalized by max-in-batch into [0, 1].
    The top hit is always 1.0. When BM25 IDF collapses to zero on tiny
    corpora (1-doc, or 2-doc with df == N/2), fall back to token-overlap
    ratio so cold-start users still get a ranking signal. Ties break on
    `query_id DESC` so more recent uploads win.

    Args:
        user_id (int): Owner whose corpus to search
        query_tokens (List[str]): Tokenized query; empty returns []
        top_k (int): Max hits to return
        min_similarity (float): Drop hits below this normalized score
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

    max_bm25 = max(bm25_scores) if len(bm25_scores) > 0 else 0.0
    if max_bm25 > 0:
        raw_scores = [max(float(s), 0.0) for s in bm25_scores]
    else:
        # BM25 IDF collapses to 0 (or goes negative) when df/N is degenerate
        # — e.g. 1-doc corpus, or a term appearing in >=50% of a 2-doc
        # corpus. Fall back to token-overlap ratio so cold-start users still
        # get a comparable relative signal.
        query_set = set(query_tokens)
        raw_scores = [
            float(len(set(doc) & query_set)) / float(len(query_set)) for doc in corpus_tokens
        ]

    max_raw = max(raw_scores) if raw_scores else 0.0
    if max_raw <= 0:
        return []

    scored: List[Dict[str, Any]] = []
    for row, raw in zip(corpus_rows, raw_scores):
        normalized = float(raw) / float(max_raw)
        if normalized < min_similarity:
            continue
        scored.append(
            {
                "query_id": row.query_id,
                "image_url": row.image_url,
                "description": row.description,
                "similarity_score": normalized,
                "row": row,
            }
        )

    scored.sort(key=lambda hit: (-hit["similarity_score"], -hit["query_id"]))
    return scored[:top_k]
