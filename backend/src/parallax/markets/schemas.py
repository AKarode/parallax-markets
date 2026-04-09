"""Shared Pydantic models for prediction market data.

The important distinction in this sprint is between:
- executable quotes: prices you can actually cross right now
- derived prices: midpoint/last/snapshot-like values for analysis only
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class OrderbookLevel(BaseModel):
    """A single orderbook level expressed as a probability-like price."""

    price: float  # 0.0-1.0 contract cost
    quantity: float

    @field_validator("price")
    @classmethod
    def clamp_price(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"Price must be between 0 and 1, got {value}")
        return value


class DepthSummary(BaseModel):
    """A compact visible-depth summary for one side of the book."""

    levels: int = 0
    visible_quantity: float = 0.0
    top_level_quantity: float | None = None


class Orderbook(BaseModel):
    """Normalized orderbook snapshot for a binary contract."""

    ticker: str
    venue_timestamp: datetime | None = None
    quote_timestamp: datetime | None = None
    yes_bids: list[OrderbookLevel] = Field(default_factory=list)
    yes_asks: list[OrderbookLevel] = Field(default_factory=list)
    no_bids: list[OrderbookLevel] = Field(default_factory=list)
    no_asks: list[OrderbookLevel] = Field(default_factory=list)


class MarketPrice(BaseModel):
    """Normalized market snapshot with explicit execution semantics.

    `yes_price` / `no_price` remain available as legacy display fields, but
    they are never used as execution inputs. Their meaning is defined by
    `derived_price_kind`.
    """

    ticker: str
    source: str  # "kalshi" or "polymarket"
    volume: float | None = None
    fetched_at: datetime
    venue_timestamp: datetime | None = None
    quote_timestamp: datetime | None = None
    best_yes_bid: float | None = None
    best_yes_ask: float | None = None
    best_no_bid: float | None = None
    best_no_ask: float | None = None
    yes_bid_ask_spread: float | None = None
    no_bid_ask_spread: float | None = None
    yes_bid_depth: DepthSummary | None = None
    yes_ask_depth: DepthSummary | None = None
    no_bid_depth: DepthSummary | None = None
    no_ask_depth: DepthSummary | None = None
    yes_price: float | None = None
    no_price: float | None = None
    derived_price_kind: str | None = None
    data_environment: str = "live"

    @field_validator(
        "best_yes_bid",
        "best_yes_ask",
        "best_no_bid",
        "best_no_ask",
        "yes_price",
        "no_price",
    )
    @classmethod
    def clamp_probability(cls, value: float | None) -> float | None:
        if value is None:
            return value
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"Price must be between 0 and 1, got {value}")
        return value

    @field_validator("yes_bid_ask_spread", "no_bid_ask_spread")
    @classmethod
    def clamp_spread(cls, value: float | None) -> float | None:
        if value is None:
            return value
        if value < 0.0:
            raise ValueError(f"Spread cannot be negative, got {value}")
        return value

    def executable_price(self, side: str) -> float | None:
        """Return the current cost to buy YES or NO."""
        normalized = side.lower()
        if normalized == "yes":
            return self.best_yes_ask
        if normalized == "no":
            return self.best_no_ask
        raise ValueError(f"Unknown side: {side}")

    def reference_price(self) -> float | None:
        """Return the derived display/reference YES price, if any."""
        return self.yes_price


class Position(BaseModel):
    """A venue position snapshot."""

    ticker: str
    side: str  # "yes" or "no"
    quantity: float
    avg_price: float
    market_price: float | None = None
    unrealized_pnl: float | None = None


class PaperTrade(BaseModel):
    """Legacy compatibility model for older sandbox code paths."""

    ticker: str
    side: str
    quantity: int
    price: int
    created_at: datetime
    order_id: str | None = None
    status: str = "pending"
