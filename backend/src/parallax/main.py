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

logger = logging.getLogger(__name__)

DUCKDB_PATH = os.environ.get("DUCKDB_PATH", "/app/data/parallax.duckdb")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize DuckDB and create tables on startup."""
    db_path = DUCKDB_PATH
    if db_path != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    conn = duckdb.connect(db_path)
    create_tables(conn)
    app.state.db = conn

    # Initialize market clients (optional — may not have credentials)
    app.state.kalshi = None
    app.state.polymarket = None
    app.state.last_predictions = []
    app.state.last_markets = []
    app.state.last_divergences = []
    app.state.last_brief_time = None

    kalshi_key = os.environ.get("KALSHI_API_KEY", "")
    kalshi_pk = os.environ.get("KALSHI_PRIVATE_KEY_PATH", "")
    if kalshi_key and kalshi_pk:
        from parallax.markets.kalshi import KalshiClient
        app.state.kalshi = KalshiClient(api_key=kalshi_key, private_key_path=kalshi_pk)

    from parallax.markets.polymarket import PolymarketClient
    app.state.polymarket = PolymarketClient()

    logger.info("Parallax API started")
    yield

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
    """Return open paper trades with P&L."""
    try:
        conn = app.state.db
        result = conn.execute("SELECT * FROM paper_trades ORDER BY opened_at DESC").fetchall()
        columns = [desc[0] for desc in conn.description()]
        return {"trades": [dict(zip(columns, row)) for row in result]}
    except Exception:
        return {"trades": []}


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
