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

from src.service.llm.models import FoodHealthAnalysis
from src.service.llm.pricing import compute_price_usd, extract_token_usage


def enrich_result_with_metadata(
    result: Dict[str, Any],
    model: str,
    analysis_start_time: float
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
    result['model'] = model

    # Compute price if token counts are available
    try:
        in_tok = int(result.get('input_token') or 0)
        out_tok = int(result.get('output_token') or 0)
        result['price_usd'] = compute_price_usd(
            model=model,
            vendor='gemini',
            input_tokens=in_tok,
            output_tokens=out_tok
        )
    except Exception:
        pass

    # Add analysis time
    result['analysis_time'] = round(time.time() - analysis_start_time, 3)

    return result


async def analyze_with_gemini_async(
    image_path: Path,
    analysis_prompt: str,
    gemini_model: str = "gemini-2.5-flash",
    thinking_budget: int = -1
) -> Dict[str, Any]:
    """
    Async: Analyze dish image using Gemini.

    Args:
        image_path: Path to the food dish image file
        analysis_prompt: Analysis prompt text
        gemini_model: Gemini model to use
        thinking_budget: Thinking budget for Gemini

    Returns:
        Dict[str, Any]: Analysis results with metadata
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
        image_part = types.Part.from_bytes(
            data=image_bytes,
            mime_type="image/jpeg"
        )

        # Run in executor (Gemini SDK isn't truly async)
        loop = asyncio.get_event_loop()

        def _sync_gemini_call():
            return client.models.generate_content(
                model=gemini_model,
                contents=[analysis_prompt, image_part],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=FoodHealthAnalysis,
                    temperature=0,
                    thinking_config=types.ThinkingConfig(
                        thinking_budget=thinking_budget
                    ),
                )
            )

        response = await loop.run_in_executor(None, _sync_gemini_call)
        print(f"Gemini response: {response}")

        # Parse response
        if response.parsed:
            result = response.parsed.model_dump()
        else:
            # Fallback to text parsing
            result = json.loads(response.text)
        
        # LOG: Verify related_keywords is present
        print(
            f"[Gemini] Related keywords: "
            f"{result.get('related_keywords', 'NOT FOUND')}"
        )

        # Extract token usage
        input_tok, output_tok = extract_token_usage(response, 'gemini')
        result['input_token'] = input_tok
        result['output_token'] = output_tok

        # Enrich with metadata
        result = enrich_result_with_metadata(
            result, gemini_model, analysis_start_time
        )

        return result

    except FileNotFoundError:
        raise
    except Exception as e:
        raise ValueError(f"Error calling Gemini API: {e}") from e

