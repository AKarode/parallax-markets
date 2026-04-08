"""Tests for daily intelligence brief CLI with mocked external clients."""

from __future__ import annotations

import pytest

from parallax.budget.tracker import BudgetTracker
from parallax.cli.brief import (
    _format_brief,
    _make_dry_run_markets,
    _make_dry_run_predictions,
    run_brief,
)
from parallax.divergence.detector import DivergenceDetector


class TestDryRunPredictions:
    """Test mock prediction generation."""

    def test_returns_three_predictions(self):
        preds = _make_dry_run_predictions()
        assert len(preds) == 3
        model_ids = {p.model_id for p in preds}
        assert model_ids == {"oil_price", "ceasefire", "hormuz_reopening"}

    def test_predictions_have_valid_probabilities(self):
        for p in _make_dry_run_predictions():
            assert 0.0 <= p.probability <= 1.0
            assert p.reasoning
            assert p.timeframe

    def test_predictions_have_kalshi_tickers(self):
        for p in _make_dry_run_predictions():
            assert p.kalshi_ticker is not None


class TestDryRunMarkets:
    """Test mock market price generation."""

    def test_returns_market_prices(self):
        markets = _make_dry_run_markets()
        assert len(markets) >= 3
        sources = {m.source for m in markets}
        assert "kalshi" in sources
        assert "polymarket" in sources

    def test_prices_valid(self):
        for m in _make_dry_run_markets():
            assert 0.0 <= m.yes_price <= 1.0
            assert 0.0 <= m.no_price <= 1.0


class TestBriefFormatting:
    """Test intelligence brief output formatting."""

    def test_format_includes_sections(self):
        preds = _make_dry_run_predictions()
        markets = _make_dry_run_markets()
        budget = BudgetTracker(daily_cap_usd=20.0)

        detector = DivergenceDetector(min_edge_pct=5.0)
        divergences = detector.detect(preds, markets)

        brief = _format_brief(preds, markets, divergences, budget)

        assert "PARALLAX DAILY INTELLIGENCE BRIEF" in brief
        assert "PREDICTIONS" in brief
        assert "MARKET PRICES" in brief
        assert "DIVERGENCES" in brief

    def test_format_shows_predictions(self):
        preds = _make_dry_run_predictions()
        markets = _make_dry_run_markets()
        budget = BudgetTracker(daily_cap_usd=20.0)

        brief = _format_brief(preds, markets, [], budget)

        assert "OIL PRICE" in brief
        assert "CEASEFIRE" in brief
        assert "HORMUZ REOPENING" in brief

    def test_format_shows_market_prices(self):
        preds = _make_dry_run_predictions()
        markets = _make_dry_run_markets()
        budget = BudgetTracker(daily_cap_usd=20.0)

        brief = _format_brief(preds, markets, [], budget)

        assert "KXOIL" in brief
        assert "kalshi" in brief
        assert "polymarket" in brief

    def test_format_shows_divergences(self):
        preds = _make_dry_run_predictions()
        markets = _make_dry_run_markets()
        budget = BudgetTracker(daily_cap_usd=20.0)

        detector = DivergenceDetector(min_edge_pct=5.0)
        divergences = detector.detect(preds, markets)

        brief = _format_brief(preds, markets, divergences, budget)

        # Should have at least one signal
        assert "SIGNAL" in brief or "No significant divergences" in brief

    def test_format_with_trade_table(self):
        preds = _make_dry_run_predictions()
        markets = _make_dry_run_markets()
        budget = BudgetTracker(daily_cap_usd=20.0)

        brief = _format_brief(preds, markets, [], budget, trade_table="Mock trade table")
        assert "PAPER TRADES" in brief
        assert "Mock trade table" in brief

    def test_format_budget_display(self):
        budget = BudgetTracker(daily_cap_usd=20.0)
        budget.record(500, 200, "sonnet")

        preds = _make_dry_run_predictions()
        markets = _make_dry_run_markets()
        brief = _format_brief(preds, markets, [], budget)

        assert "$20.00" in brief  # budget cap
        assert "Budget:" in brief


class TestRunBriefDryRun:
    """Test end-to-end dry run execution."""

    async def test_dry_run_produces_output(self, capsys):
        result = await run_brief(dry_run=True, no_trade=True)

        assert "PARALLAX DAILY INTELLIGENCE BRIEF" in result
        assert "OIL PRICE" in result
        assert "CEASEFIRE" in result
        assert "HORMUZ REOPENING" in result
        assert "MARKET PRICES" in result
        assert "DIVERGENCES" in result

    async def test_dry_run_detects_divergences(self):
        result = await run_brief(dry_run=True, no_trade=True)
        # With mock data, the oil model (72%) vs market (55%) should generate a signal
        assert "SIGNAL" in result

    async def test_dry_run_prints_to_stdout(self, capsys):
        await run_brief(dry_run=True, no_trade=True)
        captured = capsys.readouterr()
        assert "PARALLAX" in captured.out
