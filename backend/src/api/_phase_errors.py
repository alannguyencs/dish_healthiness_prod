"""
Shared error classification and persistence for the two-phase Gemini pipeline.

Used by:
  - src/api/item_step1_tasks.py     (Phase 1 — Component Identification)
  - src/api/item_tasks.py           (Phase 2 — Nutritional Analysis)

Both phases write a parallel error block (`step1_error` / `step2_error`) into
`result_gemini` when the background task catches an exception, and clear it on
the next successful run. The user-facing `Step2ErrorCard` -> `PhaseErrorCard`
component reads these blocks to render the retry UI.
"""

from datetime import datetime, timezone

from src.crud.crud_food_image_query import (
    get_dish_image_query_by_id,
    update_dish_image_query_results,
)


# Error classification buckets surfaced to the frontend via {step1,step2}_error.
ERROR_USER_MESSAGE = {
    "config_error": (
        "An internal configuration issue is preventing analysis. Please try again later."
    ),
    "image_missing": "The dish image is no longer available. Please re-upload the meal.",
    "parse_error": ("The AI response could not be parsed. Try again — this is usually transient."),
    "api_error": "The nutrition service is temporarily unavailable. Try again in a moment.",
    "unknown": "Something went wrong. Try again.",
}


def classify_phase_error(exc: Exception) -> str:
    """Bucket an exception into one of the error_type values used in {step}_error."""
    msg = str(exc).lower()
    type_name = type(exc).__name__.lower()
    if "gemini_api_key" in msg or "api key" in msg:
        return "config_error"
    if type_name == "filenotfounderror" or ("image" in msg and "not found" in msg):
        return "image_missing"
    if "parse" in msg or "validation" in msg or "schema" in msg:
        return "parse_error"
    if any(token in msg for token in ("503", "429", "timeout", "connection")) or (
        type_name == "timeouterror"
    ):
        return "api_error"
    return "unknown"


def persist_phase_error(query_id: int, exc: Exception, retry_count: int, error_key: str) -> None:
    """
    Write `error_key` (e.g. 'step1_error' / 'step2_error') into result_gemini.

    If `result_gemini` is None (the common case for a Phase 1 failure with no
    prior state), initialize it as a minimal blob with `step = 0` so the
    frontend can branch consistently on `step in (0, 1, 2)`.
    """
    record = get_dish_image_query_by_id(query_id)
    if not record:
        return

    base = (record.result_gemini or {"step": 0, "step1_data": None}).copy()
    error_type = classify_phase_error(exc)
    base[error_key] = {
        "error_type": error_type,
        "message": ERROR_USER_MESSAGE[error_type],
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "retry_count": retry_count,
    }
    update_dish_image_query_results(query_id=query_id, result_openai=None, result_gemini=base)
