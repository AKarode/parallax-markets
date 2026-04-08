"""Tests for Kalshi API client — RSA-PSS auth and mocked API responses."""

from __future__ import annotations

import base64
import json
import tempfile

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from parallax.markets.kalshi import KalshiClient, KalshiAPIError


@pytest.fixture()
def rsa_keypair(tmp_path):
    """Generate a test RSA keypair and write private key to a temp file."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    key_path = tmp_path / "test_key.pem"
    key_path.write_bytes(pem)
    return private_key, str(key_path)


@pytest.fixture()
def client(rsa_keypair):
    """Create a KalshiClient with test keypair."""
    _, key_path = rsa_keypair
    return KalshiClient(
        api_key="test-api-key",
        private_key_path=key_path,
        base_url="https://demo-api.kalshi.co/trade-api/v2",
    )


class TestRSAPSSSignature:
    """Test RSA-PSS signature generation."""

    def test_sign_request_returns_required_headers(self, client):
        headers = client._sign_request("GET", "/markets")
        assert "KALSHI-ACCESS-KEY" in headers
        assert "KALSHI-ACCESS-SIGNATURE" in headers
        assert "KALSHI-ACCESS-TIMESTAMP" in headers
        assert headers["KALSHI-ACCESS-KEY"] == "test-api-key"

    def test_signature_is_valid_base64(self, client):
        headers = client._sign_request("GET", "/markets")
        sig = headers["KALSHI-ACCESS-SIGNATURE"]
        # Should not raise
        decoded = base64.b64decode(sig)
        assert len(decoded) > 0

    def test_signature_verifies_with_public_key(self, rsa_keypair, client):
        private_key, _ = rsa_keypair
        public_key = private_key.public_key()

        headers = client._sign_request("GET", "/markets")
        timestamp = headers["KALSHI-ACCESS-TIMESTAMP"]
        sig = base64.b64decode(headers["KALSHI-ACCESS-SIGNATURE"])
        message = (timestamp + "GET" + "/markets").encode("utf-8")

        # Should not raise InvalidSignature
        public_key.verify(
            sig,
            message,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH,
            ),
            hashes.SHA256(),
        )

    def test_timestamp_is_milliseconds(self, client):
        headers = client._sign_request("GET", "/test")
        ts = int(headers["KALSHI-ACCESS-TIMESTAMP"])
        # Should be in milliseconds (13+ digits)
        assert ts > 1_000_000_000_000


class TestKalshiClientMocked:
    """Test API methods with mocked httpx responses."""

    @pytest.fixture(autouse=True)
    def _patch_httpx(self, monkeypatch, client):
        self.client = client
        self._responses: list[tuple[int, dict]] = []

        class MockResponse:
            def __init__(self, status_code, data):
                self.status_code = status_code
                self._data = data
                self.text = json.dumps(data)

            def json(self):
                return self._data

        class MockAsyncClient:
            def __init__(inner_self):
                pass

            async def __aenter__(inner_self):
                return inner_self

            async def __aexit__(inner_self, *args):
                pass

            async def request(inner_self, method, url, **kwargs):
                if self._responses:
                    code, data = self._responses.pop(0)
                    return MockResponse(code, data)
                return MockResponse(200, {})

        monkeypatch.setattr("parallax.markets.kalshi.httpx.AsyncClient", MockAsyncClient)

    async def test_get_markets(self):
        self._responses = [(200, {
            "markets": [
                {"ticker": "HORMUZ-26APR15", "title": "Hormuz closure"},
                {"ticker": "OIL-26APR15", "title": "Oil above $80"},
            ],
        })]
        markets = await self.client.get_markets()
        assert len(markets) == 2
        assert markets[0]["ticker"] == "HORMUZ-26APR15"

    async def test_get_markets_with_series_filter(self):
        self._responses = [(200, {"markets": [{"ticker": "HORMUZ-26APR15"}]})]
        markets = await self.client.get_markets(series_ticker="KXCLOSEHORMUZ")
        assert len(markets) == 1

    async def test_get_market_price(self):
        self._responses = [(200, {
            "market": {
                "ticker": "HORMUZ-26APR15",
                "yes_bid_dollars": 0.35,
                "no_bid_dollars": 0.62,
                "volume_fp": 5000,
            },
        })]
        price = await self.client.get_market_price("HORMUZ-26APR15")
        assert price.ticker == "HORMUZ-26APR15"
        assert price.source == "kalshi"
        assert price.yes_price == 0.35
        assert price.no_price == 0.62
        assert price.volume == 5000.0

    async def test_get_orderbook(self):
        self._responses = [(200, {
            "orderbook": {
                "yes": [{"price": 35, "quantity": 100}],
                "no": [{"price": 65, "quantity": 50}],
            },
        })]
        ob = await self.client.get_orderbook("HORMUZ-26APR15")
        assert ob.ticker == "HORMUZ-26APR15"
        assert len(ob.yes_bids) == 1
        assert ob.yes_bids[0].price == 35

    async def test_place_order(self):
        self._responses = [(200, {"order": {"order_id": "abc123", "status": "pending"}})]
        result = await self.client.place_order("HORMUZ-26APR15", "yes", 10, 35)
        assert result["order"]["order_id"] == "abc123"

    async def test_get_positions(self):
        self._responses = [(200, {
            "market_positions": [
                {
                    "ticker": "HORMUZ-26APR15",
                    "position": 10,
                    "average_price": 3500,
                    "market_price": 4000,
                    "unrealized_pnl": 500,
                },
            ],
        })]
        positions = await self.client.get_positions()
        assert len(positions) == 1
        assert positions[0].ticker == "HORMUZ-26APR15"
        assert positions[0].side == "yes"
        assert positions[0].quantity == 10

    async def test_get_balance(self):
        self._responses = [(200, {"balance": 100000})]
        balance = await self.client.get_balance()
        assert balance == 1000.0

    async def test_api_error_raises(self):
        self._responses = [(403, {"error": "Forbidden"})]
        with pytest.raises(KalshiAPIError) as exc_info:
            await self.client.get_markets()
        assert exc_info.value.status_code == 403
