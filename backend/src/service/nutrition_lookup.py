"""
Phase 2.1 (Stage 5) — nutrition-DB lookup orchestrator.

Composes Stage 1's `NutritionCollectionService.collect_from_nutrition_db`
into the reference project's per-component + dish_name search loop, with
a comma-joined combined-terms fallback when the best individual match
scores below 0.75.

Public surface: one function, `extract_and_lookup_nutrition`. Called from
`trigger_nutrition_analysis_background` before the Gemini 2.5 Pro call so the
resulting dict can be persisted on `result_gemini.nutrition_db_matches`
and survive any subsequent Step 2 failure / retry.

Reference: /Volumes/wd/projects/dish_healthiness/src/service/ai_agent.py
`AIAgent._extract_and_lookup_nutrition`. Simplified to the Gemini-only
input already available here — no OpenAI branch.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from src.service.nutrition_db import NutritionDBEmptyError, get_nutrition_service

logger = logging.getLogger(__name__)

_FALLBACK_TRIGGER_THRESHOLD = 0.75
_STAGE_1_MIN_CONFIDENCE = 70
_STAGE_2_MIN_CONFIDENCE = 60


def _dedupe_preserve(values: List[str]) -> List[str]:
    """Order-preserving dedupe of a string list, dropping empty entries."""
    seen: Dict[str, None] = {}
    for value in values:
        if value and value not in seen:
            seen[value] = None
    return list(seen.keys())


def _attempt_record(query: str, result: Dict[str, Any]) -> Dict[str, Any]:
    """Shape a `search_attempts` entry from a completed `collect_from_nutrition_db` call."""
    matches = result.get("nutrition_matches") or []
    top_confidence = matches[0].get("confidence", 0.0) if matches else 0.0
    return {
        "query": query,
        "success": result.get("success", False),
        "matches": len(matches),
        "top_confidence": top_confidence,
    }


def _single_query_attempt(
    svc, query: str, min_confidence: int
) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
    """
    Run one `collect_from_nutrition_db` call and shape the attempt entry.

    Returns (attempt_dict, full_result_or_None). On exception, attempt
    carries `error`; the full result is None.
    """
    try:
        result = svc.collect_from_nutrition_db(
            query, min_confidence=min_confidence, deduplicate=True
        )
        return _attempt_record(query, result), result
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.warning("Phase 2.1 query '%s' failed: %s", query, exc)
        return {"query": query, "success": False, "error": str(exc)}, None


def _empty_response(
    input_text: str,
    *,
    reason: str,
    search_attempts: Optional[List[Dict[str, Any]]] = None,
    dish_candidates: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Stage-7-compatible empty response for the orchestrator's failure paths
    (empty DB, no matches across strategies).
    """
    return {
        "success": True,
        "method": "Direct BM25 Text Matching",
        "input_text": input_text,
        "nutrition_matches": [],
        "total_nutrition": {},
        "recommendations": [],
        "match_summary": {
            "total_matched": 0,
            "match_rate": 0.0,
            "avg_confidence": 0.0,
            "deduplication_enabled": True,
            "search_method": "Direct BM25",
            "reason": reason,
        },
        "processing_info": {},
        "search_strategy": "none",
        "search_attempts": list(search_attempts or []),
        "dish_candidates": list(dish_candidates or []),
    }


def extract_and_lookup_nutrition(
    dish_name: str,
    components: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Phase 2.1 orchestrator.

    Runs a per-query search (`dish_name` + each component's
    `component_name`) at `min_confidence=70`. If the best individual
    match scores below 0.75, falls back to a comma-joined combined
    search at `min_confidence=60` and replaces the best only if the
    combined result scores higher.

    Args:
        dish_name: User-confirmed dish name (Stage 4 `confirmed_dish_name`).
        components: Confirmed components; only `component_name` is read.

    Returns:
        Stage-7-compatible dict. `nutrition_matches` carries the single
        best strategy's top-K results; `search_attempts` records every
        strategy tried; `dish_candidates` records [dish_name].
    """
    try:
        svc = get_nutrition_service()
    except NutritionDBEmptyError as exc:
        logger.warning("Phase 2.1 nutrition DB is empty; returning empty match set: %s", exc)
        return _empty_response(
            dish_name or "",
            reason="nutrition_db_empty",
            dish_candidates=[dish_name] if dish_name else [],
        )

    candidates = _dedupe_preserve(
        [dish_name] + [c.get("component_name", "") for c in components or []]
    )
    dish_candidates = [dish_name] if dish_name else []

    best_result: Optional[Dict[str, Any]] = None
    best_confidence = 0.0
    search_attempts: List[Dict[str, Any]] = []

    for query in candidates:
        attempt, result = _single_query_attempt(svc, query, _STAGE_1_MIN_CONFIDENCE)
        search_attempts.append(attempt)
        top_confidence = attempt.get("top_confidence", 0.0)
        if result and result.get("nutrition_matches") and top_confidence > best_confidence:
            best_confidence = top_confidence
            best_result = dict(result)
            best_result["search_strategy"] = f"individual_dish_name: {query}"

    if best_confidence < _FALLBACK_TRIGGER_THRESHOLD and candidates:
        combined_text = ", ".join(candidates)
        attempt, combined = _single_query_attempt(svc, combined_text, _STAGE_2_MIN_CONFIDENCE)
        search_attempts.append(attempt)
        combined_top = attempt.get("top_confidence", 0.0)
        if combined and combined.get("nutrition_matches") and combined_top > best_confidence:
            best_confidence = combined_top
            best_result = dict(combined)
            best_result["search_strategy"] = f"combined_terms: {combined_text}"

    if best_result is None:
        return _empty_response(
            dish_name or "",
            reason="no_matches_across_strategies",
            search_attempts=search_attempts,
            dish_candidates=dish_candidates,
        )

    best_result["search_attempts"] = search_attempts
    best_result["dish_candidates"] = dish_candidates
    return best_result
