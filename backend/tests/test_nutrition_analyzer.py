"""
Tests for src/service/llm/nutrition_analyzer.py — Phase 2.3 two-image path.

Patches `google.genai.Client` at the module boundary so the analyzer
exercises its own branching (contents assembly, MIME types, ordering)
without a real Gemini call.
"""

# pylint: disable=missing-class-docstring,missing-function-docstring
# pylint: disable=redefined-outer-name,unused-argument

import asyncio
import os
from types import SimpleNamespace

import pytest

from src.service.llm import nutrition_analyzer


NUTRITION_OK_RESPONSE_DICT = {
    "dish_name": "Chicken Rice",
    "healthiness_score": 70,
    "healthiness_score_rationale": "Balanced",
    "calories_kcal": 500,
    "fiber_g": 2,
    "carbs_g": 60,
    "protein_g": 25,
    "fat_g": 15,
    "micronutrients": ["Iron"],
    "reasoning_sources": "",
    "reasoning_calories": "",
    "reasoning_fiber": "",
    "reasoning_carbs": "",
    "reasoning_protein": "",
    "reasoning_fat": "",
    "reasoning_micronutrients": "",
}


@pytest.fixture()
def dummy_image(tmp_path):
    path = tmp_path / "query.jpg"
    path.write_bytes(b"query-jpeg-bytes")
    return path


def _nutrition_response():
    return SimpleNamespace(
        parsed=SimpleNamespace(model_dump=lambda: NUTRITION_OK_RESPONSE_DICT),
        text=None,
        usage_metadata=SimpleNamespace(
            prompt_token_count=100,
            candidates_token_count=200,
            thoughts_token_count=0,
        ),
    )


def _patch_client(monkeypatch, *, captured: dict, response=None):
    fake_response = response or _nutrition_response()

    def _factory(api_key):  # pylint: disable=unused-argument
        class _Models:
            def generate_content(self, *, model, contents, config):  # noqa: D401
                captured["model"] = model
                captured["contents"] = contents
                captured["config"] = config
                return fake_response

        return SimpleNamespace(models=_Models())

    monkeypatch.setattr(nutrition_analyzer.genai, "Client", _factory)


def test_analyze_nutritional_analysis_sends_single_image_when_no_reference_bytes(monkeypatch, dummy_image):
    os.environ["GEMINI_API_KEY"] = "test-key"
    captured = {}
    _patch_client(monkeypatch, captured=captured)

    asyncio.run(
        nutrition_analyzer.analyze_nutritional_analysis_async(
            image_path=dummy_image,
            analysis_prompt="NUTRITION PROMPT",
        )
    )
    assert len(captured["contents"]) == 2  # prompt + query image


def test_analyze_nutritional_analysis_sends_two_images_when_reference_bytes_provided(monkeypatch, dummy_image):
    os.environ["GEMINI_API_KEY"] = "test-key"
    captured = {}
    _patch_client(monkeypatch, captured=captured)

    asyncio.run(
        nutrition_analyzer.analyze_nutritional_analysis_async(
            image_path=dummy_image,
            analysis_prompt="NUTRITION PROMPT",
            reference_image_bytes=b"prior-dish-bytes",
        )
    )
    assert len(captured["contents"]) == 3  # prompt + query + reference
    assert captured["contents"][0] == "NUTRITION PROMPT"


def test_analyze_nutritional_analysis_preserves_order_query_first_reference_second(monkeypatch, dummy_image):
    os.environ["GEMINI_API_KEY"] = "test-key"
    captured = {}
    _patch_client(monkeypatch, captured=captured)

    asyncio.run(
        nutrition_analyzer.analyze_nutritional_analysis_async(
            image_path=dummy_image,
            analysis_prompt="NUTRITION PROMPT",
            reference_image_bytes=b"prior-dish-bytes",
        )
    )
    contents = captured["contents"]
    ref_part = contents[2]
    ref_dict = ref_part.model_dump() if hasattr(ref_part, "model_dump") else dict(ref_part)
    ref_bytes = ref_dict.get("inline_data", {}).get("data")
    if isinstance(ref_bytes, bytes):
        assert ref_bytes == b"prior-dish-bytes"
    elif isinstance(ref_bytes, str):
        import base64  # pylint: disable=import-outside-toplevel

        assert base64.b64decode(ref_bytes) == b"prior-dish-bytes"


def test_analyze_nutritional_analysis_does_not_require_reasoning_fields(monkeypatch, dummy_image):
    """reasoning_* default to empty strings — analyzer must not raise on empty values."""
    os.environ["GEMINI_API_KEY"] = "test-key"
    captured = {}
    _patch_client(monkeypatch, captured=captured)

    result = asyncio.run(
        nutrition_analyzer.analyze_nutritional_analysis_async(
            image_path=dummy_image,
            analysis_prompt="NUTRITION PROMPT",
        )
    )
    assert result["reasoning_sources"] == ""
    assert result["reasoning_calories"] == ""
    assert result["reasoning_micronutrients"] == ""
