"""
Gemini 2.5 Flash fast-caption helper.

Phase 1.1.1 primitive: one short, free-text dish description per uploaded
image. Plain-text response (no structured output, no Pydantic schema) with
`thinking_budget=0` to disable 2.5 Flash's default reasoning step — keeps
this call cheaper and lower-latency than the Phase 1.1.2 Pro call that
follows it.

Reused by `src.service.personalized_reference.resolve_reference_for_upload`
and nowhere else in Stage 2.
"""

import asyncio
import os
from pathlib import Path
from typing import Union

from google import genai  # pylint: disable=no-name-in-module
from google.genai import types  # pylint: disable=import-error,no-name-in-module

_CAPTION_INSTRUCTIONS = (
    "Describe the dish in the image in one short sentence. Use simple, "
    "concrete words — list the main visible foods, the cooking style if "
    "obvious, and any distinctive ingredients. Do not include nutrition "
    "information, prices, or speculation about what is not visible."
)


async def generate_fast_caption_async(image_path: Union[str, Path]) -> str:
    """
    Run Gemini 2.5 Flash against the uploaded image and return a short
    dish description.

    Args:
        image_path (Union[str, Path]): Path to the JPEG on disk.

    Returns:
        str: Stripped plain-text caption.

    Raises:
        ValueError: If GEMINI_API_KEY is missing, the API call fails, or
            the response carries no text payload.
        FileNotFoundError: If `image_path` does not resolve on disk
            (propagates from the `open()` call unchanged).
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is required")

    client = genai.Client(api_key=api_key)

    try:
        with open(image_path, "rb") as image_file:
            image_bytes = image_file.read()

        image_part = types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")

        loop = asyncio.get_event_loop()

        def _sync_gemini_call():
            return client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[_CAPTION_INSTRUCTIONS, image_part],
                config=types.GenerateContentConfig(
                    temperature=0,
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
                ),
            )

        response = await loop.run_in_executor(None, _sync_gemini_call)

        text = (response.text or "").strip() if hasattr(response, "text") else ""
        if not text:
            raise ValueError("Fast-caption response carried no text")
        return text

    except FileNotFoundError:
        raise
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"Error calling Gemini API (Fast Caption): {exc}") from exc
