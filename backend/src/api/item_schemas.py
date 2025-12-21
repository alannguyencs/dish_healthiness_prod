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
    number_of_servings: float = Field(
        ..., ge=0.01, le=10.0, description="Number of servings"
    )


class Step1ConfirmationRequest(BaseModel):
    """Request body for confirming Step 1 data and triggering Step 2."""

    selected_dish_name: str = Field(..., description="User-selected or custom dish name")
    components: List[ComponentConfirmation] = Field(
        ..., min_length=1, description="List of confirmed components with serving sizes"
    )
