"""
Tests for src/service/llm/fast_caption.py.

Patches `google.genai.Client` at the module boundary so no real Gemini
call is made. Each test writes a small dummy image to a temp directory so
the `open(image_path, "rb")` path in the helper exercises real filesystem
semantics (including `FileNotFoundError` propagation).
"""

# pylint: disable=missing-class-docstring,missing-function-docstring
# pylint: disable=redefined-outer-name,unused-argument

import asyncio
import os
from types import SimpleNamespace

import pytest

from src.service.llm import fast_caption


@pytest.fixture()
def dummy_image(tmp_path):
    path = tmp_path / "dish.jpg"
    path.write_bytes(b"\xff\xd8\xff\xe0fake-jpeg-bytes")
    return path


def _patch_client(monkeypatch, *, returns=None, raises=None):
    def _factory(api_key):  # pylint: disable=unused-argument
        class _Models:
            def generate_content(self, **kwargs):  # pylint: disable=unused-argument
                if raises is not None:
                    raise raises
                return returns

        return SimpleNamespace(models=_Models())

    monkeypatch.setattr(fast_caption.genai, "Client", _factory)


def test_generate_fast_caption_async_returns_plain_text(monkeypatch, dummy_image):
    _patch_client(
        monkeypatch,
        returns=SimpleNamespace(text="  grilled chicken with rice and cucumber  "),
    )
    result = asyncio.run(fast_caption.generate_fast_caption_async(dummy_image))
    assert result == "grilled chicken with rice and cucumber"


def test_generate_fast_caption_async_raises_on_missing_api_key(monkeypatch, dummy_image):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        asyncio.run(fast_caption.generate_fast_caption_async(dummy_image))


def test_generate_fast_caption_async_raises_on_api_error(monkeypatch, dummy_image):
    os.environ["GEMINI_API_KEY"] = "test-key"
    _patch_client(monkeypatch, raises=RuntimeError("rate limited"))
    with pytest.raises(ValueError, match="Fast Caption"):
        asyncio.run(fast_caption.generate_fast_caption_async(dummy_image))


def test_generate_fast_caption_async_propagates_file_not_found(monkeypatch):
    os.environ["GEMINI_API_KEY"] = "test-key"
    _patch_client(monkeypatch, returns=SimpleNamespace(text="unused"))
    with pytest.raises(FileNotFoundError):
        asyncio.run(fast_caption.generate_fast_caption_async("/nonexistent/path.jpg"))


def test_generate_fast_caption_async_raises_on_empty_text(monkeypatch, dummy_image):
    os.environ["GEMINI_API_KEY"] = "test-key"
    _patch_client(monkeypatch, returns=SimpleNamespace(text="   "))
    with pytest.raises(ValueError, match="no text"):
        asyncio.run(fast_caption.generate_fast_caption_async(dummy_image))
