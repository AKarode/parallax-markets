"""Tests verifying crisis_context.py contains only factual content."""
from parallax.prediction.crisis_context import get_crisis_context


class TestCrisisContextEditorial:
    def test_no_what_market_may_be_missing(self):
        ctx = get_crisis_context()
        assert "What The Market May Be Missing" not in ctx

    def test_no_key_risks_bullets(self):
        ctx = get_crisis_context()
        assert "**Key risks:**" not in ctx

    def test_no_key_opportunities_bullets(self):
        ctx = get_crisis_context()
        assert "**Key opportunities:**" not in ctx

    def test_no_current_market_percentages(self):
        ctx = get_crisis_context()
        assert "~48% YES" not in ctx
        assert "~42%" not in ctx

    def test_no_wagered_amounts(self):
        ctx = get_crisis_context()
        assert "$200M+" not in ctx
        assert "$3.16M" not in ctx

    def test_no_brent_current_price_in_market_state(self):
        ctx = get_crisis_context()
        assert "~$98/barrel futures" not in ctx
        assert "$124.68 spot" not in ctx

    def test_keeps_resolution_criteria(self):
        ctx = get_crisis_context()
        assert "KXUSAIRANAGREEMENT" in ctx
        assert "SIGNED DEAL" in ctx
        assert "KXCLOSEHORMUZ" in ctx
        assert "KXWTIMAX" in ctx

    def test_keeps_factual_status(self):
        ctx = get_crisis_context()
        assert "effectively closed" in ctx
        assert "fragile" in ctx

    def test_keeps_historical_price_markers(self):
        ctx = get_crisis_context()
        assert "$120" in ctx
