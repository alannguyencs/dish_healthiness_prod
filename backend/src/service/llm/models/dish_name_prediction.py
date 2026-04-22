"""
Pydantic model for a single Step 1 dish-name prediction.
"""

from pydantic import BaseModel, Field


class DishNamePrediction(BaseModel):
    """
    Single dish name prediction with confidence score.

    Attributes:
        name (str): The predicted dish name
        confidence (float): Confidence score between 0.0 and 1.0
    """

    name: str = Field(..., description="Predicted dish name")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score between 0 and 1")
