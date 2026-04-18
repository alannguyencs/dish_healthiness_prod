"""
Database models for the application.

This module defines SQLAlchemy ORM models for the food healthiness
application, including user management and food image query storage.
"""

from typing import Any, Dict

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, JSON, String

from src.database import Base


class Users(Base):
    """
    User model for authentication and user management.

    This model stores user account information including usernames,
    hashed passwords, and user roles for the application.

    Attributes:
        id (int): Primary key for the user
        username (str): Unique username for login
        hashed_password (str): Bcrypt hashed password
        role (str): User role (optional)
    """

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default=None)

    def __repr__(self) -> str:
        """
        Return string representation of user.

        Returns:
            str: String representation showing user ID
        """
        return f"<User {self.id}>"

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert user to dictionary representation.

        Returns:
            Dict[str, Any]: Dictionary containing all user attributes
        """
        return {column.name: getattr(self, column.name) for column in self.__table__.columns}


class DishImageQuery(Base):
    """
    Dish image query model for storing food analysis requests.

    This model stores user-submitted food images along with their
    AI-generated analysis results from OpenAI and Gemini (Flow 2 & 3).

    Attributes:
        id (int): Primary key for the query
        user_id (int): Foreign key reference to Users table
        image_url (str): URL path to the uploaded image
        result_openai (dict): OpenAI analysis results (Flow 2)
        result_gemini (dict): Gemini analysis results (Flow 3)
        meal_type (str): Type of meal (breakfast, lunch, dinner, snack)
        created_at (datetime): Timestamp when record was created
        target_date (datetime): Date when the dish was actually consumed
    """

    __tablename__ = "dish_image_query_prod_dev"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    image_url = Column(String, nullable=True, default=None)
    result_openai = Column(JSON, nullable=True, default=None)
    result_gemini = Column(JSON, nullable=True, default=None)
    dish_position = Column(Integer, nullable=True, default=None)
    created_at = Column(DateTime, nullable=False)
    target_date = Column(DateTime, nullable=True, default=None)

    def __repr__(self) -> str:
        """
        Return string representation of dish image query.

        Returns:
            str: String representation showing query ID
        """
        return f"<DishImageQuery {self.id}>"

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert dish image query to dictionary representation.

        Returns:
            Dict[str, Any]: Dictionary containing all query attributes
        """
        return {column.name: getattr(self, column.name) for column in self.__table__.columns}


class PersonalizedFoodDescription(Base):
    """
    Per-user food upload index row.

    One row per DishImageQuery owned by a user. Forms the corpus that the
    BM25-based personalization retrieval (Phase 1.1.1, Phase 2.2) searches
    against. Stage 0 ships the bare row; later stages fill the optional
    columns as the dish moves through the pipeline.

    Attributes:
        id (int): Primary key
        user_id (int): Owner; FK to users.id, scopes the BM25 corpus
        query_id (int): FK to DishImageQuery.id; 1:1 (unique index)
        image_url (str): Mirror of DishImageQuery.image_url for fast access
        description (str): Gemini 2.0 Flash caption (written in Stage 2)
        tokens (list): Tokenized description; BM25 corpus document
        similarity_score_on_insert (float): Top-1 score vs prior corpus at insert
        confirmed_dish_name (str): User-confirmed dish name (Stage 4)
        confirmed_portions (float): Sum of confirmed component servings (Stage 4)
        confirmed_tokens (list): Tokenized confirmed_dish_name (Stage 4)
        corrected_step2_data (dict): User nutrient corrections (Stage 8)
        created_at (datetime): Row creation timestamp
        updated_at (datetime): Last-modified timestamp
    """

    __tablename__ = "personalized_food_descriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    query_id = Column(
        Integer,
        ForeignKey("dish_image_query_prod_dev.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    image_url = Column(String, nullable=True, default=None)
    description = Column(String, nullable=True, default=None)
    tokens = Column(JSON, nullable=True, default=None)
    similarity_score_on_insert = Column(Float, nullable=True, default=None)
    confirmed_dish_name = Column(String, nullable=True, default=None)
    confirmed_portions = Column(Float, nullable=True, default=None)
    confirmed_tokens = Column(JSON, nullable=True, default=None)
    corrected_step2_data = Column(JSON, nullable=True, default=None)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    def __repr__(self) -> str:
        """
        Return string representation of personalized food description row.

        Returns:
            str: String representation showing row ID
        """
        return f"<PersonalizedFoodDescription {self.id}>"

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert personalized food description to dictionary representation.

        Returns:
            Dict[str, Any]: Dictionary containing all row attributes
        """
        return {column.name: getattr(self, column.name) for column in self.__table__.columns}
