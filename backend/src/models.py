"""
Database models for the application.

This module defines SQLAlchemy ORM models for the food healthiness
application, including user management and food image query storage.
"""

from typing import Any, Dict

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String

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
