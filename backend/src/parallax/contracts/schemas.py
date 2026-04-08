"""Pydantic models for the contract registry and proxy classification system."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel


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


DEFAULT_DISCOUNT_MAP: dict[str, float] = {
    "direct": 1.0,
    "near_proxy": 0.6,
    "loose_proxy": 0.3,
    "none": 0.0,
}


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
    raw_edge: float
    confidence_discount: float
    effective_edge: float  # raw_edge * confidence_discount
    should_trade: bool
    reason: str
