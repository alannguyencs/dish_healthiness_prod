"""
Prompt loading and formatting utilities.

This module provides functions for loading and formatting prompts
for dish analysis.
"""

from typing import List, Dict, Any
from src.configs import RESOURCE_DIR


# ============================================================
# STEP 1 & STEP 2 PROMPTS (New Two-Step Flow)
# ============================================================


def get_step1_component_identification_prompt() -> str:
    """
    Load Step 1 prompt for component identification.

    This prompt is used for the initial analysis that identifies:
    - Dish name predictions (top 1-5)
    - Major nutrition components
    - Component-level serving size predictions

    Returns:
        str: Step 1 component identification prompt text

    Raises:
        FileNotFoundError: If step1 prompt file is not found
    """
    prompt_path = RESOURCE_DIR / "step1_component_identification.md"
    if not prompt_path.exists():
        raise FileNotFoundError(f"Step 1 component identification prompt not found: {prompt_path}")

    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()


def get_step2_nutritional_analysis_prompt(dish_name: str, components: List[Dict[str, Any]]) -> str:
    """
    Load and format Step 2 prompt for nutritional analysis.

    This prompt is used after user confirms Step 1 data. It provides
    comprehensive nutritional analysis based on confirmed components.

    Args:
        dish_name: User-confirmed dish name
        components: List of confirmed components with serving sizes
                   Each component should have:
                   - component_name (str)
                   - selected_serving_size (str)
                   - number_of_servings (float)

    Returns:
        str: Step 2 nutritional analysis prompt with confirmed data

    Raises:
        FileNotFoundError: If step2 prompt file is not found
    """
    prompt_path = RESOURCE_DIR / "step2_nutritional_analysis.md"
    if not prompt_path.exists():
        raise FileNotFoundError(f"Step 2 nutritional analysis prompt not found: {prompt_path}")

    with open(prompt_path, "r", encoding="utf-8") as f:
        base_prompt = f.read()

    # Format component data for injection into prompt
    components_text = "\n\n**USER-CONFIRMED DATA FROM STEP 1:**\n\n"
    components_text += f"**Dish Name:** {dish_name}\n\n"
    components_text += "**Components with Serving Sizes:**\n"

    for comp in components:
        comp_name = comp.get("component_name", "Unknown")
        serving_size = comp.get("selected_serving_size", "Unknown")
        servings = comp.get("number_of_servings", 1.0)
        components_text += f"- {comp_name}: {serving_size} × {servings}\n"

    components_text += (
        "\n**Calculate nutritional values for the entire dish "
        "based on the above confirmed data.**\n"
    )

    # Append confirmed data to the prompt
    return base_prompt + components_text
