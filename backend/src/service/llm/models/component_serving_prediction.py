"""
Pydantic model for a single Step 1 individual-dish serving-size prediction.
"""

from typing import List

from pydantic import BaseModel, Field


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
