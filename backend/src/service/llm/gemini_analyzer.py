"""
Gemini analysis module.

Provides async Gemini API integration for dish health analysis.
"""

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any, Dict

from google import genai
from google.genai import types

from src.service.llm.models import Step1ComponentIdentification, Step2NutritionalAnalysis
from src.service.llm.pricing import compute_price_usd, extract_token_usage


def enrich_result_with_metadata(
    result: Dict[str, Any], model: str, analysis_start_time: float
) -> Dict[str, Any]:
    """
    Enrich result dict with model, price, and timing metadata.

    Args:
        result: Analysis result dictionary
        model: Model identifier string
        analysis_start_time: Start time from time.time()

    Returns:
        Dict[str, Any]: Enriched result dictionary
    """
    result["model"] = model

    # Compute price if token counts are available
    try:
        in_tok = int(result.get("input_token") or 0)
        out_tok = int(result.get("output_token") or 0)
        result["price_usd"] = compute_price_usd(
            model=model, vendor="gemini", input_tokens=in_tok, output_tokens=out_tok
        )
    except Exception:
        pass

    # Add analysis time
    result["analysis_time"] = round(time.time() - analysis_start_time, 3)

    return result


# ============================================================
# STEP 1 & STEP 2 ANALYZERS
# ============================================================


async def analyze_step1_component_identification_async(
    image_path: Path,
    analysis_prompt: str,
    gemini_model: str = "gemini-2.5-pro",
    thinking_budget: int = -1,
) -> Dict[str, Any]:
    """
    Async: Step 1 - Identify components and predict serving sizes using Gemini.

    This function performs the first step of dish analysis:
    - Predicts dish names (top 1-5 with confidence)
    - Identifies major nutrition components
    - Provides component-level serving size predictions

    Args:
        image_path: Path to the food dish image file
        analysis_prompt: Step 1 component identification prompt text
        gemini_model: Gemini model to use
        thinking_budget: Thinking budget for Gemini

    Returns:
        Dict[str, Any]: Step 1 results with metadata
                       Contains dish_predictions and components
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

        # Log model being used
        print(
            f"[Gemini Step 1] Using model: {gemini_model} with thinking_budget: {thinking_budget}"
        )

        # Run in executor (Gemini SDK isn't truly async)
        loop = asyncio.get_event_loop()

        def _sync_gemini_call():
            return client.models.generate_content(
                model=gemini_model,
                contents=[analysis_prompt, image_part],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=Step1ComponentIdentification,
                    temperature=0,
                    thinking_config=types.ThinkingConfig(thinking_budget=thinking_budget),
                ),
            )

        response = await loop.run_in_executor(None, _sync_gemini_call)
        print(f"[Gemini Step 1] Response received: {response}")

        # Parse response
        if response.parsed:
            result = response.parsed.model_dump()
        else:
            # Fallback to text parsing
            result = json.loads(response.text)

        # Verify structure
        if "dish_predictions" not in result or "components" not in result:
            raise ValueError(
                "Step 1 response missing required fields (dish_predictions or components)"
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
        raise ValueError(f"Error calling Gemini API (Step 1): {e}") from e


async def analyze_step2_nutritional_analysis_async(
    image_path: Path,
    analysis_prompt: str,
    gemini_model: str = "gemini-2.5-pro",
    thinking_budget: int = -1,
) -> Dict[str, Any]:
    """
    Async: Step 2 - Calculate nutritional values using Gemini.

    This function performs the second step of dish analysis after user
    confirms Step 1 data (dish name and components). It calculates:
    - Healthiness score and rationale
    - Calories and macronutrients
    - Notable micronutrients

    Args:
        image_path: Path to the food dish image file
        analysis_prompt: Step 2 nutritional analysis prompt (with confirmed data)
        gemini_model: Gemini model to use
        thinking_budget: Thinking budget for Gemini

    Returns:
        Dict[str, Any]: Step 2 results with metadata
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

        # Log model being used
        print(
            f"[Gemini Step 2] Using model: {gemini_model} with thinking_budget: {thinking_budget}"
        )

        # Run in executor (Gemini SDK isn't truly async)
        loop = asyncio.get_event_loop()

        def _sync_gemini_call():
            return client.models.generate_content(
                model=gemini_model,
                contents=[analysis_prompt, image_part],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=Step2NutritionalAnalysis,
                    temperature=0,
                    thinking_config=types.ThinkingConfig(thinking_budget=thinking_budget),
                ),
            )

        response = await loop.run_in_executor(None, _sync_gemini_call)
        print(f"[Gemini Step 2] Response received: {response}")

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
                raise ValueError(f"Step 2 response missing required field: {field}")

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
        raise ValueError(f"Error calling Gemini API (Step 2): {e}") from e
