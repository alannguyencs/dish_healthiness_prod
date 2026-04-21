"""
`collect_from_nutrition_db` free-function implementation.

Kept out of `nutrition_db.py` to keep that file under the 300-line cap.
`NutritionCollectionService.collect_from_nutrition_db` is a thin delegator
to `collect_from_nutrition_db(service, ...)` here; callers may also import
this module directly if they already have a service instance in scope.
"""

from typing import Any, Dict

from src.service._nutrition_aggregation import (
    calculate_optimal_nutrition,
    deduplicate_matches,
    generate_recommendations,
)


def processing_info(service, min_confidence: int) -> Dict[str, Any]:
    """Source row counts + threshold — a common footer for both success and empty responses."""
    return {
        "malaysian_foods_count": len(service.malaysian_foods),
        "myfcd_foods_count": len(service.myfcd_foods),
        "anuvaad_foods_count": len(service.anuvaad_foods),
        "ciqual_foods_count": len(service.ciqual_foods),
        "min_confidence_threshold": min_confidence,
        "approach": "Full text to dish matching",
    }


def empty_collect_response(service, text: str, min_confidence: int, reason: str) -> Dict[str, Any]:
    """Stage-7-compatible empty response shape."""
    return {
        "success": True,
        "method": "Direct BM25 Text Matching",
        "input_text": text,
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
        "processing_info": processing_info(service, min_confidence),
    }


def collect_from_nutrition_db(
    service,
    text: str,
    min_confidence: int = 70,
    deduplicate: bool = True,
) -> Dict[str, Any]:
    """
    Stage-7-compatible full-shape lookup.

    `min_confidence` is 0-100 (percent). Converted to 0-1 for the BM25
    search. On no matches, returns the empty-response shape (same top-level
    keys, `nutrition_matches: []`). Raises `ValueError` on empty text.
    """
    if not text or not text.strip():
        raise ValueError("Text input cannot be empty")

    min_confidence_normalized = min_confidence / 100.0
    matches = service._search_dishes_direct(  # pylint: disable=protected-access
        text, top_k=10, min_confidence=min_confidence_normalized
    )
    if not matches:
        return empty_collect_response(service, text, min_confidence, "no_relevant_dishes")

    if deduplicate:
        matches = deduplicate_matches(matches)

    total_nutrition = calculate_optimal_nutrition(matches)
    recommendations = generate_recommendations(total_nutrition)
    avg_confidence = sum(m["confidence"] for m in matches) / len(matches)

    return {
        "success": True,
        "method": "Direct BM25 Text Matching",
        "input_text": text,
        "nutrition_matches": matches,
        "total_nutrition": total_nutrition,
        "recommendations": recommendations,
        "match_summary": {
            "total_matched": len(matches),
            "match_rate": 1.0,
            "avg_confidence": round(avg_confidence * 100, 1),
            "deduplication_enabled": deduplicate,
            "search_method": "Direct BM25",
        },
        "processing_info": processing_info(service, min_confidence),
    }
