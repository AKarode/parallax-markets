"""Ensemble prediction utility -- multi-call LLM with aggregation."""

from __future__ import annotations

import asyncio
import json
import logging
import statistics
from typing import Any

logger = logging.getLogger(__name__)

ENSEMBLE_TEMPERATURES = [0.3, 0.5, 0.7]
INSTABILITY_THRESHOLD = 0.10  # 10 percentage points


def parse_llm_json(raw_text: str) -> dict:
    """Parse JSON from LLM response, stripping markdown code fences if present.

    Extracts the duplicated parse logic from oil_price.py, ceasefire.py,
    and hormuz.py into a single reusable function.

    Raises:
        ValueError: If the text cannot be parsed as JSON.
    """
    text = raw_text.strip()
    if text.startswith("```json") or text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:]).strip()
    if text.endswith("```"):
        text = text[:-3].rstrip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Failed to parse LLM response as JSON: {raw_text[:200]}"
        ) from exc


def trimmed_mean(values: list[float]) -> float:
    """Compute trimmed mean of values.

    With n=3 this equals the median (drops min and max, returns middle value).
    With n<=2 returns the arithmetic mean.
    """
    if len(values) <= 2:
        return statistics.mean(values)
    sorted_vals = sorted(values)
    trimmed = sorted_vals[1:-1]
    return statistics.mean(trimmed)


def compute_ensemble(probabilities: list[float]) -> dict:
    """Aggregate ensemble probabilities into a single result.

    Returns:
        Dict with keys: probability, std_dev, is_unstable, individual_probabilities.
    """
    if len(probabilities) < 2:
        return {
            "probability": probabilities[0] if probabilities else 0.5,
            "std_dev": 0.0,
            "is_unstable": False,
            "individual_probabilities": list(probabilities),
        }
    std_dev = statistics.stdev(probabilities)
    return {
        "probability": trimmed_mean(probabilities),
        "std_dev": std_dev,
        "is_unstable": std_dev > INSTABILITY_THRESHOLD,
        "individual_probabilities": list(probabilities),
    }


async def ensemble_predict(
    client: Any,
    model: str,
    prompt: str,
    budget: Any,
    max_tokens: int = 2000,
) -> dict:
    """Make 3 concurrent Claude calls at different temperatures and aggregate.

    Args:
        client: AsyncAnthropic client instance.
        model: Model name (e.g. "claude-sonnet-4-20250514").
        prompt: The user prompt to send to each call.
        budget: BudgetTracker instance for recording token usage.
        max_tokens: Max tokens per call.

    Returns:
        Dict with keys: ensemble, parsed, all_parsed, call_count.

    Raises:
        ValueError: If all 3 calls fail to parse.
    """
    async def _single_call(temperature: float):
        return await client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}],
        )

    # Make 3 concurrent calls
    responses = await asyncio.gather(
        *[_single_call(temp) for temp in ENSEMBLE_TEMPERATURES],
        return_exceptions=True,
    )

    all_parsed: list[dict] = []
    probabilities: list[float] = []

    for i, resp in enumerate(responses):
        if isinstance(resp, Exception):
            logger.warning(
                "Ensemble call %d failed with exception: %s", i, resp
            )
            continue

        # Record budget for each individual call
        budget.record(resp.usage.input_tokens, resp.usage.output_tokens, "sonnet")

        try:
            parsed = parse_llm_json(resp.content[0].text)
            all_parsed.append(parsed)
            probabilities.append(parsed["probability"])
        except (ValueError, KeyError, IndexError) as exc:
            logger.warning(
                "Ensemble call %d failed to parse: %s", i, exc
            )

    if not all_parsed:
        raise ValueError("All ensemble calls failed to parse")

    ensemble_result = compute_ensemble(probabilities)

    # Pick the response closest to ensemble probability for reasoning/evidence
    ensemble_prob = ensemble_result["probability"]
    median_parsed = min(
        all_parsed,
        key=lambda p: abs(p.get("probability", 0) - ensemble_prob),
    )

    return {
        "ensemble": ensemble_result,
        "parsed": median_parsed,
        "all_parsed": all_parsed,
        "call_count": len(all_parsed),
    }
