"""The `Venue` interface the scanner reads through.

`parallax.markets` already normalizes Kalshi into an `Orderbook`, but the
Polymarket client returns raw CLOB dicts and carries crisis-specific helpers.
Rather than rewrite either client, this module wraps both behind one read-only
interface with explicit semantics:

- **Outcome identity.** A venue is asked for the book of a *specific outcome*
  (`OutcomeRef`), never for "the market". Cross-venue polarity mistakes are the
  easiest way to book a loss as an arb.
- **Executable depth, sorted.** `bids` descend, `asks` ascend, so the scanner
  can walk depth without re-sorting and without trusting venue ordering.
- **Timestamps required.** Every quote carries the time it was observed. A
  snapshot with no age cannot be checked for staleness, and a stale book is how
  a cross-venue scan reports edge that was never executable.
- **Missing data is None, never an empty book.** An empty `Quote` and a failed
  fetch mean very different things and must not be conflated.

This interface is deliberately read-only. Order placement stays in the venue
clients; `parallax.arb` exists to measure opportunity, not to trade it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal, Protocol

from parallax.arb.fees import FeeModel

Side = Literal["yes", "no"]


@dataclass(frozen=True)
class OutcomeRef:
    """Points at one binary outcome on one venue.

    `market_id` is whatever that venue uses to address the outcome: a Kalshi
    ticker, or a Polymarket CLOB token id (which already encodes the side, so
    `side` is carried alongside for explicitness and validation).
    """

    venue: str
    market_id: str
    side: Side


@dataclass(frozen=True)
class Level:
    """One executable price level. `price` is in dollars, 0..1."""

    price: Decimal
    quantity: int


@dataclass(frozen=True)
class Quote:
    """A point-in-time view of one outcome's executable book."""

    outcome: OutcomeRef
    bids: tuple[Level, ...]
    asks: tuple[Level, ...]
    observed_at: datetime

    @property
    def best_ask(self) -> Level | None:
        return self.asks[0] if self.asks else None

    @property
    def best_bid(self) -> Level | None:
        return self.bids[0] if self.bids else None

    def age_seconds(self, now: datetime | None = None) -> float:
        reference = now or datetime.now(timezone.utc)
        return (reference - self.observed_at).total_seconds()


class Venue(Protocol):
    """Read-only access to one trading venue."""

    name: str
    fees: FeeModel

    async def quote(self, outcome: OutcomeRef) -> Quote | None:
        """Return the executable book for `outcome`, or None if unavailable.

        Implementations must sort bids descending and asks ascending, stamp
        `observed_at` at the moment of observation, and return None rather than
        an empty `Quote` when the fetch fails.
        """
        ...
