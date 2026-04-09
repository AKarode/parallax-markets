"""Tests verifying prediction models do not receive or inject market prices."""
import inspect
import pytest

from parallax.prediction.oil_price import OilPricePredictor, OIL_PRICE_SYSTEM_PROMPT
from parallax.prediction.ceasefire import CeasefirePredictor, CEASEFIRE_SYSTEM_PROMPT
from parallax.prediction.hormuz import HormuzReopeningPredictor, HORMUZ_SYSTEM_PROMPT


class TestMarketPriceRemoval:
    """Verify market prices are not injected into LLM prompts."""

    def test_oil_price_prompt_has_no_market_prices(self):
        assert "market_prices" not in OIL_PRICE_SYSTEM_PROMPT
        assert "market prices" not in OIL_PRICE_SYSTEM_PROMPT.lower()

    def test_ceasefire_prompt_has_no_market_prices(self):
        assert "market_prices" not in CEASEFIRE_SYSTEM_PROMPT
        assert "market prices" not in CEASEFIRE_SYSTEM_PROMPT.lower()

    def test_hormuz_prompt_has_no_market_prices(self):
        assert "market_prices" not in HORMUZ_SYSTEM_PROMPT
        assert "market prices" not in HORMUZ_SYSTEM_PROMPT.lower()

    def test_oil_price_predict_has_no_market_prices_param(self):
        sig = inspect.signature(OilPricePredictor.predict)
        assert "market_prices" not in sig.parameters

    def test_ceasefire_predict_has_no_market_prices_param(self):
        sig = inspect.signature(CeasefirePredictor.predict)
        assert "market_prices" not in sig.parameters

    def test_hormuz_predict_has_no_market_prices_param(self):
        sig = inspect.signature(HormuzReopeningPredictor.predict)
        assert "market_prices" not in sig.parameters

    def test_oil_price_has_no_format_market_prices_method(self):
        assert not hasattr(OilPricePredictor, "_format_market_prices")

    def test_ceasefire_has_no_format_market_prices_method(self):
        assert not hasattr(CeasefirePredictor, "_format_market_prices")

    def test_hormuz_has_no_format_market_prices_method(self):
        assert not hasattr(HormuzReopeningPredictor, "_format_market_prices")
