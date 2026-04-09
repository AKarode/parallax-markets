"""Pydantic models for contract mapping, fair-value estimation, and gating."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class ProxyClass(str, Enum):
    """How closely a market contract maps to a prediction model's output.

    DIRECT: Contract resolves on exactly what the model predicts.
    NEAR_PROXY: Contract is closely related (e.g., ceasefire -> US-Iran agreement).
    LOOSE_PROXY: Contract is loosely related (e.g., oil price -> Hormuz closure).
    NONE: No meaningful relationship.
    """

    DIRECT = "direct"
    NEAR_PROXY = "near_proxy"
    LOOSE_PROXY = "loose_proxy"
    NONE = "none"


class ContractFamily(str, Enum):
    """Supported contract-native pricing families."""

    GENERIC_BINARY = "generic_binary"
    IRAN_AGREEMENT = "iran_agreement"
    HORMUZ_CLOSURE = "hormuz_closure"
    OIL_PRICE_MAX = "oil_price_max"
    OIL_PRICE_MIN = "oil_price_min"


DEFAULT_DISCOUNT_MAP: dict[str, float] = {
    "direct": 1.0,
    "near_proxy": 0.6,
    "loose_proxy": 0.3,
    "none": 0.0,
}


class MappingCostInputs(BaseModel):
    """Expected crossing costs expressed as probability points."""

    expected_fee_rate: float = 0.01
    expected_slippage_rate: float = 0.01
    use_half_spread_as_slippage_floor: bool = True

    @field_validator("expected_fee_rate", "expected_slippage_rate")
    @classmethod
    def clamp_rate(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"Rate must be between 0 and 1, got {value}")
        return value

    def slippage_for_spread(self, observed_spread: float | None) -> float:
        """Use configured slippage, optionally floored by half the live spread."""
        if not self.use_half_spread_as_slippage_floor or observed_spread is None:
            return self.expected_slippage_rate
        return max(self.expected_slippage_rate, observed_spread / 2.0)

    def total_cost_for_spread(self, observed_spread: float | None) -> float:
        """Total expected cost to cross the book."""
        return self.expected_fee_rate + self.slippage_for_spread(observed_spread)


class MarketStalenessPolicy(BaseModel):
    """Quote freshness rules for executable mapping decisions."""

    max_quote_age_seconds: float = 300.0
    allow_fetched_at_fallback: bool = True

    @field_validator("max_quote_age_seconds")
    @classmethod
    def validate_age(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("max_quote_age_seconds must be positive")
        return value


class FairValueEstimate(BaseModel):
    """Contract-native YES/NO fair values produced by an explicit estimator."""

    estimator_name: str
    contract_family: ContractFamily
    fair_value_yes: float = Field(ge=0.0, le=1.0)
    fair_value_no: float = Field(ge=0.0, le=1.0)
    inputs: dict[str, Any] | None = None


class ContractRecord(BaseModel):
    """A tradeable prediction market contract with proxy classification."""

    ticker: str
    source: str  # "kalshi" or "polymarket"
    event_ticker: str
    title: str
    resolution_criteria: str
    resolution_date: datetime | None = None
    proxy_map: dict[str, ProxyClass]  # model_type -> proxy class
    discount_map: dict[str, float] = DEFAULT_DISCOUNT_MAP
    is_active: bool = True
    last_checked: datetime | None = None
    metadata: dict[str, Any] | None = None  # threshold values etc.
    invert_probability: dict[str, bool] | None = None  # model_type -> should invert


class MappingResult(BaseModel):
    """Result of mapping a prediction to a contract via proxy classification."""

    prediction_model_id: str
    contract_ticker: str
    proxy_class: ProxyClass
    contract_family: ContractFamily | None = None
    estimator_name: str | None = None
    fair_value_yes: float | None = None
    fair_value_no: float | None = None
    quote_timestamp: datetime | None = None
    quote_age_seconds: float | None = None
    staleness_threshold_seconds: float | None = None
    quote_is_stale: bool = False
    buy_yes_edge: float | None = None
    buy_no_edge: float | None = None
    gross_edge: float | None = None
    raw_edge: float | None = None
    confidence_discount: float
    expected_fee_rate: float | None = None
    expected_slippage_rate: float | None = None
    expected_total_cost: float | None = None
    net_edge: float | None = None
    effective_edge: float | None = None
    entry_side: str | None = None
    entry_price: float | None = None
    entry_price_kind: str | None = None
    entry_price_is_executable: bool = False
    tradeability_status: str = "unknown"
    should_trade: bool
    reason: str
