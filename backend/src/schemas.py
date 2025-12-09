"""
Schema definitions for authentication tokens and data models.

This module defines Pydantic models used for request/response validation
and serialization in the food healthiness application API endpoints.
"""

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class Token(BaseModel):
    """
    Schema model for authentication token response.

    Used when returning JWT access tokens to authenticated users.

    Attributes:
        access_token (str): The JWT access token string
        token_type (str): Type of token (typically "bearer")
    """

    access_token: str
    token_type: str


class UserBase(BaseModel):
    """
    Base schema for User model containing common fields.

    This base class contains fields that are shared across
    different user-related schemas.

    Attributes:
        username (str): Unique username for the user
        role (Optional[str]): User role, if assigned
    """

    username: str
    role: Optional[str] = None


class UserCreate(UserBase):
    """
    Schema for creating a new user.

    Extends UserBase with password field for user registration.

    Attributes:
        password (str): Plain text password (will be hashed)
    """

    password: str


class UserResponse(UserBase):
    """
    Schema for user response (without sensitive data).

    Used when returning user information in API responses.
    Excludes sensitive fields like passwords.

    Attributes:
        id (int): Unique user identifier
    """

    id: int

    class Config:
        """Pydantic configuration for ORM mode compatibility."""
        from_attributes = True


class DishImageQueryBase(BaseModel):
    """
    Base schema for DishImageQuery model containing common fields.

    This base class contains fields that are shared across
    different dish image query-related schemas.

    Attributes:
        image_url (Optional[str]): URL path to the uploaded image
        result_openai (Optional[Dict]): OpenAI analysis results (Flow 2)
        result_gemini (Optional[Dict]): Gemini analysis results (Flow 3)
    """

    image_url: Optional[str] = None
    result_openai: Optional[Dict[str, Any]] = None
    result_gemini: Optional[Dict[str, Any]] = None


class DishImageQueryCreate(DishImageQueryBase):
    """
    Schema for creating a new dish image query.

    Extends DishImageQueryBase with user_id for query creation.

    Attributes:
        user_id (int): ID of the user making the query
    """

    user_id: int


class DishImageQueryResponse(DishImageQueryBase):
    """
    Schema for dish image query response.

    Used when returning dish image query information in API responses.

    Attributes:
        id (int): Unique query identifier
        user_id (int): ID of the user who made the query
        created_at (Optional[datetime]): When the query was created
        target_date (Optional[datetime]): When the dish was consumed
    """

    id: int
    user_id: int
    created_at: Optional[datetime] = None
    target_date: Optional[datetime] = None

    class Config:
        """Pydantic configuration for ORM mode compatibility."""
        from_attributes = True


class MetadataUpdate(BaseModel):
    """
    Schema for metadata update request.

    Used when users update dish, serving size, or servings count
    for a food analysis.

    Attributes:
        selected_dish (str): User-selected or custom dish name
        selected_serving_size (str): Selected or custom serving size
        number_of_servings (float): Quantity consumed (0.1 - 10.0)
    """
    selected_dish: str
    selected_serving_size: str
    number_of_servings: float = Field(..., ge=0.1, le=10.0)

