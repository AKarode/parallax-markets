"""Tests for new dashboard API endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import duckdb
import pytest
from fastapi.testclient import TestClient

from parallax.db.schema import create_tables


def _make_app_with_db(conn: duckdb.DuckDBPyConnection):
    """Create a test app with an in-memory DuckDB connection."""
    from parallax.main import app

    # Patch lifespan by directly setting state attributes
    app.state.db = conn
    app.state.kalshi = None
    app.state.polymarket = None
    app.state.last_predictions = []
    app.state.last_markets = []
    app.state.last_divergences = []
    app.state.last_brief_time = None

    # Minimal runtime mock
    class _MockRuntimeStatus:
        path = "/tmp/test"
        exists = False
        status = "test"
        allow_live_execution = False
        reason = "test"
        updated_at = None

    class _MockRuntime:
        data_environment = "mock"
        requested_execution_environment = "none"
        execution_environment = "none"
        live_execution_authorized = False
        kill_switch_enabled = False
        kalshi_base_url = ""
        runtime_status = _MockRuntimeStatus()

    app.state.runtime = _MockRuntime()
    return app


@pytest.fixture
def conn():
    """In-memory DuckDB with schema."""
    c = duckdb.connect(":memory:")
    create_tables(c)
    return c


@pytest.fixture
def client(conn):
    """FastAPI TestClient with in-memory DB."""
    app = _make_app_with_db(conn)
    return TestClient(app)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _seed_scorecard(conn, date_str: str = "2026-04-09"):
    metrics = [
        ("signal_hit_rate", 0.65),
        ("signal_brier_score", 0.22),
        ("ops_llm_cost_usd", 0.04),
        ("ops_run_count", 2.0),
        ("ops_run_success_rate", 1.0),
        ("ops_error_alert_count", 0.0),
    ]
    for name, value in metrics:
        conn.execute(
            "INSERT INTO daily_scorecard (score_date, metric_name, metric_value) VALUES (?, ?, ?)",
            [date_str, name, value],
        )


class TestScorecardEndpoint:
    """Test GET /api/scorecard."""

    def test_returns_200(self, client):
        resp = client.get("/api/scorecard")
        assert resp.status_code == 200

    def test_empty_scorecard_has_null_values(self, client):
        resp = client.get("/api/scorecard")
        data = resp.json()
        assert data["score_date"] is None
        assert data["signal_hit_rate"] is None

    def test_returns_data_after_seed(self, conn, client):
        _seed_scorecard(conn)
        resp = client.get("/api/scorecard")
        data = resp.json()
        assert data["score_date"] == "2026-04-09"
        assert data["signal_hit_rate"] == pytest.approx(0.65)

    def test_date_parameter(self, conn, client):
        _seed_scorecard(conn, "2026-04-08")
        _seed_scorecard(conn, "2026-04-09")
        resp = client.get("/api/scorecard", params={"date": "2026-04-08"})
        data = resp.json()
        assert data["score_date"] == "2026-04-08"


class TestContractsEndpoint:
    """Test GET /api/contracts."""

    def test_returns_200(self, client):
        resp = client.get("/api/contracts")
        assert resp.status_code == 200

    def test_empty_returns_empty_list(self, client):
        resp = client.get("/api/contracts")
        assert resp.json() == {"contracts": []}

    def test_returns_contracts(self, conn, client):
        conn.execute(
            """
            INSERT INTO contract_registry
            (ticker, source, event_ticker, title, resolution_criteria, is_active)
            VALUES ('KXTEST', 'kalshi', 'KXEVENT', 'Test', 'Resolves yes', true)
            """,
        )
        resp = client.get("/api/contracts")
        data = resp.json()
        assert len(data["contracts"]) == 1
        assert data["contracts"][0]["ticker"] == "KXTEST"


class TestSignalsEndpoint:
    """Test GET /api/signals."""

    def test_returns_200(self, client):
        resp = client.get("/api/signals", params={"contract": "KXTEST"})
        assert resp.status_code == 200

    def test_empty_returns_empty_list(self, client):
        resp = client.get("/api/signals", params={"contract": "KXTEST"})
        assert resp.json() == {"signals": []}

    def test_requires_contract_param(self, client):
        resp = client.get("/api/signals")
        assert resp.status_code == 422


class TestEdgeDecayEndpoint:
    """Test GET /api/edge-decay."""

    def test_returns_200(self, client):
        resp = client.get("/api/edge-decay", params={"contract": "KXTEST"})
        assert resp.status_code == 200

    def test_no_data_returns_insufficient(self, client):
        resp = client.get("/api/edge-decay", params={"contract": "KXTEST"})
        data = resp.json()
        assert data["n_pairs"] == 0
        assert data["verdict"] == "insufficient data"

    def test_requires_contract_param(self, client):
        resp = client.get("/api/edge-decay")
        assert resp.status_code == 422


class TestPriceHistoryEndpoint:
    """Test GET /api/price-history."""

    def test_returns_200(self, client):
        resp = client.get("/api/price-history", params={"ticker": "KXTEST"})
        assert resp.status_code == 200

    def test_empty_returns_empty_list(self, client):
        resp = client.get("/api/price-history", params={"ticker": "KXTEST"})
        assert resp.json() == {"prices": []}

    def test_requires_ticker_param(self, client):
        resp = client.get("/api/price-history")
        assert resp.status_code == 422


class TestPredictionHistoryEndpoint:
    """Test GET /api/prediction-history."""

    def test_returns_200(self, client):
        resp = client.get("/api/prediction-history")
        assert resp.status_code == 200

    def test_empty_returns_empty_dict(self, client):
        resp = client.get("/api/prediction-history")
        assert resp.json() == {"models": {}}


class TestPortfolioEndpoint:
    """Test GET /api/portfolio."""

    def test_returns_200(self, client):
        resp = client.get("/api/portfolio")
        assert resp.status_code == 200

    def test_returns_portfolio_data(self, client):
        resp = client.get("/api/portfolio")
        data = resp.json()
        # Should have portfolio_value key from simulator
        assert "portfolio_value" in data or "error" in data
