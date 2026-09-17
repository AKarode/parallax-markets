"""Per-venue fee models.

Fees are the difference between a real cross-venue arbitrage and a mirage, so
they are modeled exactly rather than approximated:

- Exact cent arithmetic via ``Decimal``. Kalshi rounds fees *up to the next
  cent per order*, which float arithmetic cannot represent faithfully and
  which dominates the economics of small orders.
- Every schedule carries ``as_of`` and ``source`` so a stale fee assumption is
  visible in the data rather than silently wrong.
- Fee rates are resolved *per market*, not per venue. Polymarket's 4% taker fee
  applies to selected categories only; assuming it everywhere overstates costs
  on some markets and understates them on others.

References:
- Kalshi fee schedule (July 2026): https://kalshi.com/docs/kalshi-fee-schedule.pdf
- Polymarket trading fees: https://docs.polymarket.com/trading/fees
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_CEILING, Decimal
from typing import Literal, Protocol

Role = Literal["taker", "maker"]

CENT = Decimal("0.01")


def _ceil_cent(amount: Decimal) -> Decimal:
    """Round a dollar amount up to the next whole cent."""
    return amount.quantize(CENT, rounding=ROUND_CEILING)


class FeeModel(Protocol):
    """Computes the fee on one leg of a trade, in dollars."""

    venue: str
    as_of: date
    source: str

    def fee(self, price: Decimal, quantity: int, role: Role = "taker") -> Decimal:
        """Total fee in dollars for `quantity` contracts executed at `price`."""
        ...


@dataclass(frozen=True)
class KalshiFees:
    """Kalshi's published trading fee.

        fee = ceil_to_cent(0.07 * C * P * (1 - P))

    where C is the contract count and P the price in dollars. The maker fee is
    25% of the taker *rate* — but it is rounded up to the cent independently,
    which is not the same as taking 25% of an already-rounded taker fee.

    The July 2026 revision keeps the 0.07 coefficient and adds a per-contract
    multiplier that defaults to 1 for a standard market.

    The ceiling is the important part for an arbitrageur: a 1-contract order
    pays a full cent of fee no matter how far from 50c it trades, so small
    packages are structurally unprofitable.
    """

    venue: str = "kalshi"
    taker_coefficient: Decimal = Decimal("0.07")
    maker_multiplier: Decimal = Decimal("0.25")
    market_multiplier: Decimal = Decimal("1")
    as_of: date = date(2026, 7, 7)
    source: str = "https://kalshi.com/docs/kalshi-fee-schedule.pdf"

    def fee(self, price: Decimal, quantity: int, role: Role = "taker") -> Decimal:
        if quantity <= 0:
            return Decimal("0.00")
        coefficient = self.taker_coefficient
        if role == "maker":
            coefficient = coefficient * self.maker_multiplier
        raw = coefficient * self.market_multiplier * Decimal(quantity) * price * (Decimal("1") - price)
        return _ceil_cent(raw)


@dataclass(frozen=True)
class PolymarketFees:
    """Polymarket's taker fee, which is category-specific.

        fee_per_share = rate * P * (1 - P)

    Makers pay zero. The rate is NOT a venue constant: it was verified at 0.04
    for politics markets on 2026-06-04 against the live ``feeSchedule``
    ``{rate: 0.04, takerOnly: true}``, while other categories differ and some
    carry no fee at all.

    Construct this per market with the rate you actually read from the venue.
    The default rate is zero so that an unconfigured market cannot silently
    inherit somebody else's fee.
    """

    rate: Decimal = Decimal("0")
    venue: str = "polymarket"
    as_of: date = date(2026, 6, 4)
    source: str = "https://docs.polymarket.com/trading/fees"

    def fee(self, price: Decimal, quantity: int, role: Role = "taker") -> Decimal:
        if quantity <= 0 or role == "maker":
            return Decimal("0.00")
        return self.rate * Decimal(quantity) * price * (Decimal("1") - price)


POLITICS_TAKER_RATE = Decimal("0.04")
"""Verified 2026-06-04 against the live politics feeSchedule. Do not reuse for
other categories without re-reading the venue's schedule."""
