"""
Pydantic model for the Component Identification response (Phase 1.1.2).
"""

from typing import List

from pydantic import BaseModel, Field

from src.service.llm.models.component_serving_prediction import ComponentServingPrediction
from src.service.llm.models.dish_name_prediction import DishNamePrediction


class ComponentIdentification(BaseModel):
    """
    Component Identification: individual dish identification and serving size predictions.

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
