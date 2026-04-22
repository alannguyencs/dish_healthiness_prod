"""
Phase 2.2 (Stage 6) — per-user personalization retrieval.

Queries the user's `personalized_food_descriptions` corpus with the union
of caption tokens (from Phase 1.1.1 reference_image.description) and
confirmed_dish_name tokens (from Stage 4 post-confirm). Each hit is joined
back to its DishImageQuery to carry `prior_nutrition_data`, and to the
personalization row itself for `corrected_nutrition_data` (Stage 8 writes).

Called from `trigger_nutrition_analysis_background` in parallel with
`extract_and_lookup_nutrition` via `asyncio.gather`. Signature is sync;
the caller schedules the call on the default executor via
`asyncio.to_thread`.
"""

import logging
from typing import Any, Dict, List, Optional

from src.configs import THRESHOLD_PHASE_2_2_SIMILARITY
from src.crud.crud_food_image_query import get_dish_image_query_by_id
from src.service import personalized_food_index

logger = logging.getLogger(__name__)

DEFAULT_TOP_K = 5


def _build_query_tokens(description: Optional[str], confirmed_dish_name: str) -> List[str]:
    """
    Token union: caption tokens ∪ confirmed-dish-name tokens.

    Either argument may be empty / None; the remaining side still produces
    a usable query. Both empty → empty list (caller short-circuits).
    """
    caption_tokens = set(personalized_food_index.tokenize(description or ""))
    dish_tokens = set(personalized_food_index.tokenize(confirmed_dish_name or ""))
    return list(caption_tokens | dish_tokens)


def lookup_personalization(
    user_id: int,
    query_id: int,
    description: Optional[str],
    confirmed_dish_name: str,
    top_k: int = DEFAULT_TOP_K,
    min_similarity: float = THRESHOLD_PHASE_2_2_SIMILARITY,
) -> List[Dict[str, Any]]:
    """
    Return up to `top_k` historical personalization matches for `user_id`.

    Each match carries:
        query_id                 — referenced DishImageQuery id
        image_url                — referenced dish's image URL
        description              — Phase 1.1.1 caption on the referenced row
        similarity_score         — 0..1 max-in-batch normalized
        prior_nutrition_data     — referenced DishImageQuery.result_gemini.nutrition_data, or None
        corrected_nutrition_data — personalization row's corrected_nutrition_data, or None

    Self-excluding: `search_for_user` is called with
    `exclude_query_id=query_id` so the current upload never matches itself.
    """
    query_tokens = _build_query_tokens(description, confirmed_dish_name)
    if not query_tokens:
        return []

    hits = personalized_food_index.search_for_user(
        user_id,
        query_tokens,
        top_k=top_k,
        min_similarity=min_similarity,
        exclude_query_id=query_id,
    )

    matches: List[Dict[str, Any]] = []
    for hit in hits:
        referenced = get_dish_image_query_by_id(hit["query_id"])
        prior_nutrition_data = None
        if referenced and referenced.result_gemini:
            prior_nutrition_data = referenced.result_gemini.get("nutrition_data")
        corrected_nutrition_data = getattr(
            hit.get("row"), "corrected_nutrition_data", None
        )
        matches.append(
            {
                "query_id": hit["query_id"],
                "image_url": hit["image_url"],
                "description": hit["description"],
                "similarity_score": hit["similarity_score"],
                "prior_nutrition_data": prior_nutrition_data,
                "corrected_nutrition_data": corrected_nutrition_data,
            }
        )
    return matches
