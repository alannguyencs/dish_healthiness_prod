"""
CRUD operations for User model.

This module provides create, read, update, and delete operations for the
Users model, including functions for user authentication and management.
"""

from typing import Optional

from sqlalchemy.orm import Session

from src.database import SessionLocal
from src.models import Users


def get_db_session() -> Session:
    """
    Get a database session for CRUD operations.

    Returns:
        Session: SQLAlchemy database session
    """
    return SessionLocal()


def get_user_by_username(username: str) -> Optional[Users]:
    """
    Get a user by username.

    Args:
        username (str): Username to search for

    Returns:
        Optional[Users]: User object if found, None otherwise
    """
    db = get_db_session()
    try:
        return db.query(Users).filter(Users.username == username).first()
    finally:
        db.close()


def get_user_by_id(user_id: int) -> Optional[Users]:
    """
    Get a user by ID.

    Args:
        user_id (int): User ID to search for

    Returns:
        Optional[Users]: User object if found, None otherwise
    """
    db = get_db_session()
    try:
        return db.query(Users).filter(Users.id == user_id).first()
    finally:
        db.close()


def create_user(username: str, hashed_password: str, role: Optional[str] = None) -> Users:
    """
    Create a new user.

    Args:
        username (str): Username for the new user
        hashed_password (str): Hashed password for the new user
        role (Optional[str]): Role for the new user

    Returns:
        Users: Created user object

    Raises:
        Exception: If user creation fails
    """
    db = get_db_session()
    try:
        db_user = Users(username=username, hashed_password=hashed_password, role=role)
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def update_user_password(user_id: int, new_hashed_password: str) -> Optional[Users]:
    """
    Update user password.

    Args:
        user_id (int): User ID to update
        new_hashed_password (str): New hashed password

    Returns:
        Optional[Users]: Updated user object if found, None otherwise

    Raises:
        Exception: If password update fails
    """
    db = get_db_session()
    try:
        user = db.query(Users).filter(Users.id == user_id).first()
        if user:
            user.hashed_password = new_hashed_password
            db.commit()
            db.refresh(user)
        return user
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def delete_user(user_id: int) -> bool:
    """
    Delete a user.

    Args:
        user_id (int): User ID to delete

    Returns:
        bool: True if user was deleted, False otherwise

    Raises:
        Exception: If user deletion fails
    """
    db = get_db_session()
    try:
        user = db.query(Users).filter(Users.id == user_id).first()
        if user:
            db.delete(user)
            db.commit()
            return True
        return False
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
