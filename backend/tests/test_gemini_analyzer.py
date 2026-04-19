"""
Tests for src/service/llm/gemini_analyzer.py — Phase 1.1.2 two-image path.

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

from src.service.llm import gemini_analyzer


@pytest.fixture()
def dummy_image(tmp_path):
    path = tmp_path / "query.jpg"
    path.write_bytes(b"query-jpeg-bytes")
    return path


STEP2_OK_RESPONSE_DICT = {
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


def _patch_client(monkeypatch, *, captured: dict, response=None):
    fake_response = response or SimpleNamespace(
        parsed=SimpleNamespace(
            model_dump=lambda: {
                "dish_predictions": [{"name": "X", "confidence": 0.9}],
                "components": [{"component_name": "X", "serving_sizes": ["1 oz"]}],
            }
        ),
        text=None,
        usage_metadata=SimpleNamespace(
            prompt_token_count=10,
            candidates_token_count=20,
            thoughts_token_count=0,
        ),
    )

    def _factory(api_key):  # pylint: disable=unused-argument
        class _Models:
            def generate_content(self, *, model, contents, config):  # noqa: D401
                captured["model"] = model
                captured["contents"] = contents
                captured["config"] = config
                return fake_response

        return SimpleNamespace(models=_Models())

    monkeypatch.setattr(gemini_analyzer.genai, "Client", _factory)


def test_analyze_step1_sends_single_image_when_no_reference_bytes(monkeypatch, dummy_image):
    os.environ["GEMINI_API_KEY"] = "test-key"
    captured = {}
    _patch_client(monkeypatch, captured=captured)

    result = asyncio.run(
        gemini_analyzer.analyze_step1_component_identification_async(
            image_path=dummy_image,
            analysis_prompt="SYSTEM PROMPT",
        )
    )
    assert result["dish_predictions"][0]["name"] == "X"
    contents = captured["contents"]
    # [prompt, query_image]
    assert len(contents) == 2
    assert contents[0] == "SYSTEM PROMPT"


def test_analyze_step1_sends_two_images_when_reference_bytes_provided(monkeypatch, dummy_image):
    os.environ["GEMINI_API_KEY"] = "test-key"
    captured = {}
    _patch_client(monkeypatch, captured=captured)

    asyncio.run(
        gemini_analyzer.analyze_step1_component_identification_async(
            image_path=dummy_image,
            analysis_prompt="SYSTEM PROMPT",
            reference_image_bytes=b"reference-jpeg-bytes",
        )
    )
    contents = captured["contents"]
    # [prompt, query_image, reference_image]
    assert len(contents) == 3
    assert contents[0] == "SYSTEM PROMPT"


def test_analyze_step1_preserves_image_order_query_first_reference_second(
    monkeypatch, dummy_image
):
    os.environ["GEMINI_API_KEY"] = "test-key"
    captured = {}
    _patch_client(monkeypatch, captured=captured)

    asyncio.run(
        gemini_analyzer.analyze_step1_component_identification_async(
            image_path=dummy_image,
            analysis_prompt="SYSTEM PROMPT",
            reference_image_bytes=b"reference-jpeg-bytes",
        )
    )
    contents = captured["contents"]
    query_part = contents[1]
    reference_part = contents[2]
    # `types.Part.from_bytes` wraps bytes in an inline_data container.
    # Inspect via dict dump to avoid tight SDK coupling.
    query_dict = query_part.model_dump() if hasattr(query_part, "model_dump") else dict(query_part)
    ref_dict = (
        reference_part.model_dump()
        if hasattr(reference_part, "model_dump")
        else dict(reference_part)
    )
    query_bytes = query_dict.get("inline_data", {}).get("data")
    ref_bytes = ref_dict.get("inline_data", {}).get("data")
    # Either raw bytes or base64-encoded strings depending on SDK version.
    assert query_bytes != ref_bytes
    # Reference bytes are the ones we passed in.
    if isinstance(ref_bytes, bytes):
        assert ref_bytes == b"reference-jpeg-bytes"
    elif isinstance(ref_bytes, str):
        import base64  # pylint: disable=import-outside-toplevel

        assert base64.b64decode(ref_bytes) == b"reference-jpeg-bytes"


# ---------------------------------------------------------------------------
# Stage 7 — Step 2 analyzer with optional reference_image_bytes
# ---------------------------------------------------------------------------


def _step2_response():
    return SimpleNamespace(
        parsed=SimpleNamespace(model_dump=lambda: STEP2_OK_RESPONSE_DICT),
        text=None,
        usage_metadata=SimpleNamespace(
            prompt_token_count=100,
            candidates_token_count=200,
            thoughts_token_count=0,
        ),
    )


def test_analyze_step2_sends_single_image_when_no_reference_bytes(monkeypatch, dummy_image):
    os.environ["GEMINI_API_KEY"] = "test-key"
    captured = {}
    _patch_client(monkeypatch, captured=captured, response=_step2_response())

    asyncio.run(
        gemini_analyzer.analyze_step2_nutritional_analysis_async(
            image_path=dummy_image,
            analysis_prompt="STEP2 PROMPT",
        )
    )
    assert len(captured["contents"]) == 2  # prompt + query image


def test_analyze_step2_sends_two_images_when_reference_bytes_provided(monkeypatch, dummy_image):
    os.environ["GEMINI_API_KEY"] = "test-key"
    captured = {}
    _patch_client(monkeypatch, captured=captured, response=_step2_response())

    asyncio.run(
        gemini_analyzer.analyze_step2_nutritional_analysis_async(
            image_path=dummy_image,
            analysis_prompt="STEP2 PROMPT",
            reference_image_bytes=b"prior-dish-bytes",
        )
    )
    assert len(captured["contents"]) == 3  # prompt + query + reference
    assert captured["contents"][0] == "STEP2 PROMPT"


def test_analyze_step2_preserves_order_query_first_reference_second(monkeypatch, dummy_image):
    os.environ["GEMINI_API_KEY"] = "test-key"
    captured = {}
    _patch_client(monkeypatch, captured=captured, response=_step2_response())

    asyncio.run(
        gemini_analyzer.analyze_step2_nutritional_analysis_async(
            image_path=dummy_image,
            analysis_prompt="STEP2 PROMPT",
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


def test_analyze_step2_does_not_require_reasoning_fields(monkeypatch, dummy_image):
    """reasoning_* default to empty strings — analyzer must not raise on empty values."""
    os.environ["GEMINI_API_KEY"] = "test-key"
    captured = {}
    _patch_client(monkeypatch, captured=captured, response=_step2_response())

    result = asyncio.run(
        gemini_analyzer.analyze_step2_nutritional_analysis_async(
            image_path=dummy_image,
            analysis_prompt="STEP2 PROMPT",
        )
    )
    assert result["reasoning_sources"] == ""
    assert result["reasoning_calories"] == ""
    assert result["reasoning_micronutrients"] == ""
