"""Polymarket read-only client for fetching executable quote snapshots."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from parallax.markets.schemas import DepthSummary, MarketPrice, OrderbookLevel

logger = logging.getLogger(__name__)

IRAN_SEARCH_TERMS = ("Iran", "Hormuz", "oil price", "ceasefire Iran")


def _parse_ts(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    text = str(value)
    if text.endswith("Z"):
        text = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _coerce_price(value: Any) -> float | None:
    if value in (None, "", 0, 0.0, "0", "0.0"):
        return None
    numeric = float(value)
    if numeric > 1.0:
        numeric = numeric / 100.0
    return min(max(numeric, 0.0), 1.0)


def _coerce_qty(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    return float(value)


def _to_levels(side: list[dict[str, Any]]) -> list[OrderbookLevel]:
    levels: list[OrderbookLevel] = []
    for level in side:
        price = _coerce_price(level.get("price"))
        if price is None:
            continue
        levels.append(
            OrderbookLevel(
                price=price,
                quantity=_coerce_qty(level.get("size", level.get("quantity"))),
            ),
        )
    return levels


def _depth(levels: list[OrderbookLevel]) -> DepthSummary | None:
    if not levels:
        return None
    return DepthSummary(
        levels=len(levels),
        visible_quantity=sum(level.quantity for level in levels),
        top_level_quantity=levels[0].quantity,
    )


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
        logger.debug("Polymarket search: %s", query)
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self._gamma_base}/markets",
                params={"_q": query, "closed": "false", "active": "true"},
            )
            resp.raise_for_status()
            return resp.json()

    async def get_event(self, event_id: str) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self._gamma_base}/events/{event_id}")
            resp.raise_for_status()
            return resp.json()

    async def get_market(self, market_id: str) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self._gamma_base}/markets/{market_id}")
            resp.raise_for_status()
            return resp.json()

    async def get_price(self, token_id: str) -> float:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self._clob_base}/price",
                params={"token_id": token_id},
            )
            resp.raise_for_status()
            data = resp.json()
            return float(data.get("price", 0.0))

    async def get_book(self, token_id: str) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self._clob_base}/book",
                params={"token_id": token_id},
            )
            resp.raise_for_status()
            return resp.json()

    async def _normalize_market(self, market: dict[str, Any]) -> MarketPrice | None:
        tokens = market.get("tokens", [])
        yes_token = next(
            (token for token in tokens if token.get("outcome", "").lower() == "yes"),
            None,
        )
        no_token = next(
            (token for token in tokens if token.get("outcome", "").lower() == "no"),
            None,
        )
        if yes_token is None or no_token is None:
            outcome_prices = market.get("outcomePrices", "")
            derived_yes = None
            derived_no = None
            if outcome_prices and isinstance(outcome_prices, str):
                try:
                    prices = json.loads(outcome_prices)
                    if len(prices) >= 2:
                        derived_yes = _coerce_price(prices[0])
                        derived_no = _coerce_price(prices[1])
                except (json.JSONDecodeError, ValueError, IndexError):
                    pass
            if derived_yes is None and derived_no is None:
                return None
            quote_timestamp = _parse_ts(market.get("updatedAt")) or _parse_ts(market.get("createdAt"))
            return MarketPrice(
                ticker=market.get("slug") or market.get("condition_id", ""),
                source="polymarket",
                volume=float(market.get("volume", 0) or 0),
                fetched_at=datetime.now(timezone.utc),
                venue_timestamp=_parse_ts(market.get("endDate")) or quote_timestamp,
                quote_timestamp=quote_timestamp,
                yes_price=derived_yes,
                no_price=derived_no,
                derived_price_kind="outcome_prices_snapshot",
                data_environment="live",
            )

        yes_book, no_book = await asyncio.gather(
            self.get_book(str(yes_token.get("token_id"))),
            self.get_book(str(no_token.get("token_id"))),
            return_exceptions=True,
        )

        if isinstance(yes_book, Exception) or isinstance(no_book, Exception):
            logger.debug(
                "Polymarket book fetch failed for %s",
                market.get("slug", market.get("condition_id", "")),
            )
            yes_book = {} if isinstance(yes_book, Exception) else yes_book
            no_book = {} if isinstance(no_book, Exception) else no_book

        if not isinstance(yes_book, dict):
            yes_book = {}
        if not isinstance(no_book, dict):
            no_book = {}

        yes_bids = _to_levels(yes_book.get("bids", []))
        yes_asks = _to_levels(yes_book.get("asks", []))
        no_bids = _to_levels(no_book.get("bids", []))
        no_asks = _to_levels(no_book.get("asks", []))

        best_yes_bid = yes_bids[0].price if yes_bids else None
        best_yes_ask = yes_asks[0].price if yes_asks else None
        best_no_bid = no_bids[0].price if no_bids else None
        best_no_ask = no_asks[0].price if no_asks else None

        derived_yes = None
        derived_no = None
        derived_kind = None
        if best_yes_bid is not None and best_yes_ask is not None:
            derived_yes = (best_yes_bid + best_yes_ask) / 2.0
            derived_no = 1.0 - derived_yes
            derived_kind = "midpoint"
        elif yes_token.get("price") is not None:
            derived_yes = _coerce_price(yes_token.get("price"))
            derived_no = None if derived_yes is None else 1.0 - derived_yes
            derived_kind = "token_snapshot"
        else:
            outcome_prices = market.get("outcomePrices", "")
            if outcome_prices and isinstance(outcome_prices, str):
                try:
                    prices = json.loads(outcome_prices)
                    if len(prices) >= 2:
                        derived_yes = _coerce_price(prices[0])
                        derived_no = _coerce_price(prices[1])
                        derived_kind = "outcome_prices_snapshot"
                except (json.JSONDecodeError, ValueError, IndexError):
                    pass

        quote_timestamp = (
            _parse_ts(yes_book.get("timestamp"))
            or _parse_ts(no_book.get("timestamp"))
            or _parse_ts(market.get("updatedAt"))
            or _parse_ts(market.get("createdAt"))
        )

        ticker = market.get("slug") or market.get("condition_id", "")
        return MarketPrice(
            ticker=ticker,
            source="polymarket",
            volume=float(market.get("volume", 0) or 0),
            fetched_at=datetime.now(timezone.utc),
            venue_timestamp=_parse_ts(market.get("endDate")) or quote_timestamp,
            quote_timestamp=quote_timestamp,
            best_yes_bid=best_yes_bid,
            best_yes_ask=best_yes_ask,
            best_no_bid=best_no_bid,
            best_no_ask=best_no_ask,
            yes_bid_ask_spread=(
                best_yes_ask - best_yes_bid
                if best_yes_bid is not None and best_yes_ask is not None else None
            ),
            no_bid_ask_spread=(
                best_no_ask - best_no_bid
                if best_no_bid is not None and best_no_ask is not None else None
            ),
            yes_bid_depth=_depth(yes_bids),
            yes_ask_depth=_depth(yes_asks),
            no_bid_depth=_depth(no_bids),
            no_ask_depth=_depth(no_asks),
            yes_price=derived_yes,
            no_price=derived_no,
            derived_price_kind=derived_kind,
            data_environment="live",
        )

    async def get_iran_markets(self) -> list[MarketPrice]:
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
                normalized = await self._normalize_market(market)
                if normalized is not None:
                    results.append(normalized)

        return results
