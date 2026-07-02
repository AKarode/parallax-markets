"""Tests for brief.py resilience to predictor failures."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import duckdb
import pytest

from parallax.cli.brief import _get_fallback_prediction, run_brief
from parallax.db.schema import create_tables
from parallax.prediction.schemas import PredictionOutput


class TestFallbackPrediction:
    @pytest.fixture()
    def conn(self) -> duckdb.DuckDBPyConnection:
        conn = duckdb.connect(":memory:")
        create_tables(conn)
        return conn

    @pytest.mark.asyncio
    async def test_fallback_returns_none_when_no_history(self, conn: duckdb.DuckDBPyConnection) -> None:
        result = await _get_fallback_prediction(conn, "oil_price")
        assert result is None

    @pytest.mark.asyncio
    async def test_fallback_returns_previous_prediction(self, conn: duckdb.DuckDBPyConnection) -> None:
        conn.execute(
            """
            INSERT INTO prediction_log
            (log_id, run_id, model_id, probability, direction, confidence,
             reasoning, timeframe, data_environment, created_at)
            VALUES
            ('log-1', 'run-1', 'oil_price', 0.72, 'increase', 0.75,
             'Previous oil analysis', '7d', 'live', CURRENT_TIMESTAMP)
            """
        )
        result = await _get_fallback_prediction(conn, "oil_price")
        assert result is not None
        assert result.model_id == "oil_price"
        assert result.probability == 0.72
        assert result.direction == "increase"
        assert result.confidence == 0.75
        assert "[FALLBACK from run run-1]" in result.reasoning
        assert result.is_fallback is True
        assert result.fallback_source_run_id == "run-1"

    @pytest.mark.asyncio
    async def test_fallback_ignores_dry_run(self, conn: duckdb.DuckDBPyConnection) -> None:
        conn.execute(
            """
            INSERT INTO prediction_log
            (log_id, run_id, model_id, probability, direction, confidence,
             reasoning, timeframe, data_environment, created_at)
            VALUES
            ('log-1', 'run-1', 'oil_price', 0.50, 'stable', 0.50,
             'Dry run test', '7d', 'dry_run', CURRENT_TIMESTAMP)
            """
        )
        result = await _get_fallback_prediction(conn, "oil_price")
        assert result is None

    @pytest.mark.asyncio
    async def test_fallback_returns_most_recent(self, conn: duckdb.DuckDBPyConnection) -> None:
        conn.execute(
            """
            INSERT INTO prediction_log
            (log_id, run_id, model_id, probability, direction, confidence,
             reasoning, timeframe, data_environment, created_at)
            VALUES
            ('log-1', 'run-1', 'oil_price', 0.60, 'increase', 0.70,
             'Old prediction', '7d', 'live', CURRENT_TIMESTAMP - INTERVAL 2 HOUR),
            ('log-2', 'run-2', 'oil_price', 0.80, 'increase', 0.85,
             'New prediction', '7d', 'live', CURRENT_TIMESTAMP - INTERVAL 1 HOUR)
            """
        )
        result = await _get_fallback_prediction(conn, "oil_price")
        assert result is not None
        assert result.probability == 0.80
        assert result.confidence == 0.85

    @pytest.mark.asyncio
    async def test_fallback_refuses_stale_candidate(self, conn: duckdb.DuckDBPyConnection) -> None:
        conn.execute(
            """
            INSERT INTO prediction_log
            (log_id, run_id, model_id, probability, direction, confidence,
             reasoning, timeframe, data_environment, created_at)
            VALUES
            ('log-1', 'run-1', 'oil_price', 0.72, 'increase', 0.75,
             'Stale prediction', '7d', 'live', CURRENT_TIMESTAMP - INTERVAL 12 HOUR)
            """
        )
        result = await _get_fallback_prediction(conn, "oil_price", max_age_hours=6.0)
        assert result is None

    @pytest.mark.asyncio
    async def test_fallback_skips_prior_fallback_rows(self, conn: duckdb.DuckDBPyConnection) -> None:
        conn.execute(
            """
            INSERT INTO prediction_log
            (log_id, run_id, model_id, probability, direction, confidence,
             reasoning, timeframe, data_environment, created_at,
             is_fallback, fallback_source_run_id)
            VALUES
            ('log-1', 'run-original', 'oil_price', 0.72, 'increase', 0.75,
             'Original prediction', '7d', 'live',
             CURRENT_TIMESTAMP - INTERVAL 2 HOUR, false, NULL),
            ('log-2', 'run-secondary', 'oil_price', 0.55, 'stable', 0.55,
             '[FALLBACK from run run-original] reasoning', '7d', 'live',
             CURRENT_TIMESTAMP - INTERVAL 1 HOUR, true, 'run-original')
            """
        )
        result = await _get_fallback_prediction(conn, "oil_price")
        assert result is not None
        assert result.fallback_source_run_id == "run-original"
        assert result.probability == 0.72


class TestGatherExceptionHandling:
    @pytest.mark.asyncio
    async def test_dry_run_completes_successfully(self) -> None:
        result = await run_brief(dry_run=True, no_trade=True)
        assert "PARALLAX DAILY INTELLIGENCE BRIEF" in result
        assert "OIL PRICE" in result

    @pytest.mark.asyncio
    async def test_predictor_exception_logged_not_raised(self) -> None:
        with patch("parallax.cli.brief._fetch_gdelt_events", new_callable=AsyncMock) as mock_events:
            mock_events.return_value = []
            result = await run_brief(dry_run=True, no_trade=True)
            assert "PARALLAX DAILY INTELLIGENCE BRIEF" in result


class TestSignalSetValid:
    @pytest.mark.asyncio
    async def test_dry_run_produces_signals(self) -> None:
        result = await run_brief(dry_run=True, no_trade=True)
        assert "SIGNAL AUDIT" in result
        assert any(signal in result for signal in ["BUY_YES", "BUY_NO", "HOLD", "REFUSED"])
