"""Polymarket read-only client for fetching prediction market prices.

Uses the Gamma API for market search and the CLOB API for price data.
No authentication required — all endpoints are public.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from parallax.markets.schemas import MarketPrice

logger = logging.getLogger(__name__)

# Search terms for Iran/Hormuz-related markets
IRAN_SEARCH_TERMS = ("Iran", "Hormuz", "oil price", "ceasefire Iran")


class PolymarketClient:
    """Async read-only client for Polymarket Gamma and CLOB APIs."""

    def __init__(
        self,
        gamma_base: str = "https://gamma-api.polymarket.com",
        clob_base: str = "https://clob.polymarket.com",
    ) -> None:
        self._gamma_base = gamma_base.rstrip("/")
        self._clob_base = clob_base.rstrip("/")

    async def search_markets(self, query: str) -> list[dict]:
        """Search for markets by keyword via Gamma API."""
        logger.debug("Polymarket search: %s", query)
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self._gamma_base}/markets",
                params={"_q": query, "closed": "false", "active": "true"},
            )
            resp.raise_for_status()
            return resp.json()

    async def get_event(self, event_id: str) -> dict:
        """Fetch event details by ID."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self._gamma_base}/events/{event_id}")
            resp.raise_for_status()
            return resp.json()

    async def get_market(self, market_id: str) -> dict:
        """Fetch market details by condition ID."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self._gamma_base}/markets/{market_id}")
            resp.raise_for_status()
            return resp.json()

    async def get_price(self, token_id: str) -> float:
        """Fetch current YES token price from CLOB API.

        Returns the probability as a float 0.0-1.0.
        """
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self._clob_base}/price",
                params={"token_id": token_id},
            )
            resp.raise_for_status()
            data = resp.json()
            return float(data.get("price", 0.0))

    async def get_iran_markets(self) -> list[MarketPrice]:
        """Search for Iran/Hormuz-related markets and return MarketPrice objects.

        Searches multiple terms, deduplicates by condition_id, and returns
        active markets with current prices.
        """
        seen_ids: set[str] = set()
        results: list[MarketPrice] = []

        for term in IRAN_SEARCH_TERMS:
            try:
                markets = await self.search_markets(term)
            except httpx.HTTPError:
                logger.warning("Polymarket search failed for '%s'", term)
                continue

            for market in markets:
                condition_id = market.get("condition_id", "")
                if not condition_id or condition_id in seen_ids:
                    continue
                seen_ids.add(condition_id)

                # Extract YES/NO token prices
                tokens = market.get("tokens", [])
                yes_price = 0.0
                no_price = 0.0
                for token in tokens:
                    outcome = token.get("outcome", "").lower()
                    price = float(token.get("price", 0.0))
                    if outcome == "yes":
                        yes_price = price
                    elif outcome == "no":
                        no_price = price

                # If no token prices, try top-level outcomePrices
                if yes_price == 0.0 and no_price == 0.0:
                    outcome_prices = market.get("outcomePrices", "")
                    if outcome_prices and isinstance(outcome_prices, str):
                        try:
                            import json
                            prices = json.loads(outcome_prices)
                            if len(prices) >= 2:
                                yes_price = float(prices[0])
                                no_price = float(prices[1])
                        except (json.JSONDecodeError, ValueError, IndexError):
                            pass

                volume = float(market.get("volume", 0))
                slug = market.get("slug", condition_id)

                results.append(MarketPrice(
                    ticker=slug,
                    source="polymarket",
                    yes_price=min(max(yes_price, 0.0), 1.0),
                    no_price=min(max(no_price, 0.0), 1.0),
                    volume=volume,
                    fetched_at=datetime.now(timezone.utc),
                ))

        return results
