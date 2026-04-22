"""
Shared helpers for the two Gemini analyzer modules.

`enrich_result_with_metadata` is called by both
`identification_analyzer.analyze_component_identification_async` and
`nutrition_analyzer.analyze_nutritional_analysis_async` to stamp model /
price / timing metadata onto the parsed response. Keeping it here avoids
duplicating the logic across the two analyzer modules.
"""

import time
from typing import Any, Dict

from src.service.llm.pricing import compute_price_usd


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
    except Exception:  # pylint: disable=broad-exception-caught
        pass

    # Add analysis time
    result["analysis_time"] = round(time.time() - analysis_start_time, 3)

    return result
