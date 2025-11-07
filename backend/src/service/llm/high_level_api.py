"""
High-level API for dish analysis.

Provides convenient functions for running multiple analyses in parallel.
"""

import asyncio
from pathlib import Path
from typing import Any, Dict, Union

from src.service.llm.openai_analyzer import analyze_with_openai_async
from src.service.llm.gemini_analyzer import analyze_with_gemini_async
from src.service.llm.prompts import get_analysis_prompt


async def analyze_dish_parallel_async(
    image_path: Union[str, Path],
    openai_model: str = "gpt-5-low",
    gemini_model: str = "gemini-2.5-pro",
    analysis_prompt: str = None,
    gemini_thinking_budget: int = -1
) -> Dict[str, Dict[str, Any]]:
    """
    Run OpenAI and Gemini analyses in parallel (Flow 2 & 3).

    Args:
        image_path: Path to dish image
        openai_model: OpenAI model to use
        gemini_model: Gemini model to use
        analysis_prompt: Optional custom prompt
        gemini_thinking_budget: Gemini thinking budget

    Returns:
        Dict with 'OpenAI' and 'Gemini' keys containing results
    """
    image_path = Path(image_path)

    if analysis_prompt is None:
        analysis_prompt = get_analysis_prompt()

    # Run both in parallel
    openai_result, gemini_result = await asyncio.gather(
        analyze_with_openai_async(
            image_path, analysis_prompt, openai_model
        ),
        analyze_with_gemini_async(
            image_path, analysis_prompt, gemini_model,
            gemini_thinking_budget
        )
    )

    return {
        "OpenAI": openai_result,
        "Gemini": gemini_result
    }


def analyze_dish_parallel(
    image_path: Union[str, Path],
    openai_model: str = "gpt-5-low",
    gemini_model: str = "gemini-2.5-pro",
    analysis_prompt: str = None,
    gemini_thinking_budget: int = -1
) -> Dict[str, Dict[str, Any]]:
    """
    Sync wrapper for parallel dish analysis.

    Args:
        image_path: Path to dish image
        openai_model: OpenAI model to use
        gemini_model: Gemini model to use
        analysis_prompt: Optional custom prompt
        gemini_thinking_budget: Gemini thinking budget

    Returns:
        Dict with 'OpenAI' and 'Gemini' keys containing results
    """
    return asyncio.run(analyze_dish_parallel_async(
        image_path=image_path,
        openai_model=openai_model,
        gemini_model=gemini_model,
        analysis_prompt=analysis_prompt,
        gemini_thinking_budget=gemini_thinking_budget
    ))

