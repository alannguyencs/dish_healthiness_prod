"""
BM25 scoring + confidence formula for the nutrition lookup.

Extracted from `nutrition_db.py` so the verbatim port of the reference
project's confidence formula sits in its own file. The formula constants
(0.85 core / 0.15 descriptors, +0.20 / +0.15 bonuses, 0.8 keyword + 0.2
BM25-quality, scaled into [0.50, 0.95]) are tuned against the 846-query
NDCG eval set; editing them invalidates the Stage 9 regression gate.
"""

import math
from typing import Any, Dict, List, Optional, Set


_QUANTITY_WORDS = frozenset(
    {
        "1",
        "2",
        "3",
        "4",
        "5",
        "6",
        "7",
        "8",
        "9",
        "small",
        "large",
        "medium",
        "big",
        "mini",
        "wraps",
        "pieces",
        "servings",
    }
)


def get_display_name(food_data: Dict[str, Any], db_type: str) -> str:
    """Return the source-appropriate display name."""
    if db_type == "malaysian_food_calories":
        return str(food_data.get("food_item") or food_data.get("food_name") or "Unknown")
    if db_type == "ciqual":
        return str(food_data.get("food_name_eng") or food_data.get("food_name") or "Unknown")
    return str(food_data.get("food_name") or "Unknown")


def direct_bm25_search(  # pylint: disable=too-many-locals
    input_tokens: List[str],
    bm25_index,
    metadata: List[Dict[str, Any]],
    db_type: str,
    top_k: int,
    current_dish_tokens: Optional[Set[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Score `input_tokens` against one source-specific BM25 index.

    Returns at most `top_k` rows with positive raw BM25 score, each
    carrying the verbatim row shape Stage 7's prompt expects:
        matched_food_name, source, confidence (0-1),
        confidence_score (0-100), nutrition_data, search_method,
        raw_bm25_score, matched_keywords, total_keywords.
    """
    scores = bm25_index.get_scores(input_tokens)
    top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]

    positive = [scores[i] for i in top_indices if scores[i] > 0]
    max_score = max(positive) if positive else 1.0

    results: List[Dict[str, Any]] = []
    input_words = set(input_tokens)
    dish_tokens = current_dish_tokens or input_words
    core_dish_tokens = dish_tokens - _QUANTITY_WORDS
    num_descriptors = len(input_words) - len(dish_tokens)

    for idx in top_indices:
        raw_score = scores[idx]
        if raw_score <= 0:
            continue

        food_data = metadata[idx]
        food_name = get_display_name(food_data, db_type)
        food_words = set(food_name.lower().split())
        matched_words = food_words & input_words
        matched_dish = food_words & core_dish_tokens
        matched_descriptors = matched_words - matched_dish

        if input_words:
            dish_ratio = len(matched_dish) / max(len(core_dish_tokens), 1)
            descriptor_ratio = (
                len(matched_descriptors) / num_descriptors if num_descriptors > 0 else 0.0
            )
            keyword_score = dish_ratio * 0.85 + descriptor_ratio * 0.15
            if len(matched_dish) >= 2:
                keyword_score = min(keyword_score + 0.20, 1.0)
            if len(matched_dish) >= 3:
                keyword_score = min(keyword_score + 0.15, 1.0)
        else:
            keyword_score = 0.0

        bm25_quality = math.log(1 + raw_score) / math.log(1 + max_score) if max_score > 0 else 0.0
        base_confidence = (keyword_score * 0.8) + (bm25_quality * 0.2)
        confidence = min(0.50 + base_confidence * 0.45, 0.95)

        results.append(
            {
                "matched_food_name": food_name,
                "source": db_type,
                "confidence": confidence,
                "confidence_score": round(confidence * 100, 1),
                "nutrition_data": food_data,
                "search_method": "Direct BM25",
                "raw_bm25_score": raw_score,
                "matched_keywords": len(matched_words),
                "total_keywords": len(input_words),
            }
        )

    return results
