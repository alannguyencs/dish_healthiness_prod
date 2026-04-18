"""
Phase 1.1.1 orchestrator — fast-caption + per-user BM25 search + write-after-read.

Composes three Stage 0 / Stage 2 primitives into a single coroutine the
Phase 1 background task calls before the Step 1 Pro component-ID call:

1. `generate_fast_caption_async` (Gemini 2.0 Flash plain-text).
2. `personalized_food_index.search_for_user` (per-user BM25).
3. `crud_personalized_food.insert_description_row` (write-after-read).

Returns the payload the caller stashes on `result_gemini.reference_image`,
or None on cold start / below-threshold / graceful-degrade / retry
short-circuit. See `docs/plan/260418_stage2_phase1_1_1_fast_caption.md`
for the full failure-mode table.
"""

import logging
from pathlib import Path
from typing import Any, Dict, Optional, Union

from src.configs import THRESHOLD_PHASE_1_1_1_SIMILARITY
from src.crud import crud_personalized_food
from src.crud.crud_food_image_query import get_dish_image_query_by_id
from src.service import personalized_food_index
from src.service.llm.fast_caption import generate_fast_caption_async

logger = logging.getLogger(__name__)


async def resolve_reference_for_upload(
    user_id: int,
    query_id: int,
    image_path: Union[str, Path],
) -> Optional[Dict[str, Any]]:
    """
    Run Phase 1.1.1 for a freshly uploaded dish.

    Args:
        user_id (int): Owner of the upload.
        query_id (int): DishImageQuery id for this upload.
        image_path (Union[str, Path]): JPEG path on disk.

    Returns:
        Optional[Dict[str, Any]]: A dict with keys
            `{query_id, image_url, description, similarity_score,
              prior_step1_data}`
            on warm-start match, or None on:
            - retry short-circuit (row already present for this query_id)
            - fast-caption failure (graceful degrade)
            - empty tokens (nothing to search with)
            - cold start or below-threshold top-1
    """
    # Retry idempotency: if a prior attempt already wrote the row, do not
    # re-run the caption/search/insert path. The existing row's payload
    # (if any) is already persisted on result_gemini.reference_image by
    # the earlier attempt; the caller simply preserves it.
    if crud_personalized_food.get_row_by_query_id(query_id) is not None:
        logger.info("Phase 1.1.1 skipped on retry for query_id=%s", query_id)
        return None

    # Fast caption — graceful degrade on any failure.
    try:
        description = await generate_fast_caption_async(image_path)
    except (ValueError, FileNotFoundError) as exc:
        logger.warning(
            "Phase 1.1.1 fast caption failed for query_id=%s; graceful degrade: %s",
            query_id,
            exc,
        )
        return None

    query_tokens = personalized_food_index.tokenize(description)

    # If tokenization collapses the caption to empty (e.g. "..."), skip the
    # search — we have nothing to match with. Still insert the row so future
    # uploads see this upload in their corpus (they will miss on tokens=[]
    # which is fine).
    if query_tokens:
        matches = personalized_food_index.search_for_user(
            user_id,
            query_tokens,
            top_k=1,
            min_similarity=THRESHOLD_PHASE_1_1_1_SIMILARITY,
            exclude_query_id=query_id,
        )
    else:
        matches = []

    reference: Optional[Dict[str, Any]]
    top_similarity: Optional[float]
    if matches:
        top = matches[0]
        prior = get_dish_image_query_by_id(top["query_id"])
        prior_step1_data = (prior.result_gemini or {}).get("step1_data") if prior else None
        reference = {
            "query_id": top["query_id"],
            "image_url": top["image_url"],
            "description": top["description"],
            "similarity_score": top["similarity_score"],
            "prior_step1_data": prior_step1_data,
        }
        top_similarity = top["similarity_score"]
    else:
        reference = None
        top_similarity = None

    # Fetch the uploader's image_url from the DishImageQuery row so later
    # stages can read it off the personalization row without a second join.
    record = get_dish_image_query_by_id(query_id)
    image_url = record.image_url if record else None

    try:
        crud_personalized_food.insert_description_row(
            user_id,
            query_id,
            image_url=image_url,
            description=description,
            tokens=query_tokens,
            similarity_score_on_insert=top_similarity,
        )
    except Exception as exc:  # pylint: disable=broad-exception-caught
        # Concurrent retry races could trip the unique-index guard. The
        # reference payload we already computed is still valid to return;
        # downstream stages do not require the row to be present for this
        # specific query_id (Stage 4/8 updaters tolerate missing rows).
        logger.warning(
            "Phase 1.1.1 insert_description_row failed for query_id=%s; "
            "continuing with computed reference: %s",
            query_id,
            exc,
        )

    return reference
