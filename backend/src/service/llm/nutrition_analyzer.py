"""
Phase 2.3 Gemini analyzer — Nutritional Analysis.

Runs the Gemini 2.5 Pro call that computes calories, macros, micros, and
the healthiness score for a meal image given the confirmed dish name and
components, optionally with a second reference image attached (Phase 2.3
reference-assisted path when the top-1 Phase 2.2 match's
similarity_score >= 0.35).
"""

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

from google import genai  # pylint: disable=no-name-in-module
from google.genai import types  # pylint: disable=import-error,no-name-in-module

from src.service.llm._analyzer_shared import enrich_result_with_metadata
from src.service.llm.models import NutritionalAnalysis
from src.service.llm.pricing import extract_token_usage


# pylint: disable=too-many-arguments
async def analyze_nutritional_analysis_async(  # pylint: disable=too-many-locals
    image_path: Path,
    analysis_prompt: str,
    gemini_model: str = "gemini-2.5-pro",
    thinking_budget: int = -1,
    reference_image_bytes: Optional[bytes] = None,
) -> Dict[str, Any]:
    """
    Async: Nutritional Analysis — calculate nutritional values using Gemini.

    This function performs the second step of dish analysis after the user
    confirms the identification payload (dish name and components). It
    calculates:
    - Healthiness score and rationale
    - Calories and macronutrients
    - Notable micronutrients

    Args:
        image_path: Path to the food dish image file
        analysis_prompt: Nutritional Analysis prompt (with confirmed data)
        gemini_model: Gemini model to use
        thinking_budget: Thinking budget for Gemini
        reference_image_bytes: Optional JPEG bytes for a second image to
            attach after the query image (Phase 2.3 two-image path when
            the top-1 Phase 2.2 match's similarity_score >= 0.35). When
            None, the request is single-image.

    Returns:
        Dict[str, Any]: Nutritional Analysis results with metadata
                       Contains nutritional values and healthiness score
    """
    analysis_start_time = time.time()

    # Validate API key
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is required")

    # Initialize client
    client = genai.Client(api_key=api_key)

    try:
        # Read image
        with open(image_path, "rb") as image_file:
            image_bytes = image_file.read()

        # Create image part
        image_part = types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")

        # Optional reference image (Phase 2.3 two-image request). Order
        # matters: the query image lands at index 1; the reference image
        # at index 2 if attached.
        contents = [analysis_prompt, image_part]
        if reference_image_bytes is not None:
            reference_part = types.Part.from_bytes(
                data=reference_image_bytes, mime_type="image/jpeg"
            )
            contents.append(reference_part)

        # Log model being used
        print(
            f"[Gemini Nutritional Analysis] Using model: {gemini_model} with "
            f"thinking_budget: {thinking_budget} image_parts: {len(contents) - 1}"
        )

        # Run in executor (Gemini SDK isn't truly async)
        loop = asyncio.get_event_loop()

        def _sync_gemini_call():
            return client.models.generate_content(
                model=gemini_model,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=NutritionalAnalysis,
                    temperature=0,
                    thinking_config=types.ThinkingConfig(thinking_budget=thinking_budget),
                ),
            )

        response = await loop.run_in_executor(None, _sync_gemini_call)
        print(f"[Gemini Nutritional Analysis] Response received: {response}")

        # Parse response
        if response.parsed:
            result = response.parsed.model_dump()
        else:
            # Fallback to text parsing
            result = json.loads(response.text)

        # Verify structure
        required_fields = [
            "dish_name",
            "healthiness_score",
            "calories_kcal",
            "fiber_g",
            "carbs_g",
            "protein_g",
            "fat_g",
        ]
        for field in required_fields:
            if field not in result:
                raise ValueError(
                    f"Nutritional Analysis response missing required field: {field}"
                )

        # Extract token usage
        input_tok, output_tok = extract_token_usage(response, "gemini")
        result["input_token"] = input_tok
        result["output_token"] = output_tok

        # Enrich with metadata
        result = enrich_result_with_metadata(result, gemini_model, analysis_start_time)

        return result

    except FileNotFoundError:
        raise
    except Exception as e:
        raise ValueError(f"Error calling Gemini API (Nutritional Analysis): {e}") from e
