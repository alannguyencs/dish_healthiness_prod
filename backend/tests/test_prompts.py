"""
Tests for src/service/llm/prompts.py — Phase 1.1.2 reference-block substitution.

The prompt file at backend/resources/step1_component_identification.md
carries a single `__REFERENCE_BLOCK__` placeholder. Stage 3's prompt
helper either substitutes a rendered reference block (when prior
step1_data is non-empty) or strips the placeholder line entirely.
"""

# pylint: disable=missing-class-docstring,missing-function-docstring
# pylint: disable=redefined-outer-name,unused-argument

from src.service.llm.prompts import get_step1_component_identification_prompt


_FULL_PRIOR = {
    "dish_predictions": [
        {"name": "Chicken Rice", "confidence": 0.91},
        {"name": "Hainanese Chicken Rice", "confidence": 0.82},
    ],
    "components": [
        {
            "component_name": "Grilled Chicken",
            "serving_sizes": ["3 oz", "4 oz", "5 oz"],
            "predicted_servings": 1.0,
        },
        {
            "component_name": "White Rice",
            "serving_sizes": ["1/2 cup", "1 cup"],
            "predicted_servings": 1.5,
        },
    ],
}


def test_get_step1_prompt_strips_placeholder_when_reference_is_none():
    prompt = get_step1_component_identification_prompt()
    assert "__REFERENCE_BLOCK__" not in prompt
    assert "## Reference results" not in prompt


def test_get_step1_prompt_strips_placeholder_when_prior_step1_data_is_none():
    prompt = get_step1_component_identification_prompt(
        reference={"query_id": 1, "prior_step1_data": None}
    )
    assert "__REFERENCE_BLOCK__" not in prompt
    assert "## Reference results" not in prompt


def test_get_step1_prompt_substitutes_block_with_full_prior_data():
    prompt = get_step1_component_identification_prompt(
        reference={"query_id": 1, "prior_step1_data": _FULL_PRIOR}
    )
    assert "__REFERENCE_BLOCK__" not in prompt
    assert "## Reference results (HINT ONLY — may or may not match)" in prompt
    assert "**Prior dish name:** Chicken Rice" in prompt
    assert "Grilled Chicken · 3 oz, 4 oz, 5 oz · 1.0" in prompt
    assert "White Rice · 1/2 cup, 1 cup · 1.5" in prompt


def test_get_step1_prompt_omits_dish_name_line_when_dish_predictions_empty():
    prior = {"dish_predictions": [], "components": _FULL_PRIOR["components"]}
    prompt = get_step1_component_identification_prompt(reference={"prior_step1_data": prior})
    assert "## Reference results" in prompt
    assert "**Prior dish name:**" not in prompt
    assert "Grilled Chicken" in prompt


def test_get_step1_prompt_omits_components_block_when_components_empty():
    prior = {"dish_predictions": _FULL_PRIOR["dish_predictions"], "components": []}
    prompt = get_step1_component_identification_prompt(reference={"prior_step1_data": prior})
    assert "**Prior dish name:** Chicken Rice" in prompt
    assert "**Prior components" not in prompt


def test_get_step1_prompt_handles_missing_component_fields_defensively():
    prior = {
        "dish_predictions": [{"name": "X"}],
        "components": [{"component_name": "Mystery"}],
    }
    prompt = get_step1_component_identification_prompt(reference={"prior_step1_data": prior})
    assert "- Mystery ·  · 1.0" in prompt


def test_get_step1_prompt_strips_placeholder_on_empty_prior_data():
    prompt = get_step1_component_identification_prompt(reference={"prior_step1_data": {}})
    assert "__REFERENCE_BLOCK__" not in prompt
    assert "## Reference results" not in prompt
