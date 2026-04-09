"""Tests for resolution checker -- Kalshi settlement polling and signal_ledger backfill."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import duckdb
import pytest

from parallax.db.schema import create_tables


@pytest.fixture
def conn():
    """In-memory DuckDB connection with schema created."""
    c = duckdb.connect(":memory:")
    create_tables(c)
    return c


def _insert_signal(conn, ticker: str, signal: str, market_yes_price: float,
                   market_no_price: float, resolution_price=None,
                   resolved_at=None, realized_pnl=None, model_was_correct=None):
    """Insert a minimal signal_ledger row for testing."""
    signal_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO signal_ledger
        (signal_id, created_at, model_id, model_claim, model_probability,
         model_timeframe, contract_ticker, proxy_class, confidence_discount,
         market_yes_price, market_no_price, entry_side, entry_price,
         raw_edge, effective_edge, signal, resolution_price, resolved_at,
         realized_pnl, model_was_correct)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [signal_id, now, "test_model", "test claim", 0.7, "7d",
         ticker, "direct", 1.0, market_yes_price, market_no_price,
         "yes" if signal == "BUY_YES" else "no",
         market_yes_price if signal == "BUY_YES" else market_no_price,
         0.1, 0.1, signal,
         resolution_price, resolved_at, realized_pnl, model_was_correct],
    )
    return signal_id


class TestCheckMarketResolution:
    """Test _check_market_resolution detection of settled markets."""

    async def test_detect_settled_market(self):
        """Finalized market should return resolution dict."""
        from parallax.scoring.resolution import _check_market_resolution

        mock_client = AsyncMock()
        mock_client._request = AsyncMock(return_value={
            "market": {
                "status": "finalized",
                "result": "yes",
                "settlement_value": "1.0",
                "settlement_ts": 1712600000,
            }
        })

        result = await _check_market_resolution(mock_client, "KXTEST-TICKER")

        assert result is not None
        assert result["resolution_price"] == 1.0
        assert result["result"] == "yes"
        assert result["status"] == "finalized"

    async def test_skip_unsettled_market(self):
        """Active market should return None."""
        from parallax.scoring.resolution import _check_market_resolution

        mock_client = AsyncMock()
        mock_client._request = AsyncMock(return_value={
            "market": {"status": "active"}
        })

        result = await _check_market_resolution(mock_client, "KXTEST-TICKER")

        assert result is None


class TestBackfillSignal:
    """Test _backfill_signal updates signal_ledger rows."""

    def test_backfill_updates_resolution_columns(self, conn):
        """BUY_YES with resolution_price=1.0 should have positive P&L."""
        from parallax.scoring.resolution import _backfill_signal

        _insert_signal(conn, "KXTEST-01", "BUY_YES",
                       market_yes_price=0.40, market_no_price=0.60)

        settled_at = datetime(2026, 4, 8, 12, 0, 0, tzinfo=timezone.utc)
        n = _backfill_signal(conn, "KXTEST-01", 1.0, settled_at)

        assert n == 1
        row = conn.execute(
            "SELECT resolution_price, realized_pnl, model_was_correct "
            "FROM signal_ledger WHERE contract_ticker = 'KXTEST-01'"
        ).fetchone()
        assert row[0] == 1.0  # resolution_price
        assert abs(row[1] - 0.60) < 0.001  # realized_pnl = 1.0 - 0.40
        assert row[2] is True  # model_was_correct

    def test_backfill_buy_no_pnl(self, conn):
        """BUY_NO with resolution result=no (price=0.0) should have positive P&L."""
        from parallax.scoring.resolution import _backfill_signal

        _insert_signal(conn, "KXTEST-02", "BUY_NO",
                       market_yes_price=0.40, market_no_price=0.60)

        settled_at = datetime(2026, 4, 8, 12, 0, 0, tzinfo=timezone.utc)
        n = _backfill_signal(conn, "KXTEST-02", 0.0, settled_at)

        assert n == 1
        row = conn.execute(
            "SELECT resolution_price, realized_pnl, model_was_correct "
            "FROM signal_ledger WHERE contract_ticker = 'KXTEST-02'"
        ).fetchone()
        assert row[0] == 0.0  # resolution_price
        # BUY_NO P&L: (1.0 - 0.0) - 0.60 = 0.40
        assert abs(row[1] - 0.40) < 0.001
        assert row[2] is True  # model_was_correct (BUY_NO and resolution <= 0.5)

    def test_backfill_skips_already_resolved(self, conn):
        """Already-resolved signals should not be double-updated."""
        from parallax.scoring.resolution import _backfill_signal

        resolved_at = datetime(2026, 4, 7, 12, 0, 0, tzinfo=timezone.utc).isoformat()
        _insert_signal(conn, "KXTEST-03", "BUY_YES",
                       market_yes_price=0.40, market_no_price=0.60,
                       resolution_price=1.0, resolved_at=resolved_at,
                       realized_pnl=0.60, model_was_correct=True)

        new_settled_at = datetime(2026, 4, 8, 12, 0, 0, tzinfo=timezone.utc)
        n = _backfill_signal(conn, "KXTEST-03", 0.0, new_settled_at)

        assert n == 0  # No rows updated
        row = conn.execute(
            "SELECT resolution_price, realized_pnl FROM signal_ledger "
            "WHERE contract_ticker = 'KXTEST-03'"
        ).fetchone()
        assert row[0] == 1.0  # Unchanged
        assert abs(row[1] - 0.60) < 0.001  # Unchanged


class TestCheckResolutionsEndToEnd:
    """Test the full check_resolutions flow."""

    async def test_check_resolutions_end_to_end(self, conn):
        """Only finalized contracts should be backfilled."""
        from parallax.scoring.resolution import check_resolutions

        _insert_signal(conn, "KXRESOLVED-01", "BUY_YES",
                       market_yes_price=0.40, market_no_price=0.60)
        _insert_signal(conn, "KXACTIVE-01", "BUY_NO",
                       market_yes_price=0.50, market_no_price=0.50)

        mock_client = AsyncMock()

        async def mock_request(method, path, **kwargs):
            if "KXRESOLVED-01" in path:
                return {"market": {
                    "status": "finalized",
                    "result": "yes",
                    "settlement_value": "1.0",
                    "settlement_ts": 1712600000,
                }}
            elif "KXACTIVE-01" in path:
                return {"market": {"status": "active"}}
            return {"market": {"status": "active"}}

        mock_client._request = AsyncMock(side_effect=mock_request)

        results = await check_resolutions(conn, mock_client)

        assert len(results) == 1
        assert results[0]["ticker"] == "KXRESOLVED-01"

        # Verify resolved signal was backfilled
        row = conn.execute(
            "SELECT resolution_price, model_was_correct FROM signal_ledger "
            "WHERE contract_ticker = 'KXRESOLVED-01'"
        ).fetchone()
        assert row[0] == 1.0
        assert row[1] is True

        # Verify active signal was NOT backfilled
        row = conn.execute(
            "SELECT resolution_price FROM signal_ledger "
            "WHERE contract_ticker = 'KXACTIVE-01'"
        ).fetchone()
        assert row[0] is None
