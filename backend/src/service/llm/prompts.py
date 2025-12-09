"""
Prompt loading and formatting utilities.

This module provides functions for loading and formatting prompts
for dish analysis.
"""

from src.configs import RESOURCE_DIR


def get_analysis_prompt() -> str:
    """
    Load default prompt for dish analysis (with dish predictions).

    Returns:
        str: Analysis prompt text

    Raises:
        FileNotFoundError: If default prompt file is not found
    """
    # Load default prompt from food_analysis.md
    prompt_path = RESOURCE_DIR / "food_analysis.md"
    if not prompt_path.exists():
        raise FileNotFoundError(
            f"Analysis prompt not found: {prompt_path}"
        )

    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()


def get_brief_analysis_prompt() -> str:
    """
    Load brief prompt for dish re-analysis (without dish predictions).

    This lighter prompt is used for re-analysis after user feedback,
    excluding dish prediction generation to save tokens.

    Returns:
        str: Brief analysis prompt text

    Raises:
        FileNotFoundError: If brief prompt file is not found
    """
    # Load brief prompt from food_analysis_brief.md
    prompt_path = RESOURCE_DIR / "food_analysis_brief.md"
    if not prompt_path.exists():
        raise FileNotFoundError(
            f"Brief analysis prompt not found: {prompt_path}"
        )

    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()

