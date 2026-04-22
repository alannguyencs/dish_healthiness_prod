"""
Pydantic model for the Nutritional Analysis response (Phase 2.3).
"""

from typing import List

from pydantic import BaseModel, Field

from src.service.llm.models.micronutrient import Micronutrient


class NutritionalAnalysis(BaseModel):
    """
    Nutritional Analysis: detailed nutrient estimation.

    This model is used after the user confirms the identification (dish name and components).
    It provides comprehensive nutritional information based on the confirmed components
    and their serving sizes.

    Attributes:
        dish_name (str): Confirmed dish name (from user selection/input)
        healthiness_score (int): Overall healthiness score (0-100)
        healthiness_score_rationale (str): Explanation for the healthiness score
        calories_kcal (float): Total calories in kcal (decimals allowed)
        fiber_g (float): Fiber content in grams (decimals allowed)
        carbs_g (float): Carbohydrate content in grams (decimals allowed)
        protein_g (float): Protein content in grams (decimals allowed)
        fat_g (float): Fat content in grams (decimals allowed)
        micronutrients (List[Micronutrient | str]): Notable micronutrients and vitamins.
            New rows use the structured form; legacy rows may still be List[str].
    """

    dish_name: str = Field(..., description="Confirmed dish name")
    healthiness_score: int = Field(..., ge=0, le=100, description="Healthiness score 0-100")
    healthiness_score_rationale: str = Field(..., description="Rationale for healthiness score")
    calories_kcal: float = Field(..., ge=0, description="Total calories in kcal")
    fiber_g: float = Field(..., ge=0, description="Fiber in grams")
    carbs_g: float = Field(..., ge=0, description="Carbohydrates in grams")
    protein_g: float = Field(..., ge=0, description="Protein in grams")
    fat_g: float = Field(..., ge=0, description="Fat in grams")
    micronutrients: List[Micronutrient] = Field(
        default_factory=list,
        description="Notable micronutrients with optional mg quantities",
    )
    reasoning_sources: str = Field(
        default="",
        description=(
            "Short string listing which sources drove this analysis "
            "(e.g. 'Nutrition DB: Chicken Rice (malaysian, 88%)', "
            "'User prior: similar upload', or 'LLM-only')."
        ),
    )
    reasoning_calories: str = Field(
        default="",
        description="Rationale for the calories_kcal estimate, citing source if any.",
    )
    reasoning_fiber: str = Field(default="", description="Rationale for fiber_g.")
    reasoning_carbs: str = Field(default="", description="Rationale for carbs_g.")
    reasoning_protein: str = Field(default="", description="Rationale for protein_g.")
    reasoning_fat: str = Field(default="", description="Rationale for fat_g.")
    reasoning_micronutrients: str = Field(
        default="",
        description=(
            "Rationale for the micronutrients list. Empty string is acceptable "
            "when no micronutrients are surfaced."
        ),
    )
