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
        """12 resolved signals, 7 correct -> '7/12 correct (58% hit rate)'."""
        for i in range(12):
            _insert_resolved_signal(
                conn,
                signal_id=f"sig-{i}",
                model_id="oil_price",
                contract_ticker=f"KXWTI-{i}",
                model_probability=0.70,
                resolution_price=1.0 if i < 7 else 0.0,
                model_was_correct=i < 7,
                signal="BUY_YES",
            )
        result = build_track_record("oil_price", conn)
        assert "7/12 correct" in result
        assert "58%" in result

    def test_last_three_signals_shown(self, conn):
        """Output includes last 3 resolved signals with ticker."""
        for i in range(12):
            _insert_resolved_signal(
                conn,
                signal_id=f"sig-{i}",
                model_id="oil_price",
                contract_ticker=f"KXWTI-{i}",
                model_probability=0.70,
                resolution_price=1.0 if i < 7 else 0.0,
                model_was_correct=i < 7,
                signal="BUY_YES",
                resolved_at=datetime(2026, 4, 1 + i, tzinfo=timezone.utc),
            )
        result = build_track_record("oil_price", conn)
        # Last 3 by resolved_at DESC: sig-11, sig-10, sig-9
        assert "KXWTI-11" in result
        assert "KXWTI-10" in result
        assert "KXWTI-9" in result

    def test_correct_wrong_labels(self, conn):
        """Output shows CORRECT/WRONG labels."""
        for i in range(10):
            _insert_resolved_signal(
                conn,
                signal_id=f"sig-cw-{i}",
                model_id="ceasefire",
                contract_ticker=f"KXAGREE-{i}",
                model_probability=0.80,
                resolution_price=1.0 if i < 8 else 0.0,
                model_was_correct=i < 8,
                signal="BUY_YES",
                resolved_at=datetime(2026, 4, 1 + i, tzinfo=timezone.utc),
            )
        result = build_track_record("ceasefire", conn)
        assert "CORRECT" in result
        assert "WRONG" in result

    def test_only_returns_specified_model(self, conn):
        """Per D-11: per-model only -- no cross-model stats."""
        for i in range(10):
            _insert_resolved_signal(
                conn,
                signal_id=f"sig-oil-{i}",
                model_id="oil_price",
                contract_ticker=f"KXWTI-{i}",
                model_probability=0.70,
                resolution_price=1.0 if i < 7 else 0.0,
                model_was_correct=i < 7,
                signal="BUY_YES",
            )
        for i in range(10):
            _insert_resolved_signal(
                conn,
                signal_id=f"sig-cease-{i}",
                model_id="ceasefire",
                contract_ticker=f"KXAGREE-{i}",
                model_probability=0.60,
                resolution_price=0.0,
                model_was_correct=False,
                signal="BUY_NO",
            )
        oil_result = build_track_record("oil_price", conn)
        assert "7/10 correct" in oil_result
        assert "KXAGREE" not in oil_result

        cease_result = build_track_record("ceasefire", conn)
        assert "0/10 correct" in cease_result
        assert "KXWTI" not in cease_result

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
        for i in range(10):
            _insert_resolved_signal(
                conn,
                signal_id=f"sig-dir-{i}",
                model_id="oil_price",
                contract_ticker=f"KXWTI-DIR-{i}",
                model_probability=0.70,
                resolution_price=1.0,
                model_was_correct=True,
                signal="BUY_YES",
            )
        result = build_track_record("oil_price", conn)
        assert "BUY_YES" in result


class TestBuildTrackRecordSmallSample:
    """Test sample size guard for n<10."""

    def test_fewer_than_10_returns_informational(self, conn):
        """With 5 resolved signals, should return informational text without stats."""
        for i in range(5):
            _insert_resolved_signal(
                conn,
                signal_id=f"sig-small-{i}",
                model_id="oil_price",
                contract_ticker=f"KXWTI-SMALL-{i}",
                model_probability=0.70,
                resolution_price=1.0 if i < 3 else 0.0,
                model_was_correct=i < 3,
                signal="BUY_YES",
            )
        result = build_track_record("oil_price", conn)
        assert "too few" in result
        assert "minimum 10" in result
        assert "hit rate" not in result.lower()

    def test_exactly_10_returns_full_stats(self, conn):
        """With exactly 10 resolved signals, should return full statistics."""
        for i in range(10):
            _insert_resolved_signal(
                conn,
                signal_id=f"sig-ten-{i}",
                model_id="oil_price",
                contract_ticker=f"KXWTI-TEN-{i}",
                model_probability=0.70,
                resolution_price=1.0 if i < 7 else 0.0,
                model_was_correct=i < 7,
                signal="BUY_YES",
            )
        result = build_track_record("oil_price", conn)
        assert "7/10 correct" in result
        assert "70%" in result
