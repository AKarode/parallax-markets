"""Configuration-backed portfolio risk limits."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _normalize_theme_key(value: str) -> str:
    normalized = value.strip().lower()
    if not normalized:
        raise ValueError("Theme keys must be non-empty")
    return normalized


class RiskLimits(BaseModel):
    """Hard portfolio caps applied by the portfolio allocator."""

    model_config = ConfigDict(extra="ignore")

    max_notional: float = 250.0
    max_open_orders: int = 5
    max_open_positions: int = 10
    daily_loss_limit: float = 50.0
    default_order_size: int = 10
    min_order_size: int = 1
    bankroll: float = 250.0
    kelly_multiplier: float = 0.25
    theme_limits: dict[str, float] = Field(default_factory=dict)

    @field_validator("max_notional", "daily_loss_limit", "bankroll")
    @classmethod
    def validate_non_negative_float(cls, value: float) -> float:
        if value < 0.0:
            raise ValueError(f"Risk limits must be non-negative, got {value}")
        return value

    @field_validator("kelly_multiplier")
    @classmethod
    def validate_kelly_multiplier(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"kelly_multiplier must be between 0 and 1, got {value}")
        return value

    @field_validator("max_open_orders", "max_open_positions", "default_order_size", "min_order_size")
    @classmethod
    def validate_non_negative_int(cls, value: int) -> int:
        if value < 0:
            raise ValueError(f"Risk limits must be non-negative, got {value}")
        return value

    @field_validator("theme_limits")
    @classmethod
    def validate_theme_limits(cls, value: dict[str, float]) -> dict[str, float]:
        normalized: dict[str, float] = {}
        for theme, limit in value.items():
            if limit < 0.0:
                raise ValueError(f"Theme limit for {theme} must be non-negative, got {limit}")
            normalized[_normalize_theme_key(theme)] = limit
        return normalized

    @model_validator(mode="after")
    def validate_size_relationships(self) -> "RiskLimits":
        if self.default_order_size < self.min_order_size:
            raise ValueError("default_order_size must be >= min_order_size")
        return self

    def theme_limit_for(self, theme: str) -> float | None:
        normalized = _normalize_theme_key(theme)
        if normalized in self.theme_limits:
            return self.theme_limits[normalized]
        return self.theme_limits.get("default")

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "RiskLimits":
        data = dict(payload)
        if "risk" in data and isinstance(data["risk"], Mapping):
            data = dict(data["risk"])
        elif "portfolio_risk" in data and isinstance(data["portfolio_risk"], Mapping):
            data = dict(data["portfolio_risk"])
        return cls.model_validate(data)

    @classmethod
    def from_yaml(cls, path: str | Path) -> "RiskLimits":
        import yaml

        with Path(path).open("r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle) or {}
        if not isinstance(payload, Mapping):
            raise ValueError(f"Risk config at {path} must be a mapping")
        return cls.from_dict(payload)


DEFAULT_RISK_LIMITS = RiskLimits()


def load_risk_limits(
    path: str | Path | None = None,
    *,
    overrides: Mapping[str, Any] | None = None,
) -> RiskLimits:
    """Load risk limits from YAML, env-selected YAML, or defaults."""

    config_path = path or os.environ.get("PARALLAX_RISK_CONFIG")
    if config_path:
        limits = RiskLimits.from_yaml(config_path)
    else:
        limits = DEFAULT_RISK_LIMITS

    if not overrides:
        return limits

    merged = limits.model_dump()
    for key, value in overrides.items():
        if (
            isinstance(value, Mapping)
            and isinstance(merged.get(key), dict)
        ):
            merged[key] = {**merged[key], **value}
        else:
            merged[key] = value
    return RiskLimits.from_dict(merged)
