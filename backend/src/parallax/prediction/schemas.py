"""Prediction output schemas for the 3 focused models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, field_validator


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
