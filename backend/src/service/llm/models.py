"""
Pydantic models for LLM analysis.

This module defines the data structures used for dish analysis.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class DishPrediction(BaseModel):
    """
    Single dish prediction with confidence score, serving sizes, and predicted servings.

    Attributes:
        name (str): The predicted dish name
        confidence (float): Confidence score between 0.0 and 1.0
        serving_sizes (List[str]): Top 3 serving size options for this dish
        predicted_servings (float): Estimated number of servings visible in the image
    """
    name: str = Field(..., description="Predicted dish name")
    confidence: float = Field(..., ge=0.0, le=1.0,
                             description="Confidence score between 0 and 1")
    serving_sizes: List[str] = Field(
        default_factory=list,
        description="Top 3 serving size options specific to this dish"
    )
    predicted_servings: float = Field(
        default=1.0,
        ge=0.01,
        description="Estimated number of servings visible in the image"
    )


class FoodHealthAnalysis(BaseModel):
    """
    Full analysis model with dish predictions (for initial analysis).

    This model defines the structure for dish analysis results with
    dish predictions, used for the initial analysis that generates
    feedback options for users.
    """
    dish_name: str
    related_keywords: str = ""
    healthiness_score: int
    healthiness_score_rationale: str
    calories_kcal: int
    fiber_g: int
    carbs_g: int
    protein_g: int
    fat_g: int
    micronutrients: List[str]
    dish_predictions: Optional[List[DishPrediction]] = None


class FoodHealthAnalysisBrief(BaseModel):
    """
    Brief analysis model without dish predictions (for re-analysis).

    This lighter model is used for re-analysis after user feedback,
    excluding dish predictions to save 20-30% token usage.
    """
    dish_name: str
    related_keywords: str = ""
    healthiness_score: int
    healthiness_score_rationale: str
    calories_kcal: int
    fiber_g: int
    carbs_g: int
    protein_g: int
    fat_g: int
    micronutrients: List[str]

