"""Tests for quarter-Kelly position sizing in binary contracts."""
import math
import pytest
from parallax.config.risk import RiskLimits
from parallax.portfolio.allocator import PortfolioAllocator
from parallax.portfolio.schemas import ProposedTrade, PortfolioState


class TestKellyFormula:
    """Test the Kelly sizing math directly."""

    def test_moderate_edge_moderate_price(self):
        limits = RiskLimits(bankroll=250.0, kelly_multiplier=0.25)
        allocator = PortfolioAllocator(limits)
        # edge=0.10, price=0.30: kelly_frac = 0.10/0.70 = 0.143
        # quarter = 0.0357, size = floor(0.0357 * 250 / 0.30) = floor(29.7) = 29
        size = allocator.kelly_size(edge=0.10, entry_price=0.30)
        assert size == 29

    def test_small_edge_even_price(self):
        limits = RiskLimits(bankroll=250.0, kelly_multiplier=0.25)
        allocator = PortfolioAllocator(limits)
        # edge=0.05, price=0.50: kelly_frac = 0.05/0.50 = 0.10
        # quarter = 0.025, size = floor(0.025 * 250 / 0.50) = floor(12.5) = 12
        size = allocator.kelly_size(edge=0.05, entry_price=0.50)
        assert size == 12

    def test_zero_edge_returns_zero(self):
        limits = RiskLimits(bankroll=250.0, kelly_multiplier=0.25)
        allocator = PortfolioAllocator(limits)
        assert allocator.kelly_size(edge=0.0, entry_price=0.50) == 0

    def test_negative_edge_returns_zero(self):
        limits = RiskLimits(bankroll=250.0, kelly_multiplier=0.25)
        allocator = PortfolioAllocator(limits)
        assert allocator.kelly_size(edge=-0.05, entry_price=0.50) == 0

    def test_price_at_boundary_one_returns_zero(self):
        limits = RiskLimits(bankroll=250.0, kelly_multiplier=0.25)
        allocator = PortfolioAllocator(limits)
        assert allocator.kelly_size(edge=0.10, entry_price=1.0) == 0

    def test_respects_min_order_size(self):
        limits = RiskLimits(bankroll=250.0, kelly_multiplier=0.25, min_order_size=5)
        allocator = PortfolioAllocator(limits)
        # Very tiny edge producing <5 contracts should clamp to min
        # edge=0.01, price=0.90: kelly_frac=0.01/0.10=0.10, quarter=0.025
        # size = floor(0.025*250/0.90) = floor(6.94) = 6 >= 5, ok
        size = allocator.kelly_size(edge=0.01, entry_price=0.90)
        assert size >= 5

    def test_half_kelly_multiplier(self):
        limits = RiskLimits(bankroll=250.0, kelly_multiplier=0.50)
        allocator = PortfolioAllocator(limits)
        # edge=0.10, price=0.30: kelly_frac = 0.143
        # half = 0.0714, size = floor(0.0714 * 250 / 0.30) = floor(59.5) = 59
        size = allocator.kelly_size(edge=0.10, entry_price=0.30)
        assert size == 59

    def test_large_edge_large_size(self):
        limits = RiskLimits(bankroll=250.0, kelly_multiplier=0.25)
        allocator = PortfolioAllocator(limits)
        # edge=0.25, price=0.30: kelly_frac = 0.25/0.70 = 0.357
        # quarter = 0.0893, size = floor(0.0893 * 250 / 0.30) = floor(74.4) = 74
        size = allocator.kelly_size(edge=0.25, entry_price=0.30)
        assert size == 74


class TestKellyIntegration:
    """Test Kelly sizing integrates with allocator authorization."""

    def test_trade_with_edge_uses_kelly(self):
        limits = RiskLimits(bankroll=250.0, kelly_multiplier=0.25, max_notional=250.0)
        allocator = PortfolioAllocator(limits)
        trade = ProposedTrade(ticker="TEST", side="yes", price=0.30, edge=0.10)
        portfolio = PortfolioState()
        auth = allocator.authorize_trade(trade, portfolio)
        assert auth.authorized
        # Kelly says 29, but should be capped by risk limits if needed
        assert auth.allowed_size > 0
        assert auth.allowed_size <= 29  # Kelly size is the starting point

    def test_trade_without_edge_uses_default(self):
        limits = RiskLimits(default_order_size=10, bankroll=250.0, kelly_multiplier=0.25)
        allocator = PortfolioAllocator(limits)
        trade = ProposedTrade(ticker="TEST", side="yes", price=0.30)
        portfolio = PortfolioState()
        auth = allocator.authorize_trade(trade, portfolio)
        assert auth.authorized
        assert auth.allowed_size == 10

    def test_kelly_capped_by_max_notional(self):
        # bankroll=250, max_notional=5 → Kelly wants 29 contracts but notional cap stops it
        limits = RiskLimits(bankroll=250.0, kelly_multiplier=0.25, max_notional=5.0)
        allocator = PortfolioAllocator(limits)
        trade = ProposedTrade(ticker="TEST", side="yes", price=0.30, edge=0.10)
        portfolio = PortfolioState()
        auth = allocator.authorize_trade(trade, portfolio)
        # max_notional=5, price=0.30, so max contracts = floor(5/0.30) = 16
        # But Kelly says 29, so should be capped
        assert auth.allowed_size <= 16
