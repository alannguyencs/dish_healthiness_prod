"""
OpenAI analysis module.

Provides async OpenAI API integration for dish health analysis.
"""

import base64
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from openai import AsyncOpenAI

from src.service.llm.models import FoodHealthAnalysis
from src.service.llm.pricing import compute_price_usd, extract_token_usage


def prepare_openai_model_and_reasoning(
    llm_model: str
) -> Tuple[str, Optional[str]]:
    """
    Extract reasoning mode and actual model name for GPT-5 variants.

    Args:
        llm_model: Model string (e.g., 'gpt-5-high')

    Returns:
        Tuple[str, Optional[str]]: (actual_model, reasoning_mode)
    """
    reasoning_mode = None
    actual_model = llm_model

    if llm_model.startswith("gpt-5"):
        actual_model = "gpt-5"
        if llm_model == "gpt-5-low":
            reasoning_mode = "low"
        elif llm_model == "gpt-5-medium":
            reasoning_mode = "medium"
        elif llm_model == "gpt-5-high":
            reasoning_mode = "high"

    return actual_model, reasoning_mode


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
            vendor='openai',
            input_tokens=in_tok,
            output_tokens=out_tok
        )
    except Exception:
        pass

    # Add analysis time
    result['analysis_time'] = round(time.time() - analysis_start_time, 3)

    return result


async def analyze_with_openai_async(
    image_path: Path,
    analysis_prompt: str,
    llm_model: str = "gpt-5-low"
) -> Dict[str, Any]:
    """
    Async: Analyze dish image using OpenAI.

    Args:
        image_path: Path to the food dish image file
        analysis_prompt: Analysis prompt text
        llm_model: OpenAI model to use

    Returns:
        Dict[str, Any]: Analysis results with metadata
    """
    analysis_start_time = time.time()

    # Encode image
    with open(image_path, "rb") as image_file:
        b64_image = base64.b64encode(image_file.read()).decode("utf-8")

    print(f"OpenAI model: {llm_model}")

    # Prepare model and reasoning
    actual_model, reasoning_mode = prepare_openai_model_and_reasoning(
        llm_model
    )

    # Validate API key
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable is required")

    # Initialize client
    client = AsyncOpenAI(api_key=api_key)

    # Make API call
    response = await client.responses.parse(
        model=actual_model,
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": analysis_prompt
                    },
                    {
                        "type": "input_image",
                        "image_url": f"data:image/jpeg;base64,{b64_image}"
                    },
                ]
            }
        ],
        text_format=FoodHealthAnalysis,
        reasoning={"effort": reasoning_mode}
    )

    print(f'OpenAI response: {response}')

    # Parse response
    output_parsed = response.output_parsed
    result = output_parsed.model_dump()
    
    # LOG: Verify related_keywords is present
    print(
        f"[OpenAI] Related keywords: "
        f"{result.get('related_keywords', 'NOT FOUND')}"
    )

    # Extract token usage
    input_tok, output_tok = extract_token_usage(response, 'openai')
    result['input_token'] = input_tok
    result['output_token'] = output_tok

    # Enrich with metadata
    result = enrich_result_with_metadata(
        result, llm_model, analysis_start_time
    )

    return result

