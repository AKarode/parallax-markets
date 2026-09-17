"""Scanner tests, weighted toward the ways a fake edge gets through.

Each test here corresponds to a specific way a cross-venue scan can report
profit that was never available: unreviewed settlement terms, stale books,
top-of-book size that the other venue cannot match, and depth that is only
profitable before fees.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from parallax.arb.fees import POLITICS_TAKER_RATE, KalshiFees, PolymarketFees
from parallax.arb.pairs import MarketPair, UnreviewedPairError
from parallax.arb.scanner import StaleQuoteError, evaluate
from parallax.arb.venue import Level, OutcomeRef, Quote

NOW = datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc)

YES_REF = OutcomeRef(venue="kalshi", market_id="KXTEST-26", side="yes")
NO_REF = OutcomeRef(venue="polymarket", market_id="0xtoken", side="no")


class _Venue:
    def __init__(self, name, fees):
        self.name = name
        self.fees = fees

    async def quote(self, outcome):  # pragma: no cover - not exercised here
        raise NotImplementedError


KALSHI = _Venue("kalshi", KalshiFees())
POLY = _Venue("polymarket", PolymarketFees(rate=POLITICS_TAKER_RATE))
FREE = _Venue("free", PolymarketFees())


def _pair(**overrides) -> MarketPair:
    base = dict(
        name="test-pair",
        yes_leg=YES_REF,
        no_leg=NO_REF,
        deadline=datetime(2026, 12, 31, 23, 59, tzinfo=timezone.utc),
        resolution_source="Test Source",
        void_rules="both venues void together",
        reviewed=True,
        reviewed_by="tester",
    )
    base.update(overrides)
    return MarketPair(**base)


def _quote(ref, asks, observed_at=NOW) -> Quote:
    return Quote(
        outcome=ref,
        bids=(),
        asks=tuple(Level(price=Decimal(p), quantity=q) for p, q in asks),
        observed_at=observed_at,
    )


class TestSettlementGate:
    def test_unreviewed_pair_is_refused(self):
        pair = _pair(reviewed=False, reviewed_by=None)
        with pytest.raises(UnreviewedPairError):
            evaluate(
                pair,
                _quote(YES_REF, [("0.40", 100)]),
                _quote(NO_REF, [("0.40", 100)]),
                KALSHI,
                FREE,
                now=NOW,
            )


class TestStaleness:
    def test_stale_book_is_refused(self):
        stale = NOW - timedelta(seconds=120)
        with pytest.raises(StaleQuoteError):
            evaluate(
                _pair(),
                _quote(YES_REF, [("0.40", 100)], observed_at=stale),
                _quote(NO_REF, [("0.40", 100)]),
                KALSHI,
                FREE,
                now=NOW,
            )


class TestPackageAccounting:
    def test_obvious_edge_is_found(self):
        """0.40 + 0.40 = 0.80 for a $1.00 package, on a fee-free venue pair."""
        opp = evaluate(
            _pair(),
            _quote(YES_REF, [("0.40", 10)]),
            _quote(NO_REF, [("0.40", 10)]),
            FREE,
            FREE,
            now=NOW,
        )
        assert opp.packages == 10
        assert opp.net_profit == Decimal("2.00")
        assert opp.profit_per_package == Decimal("0.20")

    def test_size_is_limited_by_the_thinner_venue(self):
        """A deep book on one side cannot inflate the package count."""
        opp = evaluate(
            _pair(),
            _quote(YES_REF, [("0.40", 1000)]),
            _quote(NO_REF, [("0.40", 5)]),
            FREE,
            FREE,
            now=NOW,
        )
        assert opp.packages == 5

    def test_coherent_book_yields_nothing(self):
        """Legs summing to 1.00 leave no room; this is the modal real outcome."""
        opp = evaluate(
            _pair(),
            _quote(YES_REF, [("0.55", 100)]),
            _quote(NO_REF, [("0.45", 100)]),
            FREE,
            FREE,
            now=NOW,
        )
        assert opp.packages == 0
        assert opp.net_profit == Decimal("0")
        assert not opp.is_profitable

    def test_fees_erase_a_gross_edge(self):
        """0.495 + 0.495 = 0.99 looks like a cent of edge per package.

        Kalshi's fee on a 49.5c contract rounds up to 2c on its own, so the
        package is a loser and the scanner must report nothing.
        """
        opp = evaluate(
            _pair(),
            _quote(YES_REF, [("0.495", 100)]),
            _quote(NO_REF, [("0.495", 100)]),
            KALSHI,
            POLY,
            now=NOW,
        )
        assert opp.packages == 0
        assert not opp.is_profitable

    def test_depth_stops_where_the_edge_dies(self):
        """Profitable top level, unprofitable second level: only the first counts."""
        opp = evaluate(
            _pair(),
            _quote(YES_REF, [("0.30", 10), ("0.60", 100)]),
            _quote(NO_REF, [("0.30", 10), ("0.60", 100)]),
            FREE,
            FREE,
            now=NOW,
        )
        assert opp.packages == 10
        assert opp.net_profit == Decimal("4.00")
