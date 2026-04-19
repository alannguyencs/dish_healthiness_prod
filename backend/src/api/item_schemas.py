"""
Request/response schemas for item API endpoints.

This module defines Pydantic models for Step 1 confirmation requests.
"""

from typing import List
from pydantic import BaseModel, Field


class ComponentConfirmation(BaseModel):
    """User-confirmed component with serving size and servings."""

    component_name: str = Field(..., description="Component name")
    selected_serving_size: str = Field(..., description="Selected serving size")
    number_of_servings: float = Field(..., ge=0.1, le=10.0, description="Number of servings")


class Step1ConfirmationRequest(BaseModel):
    """Request body for confirming Step 1 data and triggering Step 2."""

    selected_dish_name: str = Field(..., description="User-selected or custom dish name")
    components: List[ComponentConfirmation] = Field(
        ..., min_length=1, description="List of confirmed components with serving sizes"
    )


class Step2CorrectionRequest(BaseModel):
    """
    Request body for POST /api/item/{record_id}/correction (Stage 8).

    Field names mirror `Step2NutritionalAnalysis` so the frontend can submit
    the same keys the AI's original response used. Written onto
    `result_gemini.step2_corrected` while `result_gemini.step2_data` is
    preserved for audit; additionally flows into
    `personalized_food_descriptions.corrected_step2_data` so future
    Phase 2.2 retrieval surfaces the user-verified nutrients.
    """

    healthiness_score: int = Field(
        ..., ge=0, le=100, description="User-corrected healthiness score (0-100)"
    )
    healthiness_score_rationale: str = Field(
        ..., description="User-corrected rationale for the healthiness score"
    )
    calories_kcal: float = Field(..., ge=0, description="User-corrected total calories")
    fiber_g: float = Field(..., ge=0, description="User-corrected fiber grams")
    carbs_g: float = Field(..., ge=0, description="User-corrected carbohydrate grams")
    protein_g: float = Field(..., ge=0, description="User-corrected protein grams")
    fat_g: float = Field(..., ge=0, description="User-corrected fat grams")
    micronutrients: List[str] = Field(
        default_factory=list,
        description="User-corrected micronutrients list (plain strings, chip add/remove UI)",
    )
