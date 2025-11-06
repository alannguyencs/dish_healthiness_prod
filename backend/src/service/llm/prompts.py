"""
Prompt loading and formatting utilities.

This module provides functions for loading and formatting prompts
for dish analysis.
"""

from src.configs import RESOURCE_DIR


def get_analysis_prompt() -> str:
    """
    Load default prompt for dish analysis.

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

