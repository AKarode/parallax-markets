"""Prediction output schemas for the 3 focused models."""

from __future__ import annotations

import logging
import re
from datetime import datetime

from pydantic import BaseModel, field_validator, model_validator

logger = logging.getLogger(__name__)

_CONTROL_CHAR_RE = re.compile(r"[\x00-\x1f\x7f]")


def _sanitize_headline(text: str) -> str:
    """Sanitize a headline before interpolating into LLM prompts.

    Makes prompt injection harder (not impossible) by stripping control chars,
    capping length, neutralizing triple-quotes, and escaping prompt-template
    delimiters. Input is news APIs, not adversarial user input.
    """
    if not text:
        return ""
    cleaned = text.replace("\n", " ").replace("\r", " ")
    cleaned = _CONTROL_CHAR_RE.sub(" ", cleaned)
    cleaned = cleaned.replace('"""', '"_"')
    cleaned = cleaned.replace("`", "'").replace("{", "(").replace("}", ")")
    return cleaned[:300]


class PredictionOutput(BaseModel):
    """Structured prediction from a model, comparable to market prices."""

    model_id: str  # "oil_price", "ceasefire", "hormuz_reopening"
    prediction_type: str  # maps to market category
    probability: float  # 0.0-1.0, comparable to market price
    direction: str  # "increase", "decrease", "stable" (for oil)
    magnitude_range: list[float]  # [low, high]
    unit: str
    timeframe: str  # "7d", "14d", "30d"
    confidence: float  # model's self-assessed confidence
    reasoning: str  # chain-of-thought explanation
    evidence: list[str]  # key GDELT events or data points used
    created_at: datetime
    kalshi_ticker: str | None = None  # mapped market ticker
    polymarket_id: str | None = None  # mapped market ID
    ensemble_probabilities: list[float] | None = None
    ensemble_std_dev: float | None = None
    ensemble_is_unstable: bool = False
    is_fallback: bool = False
    fallback_source_run_id: str | None = None
    context_age_hours: float | None = None
    penalty_factor: float = 1.0
    staleness_penalty_applied: bool = False

    @field_validator("probability", "confidence")
    @classmethod
    def clamp_probability(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"Must be between 0 and 1, got {v}")
        return v

    @field_validator("direction")
    @classmethod
    def valid_direction(cls, v: str) -> str:
        if v not in ("increase", "decrease", "stable"):
            raise ValueError(f"Direction must be increase/decrease/stable, got {v}")
        return v

    @model_validator(mode="after")
    def check_probability_confidence_consistency(self) -> PredictionOutput:
        """Clamp confidence when it contradicts the probability estimate.

        Very high confidence (>0.9) paired with a near-50/50 probability is
        logically inconsistent: the model claims certainty about an explicit
        coin-flip. We log a warning and clamp confidence rather than fail
        validation so predictions still flow through the pipeline.
        """
        if self.confidence > 0.9 and abs(self.probability - 0.5) < 0.1:
            logger.warning(
                "Inconsistent prediction for %s: confidence=%.3f but probability=%.3f "
                "(near 50/50). Clamping confidence to 0.7.",
                self.model_id,
                self.confidence,
                self.probability,
            )
            self.confidence = 0.7
        return self
