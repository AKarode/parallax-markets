"""Tests for build_track_record() shared utility."""

from __future__ import annotations

from datetime import datetime, timezone

import duckdb
import pytest

from parallax.db.schema import create_tables
from parallax.scoring.track_record import build_track_record


@pytest.fixture()
def conn():
    """Create an in-memory DuckDB connection with schema."""
    c = duckdb.connect(":memory:")
    create_tables(c)
    yield c
    c.close()


def _insert_resolved_signal(
    conn: duckdb.DuckDBPyConnection,
    signal_id: str,
    model_id: str,
    contract_ticker: str,
    model_probability: float,
    resolution_price: float,
    model_was_correct: bool,
    signal: str,
    resolved_at: datetime | None = None,
) -> None:
    """Insert a resolved signal into the ledger for testing."""
    resolved = resolved_at or datetime.now(timezone.utc)
    conn.execute(
        """
        INSERT INTO signal_ledger (
            signal_id, created_at, model_id, model_claim, model_probability,
            model_timeframe, contract_ticker, proxy_class, confidence_discount,
            market_yes_price, market_no_price, raw_edge, effective_edge,
            signal, resolution_price, resolved_at, model_was_correct
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            signal_id,
            datetime.now(timezone.utc),
            model_id,
            f"{model_id}: test claim",
            model_probability,
            "7d",
            contract_ticker,
            "direct",
            1.0,
            0.50,
            0.50,
            0.10,
            0.10,
            signal,
            resolution_price,
            resolved,
            model_was_correct,
        ],
    )


class TestBuildTrackRecordEmpty:
    """Test with no resolved signals."""

    def test_no_resolved_signals_returns_fallback(self, conn):
        result = build_track_record("oil_price", conn)
        assert result == "No track record available yet."

    def test_nonexistent_model_returns_fallback(self, conn):
        result = build_track_record("nonexistent", conn)
        assert result == "No track record available yet."


class TestBuildTrackRecordWithData:
    """Test with resolved signal data."""

    def test_aggregate_stats_correct(self, conn):
        """5 resolved signals, 3 correct -> '3/5 correct (60% hit rate)'."""
        for i in range(5):
            _insert_resolved_signal(
                conn,
                signal_id=f"sig-{i}",
                model_id="oil_price",
                contract_ticker=f"KXWTI-{i}",
                model_probability=0.70,
                resolution_price=1.0 if i < 3 else 0.0,
                model_was_correct=i < 3,
                signal="BUY_YES",
            )
        result = build_track_record("oil_price", conn)
        assert "3/5 correct" in result
        assert "60%" in result

    def test_last_three_signals_shown(self, conn):
        """Output includes last 3 resolved signals with ticker."""
        for i in range(5):
            _insert_resolved_signal(
                conn,
                signal_id=f"sig-{i}",
                model_id="oil_price",
                contract_ticker=f"KXWTI-{i}",
                model_probability=0.70,
                resolution_price=1.0 if i < 3 else 0.0,
                model_was_correct=i < 3,
                signal="BUY_YES",
                resolved_at=datetime(2026, 4, 1 + i, tzinfo=timezone.utc),
            )
        result = build_track_record("oil_price", conn)
        # Last 3 by resolved_at DESC: sig-4, sig-3, sig-2
        assert "KXWTI-4" in result
        assert "KXWTI-3" in result
        assert "KXWTI-2" in result

    def test_correct_wrong_labels(self, conn):
        """Output shows CORRECT/WRONG labels."""
        _insert_resolved_signal(
            conn,
            signal_id="sig-correct",
            model_id="ceasefire",
            contract_ticker="KXAGREE-1",
            model_probability=0.80,
            resolution_price=1.0,
            model_was_correct=True,
            signal="BUY_YES",
        )
        _insert_resolved_signal(
            conn,
            signal_id="sig-wrong",
            model_id="ceasefire",
            contract_ticker="KXAGREE-2",
            model_probability=0.80,
            resolution_price=0.0,
            model_was_correct=False,
            signal="BUY_YES",
        )
        result = build_track_record("ceasefire", conn)
        assert "CORRECT" in result
        assert "WRONG" in result

    def test_only_returns_specified_model(self, conn):
        """Per D-11: per-model only -- no cross-model stats."""
        _insert_resolved_signal(
            conn,
            signal_id="sig-oil",
            model_id="oil_price",
            contract_ticker="KXWTI-1",
            model_probability=0.70,
            resolution_price=1.0,
            model_was_correct=True,
            signal="BUY_YES",
        )
        _insert_resolved_signal(
            conn,
            signal_id="sig-cease",
            model_id="ceasefire",
            contract_ticker="KXAGREE-1",
            model_probability=0.60,
            resolution_price=0.0,
            model_was_correct=False,
            signal="BUY_NO",
        )
        oil_result = build_track_record("oil_price", conn)
        assert "KXWTI-1" in oil_result
        assert "KXAGREE-1" not in oil_result

        cease_result = build_track_record("ceasefire", conn)
        assert "KXAGREE-1" in cease_result
        assert "KXWTI-1" not in cease_result

    def test_output_under_1600_chars(self, conn):
        """Output should be under ~400 tokens (~1600 chars)."""
        for i in range(20):
            _insert_resolved_signal(
                conn,
                signal_id=f"sig-{i}",
                model_id="oil_price",
                contract_ticker=f"KXWTI-{i}",
                model_probability=0.70,
                resolution_price=1.0,
                model_was_correct=True,
                signal="BUY_YES",
            )
        result = build_track_record("oil_price", conn)
        assert len(result) < 1600

    def test_signal_direction_shown(self, conn):
        """Output includes signal direction (BUY_YES/BUY_NO)."""
        _insert_resolved_signal(
            conn,
            signal_id="sig-1",
            model_id="oil_price",
            contract_ticker="KXWTI-1",
            model_probability=0.70,
            resolution_price=1.0,
            model_was_correct=True,
            signal="BUY_YES",
        )
        result = build_track_record("oil_price", conn)
        assert "BUY_YES" in result
