"""Shared Pydantic models for prediction market data."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, field_validator


class MarketPrice(BaseModel):
    """A snapshot of a prediction market contract price."""

    ticker: str
    source: str  # "kalshi" or "polymarket"
    yes_price: float  # 0.0-1.0 (probability)
    no_price: float
    volume: float
    fetched_at: datetime

    @field_validator("yes_price", "no_price")
    @classmethod
    def clamp_probability(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"Price must be between 0 and 1, got {v}")
        return v


class OrderbookLevel(BaseModel):
    """A single level in an orderbook."""

    price: int  # cents (1-99)
    quantity: int


class Orderbook(BaseModel):
    """Full orderbook for a market."""

    ticker: str
    yes_bids: list[OrderbookLevel]
    yes_asks: list[OrderbookLevel]
    no_bids: list[OrderbookLevel]
    no_asks: list[OrderbookLevel]


class Position(BaseModel):
    """A position in a prediction market contract."""

    ticker: str
    side: str  # "yes" or "no"
    quantity: int
    avg_price: float
    market_price: float
    unrealized_pnl: float


class PaperTrade(BaseModel):
    """A paper trade placed via the sandbox."""

    ticker: str
    side: str  # "yes" or "no"
    quantity: int
    price: int  # limit price in cents
    created_at: datetime
    order_id: str | None = None
    status: str = "pending"  # pending, filled, cancelled
