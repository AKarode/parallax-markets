"""Known-answer tests for the venue fee models.

The published Kalshi numbers are the anchor: the fee peaks at 1.75c per
contract at a 50c price, and every order rounds up to the next whole cent.
"""

from __future__ import annotations

from decimal import Decimal

from parallax.arb.fees import POLITICS_TAKER_RATE, KalshiFees, PolymarketFees


class TestKalshiFees:
    def test_peak_fee_at_fifty_cents(self):
        # 0.07 * 1 * 0.5 * 0.5 = 0.0175 -> rounds up to 0.02
        assert KalshiFees().fee(Decimal("0.50"), 1) == Decimal("0.02")

    def test_hundred_contracts_at_fifty_cents(self):
        # 0.07 * 100 * 0.25 = 1.75, already whole cents
        assert KalshiFees().fee(Decimal("0.50"), 100) == Decimal("1.75")

    def test_ceiling_dominates_small_orders(self):
        """A 1-contract order at 2c owes a fraction of a cent but pays a full one.

        This is why thin cross-venue packages are structurally unprofitable:
        the rounding, not the rate, sets the floor.
        """
        raw = Decimal("0.07") * Decimal("0.02") * Decimal("0.98")  # 0.0013720
        assert raw < Decimal("0.01")
        assert KalshiFees().fee(Decimal("0.02"), 1) == Decimal("0.01")

    def test_maker_is_quarter_rate_rounded_independently(self):
        """25% of the *rate*, not 25% of the already-rounded taker fee."""
        fees = KalshiFees()
        taker = fees.fee(Decimal("0.50"), 1)  # 0.02 (rounded up from 0.0175)
        maker = fees.fee(Decimal("0.50"), 1, role="maker")
        # 0.07 * 0.25 * 0.25 = 0.004375 -> 0.01, which is NOT 0.25 * 0.02
        assert maker == Decimal("0.01")
        assert maker != taker * Decimal("0.25")

    def test_zero_quantity_is_free(self):
        assert KalshiFees().fee(Decimal("0.50"), 0) == Decimal("0.00")


class TestPolymarketFees:
    def test_default_rate_is_zero_not_four_percent(self):
        """An unconfigured market must not inherit the politics rate."""
        assert PolymarketFees().fee(Decimal("0.50"), 100) == Decimal("0")

    def test_politics_taker_rate(self):
        fees = PolymarketFees(rate=POLITICS_TAKER_RATE)
        # 0.04 * 100 * 0.5 * 0.5 = 1.00
        assert fees.fee(Decimal("0.50"), 100) == Decimal("1.0000")

    def test_makers_pay_nothing(self):
        fees = PolymarketFees(rate=POLITICS_TAKER_RATE)
        assert fees.fee(Decimal("0.50"), 100, role="maker") == Decimal("0.00")
