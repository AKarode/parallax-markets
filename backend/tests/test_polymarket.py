"""Tests for Polymarket read-only client with mocked HTTP responses."""

from __future__ import annotations

import json

import pytest

from parallax.markets.polymarket import PolymarketClient
from parallax.markets.schemas import MarketPrice


class MockResponse:
    """Minimal httpx.Response mock."""

    def __init__(self, data, status_code: int = 200):
        self._data = data
        self.status_code = status_code

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


@pytest.fixture()
def client():
    return PolymarketClient(
        gamma_base="https://gamma-api.polymarket.com",
        clob_base="https://clob.polymarket.com",
    )


MOCK_MARKET = {
    "condition_id": "0xabc123",
    "slug": "iran-ceasefire-2026",
    "tokens": [
        {"outcome": "Yes", "token_id": "tok_yes_1", "price": 0.65},
        {"outcome": "No", "token_id": "tok_no_1", "price": 0.35},
    ],
    "volume": 150000,
    "closed": False,
    "active": True,
}

MOCK_MARKET_OUTCOME_PRICES = {
    "condition_id": "0xdef456",
    "slug": "oil-above-80",
    "tokens": [],
    "outcomePrices": json.dumps([0.42, 0.58]),
    "volume": 80000,
    "closed": False,
    "active": True,
}


class TestPolymarketSearch:
    """Test market search functionality."""

    async def test_search_markets(self, client, monkeypatch):
        async def mock_get(self_client, url, **kwargs):
            return MockResponse([MOCK_MARKET])

        monkeypatch.setattr("httpx.AsyncClient.get", mock_get)
        results = await client.search_markets("Iran")
        assert len(results) == 1
        assert results[0]["condition_id"] == "0xabc123"

    async def test_get_market(self, client, monkeypatch):
        async def mock_get(self_client, url, **kwargs):
            return MockResponse(MOCK_MARKET)

        monkeypatch.setattr("httpx.AsyncClient.get", mock_get)
        result = await client.get_market("0xabc123")
        assert result["slug"] == "iran-ceasefire-2026"

    async def test_get_event(self, client, monkeypatch):
        event_data = {"id": "evt_1", "title": "Iran Ceasefire", "markets": [MOCK_MARKET]}

        async def mock_get(self_client, url, **kwargs):
            return MockResponse(event_data)

        monkeypatch.setattr("httpx.AsyncClient.get", mock_get)
        result = await client.get_event("evt_1")
        assert result["title"] == "Iran Ceasefire"


class TestPolymarketPrice:
    """Test price fetching from CLOB API."""

    async def test_get_price(self, client, monkeypatch):
        async def mock_get(self_client, url, **kwargs):
            return MockResponse({"price": 0.65})

        monkeypatch.setattr("httpx.AsyncClient.get", mock_get)
        price = await client.get_price("tok_yes_1")
        assert price == 0.65


class TestIranMarkets:
    """Test aggregated Iran market fetching."""

    async def test_get_iran_markets_with_tokens(self, client, monkeypatch):
        async def mock_get(self_client, url, **kwargs):
            return MockResponse([MOCK_MARKET])

        monkeypatch.setattr("httpx.AsyncClient.get", mock_get)
        results = await client.get_iran_markets()

        # Deduplicated across multiple search terms
        assert len(results) == 1
        mp = results[0]
        assert isinstance(mp, MarketPrice)
        assert mp.source == "polymarket"
        assert mp.ticker == "iran-ceasefire-2026"
        assert mp.yes_price == 0.65
        assert mp.no_price == 0.35
        assert mp.volume == 150000

    async def test_get_iran_markets_with_outcome_prices(self, client, monkeypatch):
        async def mock_get(self_client, url, **kwargs):
            return MockResponse([MOCK_MARKET_OUTCOME_PRICES])

        monkeypatch.setattr("httpx.AsyncClient.get", mock_get)
        results = await client.get_iran_markets()
        assert len(results) == 1
        assert results[0].yes_price == 0.42
        assert results[0].no_price == 0.58

    async def test_deduplicates_across_searches(self, client, monkeypatch):
        """Same market found by multiple search terms should only appear once."""
        async def mock_get(self_client, url, **kwargs):
            return MockResponse([MOCK_MARKET])

        monkeypatch.setattr("httpx.AsyncClient.get", mock_get)
        results = await client.get_iran_markets()
        # MOCK_MARKET has same condition_id regardless of search term
        assert len(results) == 1

    async def test_empty_search_results(self, client, monkeypatch):
        async def mock_get(self_client, url, **kwargs):
            return MockResponse([])

        monkeypatch.setattr("httpx.AsyncClient.get", mock_get)
        results = await client.get_iran_markets()
        assert results == []
