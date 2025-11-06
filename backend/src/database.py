"""
Database configuration and session management for SQLAlchemy.

This module configures the PostgreSQL database connection, creates the
SQLAlchemy engine, and provides database session management for the
food healthiness application.
"""

import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session

# Database configuration from environment variables
DB_USERNAME = os.getenv('DB_USERNAME')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_NAME = os.getenv('DB_NAME')
DB_URL = os.getenv('DB_URL')


def build_database_url() -> str:
    """
    Build the PostgreSQL database URL from environment variables.

    Returns:
        str: Complete database URL for SQLAlchemy

    Raises:
        ValueError: If required environment variables are missing
    """
    if not all([DB_USERNAME, DB_NAME, DB_URL]):
        raise ValueError(
            "Missing required database environment variables: "
            "DB_USERNAME, DB_NAME, DB_URL"
        )

    if DB_PASSWORD:
        return (
            f'postgresql://{DB_USERNAME}:{DB_PASSWORD}@'
            f'{DB_URL}:5432/{DB_NAME}'
        )
    return f'postgresql://{DB_USERNAME}@{DB_URL}:5432/{DB_NAME}'


# Build database URL
SQLALCHEMY_DATABASE_URL = build_database_url()

# Create SQLAlchemy engine
engine = create_engine(SQLALCHEMY_DATABASE_URL)

# Create SessionLocal class for database sessions
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create declarative base for models
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    Get a database session for dependency injection.

    This function is used as a FastAPI dependency to provide database
    sessions that are automatically closed after use.

    Yields:
        Session: SQLAlchemy database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

