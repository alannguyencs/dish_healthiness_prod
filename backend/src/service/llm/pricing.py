"""
LLM pricing and token calculation utilities.

This module provides functions for calculating API costs based on
token usage and model pricing.

Pricing is per 1 million tokens (input and output separately).
Prices are in USD.
"""

from typing import Any, Tuple

# Pricing table (USD per 1 million tokens)
PRICING = {
    # OpenAI Models
    # Cached input tokens get 90% discount (10% of regular price)
    "gpt-5": {"input": 1.25, "cached_input": 0.125, "output": 10.00},
    "gpt-5-low": {"input": 1.25, "cached_input": 0.125, "output": 10.00},
    "gpt-5-medium": {"input": 1.25, "cached_input": 0.125, "output": 10.00},
    "gpt-5-high": {"input": 1.25, "cached_input": 0.125, "output": 10.00},
    # Google Gemini Models
    "gemini-2.5-flash": {"input": 0.30, "output": 2.50},
    "gemini-2.5-pro": {"input": 1.25, "output": 10.00},
}

# Default pricing for unknown models (use cheapest available)
DEFAULT_PRICING = {"input": 0.075, "output": 0.30}


def normalize_model_key(model: str, vendor: str) -> str:
    """
    Normalize model string to a pricing key.

    Parameters
    ----------
    model : str
        Raw model name from settings or response.
    vendor : str
        Either 'openai' or 'gemini'.

    Returns
    -------
    str
        Standardized key used for pricing tables.
    """
    key = (model or "").strip().lower()
    if vendor == "openai":
        if key.startswith("gpt-5-high"):
            return "gpt-5-high"
        if key.startswith("gpt-5-medium"):
            return "gpt-5-medium"
        if key.startswith("gpt-5-low") or key.startswith("gpt-5-mini"):
            return "gpt-5-low"
        if key.startswith("gpt-5"):
            return "gpt-5"
        return "gpt-5"
    # gemini
    if key.startswith("gemini-2.5-flash"):
        return "gemini-2.5-flash"
    if key.startswith("gemini-2.5-pro"):
        return "gemini-2.5-pro"
    if key.startswith("gemini-2.5"):
        return "gemini-2.5"
    return "gemini-2.5"


def compute_price_usd(
    model: str, vendor: str, input_tokens: int, output_tokens: int, cached_input_tokens: int = 0
) -> float:
    """
    Compute price in USD based on model and token usage.

    Prices are per 1M tokens.

    Args:
        model: Model name
        vendor: Either 'openai' or 'gemini'
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        cached_input_tokens: Number of cached input tokens (OpenAI only)

    Returns:
        float: Price in USD rounded to 4 decimals
    """
    key = normalize_model_key(model, vendor)
    pricing = PRICING.get(key, DEFAULT_PRICING)

    # Calculate cost (pricing is per 1 million tokens)
    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]

    # Add cached input cost if applicable (OpenAI only)
    cached_input_cost = 0
    if cached_input_tokens > 0 and "cached_input" in pricing:
        cached_input_cost = (cached_input_tokens / 1_000_000) * pricing["cached_input"]

    total = input_cost + output_cost + cached_input_cost

    # Round to 4 decimals for display consistency
    return round(total, 4)


def extract_token_usage(response: Any, vendor: str) -> Tuple[int, int]:
    """
    Extract input and output token counts from API response.

    Args:
        response: API response object from OpenAI or Gemini
        vendor: Either 'openai' or 'gemini'

    Returns:
        Tuple[int, int]: (input_tokens, output_tokens)
    """
    input_tok = 0
    output_tok = 0

    try:
        usage = getattr(response, "usage", None)
        if usage is None:
            usage = getattr(response, "usage_metadata", None)

        if usage is not None:
            if vendor == "openai":
                input_tok = (
                    getattr(usage, "input_tokens", None)
                    or getattr(usage, "prompt_tokens", None)
                    or 0
                )

                # Base output tokens
                base_output = (
                    getattr(usage, "output_tokens", None)
                    or getattr(usage, "completion_tokens", None)
                    or 0
                )

                # Add reasoning tokens from output_tokens_details
                reasoning_tok = 0
                output_details = getattr(usage, "output_tokens_details", None)
                if output_details:
                    reasoning_tok = getattr(output_details, "reasoning_tokens", None) or 0

                output_tok = base_output + reasoning_tok

            elif vendor == "gemini":
                input_tok = getattr(usage, "prompt_token_count", None) or 0

                # Sum candidates + thoughts tokens
                candidates_tok = getattr(usage, "candidates_token_count", None) or 0
                thoughts_tok = getattr(usage, "thoughts_token_count", None) or 0

                output_tok = candidates_tok + thoughts_tok
    except Exception:
        pass

    return int(input_tok), int(output_tok)
