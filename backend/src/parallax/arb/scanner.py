"""Cross-venue package accounting.

A price difference between two venues is not an arbitrage. What is tradable is
a **package**: buy one contract of the YES leg on one venue and one contract of
the complementary NO leg on the other. If the two legs really are complements
(see `parallax.arb.pairs`), exactly one of them settles at $1.00, so a filled
package is worth exactly $1.00 no matter what happens.

The edge is therefore:

    profit_per_package = 1.00 - ask_yes - ask_no - fee_yes - fee_no

Two things this module refuses to do, because both manufacture fake profit:

1. **Compare best prices and call it size.** Edge is computed by walking both
   books level by level, so the reported package count is limited by the
   thinner side at every step, not by the top of book.
2. **Treat a package as locked.** Nothing here is executed. Two venues offer no
   atomic execution: one leg fills, the other moves, and the "hedge" becomes a
   naked position that has to be unwound at a loss. `ArbOpportunity` reports
   what was *quotable* at a moment in time; it is a measurement, not a fill.
   Leg risk, latency and adverse selection are not modeled, and any live
   attempt must treat the number here as an upper bound.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from parallax.arb.pairs import MarketPair
from parallax.arb.venue import Quote, Venue

PACKAGE_PAYOUT = Decimal("1.00")

DEFAULT_MAX_QUOTE_AGE_SECONDS = 30.0
"""Books older than this are refused. A cross-venue scan on stale quotes is the
classic way to report edge that was never executable."""


@dataclass(frozen=True)
class PackageLevel:
    """One depth step of a package: quantity available at a combined cost."""

    quantity: int
    yes_price: Decimal
    no_price: Decimal

    @property
    def gross_cost(self) -> Decimal:
        return (self.yes_price + self.no_price) * Decimal(self.quantity)


@dataclass(frozen=True)
class ArbOpportunity:
    """What a pair's two books made quotable at `observed_at`."""

    pair_name: str
    packages: int
    gross_cost: Decimal
    fees: Decimal
    net_profit: Decimal
    levels: tuple[PackageLevel, ...]
    yes_quote_age: float
    no_quote_age: float
    observed_at: datetime

    @property
    def profit_per_package(self) -> Decimal:
        if self.packages == 0:
            return Decimal("0")
        return self.net_profit / Decimal(self.packages)

    @property
    def is_profitable(self) -> bool:
        return self.net_profit > 0


class StaleQuoteError(RuntimeError):
    """Raised when a book is too old to be treated as executable."""


def _walk(yes: Quote, no: Quote) -> list[PackageLevel]:
    """Pair off ask liquidity from both books, cheapest packages first.

    Both ask ladders are consumed in parallel: each step takes the quantity the
    thinner side can support, so a deep book on one venue cannot inflate the
    package count when the other venue has nothing behind its top level.
    """
    levels: list[PackageLevel] = []
    yes_asks = list(yes.asks)
    no_asks = list(no.asks)
    yes_idx = no_idx = 0
    yes_left = yes_asks[0].quantity if yes_asks else 0
    no_left = no_asks[0].quantity if no_asks else 0

    while yes_idx < len(yes_asks) and no_idx < len(no_asks):
        take = min(yes_left, no_left)
        if take > 0:
            levels.append(
                PackageLevel(
                    quantity=take,
                    yes_price=yes_asks[yes_idx].price,
                    no_price=no_asks[no_idx].price,
                )
            )
        yes_left -= take
        no_left -= take
        if yes_left == 0:
            yes_idx += 1
            yes_left = yes_asks[yes_idx].quantity if yes_idx < len(yes_asks) else 0
        if no_left == 0:
            no_idx += 1
            no_left = no_asks[no_idx].quantity if no_idx < len(no_asks) else 0
    return levels


def evaluate(
    pair: MarketPair,
    yes_quote: Quote,
    no_quote: Quote,
    yes_venue: Venue,
    no_venue: Venue,
    *,
    now: datetime | None = None,
    max_quote_age_seconds: float = DEFAULT_MAX_QUOTE_AGE_SECONDS,
) -> ArbOpportunity:
    """Price the package ladder for `pair` against two observed books.

    Raises `UnreviewedPairError` if the pair's settlement terms were never
    confirmed equivalent, and `StaleQuoteError` if either book is too old.
    Only package steps that are profitable *after both venues' fees* are kept;
    depth beyond the point where the edge dies is not counted.
    """
    pair.require_reviewed()
    reference = now or datetime.now(timezone.utc)

    yes_age = yes_quote.age_seconds(reference)
    no_age = no_quote.age_seconds(reference)
    for age, label in ((yes_age, "yes"), (no_age, "no")):
        if age > max_quote_age_seconds:
            raise StaleQuoteError(
                f"{label} leg of {pair.name!r} is {age:.1f}s old "
                f"(limit {max_quote_age_seconds:.1f}s)"
            )

    kept: list[PackageLevel] = []
    gross = Decimal("0")
    fees = Decimal("0")

    for level in _walk(yes_quote, no_quote):
        leg_fees = yes_venue.fees.fee(level.yes_price, level.quantity) + no_venue.fees.fee(
            level.no_price, level.quantity
        )
        payout = PACKAGE_PAYOUT * Decimal(level.quantity)
        step_profit = payout - level.gross_cost - leg_fees
        if step_profit <= 0:
            # Deeper levels are strictly worse: asks only ascend.
            break
        kept.append(level)
        gross += level.gross_cost
        fees += leg_fees

    packages = sum(level.quantity for level in kept)
    net = PACKAGE_PAYOUT * Decimal(packages) - gross - fees
    return ArbOpportunity(
        pair_name=pair.name,
        packages=packages,
        gross_cost=gross,
        fees=fees,
        net_profit=net,
        levels=tuple(kept),
        yes_quote_age=yes_age,
        no_quote_age=no_age,
        observed_at=reference,
    )
