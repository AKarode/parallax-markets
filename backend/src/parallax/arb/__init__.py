"""Cross-venue arbitrage measurement.

Read-only by design: this package measures what two venues made quotable at a
moment in time. It does not place orders, and it does not model leg-fill risk,
latency or adverse selection — a reported opportunity is an upper bound on what
was available, not a fill.
"""

from parallax.arb.fees import KalshiFees, PolymarketFees
from parallax.arb.pairs import MarketPair, UnreviewedPairError, register
from parallax.arb.scanner import ArbOpportunity, StaleQuoteError, evaluate
from parallax.arb.venue import Level, OutcomeRef, Quote, Venue

__all__ = [
    "ArbOpportunity",
    "KalshiFees",
    "Level",
    "MarketPair",
    "OutcomeRef",
    "PolymarketFees",
    "Quote",
    "StaleQuoteError",
    "UnreviewedPairError",
    "Venue",
    "evaluate",
    "register",
]
