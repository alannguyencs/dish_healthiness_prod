"""
Prompt loading and formatting utilities.

This module provides functions for loading and formatting prompts
for dish analysis.
"""

import re
from typing import Any, Dict, List, Optional

from src.configs import RESOURCE_DIR
from src.service.llm._step2_blocks import (
    render_nutrition_db_block,
    render_personalized_block,
)


_REFERENCE_PLACEHOLDER = "__REFERENCE_BLOCK__"
# Match the placeholder line along with one trailing newline so stripping
# leaves no blank gap behind.
_REFERENCE_STRIP_RE = re.compile(
    r"^[ \t]*" + re.escape(_REFERENCE_PLACEHOLDER) + r"[ \t]*\n?", re.M
)

_NUTRITION_DB_PLACEHOLDER = "__NUTRITION_DB_BLOCK__"
_NUTRITION_DB_STRIP_RE = re.compile(
    r"^[ \t]*" + re.escape(_NUTRITION_DB_PLACEHOLDER) + r"[ \t]*\n?", re.M
)

_PERSONALIZED_PLACEHOLDER = "__PERSONALIZED_BLOCK__"
_PERSONALIZED_STRIP_RE = re.compile(
    r"^[ \t]*" + re.escape(_PERSONALIZED_PLACEHOLDER) + r"[ \t]*\n?", re.M
)


# ============================================================
# STEP 1 & STEP 2 PROMPTS (New Two-Step Flow)
# ============================================================


def _render_reference_block(
    prior_step1_data: Dict[str, Any],
    confirmed_dish_name: Optional[str] = None,
    confirmed_portions: Optional[float] = None,
) -> str:
    """
    Render the 'Reference results (HINT ONLY)' block from prior step1_data.

    When the prior was confirmed by the user (Phase 1.2), the user-corrected
    `confirmed_dish_name` and `confirmed_portions` override the AI's original
    proposal in the rendered block. The prompt instructs Gemini to prefer
    the user-verified values unless the query image clearly disagrees.

    Only non-empty fields are rendered so the block tracks what the
    referenced dish actually has.
    """
    has_user_edits = bool(confirmed_dish_name) or confirmed_portions is not None
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
    if has_user_edits:
        lines += [
            "",
            (
                "**The user manually corrected the prior dish's name and/or servings "
                "(fields marked 'user-verified' below).** Prefer those values over the "
                "original AI proposal when the query image shows a visually similar "
                "dish — the user knows their own meals better than the first-pass "
                "model did."
            ),
        ]
    dish_predictions = prior_step1_data.get("dish_predictions") or []
    ai_dish_name = dish_predictions[0].get("name") if dish_predictions else None
    if confirmed_dish_name:
        lines += ["", f"**Prior dish name (user-verified):** {confirmed_dish_name}"]
        if ai_dish_name and ai_dish_name != confirmed_dish_name:
            lines.append(f"**Prior dish name (AI original):** {ai_dish_name}")
    elif ai_dish_name:
        lines += ["", f"**Prior dish name:** {ai_dish_name}"]
    if confirmed_portions is not None:
        lines += [
            "",
            f"**Prior total servings (user-verified):** {confirmed_portions}",
        ]
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

    ref = reference or {}
    prior = ref.get("prior_step1_data")
    confirmed_dish_name = ref.get("prior_confirmed_dish_name")
    confirmed_portions = ref.get("prior_confirmed_portions")
    has_renderable_prior = bool(prior) and (
        bool(prior.get("dish_predictions")) or bool(prior.get("components"))
    )
    has_user_edits = bool(confirmed_dish_name) or confirmed_portions is not None
    if has_renderable_prior or has_user_edits:
        block = _render_reference_block(
            prior or {},
            confirmed_dish_name=confirmed_dish_name,
            confirmed_portions=confirmed_portions,
        )
        return prompt.replace(_REFERENCE_PLACEHOLDER, block)
    return _REFERENCE_STRIP_RE.sub("", prompt)


def _substitute_or_strip(
    prompt: str, placeholder_re: re.Pattern, placeholder: str, block: str
) -> str:
    """Substitute `placeholder` with `block` when non-empty, else strip the placeholder line."""
    if block:
        return prompt.replace(placeholder, block)
    return placeholder_re.sub("", prompt)


def get_step2_nutritional_analysis_prompt(
    dish_name: str,
    components: List[Dict[str, Any]],
    nutrition_db_matches: Optional[Dict[str, Any]] = None,
    personalized_matches: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """
    Load and format Step 2 prompt for nutritional analysis.

    Phase 2.3 (Stage 7): gate the two optional reference blocks on
    `THRESHOLD_DB_INCLUDE` and `THRESHOLD_PERSONALIZATION_INCLUDE`, then
    substitute or strip the placeholder lines accordingly. Block ordering
    is fixed in the .md: DB block precedes personalization block.

    Args:
        dish_name: User-confirmed dish name
        components: List of confirmed components with serving sizes
                   Each component should have:
                   - component_name (str)
                   - selected_serving_size (str)
                   - number_of_servings (float)
        nutrition_db_matches: Optional Stage 5 pre-Pro-persisted dict.
            When its top match's `confidence_score >= 80`, the
            `__NUTRITION_DB_BLOCK__` placeholder is substituted.
        personalized_matches: Optional Stage 6 pre-Pro-persisted list.
            When its top match's `similarity_score >= 0.30`, the
            `__PERSONALIZED_BLOCK__` placeholder is substituted.

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

    base_prompt = _substitute_or_strip(
        base_prompt,
        _NUTRITION_DB_STRIP_RE,
        _NUTRITION_DB_PLACEHOLDER,
        render_nutrition_db_block(nutrition_db_matches),
    )
    base_prompt = _substitute_or_strip(
        base_prompt,
        _PERSONALIZED_STRIP_RE,
        _PERSONALIZED_PLACEHOLDER,
        render_personalized_block(personalized_matches),
    )

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
