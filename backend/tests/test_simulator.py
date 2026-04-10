"""Tests for PortfolioSimulator -- replay signal_ledger and track equity."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import duckdb
import pytest

from parallax.db.schema import create_tables
from parallax.portfolio.simulator import PortfolioSimulator


@pytest.fixture
def conn():
    """In-memory DuckDB connection with schema created."""
    c = duckdb.connect(":memory:")
    create_tables(c)
    return c


def _insert_signal(
    conn: duckdb.DuckDBPyConnection,
    *,
    signal_id: str | None = None,
    run_id: str = "run-001",
    created_at: datetime | None = None,
    model_id: str = "ceasefire",
    model_claim: str = "ceasefire: stable with P=0.65 over 14d",
    model_probability: float = 0.65,
    model_timeframe: str = "14d",
    contract_ticker: str = "KXUSAIRANAGREEMENT-27",
    proxy_class: str = "near_proxy",
    confidence_discount: float = 0.6,
    effective_edge: float = 0.10,
    signal: str = "BUY_YES",
    entry_side: str | None = "yes",
    entry_price: float | None = 0.48,
    resolution_price: float | None = None,
    resolved_at: datetime | None = None,
    model_was_correct: bool | None = None,
    market_yes_price: float | None = 0.48,
    market_no_price: float | None = 0.52,
) -> str:
    """Insert a test signal into signal_ledger with sensible defaults."""
    sid = signal_id or str(uuid.uuid4())
    ts = created_at or datetime(2026, 4, 8, 12, 0, 0, tzinfo=timezone.utc)
    conn.execute(
        """
        INSERT INTO signal_ledger (
            signal_id, run_id, created_at, model_id, model_claim,
            model_probability, model_timeframe, contract_ticker,
            proxy_class, confidence_discount, effective_edge,
            signal, entry_side, entry_price,
            resolution_price, resolved_at, model_was_correct,
            market_yes_price, market_no_price
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            sid, run_id, ts, model_id, model_claim,
            model_probability, model_timeframe, contract_ticker,
            proxy_class, confidence_discount, effective_edge,
            signal, entry_side, entry_price,
            resolution_price, resolved_at, model_was_correct,
            market_yes_price, market_no_price,
        ],
    )
    return sid


def test_empty_portfolio(conn: duckdb.DuckDBPyConnection) -> None:
    """No signals returns starting capital unchanged."""
    sim = PortfolioSimulator(conn, starting_capital=1000.0)
    result = sim.run()

    assert result["portfolio_value"] == 1000.0
    assert result["cash"] == 1000.0
    assert result["deployed"] == 0.0
    assert result["positions"] == []
    assert result["closed_trades"] == []
    assert result["max_drawdown"] == 0.0
    assert result["total_fees"] == 0.0
    assert result["win_rate"] is None
    assert result["sharpe"] is None


def test_single_buy_signal(conn: duckdb.DuckDBPyConnection) -> None:
    """Insert one BUY_YES signal, verify position is opened."""
    _insert_signal(
        conn,
        signal="BUY_YES",
        entry_side="yes",
        entry_price=0.48,
        effective_edge=0.10,
    )
    sim = PortfolioSimulator(conn, starting_capital=1000.0)
    result = sim.run()

    assert len(result["positions"]) == 1
    pos = result["positions"][0]
    assert pos["ticker"] == "KXUSAIRANAGREEMENT-27"
    assert pos["side"] == "yes"
    assert pos["entry_price"] == 0.48
    assert pos["quantity"] > 0
    assert result["deployed"] > 0.0
    assert result["cash"] < 1000.0


def test_hold_signal_no_position(conn: duckdb.DuckDBPyConnection) -> None:
    """HOLD signal should not open any position."""
    _insert_signal(
        conn,
        signal="HOLD",
        entry_side=None,
        entry_price=None,
        effective_edge=0.02,
    )
    sim = PortfolioSimulator(conn, starting_capital=1000.0)
    result = sim.run()

    assert result["positions"] == []
    assert result["cash"] == 1000.0
    assert result["deployed"] == 0.0


def test_kelly_sizing_respects_capital(conn: duckdb.DuckDBPyConnection) -> None:
    """Position notional must not exceed 25% of portfolio capital."""
    _insert_signal(
        conn,
        signal="BUY_YES",
        entry_side="yes",
        entry_price=0.10,
        effective_edge=0.80,
    )
    sim = PortfolioSimulator(conn, starting_capital=1000.0)
    result = sim.run()

    assert len(result["positions"]) == 1
    pos = result["positions"][0]
    notional = pos["quantity"] * pos["entry_price"]
    assert notional <= 1000.0 * 0.25 + 0.01  # small float tolerance
