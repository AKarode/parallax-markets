"""Kalshi prediction market API client with RSA-PSS authentication.

Uses the Kalshi Trade API v2. Defaults to the paper trading sandbox.
Private key material is loaded from a file path (never logged or committed).
"""

from __future__ import annotations

import base64
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from parallax.markets.schemas import MarketPrice, Orderbook, OrderbookLevel, Position

logger = logging.getLogger(__name__)

# Target event tickers for Iran/Hormuz crisis
IRAN_EVENT_TICKERS = [
    "KXCLOSEHORMUZ-27JAN",       # Strait of Hormuz closure
    "KXUSAIRANAGREEMENT-27",     # US-Iran nuclear deal
    "KXIRANDEMOCRACY-27MAR01",   # Iran democracy
    "KXELECTIRAN",               # Iran presidential election
    "KXPAHLAVIHEAD-27JAN",       # Pahlavi leads Iran
    "KXPAHLAVIVISITA",           # Pahlavi visits Iran
    "KXIRANEMBASSY-27",          # US reopens Iran embassy
    "KXRECOGPERSONIRAN-26",      # US recognizes Pahlavi
    "KXNEXTIRANLEADER-45JAN01",  # Next Supreme Leader
    "KXWTIMAX-26DEC31",          # Oil (WTI) high by year end
    "KXWTIMIN-26DEC31",          # Oil (WTI) low by year end
    "KXOILRIGS-26",              # US oil rigs end of 2026
]

# Search keywords for discovering new markets
IRAN_KEYWORDS = ["iran", "hormuz", "ceasefire", "oil", "crude", "wti", "brent"]

# Legacy series constants (for backwards compat)
HORMUZ_SERIES = "KXCLOSEHORMUZ"
IRAN_CEASEFIRE_SERIES = "KXIRANCEASEFIRE"
OIL_PRICE_SERIES = "KXOIL"


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

    @staticmethod
    def _load_private_key(path: str):
        """Load RSA private key from PEM file."""
        pem_data = Path(path).read_bytes()
        return serialization.load_pem_private_key(pem_data, password=None)

    def _sign_request(self, method: str, path: str) -> dict[str, str]:
        """Generate RSA-PSS signed auth headers for a request.

        Signs: timestamp + method + path
        Returns dict with KALSHI-ACCESS-KEY, KALSHI-ACCESS-SIGNATURE, KALSHI-ACCESS-TIMESTAMP.
        """
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
        """Make an authenticated request to the Kalshi API."""
        headers = self._sign_request(method, path)
        url = self._base_url + path
        logger.debug("Kalshi %s %s", method, path)

        async with httpx.AsyncClient() as client:
            resp = await client.request(
                method, url, headers=headers, json=json, params=params,
            )

        if resp.status_code >= 400:
            raise KalshiAPIError(resp.status_code, resp.text)
        return resp.json()

    async def get_markets(self, series_ticker: str | None = None) -> list[dict]:
        """Fetch markets, optionally filtered by series ticker."""
        params = {}
        if series_ticker:
            params["series_ticker"] = series_ticker
        data = await self._request("GET", "/markets", params=params)
        return data.get("markets", [])

    async def search_markets(self, query: str) -> list[dict]:
        """Search markets by keyword (e.g., 'Iran', 'oil', 'Hormuz')."""
        params = {"status": "open"}
        data = await self._request("GET", "/markets", params=params)
        markets = data.get("markets", [])
        q = query.lower()
        return [
            m for m in markets
            if q in m.get("title", "").lower()
            or q in m.get("ticker", "").lower()
            or q in m.get("subtitle", "").lower()
        ]

    async def get_orderbook(self, ticker: str) -> Orderbook:
        """Fetch the orderbook for a specific market ticker."""
        data = await self._request("GET", f"/markets/{ticker}/orderbook")
        ob = data.get("orderbook", {})
        return Orderbook(
            ticker=ticker,
            yes_bids=[OrderbookLevel(**lvl) for lvl in ob.get("yes", [])],
            yes_asks=[OrderbookLevel(**lvl) for lvl in ob.get("no", [])],
            no_bids=[],
            no_asks=[],
        )

    async def get_market_price(self, ticker: str) -> MarketPrice:
        """Fetch the current market price for a ticker."""
        data = await self._request("GET", f"/markets/{ticker}")
        market = data.get("market", data)
        # v2 API uses _dollars suffix fields (float, 0.0-1.0)
        yes_price = float(market.get("yes_bid_dollars", 0) or market.get("last_price_dollars", 0) or 0)
        no_price = float(market.get("no_bid_dollars", 0) or 0)
        if yes_price > 0 and no_price == 0:
            no_price = 1.0 - yes_price
        volume = float(market.get("volume_fp", 0) or market.get("volume", 0) or 0)
        title = market.get("title", ticker)
        return MarketPrice(
            ticker=ticker,
            source="kalshi",
            yes_price=yes_price,
            no_price=no_price,
            volume=volume,
            fetched_at=datetime.now(timezone.utc),
        )

    async def place_order(
        self, ticker: str, side: str, quantity: int, price: int,
    ) -> dict:
        """Place an order on the Kalshi sandbox.

        Args:
            ticker: Market ticker.
            side: "yes" or "no".
            quantity: Number of contracts.
            price: Limit price in cents (1-99).
        """
        payload = {
            "ticker": ticker,
            "action": "buy",
            "side": side,
            "count": quantity,
            "type": "limit",
            "yes_price" if side == "yes" else "no_price": price,
        }
        return await self._request("POST", "/portfolio/orders", json=payload)

    async def get_positions(self) -> list[Position]:
        """Fetch current portfolio positions."""
        data = await self._request("GET", "/portfolio/positions")
        positions = []
        for pos in data.get("market_positions", []):
            positions.append(Position(
                ticker=pos.get("ticker", ""),
                side="yes" if pos.get("position", 0) > 0 else "no",
                quantity=abs(pos.get("position", 0)),
                avg_price=pos.get("average_price", 0) / 100.0,
                market_price=pos.get("market_price", 0) / 100.0,
                unrealized_pnl=pos.get("unrealized_pnl", 0) / 100.0,
            ))
        return positions

    async def get_balance(self) -> float:
        """Fetch account balance in USD."""
        data = await self._request("GET", "/portfolio/balance")
        return data.get("balance", 0) / 100.0
