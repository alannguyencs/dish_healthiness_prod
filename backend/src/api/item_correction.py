"""
Stage 8 — POST /api/item/{record_id}/correction.

Persists a user correction of the Step 2 nutritional analysis. Lives in
its own module so `backend/src/api/item.py` stays under the 300-line file
cap (parallel to `item_retry.py` / `item_identification_tasks.py`).

Dual write:
  1. `DishImageQuery.result_gemini.nutrition_corrected` — the user override,
     preserving `nutrition_data` untouched for audit.
  2. `personalized_food_descriptions.corrected_nutrition_data` — same payload
     written onto the personalization row via Stage 0's CRUD so future
     Phase 2.2 retrieval surfaces the user-verified nutrients.

The personalization half is wrapped in try/except-swallow-log: the user's
primary intent (save correction) succeeds even if the enrichment fails.
Matches Stage 4's pattern.
"""

import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from src.api.item_schemas import AiAssistantCorrectionRequest, NutritionCorrectionRequest
from src.auth import authenticate_user_from_request
from src.crud import crud_personalized_food
from src.crud.crud_food_image_query import (
    get_dish_image_query_by_id,
    update_dish_image_query_results,
)
from src.service.llm.nutrition_assistant import revise_nutrition_with_hint

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/item", tags=["item"])


def _enrich_personalization_corrected_data(record_id: int, payload: Dict[str, Any]) -> None:
    """
    Stage 8: mirror the user correction onto the personalization row.

    Fire-and-forget — failures must not bounce the user since the main
    `result_gemini.nutrition_corrected` write already landed.
    """
    try:
        updated_row = crud_personalized_food.update_corrected_nutrition_data(
            query_id=record_id,
            payload=payload,
        )
        if updated_row is None:
            logger.warning(
                "Stage 8 enrichment skipped: no personalized_food_descriptions "
                "row for query_id=%s",
                record_id,
            )
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.warning("Stage 8 enrichment failed for query_id=%s: %s", record_id, exc)


@router.post("/{record_id}/correction")
async def save_nutrition_correction(
    record_id: int,
    request: Request,
    correction: NutritionCorrectionRequest,
) -> JSONResponse:
    """
    Save a user correction of the Step 2 nutritional analysis.

    Writes `result_gemini.nutrition_corrected` (preserving `nutrition_data` for
    audit) and best-effort mirrors the payload onto
    `personalized_food_descriptions.corrected_nutrition_data`.
    """
    logger.info("Step 2 correction request for record_id=%s", record_id)

    user = authenticate_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    record = get_dish_image_query_by_id(record_id)
    if not record or record.user_id != user.id:
        raise HTTPException(status_code=404, detail="Record not found")

    if not record.result_gemini:
        raise HTTPException(
            status_code=400,
            detail="Step 2 analysis has not completed; nothing to correct.",
        )

    payload = correction.model_dump()

    new_blob = dict(record.result_gemini)
    new_blob["nutrition_corrected"] = payload
    update_dish_image_query_results(
        query_id=record_id,
        result_openai=None,
        result_gemini=new_blob,
    )

    _enrich_personalization_corrected_data(record_id, payload)

    return JSONResponse(
        content={
            "success": True,
            "record_id": record_id,
            "nutrition_corrected": payload,
        }
    )


def _compose_ai_assistant_payload(revised: Dict[str, Any], user_hint: str) -> Dict[str, Any]:
    """
    Shape the revised Gemini output into the `nutrition_corrected` payload,
    dropping engineering metadata fields and stamping the audit hint.
    """
    return {
        "dish_name": revised.get("dish_name"),
        "healthiness_score": revised["healthiness_score"],
        "healthiness_score_rationale": revised["healthiness_score_rationale"],
        "calories_kcal": revised["calories_kcal"],
        "fiber_g": revised["fiber_g"],
        "carbs_g": revised["carbs_g"],
        "protein_g": revised["protein_g"],
        "fat_g": revised["fat_g"],
        "micronutrients": revised.get("micronutrients", []),
        "ai_assistant_prompt": user_hint,
    }


@router.post("/{record_id}/ai-assistant-correction")
async def save_ai_assistant_correction(
    record_id: int,
    request: Request,
    body: AiAssistantCorrectionRequest,
) -> JSONResponse:
    """
    Stage 10 — prompt-driven Step 2 revision.

    Loads the current effective Step 2 payload as baseline, calls Gemini
    2.5 Pro with the query image + trimmed baseline + user hint, and
    commits the revised payload directly via the same `/correction`
    persistence path. `ai_assistant_prompt` is stashed on the corrected
    payload (latest hint wins).
    """
    logger.info("AI Assistant Edit request for record_id=%s", record_id)

    user = authenticate_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    record = get_dish_image_query_by_id(record_id)
    if not record or record.user_id != user.id:
        raise HTTPException(status_code=404, detail="Record not found")

    if not record.result_gemini or not record.result_gemini.get("nutrition_data"):
        raise HTTPException(
            status_code=400,
            detail="Step 2 analysis has not completed; nothing to revise.",
        )

    user_hint = body.prompt.strip()
    if not user_hint:
        raise HTTPException(status_code=422, detail="Prompt must not be empty")

    try:
        revised = await revise_nutrition_with_hint(record_id, user_hint)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.exception("AI Assistant revision failed for record_id=%s", record_id)
        raise HTTPException(status_code=502, detail="AI revision failed") from exc

    payload = _compose_ai_assistant_payload(revised, user_hint)

    new_blob = dict(record.result_gemini)
    new_blob["nutrition_corrected"] = payload
    update_dish_image_query_results(
        query_id=record_id,
        result_openai=None,
        result_gemini=new_blob,
    )

    _enrich_personalization_corrected_data(record_id, payload)

    return JSONResponse(
        content={
            "success": True,
            "record_id": record_id,
            "nutrition_corrected": payload,
        }
    )
