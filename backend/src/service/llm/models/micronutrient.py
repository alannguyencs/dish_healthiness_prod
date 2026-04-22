"""
Pydantic model for a single micronutrient entry in Step 2 output.
"""

from typing import Optional

from pydantic import BaseModel, Field


class Micronutrient(BaseModel):
    """
    A single micronutrient or vitamin with an optional mg quantity.

    `amount_mg` is `None` when the LLM cannot estimate a quantity reliably;
    the frontend then renders just the name. Legacy rows stored as plain
    strings are still tolerated by the frontend (see NutritionResults.jsx).
    """

    name: str = Field(..., description="Nutrient name, e.g. 'Vitamin C', 'Iron'")
    amount_mg: Optional[float] = Field(
        default=None, ge=0, description="Quantity in milligrams, if known"
    )
