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

# Nutrition source CSVs (Anuvaad, CIQUAL, Malaysian, MyFCD basic+nutrients).
# Read by `scripts/seed/load_nutrition_db.py` only; the runtime service
# reads from the seeded `nutrition_foods` / `nutrition_myfcd_nutrients`
# tables, never from disk.
DATABASE_DIR = RESOURCE_DIR / "database"

# Stage 2 (Phase 1.1.1) — minimum similarity_score a top-1 match must clear
# to be attached as a reference on result_gemini.reference_image. The score
# is a max-in-batch relative ranking signal (see
# docs/technical/dish_analysis/personalized_food_index.md — the top hit
# always lands at 1.0), so 0.25 is a soft floor that mainly rejects corpora
# with zero lexical overlap. Re-tune after real retrieval-quality data.
THRESHOLD_PHASE_1_1_1_SIMILARITY = 0.25

# Stage 6 (Phase 2.2) — minimum similarity_score a personalization match
# must clear to be surfaced on result_gemini.personalized_matches. Same
# max-in-batch normalization as Stage 2, so this is a relative ranking
# signal that mainly rejects corpora with zero lexical overlap. Re-tune
# after real retrieval-quality data.
THRESHOLD_PHASE_2_2_SIMILARITY = 0.30

# Stage 7 (Phase 2.3) threshold gates for the Gemini prompt's optional
# reference blocks and for the image-B attach.

# Include the Nutrition Database Matches block only when the top match's
# confidence_score (0-100 scale) clears 80. Tuned against the
# reference-project NDCG eval set; editing invalidates the Stage 9 gate.
THRESHOLD_DB_INCLUDE = 80

# Include the Personalization Matches block only when the top match's
# similarity_score (0-1 scale, max-in-batch normalized) clears 0.30.
# Same value as THRESHOLD_PHASE_2_2_SIMILARITY (Stage 6's retrieval gate)
# by intent; separate knob so prompt-inclusion can be tuned independently
# of the retrieval surface.
THRESHOLD_PERSONALIZATION_INCLUDE = 0.30

# Attach the top-1 personalization match's image as a second Gemini input
# (image B) only when its similarity_score clears 0.35. Stricter than
# THRESHOLD_PERSONALIZATION_INCLUDE so the gap band [0.30, 0.35) gives
# Gemini a textual hint without an unframed second image.
THRESHOLD_PHASE_2_2_IMAGE = 0.35

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
