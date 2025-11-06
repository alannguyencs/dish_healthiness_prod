"""
Pydantic models for LLM analysis.

This module defines the data structures used for dish analysis.
"""

from typing import List
from pydantic import BaseModel


class FoodHealthAnalysis(BaseModel):
    """
    Pydantic model for simplified food health analysis results.

    This model defines the simplified structure for dish analysis results
    used by both OpenAI and Gemini to ensure consistent output format.
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

