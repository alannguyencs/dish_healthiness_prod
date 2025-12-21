"""
Configuration settings and constants for the project.

This module contains all application configuration settings, directory paths,
and settings classes using Pydantic for validation and type safety.
"""

from pathlib import Path

from pydantic_settings import BaseSettings

# Project directory structure
PROJECT_DIR = Path(__file__).parent.parent.absolute()

# Create required directories
DATA_DIR = PROJECT_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

IMAGE_DIR = DATA_DIR / "images"
IMAGE_DIR.mkdir(exist_ok=True)

RESOURCE_DIR = PROJECT_DIR / "resources"
RESOURCE_DIR.mkdir(exist_ok=True)

LOG_DIR = PROJECT_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

# Authentication configuration
TOKEN_EXPIRATION_DAYS = 90


class Settings(BaseSettings):
    """
    Application configuration settings using Pydantic BaseSettings.

    This class manages all configuration settings for the application,
    including API versioning and project identification. Settings can
    be overridden via environment variables.
    """

    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "DishHealthiness"

    def get_api_url(self) -> str:
        """
        Return the full API URL.

        Returns:
            str: The complete API URL string
        """
        return self.API_V1_STR

    def get_project_identifier(self) -> str:
        """
        Return a unique project identifier.

        Returns:
            str: Lowercase project name for use as identifier
        """
        return self.PROJECT_NAME.lower()

    model_config = {"case_sensitive": True}


# Global settings instance
settings = Settings()
