"""Parallax FastAPI application — prediction market edge finder API.

Serves predictions, market prices, divergences, and paper trades
via REST endpoints. DuckDB tables created on startup.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

import duckdb
from fastapi import FastAPI

from parallax.db.schema import create_tables
from parallax.ops import build_alert_dispatcher, build_kalshi_client_config, resolve_api_runtime

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize DuckDB and create tables on startup."""
    alerts = build_alert_dispatcher()
    app.state.alerts = alerts
    conn = None
    try:
        runtime = resolve_api_runtime(dry_run=False)
        db_path = runtime.db_path
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        conn = duckdb.connect(db_path)
        create_tables(conn)
        app.state.db = conn
        app.state.runtime = runtime

        # Initialize market clients after the runtime guard resolves the process policy.
        app.state.kalshi = None
        app.state.polymarket = None
        app.state.last_predictions = []
        app.state.last_markets = []
        app.state.last_divergences = []
        app.state.last_brief_time = None

        if runtime.live_execution_requested and not runtime.live_execution_authorized:
            await alerts.emit(
                event_type="live_execution_blocked",
                severity="critical",
                message="Blocked live execution request during API startup.",
                details={
                    "data_environment": runtime.data_environment,
                    "requested_execution_environment": runtime.requested_execution_environment,
                    "resolved_execution_environment": runtime.execution_environment,
                    "reason": runtime.authorization_reason,
                    "runtime_status_path": runtime.runtime_status.path,
                },
            )
        elif runtime.kill_switch_enabled:
            await alerts.emit(
                event_type="kill_switch_engaged",
                severity="warning",
                message="Kill switch is engaged; execution remains constrained.",
                details={
                    "data_environment": runtime.data_environment,
                    "execution_environment": runtime.execution_environment,
                    "reason": runtime.runtime_status.reason,
                    "runtime_status_path": runtime.runtime_status.path,
                },
            )

        kalshi_key = os.environ.get("KALSHI_API_KEY", "")
        kalshi_pk = os.environ.get("KALSHI_PRIVATE_KEY_PATH", "")
        kalshi_config = build_kalshi_client_config(
            runtime,
            api_key=kalshi_key,
            private_key_path=kalshi_pk,
        )
        if kalshi_config:
            from parallax.markets.kalshi import KalshiClient
            app.state.kalshi = KalshiClient(**kalshi_config)
        elif kalshi_key and kalshi_pk:
            await alerts.emit(
                event_type="kalshi_client_disabled",
                severity="warning",
                message="Kalshi credentials were present but runtime policy disabled client initialization.",
                details={
                    "data_environment": runtime.data_environment,
                    "requested_execution_environment": runtime.requested_execution_environment,
                    "resolved_execution_environment": runtime.execution_environment,
                    "reason": runtime.authorization_reason,
                },
            )

        from parallax.markets.polymarket import PolymarketClient
        app.state.polymarket = PolymarketClient()

        logger.info(
            "Parallax API started (data_environment=%s requested_execution=%s execution_environment=%s db=%s)",
            runtime.data_environment,
            runtime.requested_execution_environment,
            runtime.execution_environment,
            db_path,
        )
        await alerts.emit(
            event_type="api_started",
            severity="info",
            message="Parallax API runtime initialized.",
            details={
                "data_environment": runtime.data_environment,
                "requested_execution_environment": runtime.requested_execution_environment,
                "execution_environment": runtime.execution_environment,
                "kalshi_base_url": runtime.kalshi_base_url,
                "live_execution_authorized": runtime.live_execution_authorized,
            },
        )
        yield
    except Exception as exc:
        await alerts.emit(
            event_type="api_startup_failed",
            severity="critical",
            message="Parallax API startup failed.",
            details={"error": str(exc)},
        )
        raise
    finally:
        if conn is not None:
            conn.close()
        logger.info("Parallax API stopped")


app = FastAPI(title="Parallax", version="1.0.0", lifespan=lifespan)


@app.get("/api/health")
async def health():
    """Return pipeline status: last fetch times, budget stats, trade count."""
    return {
        "status": "healthy",
        "last_brief_time": app.state.last_brief_time,
        "predictions_count": len(app.state.last_predictions),
        "markets_count": len(app.state.last_markets),
        "divergences_count": len(app.state.last_divergences),
        "kalshi_configured": app.state.kalshi is not None,
        "data_environment": app.state.runtime.data_environment,
        "requested_execution_environment": app.state.runtime.requested_execution_environment,
        "execution_environment": app.state.runtime.execution_environment,
        "live_execution_authorized": app.state.runtime.live_execution_authorized,
        "kill_switch_enabled": app.state.runtime.kill_switch_enabled,
        "runtime_status": {
            "path": app.state.runtime.runtime_status.path,
            "exists": app.state.runtime.runtime_status.exists,
            "status": app.state.runtime.runtime_status.status,
            "allow_live_execution": app.state.runtime.runtime_status.allow_live_execution,
            "reason": app.state.runtime.runtime_status.reason,
            "updated_at": app.state.runtime.runtime_status.updated_at,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/predictions")
async def get_predictions():
    """Return latest predictions from all 3 models."""
    return {
        "predictions": [
            p.model_dump() if hasattr(p, "model_dump") else p
            for p in app.state.last_predictions
        ],
    }


@app.get("/api/markets")
async def get_markets():
    """Return latest Kalshi + Polymarket prices for tracked tickers."""
    return {
        "markets": [
            m.model_dump() if hasattr(m, "model_dump") else m
            for m in app.state.last_markets
        ],
    }


@app.get("/api/divergences")
async def get_divergences():
    """Return current divergences with signals."""
    return {
        "divergences": [
            d.model_dump() if hasattr(d, "model_dump") else d
            for d in app.state.last_divergences
        ],
    }


@app.get("/api/trades")
async def get_trades():
    """Return order journal plus tracked positions."""
    try:
        conn = app.state.db
        orders = conn.execute(
            """
            SELECT
                order_id, signal_id, ticker, side, quantity, intended_price,
                status, submitted_at, accepted_at, rejected_at, cancelled_at,
                avg_fill_price, venue_environment
            FROM trade_orders
            ORDER BY submitted_at DESC
            """
        ).fetchall()
        order_columns = [desc[0] for desc in conn.description]
        positions = conn.execute(
            """
            SELECT
                position_id, signal_id, ticker, side, quantity, entry_price,
                status, opened_at, closed_at, realized_pnl, unrealized_pnl,
                venue_environment
            FROM trade_positions
            ORDER BY opened_at DESC
            """
        ).fetchall()
        position_columns = [desc[0] for desc in conn.description]
        return {
            "orders": [dict(zip(order_columns, row)) for row in orders],
            "positions": [dict(zip(position_columns, row)) for row in positions],
            "data_environment": app.state.runtime.data_environment,
            "execution_environment": app.state.runtime.execution_environment,
        }
    except Exception:
        return {"orders": [], "positions": []}


@app.post("/api/brief/run")
async def run_brief_endpoint():
    """Trigger a brief run and return results as JSON."""
    from parallax.cli.brief import run_brief

    try:
        brief_text = await run_brief(dry_run=True, no_trade=True)
        app.state.last_brief_time = datetime.now(timezone.utc).isoformat()
        return {
            "status": "success",
            "brief": brief_text,
            "timestamp": app.state.last_brief_time,
        }
    except Exception as e:
        logger.exception("Brief run failed")
        return {
            "status": "error",
            "error": str(e),
        }


# ---------------------------------------------------------------------------
# Dashboard endpoints
# ---------------------------------------------------------------------------


@app.get("/api/latest-signals")
async def get_latest_signals():
    """Return latest run signals with market prices (DB-backed, always available)."""
    from parallax.dashboard.data import get_latest_signals_with_markets

    try:
        return {"signals": get_latest_signals_with_markets(app.state.db)}
    except Exception:
        logger.exception("Latest signals query failed")
        return {"signals": []}


@app.get("/api/scorecard")
async def get_scorecard(date: str | None = None):
    """Return daily scorecard metrics."""
    from parallax.dashboard.data import get_scorecard_metrics

    try:
        return get_scorecard_metrics(app.state.db, date)
    except Exception:
        logger.exception("Scorecard query failed")
        return {"error": "scorecard query failed"}


@app.get("/api/contracts")
async def get_contracts():
    """Return active contracts with proxy mappings."""
    from parallax.dashboard.data import get_active_contracts

    try:
        return {"contracts": get_active_contracts(app.state.db)}
    except Exception:
        logger.exception("Contracts query failed")
        return {"contracts": []}


@app.get("/api/signals")
async def get_signals(contract: str, limit: int = 20):
    """Return signal history for a specific contract."""
    from parallax.dashboard.data import get_signals_for_contract

    try:
        return {"signals": get_signals_for_contract(app.state.db, contract, limit)}
    except Exception:
        logger.exception("Signals query failed")
        return {"signals": []}


@app.get("/api/edge-decay")
async def get_edge_decay(contract: str):
    """Return edge decay analysis for a specific contract."""
    from parallax.dashboard.data import get_edge_decay_for_contract

    try:
        return get_edge_decay_for_contract(app.state.db, contract)
    except Exception:
        logger.exception("Edge decay query failed")
        return {"verdict": "query failed", "n_pairs": 0}


@app.get("/api/price-history")
async def get_price_history_endpoint(ticker: str, limit: int = 100):
    """Return market price history for a ticker."""
    from parallax.dashboard.data import get_price_history

    try:
        return {"prices": get_price_history(app.state.db, ticker, limit)}
    except Exception:
        logger.exception("Price history query failed")
        return {"prices": []}


@app.get("/api/prediction-history")
async def get_prediction_history():
    """Return prediction history grouped by model."""
    from parallax.dashboard.data import get_prediction_history as _get_pred_hist

    try:
        return {"models": _get_pred_hist(app.state.db)}
    except Exception:
        logger.exception("Prediction history query failed")
        return {"models": {}}


@app.get("/api/portfolio")
async def get_portfolio():
    """Return portfolio simulation results."""
    from parallax.portfolio.simulator import PortfolioSimulator

    try:
        sim = PortfolioSimulator(app.state.db)
        return sim.run()
    except Exception:
        logger.exception("Portfolio simulation failed")
        return {"portfolio_value": 1000.0, "error": "simulation failed"}
