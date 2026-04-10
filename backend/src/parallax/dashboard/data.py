"""Reusable data layer for dashboard and future API endpoints.

All functions take a DuckDB connection and return plain dicts/lists.
No Streamlit or framework dependencies -- pure data queries.
Reuses calibration.py functions per D-07 (no duplicate SQL).
"""

from __future__ import annotations

import logging

import duckdb

from parallax.scoring.calibration import (
    calibration_curve,
    edge_decay,
    edge_decay_over_time,
    hit_rate_by_proxy_class,
)

logger = logging.getLogger(__name__)


def get_latest_brief(
    conn: duckdb.DuckDBPyConnection, limit: int = 1,
) -> list[dict]:
    """Return latest prediction_log entries grouped by most recent run_id.

    Args:
        conn: DuckDB connection.
        limit: Number of distinct runs to return (default: 1 = latest run only).

    Returns:
        List of dicts with model_id, probability, direction, confidence, reasoning, created_at.
    """
    rows = conn.execute(
        """
        SELECT model_id, probability, direction, confidence, reasoning, created_at
        FROM prediction_log
        WHERE run_id = (
            SELECT run_id FROM prediction_log
            ORDER BY created_at DESC
            LIMIT 1
        )
        ORDER BY model_id
        """,
    ).fetchall()

    return [
        {
            "model_id": row[0],
            "probability": float(row[1]),
            "direction": row[2],
            "confidence": float(row[3]),
            "reasoning": row[4],
            "created_at": row[5],
        }
        for row in rows
    ]


def get_calibration_data(conn: duckdb.DuckDBPyConnection) -> dict:
    """Return calibration data from existing calibration.py queries.

    Returns:
        Dict with keys: hit_rate, calibration_curve, edge_decay.
    """
    return {
        "hit_rate": hit_rate_by_proxy_class(conn),
        "calibration_curve": calibration_curve(conn),
        "edge_decay": edge_decay(conn),
    }


def get_signal_history(
    conn: duckdb.DuckDBPyConnection, limit: int = 100,
) -> list[dict]:
    """Return recent signals from signal_ledger ordered by created_at DESC.

    Args:
        conn: DuckDB connection.
        limit: Max signals to return.

    Returns:
        List of dicts with signal fields.
    """
    rows = conn.execute(
        """
        SELECT signal_id, created_at, model_id, contract_ticker, proxy_class,
               effective_edge, signal, tradeability_status, execution_status,
               entry_price, entry_price_kind, resolution_price, counterfactual_pnl,
               model_was_correct, traded
        FROM signal_ledger
        ORDER BY created_at DESC
        LIMIT ?
        """,
        [limit],
    ).fetchall()

    return [
        {
            "signal_id": row[0],
            "created_at": row[1],
            "model_id": row[2],
            "contract_ticker": row[3],
            "proxy_class": row[4],
            "effective_edge": float(row[5]) if row[5] is not None else 0.0,
            "signal": row[6],
            "tradeability_status": row[7],
            "execution_status": row[8],
            "entry_price": float(row[9]) if row[9] is not None else None,
            "entry_price_kind": row[10],
            "resolution_price": float(row[11]) if row[11] is not None else None,
            "counterfactual_pnl": float(row[12]) if row[12] is not None else None,
            "model_was_correct": row[13],
            "traded": bool(row[14]) if row[14] is not None else False,
        }
        for row in rows
    ]


def get_market_prices(
    conn: duckdb.DuckDBPyConnection, limit: int = 50,
) -> list[dict]:
    """Return latest market_prices table entries.

    Args:
        conn: DuckDB connection.
        limit: Max entries to return.

    Returns:
        List of dicts with ticker, source, yes_price, no_price, volume, fetched_at.
    """
    rows = conn.execute(
        """
        SELECT ticker, source, best_yes_bid, best_yes_ask, best_no_bid, best_no_ask,
               yes_price, no_price, derived_price_kind, volume, fetched_at, data_environment
        FROM market_prices
        ORDER BY fetched_at DESC
        LIMIT ?
        """,
        [limit],
    ).fetchall()

    return [
        {
            "ticker": row[0],
            "source": row[1],
            "best_yes_bid": float(row[2]) if row[2] is not None else None,
            "best_yes_ask": float(row[3]) if row[3] is not None else None,
            "best_no_bid": float(row[4]) if row[4] is not None else None,
            "best_no_ask": float(row[5]) if row[5] is not None else None,
            "yes_price": float(row[6]) if row[6] is not None else None,
            "no_price": float(row[7]) if row[7] is not None else None,
            "derived_price_kind": row[8],
            "volume": float(row[9]) if row[9] is not None else None,
            "fetched_at": row[10],
            "data_environment": row[11],
        }
        for row in rows
    ]


def get_trade_journal(
    conn: duckdb.DuckDBPyConnection,
    limit: int = 100,
) -> list[dict]:
    rows = conn.execute(
        """
        SELECT
            o.order_id,
            o.signal_id,
            o.ticker,
            o.side,
            o.quantity,
            o.intended_price,
            o.status,
            o.submitted_at,
            o.accepted_at,
            o.rejected_at,
            o.cancelled_at,
            o.avg_fill_price,
            p.position_id,
            p.status,
            p.realized_pnl,
            o.venue_environment
        FROM trade_orders AS o
        LEFT JOIN trade_positions AS p
          ON p.signal_id = o.signal_id
        ORDER BY o.submitted_at DESC
        LIMIT ?
        """,
        [limit],
    ).fetchall()
    return [
        {
            "order_id": row[0],
            "signal_id": row[1],
            "ticker": row[2],
            "side": row[3],
            "quantity": row[4],
            "intended_price": float(row[5]) if row[5] is not None else None,
            "order_status": row[6],
            "submitted_at": row[7],
            "accepted_at": row[8],
            "rejected_at": row[9],
            "cancelled_at": row[10],
            "avg_fill_price": float(row[11]) if row[11] is not None else None,
            "position_id": row[12],
            "position_status": row[13],
            "realized_pnl": float(row[14]) if row[14] is not None else None,
            "venue_environment": row[15],
        }
        for row in rows
    ]


# ---------------------------------------------------------------------------
# New dashboard query functions
# ---------------------------------------------------------------------------


def get_scorecard_metrics(
    conn: duckdb.DuckDBPyConnection, date_str: str | None = None,
) -> dict:
    """Return latest daily_scorecard metrics as a flat dict.

    Args:
        conn: DuckDB connection.
        date_str: Optional ISO date string (YYYY-MM-DD). Uses most recent if None.

    Returns:
        Dict with scorecard metric keys. All None if no data.
    """
    if date_str is None:
        row = conn.execute(
            "SELECT MAX(score_date) FROM daily_scorecard",
        ).fetchone()
        if row is None or row[0] is None:
            return {
                "signal_hit_rate": None,
                "signal_brier_score": None,
                "signal_calibration_max_gap": None,
                "ops_llm_cost_usd": None,
                "ops_run_count": None,
                "ops_run_success_rate": None,
                "ops_error_alert_count": None,
                "score_date": None,
            }
        date_str = str(row[0])

    rows = conn.execute(
        """
        SELECT metric_name, metric_value
        FROM daily_scorecard
        WHERE score_date = ?
        """,
        [date_str],
    ).fetchall()

    metrics: dict = {
        "signal_hit_rate": None,
        "signal_brier_score": None,
        "signal_calibration_max_gap": None,
        "ops_llm_cost_usd": None,
        "ops_run_count": None,
        "ops_run_success_rate": None,
        "ops_error_alert_count": None,
        "score_date": date_str,
    }
    for name, value in rows:
        if name in metrics:
            metrics[name] = float(value) if value is not None else None
    return metrics


def get_signals_for_contract(
    conn: duckdb.DuckDBPyConnection, contract_ticker: str, limit: int = 20,
) -> list[dict]:
    """Signal history for a specific contract from signal_ledger, most recent first.

    Args:
        conn: DuckDB connection.
        contract_ticker: Contract ticker to filter by.
        limit: Max signals to return.

    Returns:
        List of signal dicts.
    """
    rows = conn.execute(
        """
        SELECT signal_id, created_at, model_id, effective_edge, signal,
               model_probability, entry_price, entry_side, resolution_price,
               model_was_correct, run_id
        FROM signal_ledger
        WHERE contract_ticker = ?
        ORDER BY created_at DESC
        LIMIT ?
        """,
        [contract_ticker, limit],
    ).fetchall()

    return [
        {
            "signal_id": row[0],
            "created_at": row[1],
            "model_id": row[2],
            "effective_edge": float(row[3]) if row[3] is not None else 0.0,
            "signal": row[4],
            "model_probability": float(row[5]) if row[5] is not None else None,
            "entry_price": float(row[6]) if row[6] is not None else None,
            "entry_side": row[7],
            "resolution_price": float(row[8]) if row[8] is not None else None,
            "model_was_correct": row[9],
            "run_id": row[10],
        }
        for row in rows
    ]


def get_active_contracts(conn: duckdb.DuckDBPyConnection) -> list[dict]:
    """Active contracts from contract_registry with proxy mappings.

    Returns:
        List of contract dicts with proxy_map and best_proxy fields.
    """
    contracts = conn.execute(
        """
        SELECT ticker, source, event_ticker, title, resolution_criteria,
               resolution_date, contract_family, expected_fee_rate,
               expected_slippage_rate
        FROM contract_registry
        WHERE is_active = true
        ORDER BY ticker
        """,
    ).fetchall()

    result = []
    for row in contracts:
        ticker = row[0]
        proxy_rows = conn.execute(
            """
            SELECT model_type, proxy_class, confidence_discount
            FROM contract_proxy_map
            WHERE ticker = ?
            """,
            [ticker],
        ).fetchall()

        proxy_map: dict[str, dict] = {}
        best_proxy: str | None = None
        best_discount = 0.0
        for pr in proxy_rows:
            proxy_map[pr[0]] = {
                "proxy_class": pr[1],
                "confidence_discount": float(pr[2]),
            }
            if pr[1] == "DIRECT":
                best_proxy = "DIRECT"
            elif float(pr[2]) > best_discount and best_proxy != "DIRECT":
                best_discount = float(pr[2])
                best_proxy = pr[1]

        result.append({
            "ticker": ticker,
            "source": row[1],
            "event_ticker": row[2],
            "title": row[3],
            "resolution_criteria": row[4],
            "resolution_date": row[5],
            "contract_family": row[6],
            "expected_fee_rate": float(row[7]) if row[7] is not None else None,
            "expected_slippage_rate": float(row[8]) if row[8] is not None else None,
            "proxy_map": proxy_map,
            "best_proxy": best_proxy,
        })

    return result


def get_edge_decay_for_contract(
    conn: duckdb.DuckDBPyConnection, contract_ticker: str,
) -> dict:
    """Edge decay analysis for a specific contract.

    Uses edge_decay_over_time() and filters to the given contract_ticker.

    Returns:
        Dict with n_pairs, avg_decay_rate, avg_edge_change, time_to_zero_edge,
        round_trip_cost, exit_profitable, verdict.
    """
    all_pairs = edge_decay_over_time(conn)
    pairs = [p for p in all_pairs if p["contract_ticker"] == contract_ticker]

    round_trip_cost = 0.055

    if not pairs:
        return {
            "n_pairs": 0,
            "avg_decay_rate": None,
            "avg_edge_change": None,
            "time_to_zero_edge": None,
            "round_trip_cost": round_trip_cost,
            "exit_profitable": False,
            "verdict": "insufficient data",
        }

    decay_rates = [p["decay_rate_per_hour"] for p in pairs if p["decay_rate_per_hour"] is not None]
    edge_changes = [p["edge_change"] for p in pairs]

    avg_decay_rate = sum(decay_rates) / len(decay_rates) if decay_rates else None
    avg_edge_change = sum(edge_changes) / len(edge_changes) if edge_changes else None

    time_to_zero: float | None = None
    if avg_decay_rate is not None and avg_decay_rate < 0:
        avg_edge_start = sum(p["edge_a"] for p in pairs) / len(pairs)
        if avg_edge_start > 0:
            time_to_zero = abs(avg_edge_start / avg_decay_rate)

    exit_profitable = (
        avg_edge_change is not None
        and abs(avg_edge_change) > round_trip_cost
    )

    if exit_profitable:
        verdict = "edge decays fast enough to consider exit trading"
    elif avg_edge_change is not None:
        verdict = "hold to settlement — edge decay slower than round-trip cost"
    else:
        verdict = "insufficient data"

    return {
        "n_pairs": len(pairs),
        "avg_decay_rate": avg_decay_rate,
        "avg_edge_change": avg_edge_change,
        "time_to_zero_edge": time_to_zero,
        "round_trip_cost": round_trip_cost,
        "exit_profitable": exit_profitable,
        "verdict": verdict,
    }


def get_price_history(
    conn: duckdb.DuckDBPyConnection, ticker: str, limit: int = 100,
) -> list[dict]:
    """Market price history for a ticker, oldest first (for charting).

    Args:
        conn: DuckDB connection.
        ticker: Market ticker to filter by.
        limit: Max entries to return.

    Returns:
        List of price dicts ordered oldest-first.
    """
    rows = conn.execute(
        """
        SELECT fetched_at, yes_price, no_price, volume, best_yes_bid, best_yes_ask
        FROM market_prices
        WHERE ticker = ?
        ORDER BY fetched_at ASC
        LIMIT ?
        """,
        [ticker, limit],
    ).fetchall()

    return [
        {
            "fetched_at": row[0],
            "yes_price": float(row[1]) if row[1] is not None else None,
            "no_price": float(row[2]) if row[2] is not None else None,
            "volume": float(row[3]) if row[3] is not None else None,
            "best_yes_bid": float(row[4]) if row[4] is not None else None,
            "best_yes_ask": float(row[5]) if row[5] is not None else None,
        }
        for row in rows
    ]


def get_prediction_history(
    conn: duckdb.DuckDBPyConnection, limit: int = 50,
) -> dict[str, list[dict]]:
    """Prediction history grouped by model_id, oldest first.

    Args:
        conn: DuckDB connection.
        limit: Max entries per model.

    Returns:
        Dict keyed by model_id, each value a list of prediction dicts.
    """
    rows = conn.execute(
        """
        SELECT model_id, probability, direction, confidence, created_at, run_id
        FROM prediction_log
        ORDER BY created_at ASC
        """,
    ).fetchall()

    grouped: dict[str, list[dict]] = {}
    for row in rows:
        model_id = row[0]
        entry = {
            "probability": float(row[1]),
            "direction": row[2],
            "confidence": float(row[3]),
            "created_at": row[4],
            "run_id": row[5],
        }
        if model_id not in grouped:
            grouped[model_id] = []
        grouped[model_id].append(entry)

    # Apply per-model limit
    for model_id in grouped:
        grouped[model_id] = grouped[model_id][-limit:]

    return grouped
