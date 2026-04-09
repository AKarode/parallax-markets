"""Schemas for portfolio allocation requests, state, and authorization results."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


def _normalize_side(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in {"yes", "no"}:
        raise ValueError(f"Side must be yes/no, got {value}")
    return normalized


def _normalize_theme(value: str | None) -> str:
    if value is None:
        return "general"
    normalized = value.strip().lower()
    return normalized or "general"


class ProposedTrade(BaseModel):
    """A candidate order presented to the portfolio allocator."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    ticker: str
    side: str
    price: float = Field(
        validation_alias=AliasChoices(
            "price",
            "entry_price",
            "intended_price",
            "executable_reference_price",
        ),
    )
    requested_size: int | None = Field(
        default=None,
        validation_alias=AliasChoices("requested_size", "quantity", "size"),
    )
    theme: str = "general"
    venue: str | None = None
    signal_id: str | None = None
    created_at: datetime | None = None

    @field_validator("side")
    @classmethod
    def validate_side(cls, value: str) -> str:
        return _normalize_side(value)

    @field_validator("price")
    @classmethod
    def validate_price(cls, value: float) -> float:
        if not 0.0 < value <= 1.0:
            raise ValueError(f"Price must be between 0 and 1, got {value}")
        return value

    @field_validator("requested_size")
    @classmethod
    def validate_requested_size(cls, value: int | None) -> int | None:
        if value is not None and value <= 0:
            raise ValueError(f"Requested size must be positive, got {value}")
        return value

    @field_validator("theme")
    @classmethod
    def validate_theme(cls, value: str) -> str:
        return _normalize_theme(value)

    def normalized_size(self, default_size: int) -> int:
        return self.requested_size or default_size

    def max_loss_per_contract(self) -> float:
        return self.price


class CurrentPosition(BaseModel):
    """A normalized open position snapshot used for allocator risk checks."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    ticker: str
    side: str
    quantity: int
    open_quantity: int | None = None
    entry_price: float = Field(
        validation_alias=AliasChoices("entry_price", "avg_price", "price"),
    )
    theme: str = "general"
    status: str = "open"
    venue: str | None = None
    opened_at: datetime | None = None
    unrealized_pnl: float | None = None

    @field_validator("side")
    @classmethod
    def validate_side(cls, value: str) -> str:
        return _normalize_side(value)

    @field_validator("quantity", "open_quantity")
    @classmethod
    def validate_quantity(cls, value: int | None) -> int | None:
        if value is not None and value < 0:
            raise ValueError(f"Quantity cannot be negative, got {value}")
        return value

    @field_validator("entry_price")
    @classmethod
    def validate_entry_price(cls, value: float) -> float:
        if not 0.0 < value <= 1.0:
            raise ValueError(f"Entry price must be between 0 and 1, got {value}")
        return value

    @field_validator("theme")
    @classmethod
    def validate_theme(cls, value: str) -> str:
        return _normalize_theme(value)

    def active_quantity(self) -> int:
        return self.open_quantity if self.open_quantity is not None else self.quantity

    def is_open(self) -> bool:
        return self.status.lower() == "open" and self.active_quantity() > 0

    def notional(self) -> float:
        return self.active_quantity() * self.entry_price


class OpenOrder(BaseModel):
    """A normalized active order snapshot used for allocator risk checks."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    order_id: str | None = None
    ticker: str
    side: str
    quantity: int
    price: float = Field(
        validation_alias=AliasChoices(
            "price",
            "intended_price",
            "executable_reference_price",
            "avg_fill_price",
        ),
    )
    theme: str = "general"
    status: str = "accepted"
    submitted_at: datetime | None = None

    @field_validator("side")
    @classmethod
    def validate_side(cls, value: str) -> str:
        return _normalize_side(value)

    @field_validator("quantity")
    @classmethod
    def validate_quantity(cls, value: int) -> int:
        if value < 0:
            raise ValueError(f"Quantity cannot be negative, got {value}")
        return value

    @field_validator("price")
    @classmethod
    def validate_price(cls, value: float) -> float:
        if not 0.0 < value <= 1.0:
            raise ValueError(f"Price must be between 0 and 1, got {value}")
        return value

    @field_validator("theme")
    @classmethod
    def validate_theme(cls, value: str) -> str:
        return _normalize_theme(value)

    def is_active(self) -> bool:
        return self.status.lower() in {
            "attempted",
            "accepted",
            "open",
            "pending",
            "resting",
            "partially_filled",
        }

    def notional(self) -> float:
        return self.quantity * self.price


class PortfolioState(BaseModel):
    """Portfolio snapshot required for allocator limit enforcement."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    positions: list[CurrentPosition] = Field(
        default_factory=list,
        validation_alias=AliasChoices("positions", "current_positions"),
    )
    open_orders: list[OpenOrder] = Field(
        default_factory=list,
        validation_alias=AliasChoices("open_orders", "orders", "resting_orders"),
    )
    daily_realized_pnl: float = 0.0
    daily_unrealized_pnl: float = 0.0
    as_of: datetime | None = None

    def active_positions(self) -> list[CurrentPosition]:
        return [position for position in self.positions if position.is_open()]

    def active_orders(self) -> list[OpenOrder]:
        return [order for order in self.open_orders if order.is_active()]

    def open_position_count(self) -> int:
        return len(self.active_positions())

    def open_order_count(self) -> int:
        return len(self.active_orders())

    def gross_notional(self) -> float:
        position_notional = sum(position.notional() for position in self.active_positions())
        order_notional = sum(order.notional() for order in self.active_orders())
        return position_notional + order_notional

    def theme_notional(self, theme: str) -> float:
        normalized = _normalize_theme(theme)
        position_notional = sum(
            position.notional()
            for position in self.active_positions()
            if position.theme == normalized
        )
        order_notional = sum(
            order.notional()
            for order in self.active_orders()
            if order.theme == normalized
        )
        return position_notional + order_notional

    def has_open_position(self, ticker: str, side: str) -> bool:
        normalized_side = _normalize_side(side)
        return any(
            position.ticker == ticker and position.side == normalized_side
            for position in self.active_positions()
        )


class TradeAuthorization(BaseModel):
    """Allocator response returned to the execution layer."""

    authorized: bool
    allowed_size: int
    block_reason: str = ""


def dump_model(value: Any) -> Any:
    """Return a serializable payload for Pydantic models or plain values."""

    if hasattr(value, "model_dump"):
        return value.model_dump()
    return value
