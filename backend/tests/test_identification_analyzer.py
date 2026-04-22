"""
Tests for src/service/llm/identification_analyzer.py — Phase 1.1.2 two-image path.

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

from src.service.llm import identification_analyzer


@pytest.fixture()
def dummy_image(tmp_path):
    path = tmp_path / "query.jpg"
    path.write_bytes(b"query-jpeg-bytes")
    return path


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

    monkeypatch.setattr(identification_analyzer.genai, "Client", _factory)


def test_analyze_component_identification_sends_single_image_when_no_reference_bytes(monkeypatch, dummy_image):
    os.environ["GEMINI_API_KEY"] = "test-key"
    captured = {}
    _patch_client(monkeypatch, captured=captured)

    result = asyncio.run(
        identification_analyzer.analyze_component_identification_async(
            image_path=dummy_image,
            analysis_prompt="SYSTEM PROMPT",
        )
    )
    assert result["dish_predictions"][0]["name"] == "X"
    contents = captured["contents"]
    # [prompt, query_image]
    assert len(contents) == 2
    assert contents[0] == "SYSTEM PROMPT"


def test_analyze_component_identification_sends_two_images_when_reference_bytes_provided(monkeypatch, dummy_image):
    os.environ["GEMINI_API_KEY"] = "test-key"
    captured = {}
    _patch_client(monkeypatch, captured=captured)

    asyncio.run(
        identification_analyzer.analyze_component_identification_async(
            image_path=dummy_image,
            analysis_prompt="SYSTEM PROMPT",
            reference_image_bytes=b"reference-jpeg-bytes",
        )
    )
    contents = captured["contents"]
    # [prompt, query_image, reference_image]
    assert len(contents) == 3
    assert contents[0] == "SYSTEM PROMPT"


def test_analyze_component_identification_preserves_image_order_query_first_reference_second(
    monkeypatch, dummy_image
):
    os.environ["GEMINI_API_KEY"] = "test-key"
    captured = {}
    _patch_client(monkeypatch, captured=captured)

    asyncio.run(
        identification_analyzer.analyze_component_identification_async(
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
