"""Kalshi prediction market API client with RSA-PSS authentication.

Kalshi's binary orderbook publishes bids on YES and NO. The executable asks are
implied by crossing the opposite bid:
- best_yes_ask = 1 - best_no_bid
- best_no_ask = 1 - best_yes_bid
"""

from __future__ import annotations

import base64
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from parallax.markets.schemas import (
    DepthSummary,
    MarketPrice,
    Orderbook,
    OrderbookLevel,
    Position,
)

logger = logging.getLogger(__name__)

IRAN_EVENT_TICKERS = [
    "KXCLOSEHORMUZ-27JAN",
    "KXUSAIRANAGREEMENT-27",
    "KXIRANDEMOCRACY-27MAR01",
    "KXELECTIRAN",
    "KXPAHLAVIHEAD-27JAN",
    "KXPAHLAVIVISITA",
    "KXIRANEMBASSY-27",
    "KXRECOGPERSONIRAN-26",
    "KXNEXTIRANLEADER-45JAN01",
    "KXWTIMAX-26DEC31",
    "KXWTIMIN-26DEC31",
    "KXOILRIGS-26",
]

IRAN_KEYWORDS = ["iran", "hormuz", "ceasefire", "oil", "crude", "wti", "brent"]

HORMUZ_SERIES = "KXCLOSEHORMUZ"
IRAN_CEASEFIRE_SERIES = "KXIRANCEASEFIRE"
OIL_PRICE_SERIES = "KXOIL"


def _coerce_price(value: Any) -> float | None:
    if value in (None, "", 0, 0.0, "0", "0.0", "0.0000"):
        return None
    numeric = float(value)
    if numeric > 1.0:
        numeric = numeric / 100.0
    return min(max(numeric, 0.0), 1.0)


def _coerce_quantity(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


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


def _depth_summary(levels: list[OrderbookLevel]) -> DepthSummary | None:
    if not levels:
        return None
    return DepthSummary(
        levels=len(levels),
        visible_quantity=sum(level.quantity for level in levels),
        top_level_quantity=levels[0].quantity,
    )


class KalshiAPIError(Exception):
    """Raised on non-2xx responses from the Kalshi API."""

    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        self.message = message
        super().__init__(f"Kalshi API {status_code}: {message}")


class KalshiClient:
    """Async client for Kalshi Trade API v2 with RSA-PSS auth."""

    def __init__(
        self,
        api_key: str,
        private_key_path: str,
        base_url: str = "https://demo-api.kalshi.co/trade-api/v2",
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._private_key = self._load_private_key(private_key_path)

    @property
    def venue_environment(self) -> str:
        return "demo" if "demo" in self._base_url else "live"

    @staticmethod
    def _load_private_key(path: str):
        pem_data = Path(path).read_bytes()
        return serialization.load_pem_private_key(pem_data, password=None)

    def _sign_request(self, method: str, path: str) -> dict[str, str]:
        timestamp = str(int(time.time() * 1000))
        message = timestamp + method.upper() + path
        signature = self._private_key.sign(
            message.encode("utf-8"),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH,
            ),
            hashes.SHA256(),
        )
        encoded_sig = base64.b64encode(signature).decode("utf-8")
        return {
            "KALSHI-ACCESS-KEY": self._api_key,
            "KALSHI-ACCESS-SIGNATURE": encoded_sig,
            "KALSHI-ACCESS-TIMESTAMP": timestamp,
        }

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
        params: dict | None = None,
    ) -> dict:
        headers = self._sign_request(method, path)
        url = self._base_url + path
        logger.debug("Kalshi %s %s", method, path)

        async with httpx.AsyncClient() as client:
            resp = await client.request(
                method,
                url,
                headers=headers,
                json=json,
                params=params,
            )

        if resp.status_code >= 400:
            raise KalshiAPIError(resp.status_code, resp.text)
        return resp.json()

    async def get_markets(self, series_ticker: str | None = None) -> list[dict]:
        params = {}
        if series_ticker:
            params["series_ticker"] = series_ticker
        data = await self._request("GET", "/markets", params=params)
        return data.get("markets", [])

    async def search_markets(self, query: str) -> list[dict]:
        params = {"status": "open"}
        data = await self._request("GET", "/markets", params=params)
        markets = data.get("markets", [])
        q = query.lower()
        return [
            market for market in markets
            if q in market.get("title", "").lower()
            or q in market.get("ticker", "").lower()
            or q in market.get("subtitle", "").lower()
        ]

    def _normalize_market_snapshot(self, market: dict[str, Any]) -> MarketPrice:
        best_yes_bid = _coerce_price(
            market.get("yes_bid_dollars", market.get("yes_bid")),
        )
        best_no_bid = _coerce_price(
            market.get("no_bid_dollars", market.get("no_bid")),
        )
        best_yes_ask = _coerce_price(
            market.get("yes_ask_dollars", market.get("yes_ask")),
        )
        best_no_ask = _coerce_price(
            market.get("no_ask_dollars", market.get("no_ask")),
        )

        # Kalshi publishes bids on both sides. Crossing the opposite bid is the
        # executable ask if the explicit ask is omitted.
        if best_yes_ask is None and best_no_bid is not None:
            best_yes_ask = min(max(1.0 - best_no_bid, 0.0), 1.0)
        if best_no_ask is None and best_yes_bid is not None:
            best_no_ask = min(max(1.0 - best_yes_bid, 0.0), 1.0)

        yes_price = _coerce_price(
            market.get("last_price_dollars", market.get("last_price")),
        )
        if yes_price is None and best_yes_bid is not None and market.get("yes_ask_dollars") is not None:
            yes_price = (best_yes_bid + best_yes_ask) / 2.0
        elif yes_price is None and best_yes_bid is not None:
            yes_price = best_yes_bid
        no_price = _coerce_price(
            market.get("no_price_dollars", market.get("no_price")),
        )
        if no_price is None and best_no_bid is not None:
            no_price = best_no_bid
        elif no_price is None and yes_price is not None:
            no_price = 1.0 - yes_price

        quote_timestamp = (
            _parse_ts(market.get("last_update_time"))
            or _parse_ts(market.get("updated_time"))
            or _parse_ts(market.get("close_time"))
        )
        venue_timestamp = _parse_ts(market.get("open_time")) or quote_timestamp

        return MarketPrice(
            ticker=market.get("ticker", ""),
            source="kalshi",
            volume=float(market.get("volume_fp", 0) or market.get("volume", 0) or 0),
            fetched_at=datetime.now(timezone.utc),
            venue_timestamp=venue_timestamp,
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
            yes_bid_depth=DepthSummary(
                levels=1,
                visible_quantity=_coerce_quantity(
                    market.get("yes_bid_size_fp", market.get("yes_bid_size")),
                ) or 0.0,
                top_level_quantity=_coerce_quantity(
                    market.get("yes_bid_size_fp", market.get("yes_bid_size")),
                ),
            ) if _coerce_quantity(
                market.get("yes_bid_size_fp", market.get("yes_bid_size")),
            ) is not None else None,
            yes_ask_depth=DepthSummary(
                levels=1,
                visible_quantity=_coerce_quantity(
                    market.get("yes_ask_size_fp", market.get("yes_ask_size")),
                ) or 0.0,
                top_level_quantity=_coerce_quantity(
                    market.get("yes_ask_size_fp", market.get("yes_ask_size")),
                ),
            ) if _coerce_quantity(
                market.get("yes_ask_size_fp", market.get("yes_ask_size")),
            ) is not None else None,
            no_bid_depth=DepthSummary(
                levels=1,
                visible_quantity=_coerce_quantity(
                    market.get("no_bid_size_fp", market.get("no_bid_size")),
                ) or 0.0,
                top_level_quantity=_coerce_quantity(
                    market.get("no_bid_size_fp", market.get("no_bid_size")),
                ),
            ) if _coerce_quantity(
                market.get("no_bid_size_fp", market.get("no_bid_size")),
            ) is not None else None,
            no_ask_depth=DepthSummary(
                levels=1,
                visible_quantity=_coerce_quantity(
                    market.get("no_ask_size_fp", market.get("no_ask_size")),
                ) or 0.0,
                top_level_quantity=_coerce_quantity(
                    market.get("no_ask_size_fp", market.get("no_ask_size")),
                ),
            ) if _coerce_quantity(
                market.get("no_ask_size_fp", market.get("no_ask_size")),
            ) is not None else None,
            yes_price=yes_price,
            no_price=no_price,
            derived_price_kind=(
                "last_trade"
                if _coerce_price(market.get("last_price_dollars", market.get("last_price"))) is not None
                else "midpoint_from_quotes"
                if market.get("yes_ask_dollars") is not None and yes_price is not None
                else "best_yes_bid_snapshot"
                if yes_price is not None else None
            ),
            data_environment=self.venue_environment,
        )

    async def get_orderbook(self, ticker: str) -> Orderbook:
        data = await self._request("GET", f"/markets/{ticker}/orderbook")
        raw_orderbook = data.get("orderbook_fp") or data.get("orderbook") or {}

        yes_bids = [
            OrderbookLevel(
                price=_coerce_price(level[0] if isinstance(level, list) else level.get("price")) or 0.0,
                quantity=_coerce_quantity(level[1] if isinstance(level, list) else level.get("quantity")) or 0.0,
            )
            for level in raw_orderbook.get("yes", raw_orderbook.get("yes_dollars", []))
        ]
        no_bids = [
            OrderbookLevel(
                price=_coerce_price(level[0] if isinstance(level, list) else level.get("price")) or 0.0,
                quantity=_coerce_quantity(level[1] if isinstance(level, list) else level.get("quantity")) or 0.0,
            )
            for level in raw_orderbook.get("no", raw_orderbook.get("no_dollars", []))
        ]

        # Kalshi does not publish asks directly; asks are the cross of the
        # opposite-side bids, sorted from best executable price outward.
        yes_asks = [
            OrderbookLevel(price=min(max(1.0 - level.price, 0.0), 1.0), quantity=level.quantity)
            for level in no_bids
        ]
        no_asks = [
            OrderbookLevel(price=min(max(1.0 - level.price, 0.0), 1.0), quantity=level.quantity)
            for level in yes_bids
        ]
        yes_asks.sort(key=lambda level: level.price)
        no_asks.sort(key=lambda level: level.price)

        return Orderbook(
            ticker=ticker,
            venue_timestamp=_parse_ts(data.get("market_time")),
            quote_timestamp=_parse_ts(data.get("timestamp")),
            yes_bids=yes_bids,
            yes_asks=yes_asks,
            no_bids=no_bids,
            no_asks=no_asks,
        )

    async def get_market_price(self, ticker: str) -> MarketPrice:
        data = await self._request("GET", f"/markets/{ticker}")
        market = data.get("market", data)
        return self._normalize_market_snapshot(market)

    async def place_order(
        self,
        ticker: str,
        side: str,
        quantity: int,
        price: int,
    ) -> dict:
        payload = {
            "ticker": ticker,
            "action": "buy",
            "side": side,
            "count": quantity,
            "type": "limit",
            "yes_price" if side == "yes" else "no_price": price,
        }
        return await self._request("POST", "/portfolio/orders", json=payload)

    async def get_order(self, order_id: str) -> dict:
        return await self._request("GET", f"/portfolio/orders/{order_id}")

    async def cancel_order(self, order_id: str) -> dict:
        return await self._request("DELETE", f"/portfolio/orders/{order_id}")

    async def get_positions(self) -> list[Position]:
        data = await self._request("GET", "/portfolio/positions")
        positions = []
        for pos in data.get("market_positions", []):
            positions.append(
                Position(
                    ticker=pos.get("ticker", ""),
                    side="yes" if pos.get("position", 0) > 0 else "no",
                    quantity=abs(float(pos.get("position", 0))),
                    avg_price=float(pos.get("average_price", 0) or 0) / 100.0,
                    market_price=float(pos.get("market_price", 0) or 0) / 100.0,
                    unrealized_pnl=float(pos.get("unrealized_pnl", 0) or 0) / 100.0,
                ),
            )
        return positions

    async def get_balance(self) -> float:
        data = await self._request("GET", "/portfolio/balance")
        return data.get("balance", 0) / 100.0

    def depth_summary_from_orderbook(self, orderbook: Orderbook) -> dict[str, dict[str, float] | None]:
        return {
            "yes_bid": _depth_summary(orderbook.yes_bids).model_dump() if _depth_summary(orderbook.yes_bids) else None,
            "yes_ask": _depth_summary(orderbook.yes_asks).model_dump() if _depth_summary(orderbook.yes_asks) else None,
            "no_bid": _depth_summary(orderbook.no_bids).model_dump() if _depth_summary(orderbook.no_bids) else None,
            "no_ask": _depth_summary(orderbook.no_asks).model_dump() if _depth_summary(orderbook.no_asks) else None,
        }
