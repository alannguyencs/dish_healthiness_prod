"""
Tests for src/service/llm/prompts.py — Phase 1.1.2 reference-block substitution.

The prompt file at backend/resources/step1_component_identification.md
carries a single `__REFERENCE_BLOCK__` placeholder. Stage 3's prompt
helper either substitutes a rendered reference block (when prior
step1_data is non-empty) or strips the placeholder line entirely.
"""

# pylint: disable=missing-class-docstring,missing-function-docstring
# pylint: disable=redefined-outer-name,unused-argument

from src.service.llm.prompts import (
    get_step1_component_identification_prompt,
    get_step2_nutritional_analysis_prompt,
)


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


# ---------------------------------------------------------------------------
# Stage 7 — Step 2 prompt threshold-gated blocks
# ---------------------------------------------------------------------------


_SAMPLE_COMPONENTS = [
    {"component_name": "Beef Burger", "selected_serving_size": "5 oz", "number_of_servings": 1.0}
]


def _db_match(*, confidence_score, food_name="Chicken Rice", source="malaysian_food_calories"):
    return {
        "matched_food_name": food_name,
        "source": source,
        "confidence": confidence_score / 100.0,
        "confidence_score": confidence_score,
        "nutrition_data": {"calories": 500},
        "search_method": "Direct BM25",
        "raw_bm25_score": 2.5,
        "matched_keywords": 2,
        "total_keywords": 2,
    }


def _db_payload(matches):
    return {
        "success": True,
        "nutrition_matches": matches,
        "total_nutrition": {"total_calories": 500},
        "match_summary": {"total_matched": len(matches)},
    }


def _persona_match(*, similarity_score, query_id=42, corrected=None, prior=None):
    return {
        "query_id": query_id,
        "image_url": f"/images/prior_{query_id}.jpg",
        "description": "chicken rice",
        "similarity_score": similarity_score,
        "prior_step2_data": prior
        or {"calories_kcal": 480, "protein_g": 20, "carbs_g": 55, "fat_g": 14, "fiber_g": 1},
        "corrected_step2_data": corrected,
    }


def test_step2_prompt_strips_both_placeholders_on_no_matches():
    prompt = get_step2_nutritional_analysis_prompt("Beef Burger", _SAMPLE_COMPONENTS)
    assert "__NUTRITION_DB_BLOCK__" not in prompt
    assert "__PERSONALIZED_BLOCK__" not in prompt
    assert "## Nutrition Database Matches" not in prompt
    assert "## Personalization Matches" not in prompt


def test_step2_prompt_substitutes_db_block_when_confidence_ge_threshold():
    payload = _db_payload([_db_match(confidence_score=85)])
    prompt = get_step2_nutritional_analysis_prompt(
        "Chicken Rice", _SAMPLE_COMPONENTS, nutrition_db_matches=payload
    )
    assert "__NUTRITION_DB_BLOCK__" not in prompt
    assert "## Nutrition Database Matches" in prompt
    assert '"matched_food_name": "Chicken Rice"' in prompt
    assert '"source": "malaysian_food_calories"' in prompt
    assert '"confidence_score": 85' in prompt
    # Trimmed: raw_bm25_score and matched_keywords must NOT appear in the payload
    assert "raw_bm25_score" not in prompt
    assert "matched_keywords" not in prompt


def test_step2_prompt_strips_db_block_when_confidence_below_threshold():
    payload = _db_payload([_db_match(confidence_score=75)])
    prompt = get_step2_nutritional_analysis_prompt(
        "Chicken Rice", _SAMPLE_COMPONENTS, nutrition_db_matches=payload
    )
    assert "## Nutrition Database Matches" not in prompt


def test_step2_prompt_strips_db_block_when_nutrition_matches_empty():
    payload = _db_payload([])
    prompt = get_step2_nutritional_analysis_prompt(
        "Chicken Rice", _SAMPLE_COMPONENTS, nutrition_db_matches=payload
    )
    assert "## Nutrition Database Matches" not in prompt


def test_step2_prompt_substitutes_personalization_block_when_similarity_ge_threshold():
    matches = [_persona_match(similarity_score=0.55)]
    prompt = get_step2_nutritional_analysis_prompt(
        "Chicken Rice", _SAMPLE_COMPONENTS, personalized_matches=matches
    )
    assert "__PERSONALIZED_BLOCK__" not in prompt
    assert "## Personalization Matches" in prompt
    assert '"description": "chicken rice"' in prompt
    assert '"similarity_score": 0.55' in prompt
    # Trimmed: image_url and query_id must NOT appear in the prompt's JSON payload
    assert "/images/prior_42.jpg" not in prompt
    assert '"query_id"' not in prompt


def test_step2_prompt_strips_personalization_block_when_top_below_threshold():
    matches = [_persona_match(similarity_score=0.25)]
    prompt = get_step2_nutritional_analysis_prompt(
        "Chicken Rice", _SAMPLE_COMPONENTS, personalized_matches=matches
    )
    assert "## Personalization Matches" not in prompt


def test_step2_prompt_carries_corrected_step2_data_when_present():
    corrected = {
        "calories_kcal": 420,
        "protein_g": 25,
        "carbs_g": 50,
        "fat_g": 10,
        "fiber_g": 2,
    }
    matches = [_persona_match(similarity_score=0.70, corrected=corrected)]
    prompt = get_step2_nutritional_analysis_prompt(
        "Chicken Rice", _SAMPLE_COMPONENTS, personalized_matches=matches
    )
    assert '"corrected_step2_data"' in prompt
    assert '"calories_kcal": 420' in prompt


def test_step2_prompt_trims_to_top_5_matches():
    matches = [
        _persona_match(similarity_score=1.0 - (i * 0.05), query_id=100 + i) for i in range(10)
    ]
    prompt = get_step2_nutritional_analysis_prompt(
        "Chicken Rice", _SAMPLE_COMPONENTS, personalized_matches=matches
    )
    # There should be at most 5 personalization-match entries in the rendered
    # JSON payload. Count opening description keys.
    assert prompt.count('"description":') == 5


def test_step2_prompt_db_block_precedes_personalization_block():
    db_payload = _db_payload([_db_match(confidence_score=90)])
    persona = [_persona_match(similarity_score=0.75)]
    prompt = get_step2_nutritional_analysis_prompt(
        "Chicken Rice",
        _SAMPLE_COMPONENTS,
        nutrition_db_matches=db_payload,
        personalized_matches=persona,
    )
    db_idx = prompt.index("## Nutrition Database Matches")
    persona_idx = prompt.index("## Personalization Matches")
    assert db_idx < persona_idx


def test_step2_prompt_handles_malformed_match_payload_defensively():
    # Missing most keys — renderer should not raise.
    broken_match = {
        "matched_food_name": "X",
        "source": "malaysian_food_calories",
        "confidence_score": 95,
    }
    payload = _db_payload([broken_match])
    prompt = get_step2_nutritional_analysis_prompt(
        "Chicken Rice", _SAMPLE_COMPONENTS, nutrition_db_matches=payload
    )
    assert "## Nutrition Database Matches" in prompt


def test_step2_prompt_null_corrected_step2_data_renders_as_null():
    matches = [_persona_match(similarity_score=0.60, corrected=None)]
    prompt = get_step2_nutritional_analysis_prompt(
        "Chicken Rice", _SAMPLE_COMPONENTS, personalized_matches=matches
    )
    assert '"corrected_step2_data": null' in prompt
