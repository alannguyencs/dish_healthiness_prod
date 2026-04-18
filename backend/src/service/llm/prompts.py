"""
Prompt loading and formatting utilities.

This module provides functions for loading and formatting prompts
for dish analysis.
"""

import re
from typing import Any, Dict, List, Optional

from src.configs import RESOURCE_DIR


_REFERENCE_PLACEHOLDER = "__REFERENCE_BLOCK__"
# Match the placeholder line along with one trailing newline so stripping
# leaves no blank gap behind.
_REFERENCE_STRIP_RE = re.compile(
    r"^[ \t]*" + re.escape(_REFERENCE_PLACEHOLDER) + r"[ \t]*\n?", re.M
)


# ============================================================
# STEP 1 & STEP 2 PROMPTS (New Two-Step Flow)
# ============================================================


def _render_reference_block(prior_step1_data: Dict[str, Any]) -> str:
    """
    Render the 'Reference results (HINT ONLY)' block from prior step1_data.

    Only non-empty fields are rendered so the block tracks what the
    referenced dish actually has.
    """
    lines = [
        "## Reference results (HINT ONLY — may or may not match)",
        "",
        (
            "The user has uploaded a similar dish before. The **image attached after "
            "the query image is the prior dish**, and the analysis below is what we "
            "produced for it last time. Use this ONLY as a hint — the two dishes may "
            "differ in cuisine, preparation, or portion. If the query image disagrees, "
            "trust the query image."
        ),
    ]
    dish_predictions = prior_step1_data.get("dish_predictions") or []
    if dish_predictions and dish_predictions[0].get("name"):
        lines += ["", f"**Prior dish name:** {dish_predictions[0]['name']}"]
    components = prior_step1_data.get("components") or []
    if components:
        lines += ["", "**Prior components (name · serving sizes · predicted servings):**"]
        for comp in components:
            name = comp.get("component_name", "Unknown")
            sizes = ", ".join(comp.get("serving_sizes") or [])
            servings = comp.get("predicted_servings", 1.0)
            lines.append(f"- {name} · {sizes} · {servings}")
    return "\n".join(lines)


def get_step1_component_identification_prompt(
    reference: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Load Step 1 prompt for component identification.

    This prompt is used for the initial analysis that identifies:
    - Dish name predictions (top 1-5)
    - Major nutrition components
    - Component-level serving size predictions

    Args:
        reference: Optional persisted `result_gemini.reference_image` dict.
            When provided and its `prior_step1_data` is non-empty, the
            `__REFERENCE_BLOCK__` placeholder in the prompt is substituted
            with a rendered hint block. Otherwise the placeholder line is
            stripped entirely so the prompt carries no reference section.

    Returns:
        str: Step 1 component identification prompt text

    Raises:
        FileNotFoundError: If step1 prompt file is not found
    """
    prompt_path = RESOURCE_DIR / "step1_component_identification.md"
    if not prompt_path.exists():
        raise FileNotFoundError(f"Step 1 component identification prompt not found: {prompt_path}")

    with open(prompt_path, "r", encoding="utf-8") as f:
        prompt = f.read()

    prior = (reference or {}).get("prior_step1_data")
    has_renderable_prior = bool(prior) and (
        bool(prior.get("dish_predictions")) or bool(prior.get("components"))
    )
    if has_renderable_prior:
        return prompt.replace(_REFERENCE_PLACEHOLDER, _render_reference_block(prior))
    return _REFERENCE_STRIP_RE.sub("", prompt)


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
