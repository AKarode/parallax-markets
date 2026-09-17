"""`Venue` implementations over the existing `parallax.markets` clients.

Neither client is modified. The Kalshi client already returns a normalized
`Orderbook`, so its adapter mostly re-expresses it; the Polymarket client
returns raw CLOB dicts, so its adapter does the normalization the client never
did. Both convert prices through `str` into `Decimal` — going via float first
would reintroduce exactly the representation error the fee models avoid.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from parallax.arb.fees import FeeModel, KalshiFees, PolymarketFees
from parallax.arb.venue import Level, OutcomeRef, Quote


def _to_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (ArithmeticError, ValueError):
        return None


def _levels(raw: list[Any], *, descending: bool) -> tuple[Level, ...]:
    """Normalize and sort one side of a book, dropping unusable entries."""
    out: list[Level] = []
    for entry in raw:
        if isinstance(entry, dict):
            price = _to_decimal(entry.get("price"))
            quantity = _to_decimal(entry.get("size", entry.get("quantity")))
        else:
            price = _to_decimal(getattr(entry, "price", None))
            quantity = _to_decimal(getattr(entry, "quantity", None))
        if price is None or quantity is None:
            continue
        if not (Decimal("0") <= price <= Decimal("1")) or quantity <= 0:
            continue
        out.append(Level(price=price, quantity=int(quantity)))
    out.sort(key=lambda level: level.price, reverse=descending)
    return tuple(out)


@dataclass
class KalshiVenue:
    """Reads Kalshi through the existing `KalshiClient`."""

    client: Any
    fees: FeeModel = KalshiFees()
    name: str = "kalshi"

    async def quote(self, outcome: OutcomeRef) -> Quote | None:
        orderbook = await self.client.get_orderbook(outcome.market_id)
        if orderbook is None:
            return None
        if outcome.side == "yes":
            bids, asks = orderbook.yes_bids, orderbook.yes_asks
        else:
            bids, asks = orderbook.no_bids, orderbook.no_asks
        observed = orderbook.quote_timestamp or orderbook.venue_timestamp or datetime.now(timezone.utc)
        if observed.tzinfo is None:
            observed = observed.replace(tzinfo=timezone.utc)
        return Quote(
            outcome=outcome,
            bids=_levels(list(bids), descending=True),
            asks=_levels(list(asks), descending=False),
            observed_at=observed,
        )


@dataclass
class PolymarketVenue:
    """Reads Polymarket through the existing `PolymarketClient`.

    The client's `get_book` returns the raw CLOB payload, so the normalization
    happens here. `market_id` is a CLOB token id, which already encodes the
    side — `OutcomeRef.side` records which side that token *is*, so a pair
    registry mistake is visible rather than silent.
    """

    client: Any
    fees: FeeModel = PolymarketFees()
    name: str = "polymarket"

    async def quote(self, outcome: OutcomeRef) -> Quote | None:
        raw = await self.client.get_book(outcome.market_id)
        if not raw:
            return None
        return Quote(
            outcome=outcome,
            bids=_levels(raw.get("bids", []), descending=True),
            asks=_levels(raw.get("asks", []), descending=False),
            observed_at=datetime.now(timezone.utc),
        )
