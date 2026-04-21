"""
Pydantic models for LLM analysis.

This module defines the data structures used for dish analysis.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


# ============================================================
# STEP 1 MODELS: Component Identification
# ============================================================


class DishNamePrediction(BaseModel):
    """
    Single dish name prediction with confidence score.

    Attributes:
        name (str): The predicted dish name
        confidence (float): Confidence score between 0.0 and 1.0
    """

    name: str = Field(..., description="Predicted dish name")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score between 0 and 1")


class ComponentServingPrediction(BaseModel):
    """
    Serving size predictions for a single individual dish.

    An "individual dish" is a complete food item, not ingredient-level components.
    Examples: "Beef Burger", "French Fries", "Caesar Salad", "Grilled Chicken"
    NOT: "burger bun", "lettuce", "beef patty"

    Attributes:
        component_name (str): Name of the individual dish (e.g., "Beef Burger", "French Fries")
        serving_sizes (List[str]): 3-5 serving size options for this dish (enforced)
        predicted_servings (float): Estimated number of servings for this dish
    """

    component_name: str = Field(
        ..., description="Name of the individual dish (complete item, not ingredients)"
    )
    serving_sizes: List[str] = Field(
        ...,
        min_length=3,
        max_length=5,
        description="Top 3-5 serving size options for this individual dish",
    )
    predicted_servings: float = Field(
        default=1.0, ge=0.1, le=10.0, description="Estimated number of servings for this dish"
    )


class Step1ComponentIdentification(BaseModel):
    """
    Step 1: Individual dish identification and serving size predictions.

    This model is used for the initial analysis that:
    1. Predicts an overall meal name (e.g., "Burger with Fries")
    2. Identifies individual dishes on the plate (e.g., "Beef Burger", "French Fries")

    Individual dishes are complete food items, NOT ingredient-level components.
    For example:
    - "Beef Burger" (one individual dish), NOT "bun + patty + cheese"
    - "French Fries" (one individual dish), NOT separate potato pieces

    The individual dishes are identified independently from the meal name,
    allowing users to select which dishes to include.

    Attributes:
        dish_predictions (List[DishNamePrediction]): List of predicted overall meal names
        components (List[ComponentServingPrediction]): Individual dishes visible in the image
    """

    dish_predictions: List[DishNamePrediction] = Field(
        ...,
        min_length=1,
        max_length=5,
        description=(
            "Top 1-5 predicted overall meal names "
            "(e.g., 'Burger with Fries', 'Chicken Rice Plate')"
        ),
    )
    components: List[ComponentServingPrediction] = Field(
        ...,
        min_length=1,
        max_length=10,
        description=(
            "Individual dishes visible in the image "
            "(e.g., 'Beef Burger', 'French Fries'). "
            "User will select which to include."
        ),
    )


# ============================================================
# STEP 2 MODELS: Nutritional Analysis
# ============================================================


class Micronutrient(BaseModel):
    """
    A single micronutrient or vitamin with an optional mg quantity.

    `amount_mg` is `None` when the LLM cannot estimate a quantity reliably;
    the frontend then renders just the name. Legacy rows stored as plain
    strings are still tolerated by the frontend (see Step2Results.jsx).
    """

    name: str = Field(..., description="Nutrient name, e.g. 'Vitamin C', 'Iron'")
    amount_mg: Optional[float] = Field(
        default=None, ge=0, description="Quantity in milligrams, if known"
    )


class Step2NutritionalAnalysis(BaseModel):
    """
    Step 2: Detailed nutritional analysis.

    This model is used after user confirms Step 1 data (dish name and components).
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
    micronutrients: List["Micronutrient"] = Field(
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
