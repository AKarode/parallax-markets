"""Tests for report card module -- P&L reporting with proxy class segmentation."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta

import duckdb
import pytest

from parallax.db.schema import create_tables


@pytest.fixture
def conn():
    """In-memory DuckDB connection with schema created."""
    c = duckdb.connect(":memory:")
    create_tables(c)
    return c


def _insert_resolved_signal(
    conn,
    model_id: str = "test_model",
    proxy_class: str = "DIRECT",
    signal: str = "BUY_YES",
    market_yes_price: float = 0.40,
    market_no_price: float = 0.60,
    effective_edge: float = 0.10,
    resolution_price: float = 1.0,
    realized_pnl: float = 0.60,
    model_was_correct: bool = True,
    proxy_was_aligned: bool = True,
    created_at: datetime | None = None,
    resolved_at: datetime | None = None,
):
    """Insert a closed traded position plus its originating signal."""
    signal_id = str(uuid.uuid4())
    position_id = str(uuid.uuid4())
    now = created_at or datetime.now(timezone.utc)
    res_at = resolved_at or (now + timedelta(hours=12))
    ticker = f"KXTEST-{signal_id[:6]}"
    side = "yes" if signal == "BUY_YES" else "no"
    entry_price = market_yes_price if side == "yes" else market_no_price
    conn.execute(
        """
        INSERT INTO signal_ledger
        (signal_id, created_at, model_id, model_claim, model_probability,
         model_timeframe, contract_ticker, proxy_class, confidence_discount,
         market_yes_price, market_no_price, entry_side, entry_price, position_id,
         trade_id, traded, raw_edge, effective_edge, signal, resolution_price,
         resolved_at, realized_pnl, counterfactual_pnl, model_was_correct,
         proxy_was_aligned)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            signal_id, now.isoformat(), model_id, "test claim", 0.7, "7d",
            ticker, proxy_class, 1.0, market_yes_price, market_no_price,
            side, entry_price, position_id, position_id, True, 0.1,
            effective_edge, signal, resolution_price, res_at.isoformat(),
            realized_pnl, realized_pnl, model_was_correct, proxy_was_aligned,
        ],
    )
    conn.execute(
        """
        INSERT INTO trade_positions
        (position_id, signal_id, run_id, ticker, venue, venue_environment, side,
         quantity, open_quantity, entry_price, opened_at, exit_price,
         settlement_price, closed_at, status, realized_pnl, unrealized_pnl,
         resolution_price, resolution_source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            position_id, signal_id, "run-1", ticker, "kalshi", "demo", side,
            1, 0, entry_price, now.isoformat(),
            resolution_price if side == "yes" else 1.0 - resolution_price,
            resolution_price if side == "yes" else 1.0 - resolution_price,
            res_at.isoformat(), "closed", realized_pnl, None,
            resolution_price, "test",
        ],
    )
    return signal_id


class TestGenerateReportCard:
    """Test generate_report_card() output formatting and content."""

    def test_report_contains_total_pnl_section(self, conn):
        """Report should include TOTAL P&L header."""
        from parallax.scoring.report_card import generate_report_card

        _insert_resolved_signal(conn, realized_pnl=0.60)
        report = generate_report_card(conn)
        assert "TOTAL P&L" in report

    def test_report_contains_win_rate_section(self, conn):
        """Report should include WIN RATE stat."""
        from parallax.scoring.report_card import generate_report_card

        _insert_resolved_signal(conn, realized_pnl=0.60, model_was_correct=True)
        _insert_resolved_signal(conn, realized_pnl=-0.40, model_was_correct=False)
        report = generate_report_card(conn)
        assert "WIN RATE" in report or "Win Rate" in report

    def test_report_contains_proxy_class_segmentation(self, conn):
        """Report should include BY PROXY CLASS section."""
        from parallax.scoring.report_card import generate_report_card

        _insert_resolved_signal(conn, proxy_class="DIRECT", realized_pnl=0.60)
        _insert_resolved_signal(conn, proxy_class="NEAR_PROXY", realized_pnl=0.30)
        _insert_resolved_signal(conn, proxy_class="LOOSE_PROXY", realized_pnl=-0.10)
        report = generate_report_card(conn)
        assert "BY PROXY CLASS" in report
        assert "DIRECT" in report
        assert "NEAR_PROXY" in report
        assert "LOOSE_PROXY" in report

    def test_report_sharpe_ratio(self, conn):
        """Report should include Sharpe-like ratio."""
        from parallax.scoring.report_card import generate_report_card

        _insert_resolved_signal(conn, realized_pnl=0.60)
        _insert_resolved_signal(conn, realized_pnl=0.30)
        _insert_resolved_signal(conn, realized_pnl=-0.10)
        report = generate_report_card(conn)
        assert "Sharpe" in report or "sharpe" in report

    def test_report_ztest_significance(self, conn):
        """Report should include z-test significance result."""
        from parallax.scoring.report_card import generate_report_card

        # Insert enough signals for a meaningful z-test
        for _ in range(10):
            _insert_resolved_signal(conn, realized_pnl=0.60, model_was_correct=True)
        for _ in range(2):
            _insert_resolved_signal(conn, realized_pnl=-0.40, model_was_correct=False)
        report = generate_report_card(conn)
        assert "z-score" in report.lower() or "significance" in report.lower() or "z =" in report.lower()

    def test_insufficient_data_message(self, conn):
        """No resolved signals should return insufficient data message."""
        from parallax.scoring.report_card import generate_report_card

        report = generate_report_card(conn)
        assert "Insufficient" in report

    def test_report_hold_duration(self, conn):
        """Report should include avg hold duration per proxy class."""
        from parallax.scoring.report_card import generate_report_card

        created = datetime(2026, 4, 8, 0, 0, 0, tzinfo=timezone.utc)
        resolved = datetime(2026, 4, 8, 12, 0, 0, tzinfo=timezone.utc)
        _insert_resolved_signal(conn, realized_pnl=0.60, created_at=created, resolved_at=resolved)
        report = generate_report_card(conn)
        assert "hold" in report.lower()

    def test_report_per_model_accuracy(self, conn):
        """Report should show per-model accuracy."""
        from parallax.scoring.report_card import generate_report_card

        _insert_resolved_signal(conn, model_id="oil_price", realized_pnl=0.60, model_was_correct=True)
        _insert_resolved_signal(conn, model_id="ceasefire", realized_pnl=-0.40, model_was_correct=False)
        report = generate_report_card(conn)
        assert "oil_price" in report
        assert "ceasefire" in report

    def test_report_biggest_wins_and_misses(self, conn):
        """Report should show biggest wins and misses."""
        from parallax.scoring.report_card import generate_report_card

        _insert_resolved_signal(conn, realized_pnl=0.80, model_was_correct=True)
        _insert_resolved_signal(conn, realized_pnl=0.60, model_was_correct=True)
        _insert_resolved_signal(conn, realized_pnl=-0.50, model_was_correct=False)
        _insert_resolved_signal(conn, realized_pnl=-0.30, model_was_correct=False)
        report = generate_report_card(conn)
        # Should have sections for wins/misses
        assert "win" in report.lower() or "best" in report.lower()
        assert "miss" in report.lower() or "worst" in report.lower()


class TestProxyWasAlignedInResolution:
    """Test that _backfill_signal sets proxy_was_aligned correctly."""

    def test_buy_yes_resolution_above_half_aligned(self, conn):
        """BUY_YES with resolution_price > 0.5 should set proxy_was_aligned = True."""
        from parallax.scoring.resolution import _backfill_signal

        signal_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """
            INSERT INTO signal_ledger
            (signal_id, created_at, model_id, model_claim, model_probability,
             model_timeframe, contract_ticker, proxy_class, confidence_discount,
             market_yes_price, market_no_price, entry_side, entry_price,
             raw_edge, effective_edge, signal)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [signal_id, now, "test", "claim", 0.7, "7d",
             "KXALIGN-01", "DIRECT", 1.0, 0.40, 0.60, "yes", 0.40, 0.1, 0.1, "BUY_YES"],
        )

        settled_at = datetime(2026, 4, 8, 12, 0, 0, tzinfo=timezone.utc)
        _backfill_signal(conn, "KXALIGN-01", 1.0, settled_at)

        row = conn.execute(
            "SELECT proxy_was_aligned FROM signal_ledger WHERE contract_ticker = 'KXALIGN-01'"
        ).fetchone()
        assert row[0] is True

    def test_buy_no_resolution_below_half_aligned(self, conn):
        """BUY_NO with resolution_price <= 0.5 should set proxy_was_aligned = True."""
        from parallax.scoring.resolution import _backfill_signal

        signal_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """
            INSERT INTO signal_ledger
            (signal_id, created_at, model_id, model_claim, model_probability,
             model_timeframe, contract_ticker, proxy_class, confidence_discount,
             market_yes_price, market_no_price, entry_side, entry_price,
             raw_edge, effective_edge, signal)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [signal_id, now, "test", "claim", 0.7, "7d",
             "KXALIGN-02", "DIRECT", 1.0, 0.40, 0.60, "no", 0.60, 0.1, 0.1, "BUY_NO"],
        )

        settled_at = datetime(2026, 4, 8, 12, 0, 0, tzinfo=timezone.utc)
        _backfill_signal(conn, "KXALIGN-02", 0.0, settled_at)

        row = conn.execute(
            "SELECT proxy_was_aligned FROM signal_ledger WHERE contract_ticker = 'KXALIGN-02'"
        ).fetchone()
        assert row[0] is True

    def test_buy_yes_resolution_below_half_not_aligned(self, conn):
        """BUY_YES with resolution_price <= 0.5 should set proxy_was_aligned = False."""
        from parallax.scoring.resolution import _backfill_signal

        signal_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """
            INSERT INTO signal_ledger
            (signal_id, created_at, model_id, model_claim, model_probability,
             model_timeframe, contract_ticker, proxy_class, confidence_discount,
             market_yes_price, market_no_price, entry_side, entry_price,
             raw_edge, effective_edge, signal)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [signal_id, now, "test", "claim", 0.7, "7d",
             "KXALIGN-03", "DIRECT", 1.0, 0.40, 0.60, "yes", 0.40, 0.1, 0.1, "BUY_YES"],
        )

        settled_at = datetime(2026, 4, 8, 12, 0, 0, tzinfo=timezone.utc)
        _backfill_signal(conn, "KXALIGN-03", 0.0, settled_at)

        row = conn.execute(
            "SELECT proxy_was_aligned FROM signal_ledger WHERE contract_ticker = 'KXALIGN-03'"
        ).fetchone()
        assert row[0] is False
