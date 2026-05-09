"""Backtest runner for historical prediction validation.

Replays predictions against historical data, reconstructing what news/prices
were available at each point in time. Uses LookAheadGuard to prevent
future data contamination.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any

import duckdb

from parallax.backtest.look_ahead_guard import LookAheadGuard
from parallax.contracts.registry import ContractRegistry
from parallax.contracts.schemas import ProxyClass
from parallax.db.schema import create_tables

logger = logging.getLogger(__name__)


@dataclass
class BacktestConfig:
    """Configuration for a backtest run."""

    date_range_start: date
    date_range_end: date
    contract_tickers: list[str]
    model_ids: list[str] = field(default_factory=lambda: ["oil_price", "ceasefire", "hormuz_reopening"])
    prediction_config: dict[str, Any] = field(default_factory=dict)


@dataclass
class BacktestPrediction:
    """A single prediction made during backtest."""

    prediction_id: str
    backtest_id: str
    sim_date: date
    model_id: str
    contract_ticker: str
    predicted_probability: float
    predicted_direction: str | None = None
    resolution_price: float | None = None
    resolution_date: date | None = None
    edge_predicted: float | None = None
    edge_realized: float | None = None
    was_correct: bool | None = None


@dataclass
class BacktestResult:
    """Result of a complete backtest run."""

    backtest_id: str
    config: BacktestConfig
    predictions: list[BacktestPrediction]
    started_at: datetime
    ended_at: datetime | None = None
    status: str = "completed"
    error: str | None = None


class BacktestRunner:
    """Runs backtests against historical data with look-ahead prevention."""

    def __init__(
        self,
        conn: duckdb.DuckDBPyConnection,
        config: BacktestConfig,
    ) -> None:
        """Initialize the backtest runner.

        Args:
            conn: DuckDB connection with historical data.
            config: Backtest configuration.
        """
        self._conn = conn
        self._config = config
        self._backtest_id = str(uuid.uuid4())
        self._predictions: list[BacktestPrediction] = []

    def run(self) -> BacktestResult:
        """Execute the backtest over the configured date range.

        For each day in the range:
        1. Activate look-ahead guard to filter future data
        2. Reconstruct available news/prices at that time
        3. Run prediction pipeline
        4. Record predicted probability vs eventual resolution

        Returns:
            BacktestResult with all predictions and metadata.
        """
        started_at = datetime.now(timezone.utc)

        self._persist_backtest_start()

        current_date = self._config.date_range_start
        while current_date <= self._config.date_range_end:
            try:
                self._run_day(current_date)
            except Exception as exc:
                logger.exception("Backtest failed on date %s", current_date)
                return self._finalize_result(
                    started_at=started_at,
                    status="failed",
                    error=str(exc),
                )

            current_date += timedelta(days=1)

        self._backfill_resolutions()

        return self._finalize_result(started_at=started_at, status="completed")

    def _run_day(self, sim_date: date) -> None:
        """Run predictions for a single simulated day.

        Wraps all queries in a ``LookAheadGuard`` so they read from sim-date
        bounded views (``lookahead_market_prices``, ``lookahead_crisis_events``,
        ``lookahead_prediction_log``) rather than the raw temporal tables.
        """
        logger.info("Backtest running for date: %s", sim_date)

        with LookAheadGuard(self._conn, sim_date) as guard:
            market_prices = self._get_historical_market_prices(guard)
            news_context = self._get_historical_news(guard)

            for model_id in self._config.model_ids:
                for ticker in self._config.contract_tickers:
                    proxy_class = self._get_proxy_class(ticker, model_id)
                    if proxy_class == ProxyClass.NONE:
                        continue

                    predicted_prob = self._simulate_prediction(
                        guard=guard,
                        model_id=model_id,
                        ticker=ticker,
                        sim_date=sim_date,
                    )

                    if predicted_prob is not None:
                        market_price = market_prices.get(ticker)
                        edge_predicted = None
                        if market_price is not None:
                            edge_predicted = predicted_prob - market_price

                        prediction = BacktestPrediction(
                            prediction_id=str(uuid.uuid4()),
                            backtest_id=self._backtest_id,
                            sim_date=sim_date,
                            model_id=model_id,
                            contract_ticker=ticker,
                            predicted_probability=predicted_prob,
                            edge_predicted=edge_predicted,
                        )
                        self._predictions.append(prediction)
                        self._persist_prediction(prediction)

    def _get_historical_market_prices(self, guard: LookAheadGuard) -> dict[str, float]:
        """Get market prices available on the simulated date."""
        view = guard.view_for("market_prices")
        rows = self._conn.execute(
            f"""
            SELECT DISTINCT ON (ticker) ticker, yes_price
            FROM {view}
            ORDER BY ticker, fetched_at DESC
            """
        ).fetchall()

        return {row[0]: float(row[1]) for row in rows if row[1] is not None}

    def _get_historical_news(self, guard: LookAheadGuard) -> list[dict]:
        """Get news events available on the simulated date."""
        view = guard.view_for("crisis_events")
        rows = self._conn.execute(
            f"""
            SELECT headline, source, event_time, category
            FROM {view}
            ORDER BY event_time DESC
            LIMIT 50
            """
        ).fetchall()

        return [
            {
                "headline": row[0],
                "source": row[1],
                "event_time": row[2],
                "category": row[3],
            }
            for row in rows
        ]

    def _get_proxy_class(self, ticker: str, model_id: str) -> ProxyClass:
        """Look up the proxy class for a contract/model pair."""
        row = self._conn.execute(
            "SELECT proxy_class FROM contract_proxy_map WHERE ticker = ? AND model_type = ?",
            [ticker, model_id],
        ).fetchone()

        if row is None:
            return ProxyClass.NONE
        return ProxyClass(row[0])

    def _simulate_prediction(
        self,
        guard: LookAheadGuard,
        model_id: str,
        ticker: str,
        sim_date: date,
    ) -> float | None:
        """Simulate a prediction for the given model/contract on the simulated date.

        In a full implementation, this would run the actual LLM prediction pipeline.
        For the skeleton, we use historical prediction_log if available, or return None.

        The query reads from the sim-date-bounded ``lookahead_prediction_log``
        view, so any prediction_log row with ``created_at`` after the sim_date
        is invisible regardless of the ``DATE(created_at) = ?`` filter below.
        """
        view = guard.view_for("prediction_log")
        row = self._conn.execute(
            f"""
            SELECT probability
            FROM {view}
            WHERE model_id = ?
              AND DATE(created_at) = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            [model_id, sim_date],
        ).fetchone()

        if row is not None:
            return float(row[0])

        return None

    def _backfill_resolutions(self) -> None:
        """Backfill resolution prices for predictions from actual outcomes.

        For each prediction, picks the EARLIEST resolution that occurred at or
        after the sim_date — the resolution of the contract instance that the
        prediction was for. The previous implementation always took the latest
        resolution by ``resolved_at DESC LIMIT 1``, which silently injected a
        future-dated outcome (e.g. next week's settle) into every sim_date
        prediction for the same ticker. That's itself a look-ahead violation.
        """
        for prediction in self._predictions:
            sim_datetime = datetime.combine(
                prediction.sim_date, datetime.min.time(), tzinfo=timezone.utc,
            )
            row = self._conn.execute(
                """
                SELECT resolution_price, resolved_at
                FROM signal_ledger
                WHERE contract_ticker = ?
                  AND resolution_price IS NOT NULL
                  AND resolved_at >= ?
                ORDER BY resolved_at ASC
                LIMIT 1
                """,
                [prediction.contract_ticker, sim_datetime],
            ).fetchone()

            if row is not None:
                prediction.resolution_price = float(row[0])
                prediction.resolution_date = row[1].date() if row[1] else None

                if prediction.resolution_price is not None:
                    prediction.was_correct = (
                        (prediction.predicted_probability >= 0.5 and prediction.resolution_price >= 0.5)
                        or (prediction.predicted_probability < 0.5 and prediction.resolution_price < 0.5)
                    )
                    if prediction.edge_predicted is not None:
                        actual_outcome = 1.0 if prediction.resolution_price >= 0.5 else 0.0
                        prediction.edge_realized = actual_outcome - prediction.predicted_probability

                self._update_prediction_resolution(prediction)

    def _persist_backtest_start(self) -> None:
        """Persist backtest run metadata to DB."""
        self._conn.execute(
            """
            INSERT INTO backtest_runs
            (backtest_id, started_at, date_range_start, date_range_end, config_hash, contract_list, status)
            VALUES (?, ?, ?, ?, ?, ?, 'running')
            """,
            [
                self._backtest_id,
                datetime.now(timezone.utc),
                self._config.date_range_start,
                self._config.date_range_end,
                None,
                json.dumps(self._config.contract_tickers),
            ],
        )

    def _persist_prediction(self, prediction: BacktestPrediction) -> None:
        """Persist a single prediction to DB."""
        self._conn.execute(
            """
            INSERT INTO backtest_predictions
            (prediction_id, backtest_id, sim_date, model_id, contract_ticker,
             predicted_probability, predicted_direction, edge_predicted)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                prediction.prediction_id,
                prediction.backtest_id,
                prediction.sim_date,
                prediction.model_id,
                prediction.contract_ticker,
                prediction.predicted_probability,
                prediction.predicted_direction,
                prediction.edge_predicted,
            ],
        )

    def _update_prediction_resolution(self, prediction: BacktestPrediction) -> None:
        """Update a prediction with resolution data."""
        self._conn.execute(
            """
            UPDATE backtest_predictions
            SET resolution_price = ?,
                resolution_date = ?,
                edge_realized = ?,
                was_correct = ?
            WHERE prediction_id = ?
            """,
            [
                prediction.resolution_price,
                prediction.resolution_date,
                prediction.edge_realized,
                prediction.was_correct,
                prediction.prediction_id,
            ],
        )

    def _finalize_result(
        self,
        started_at: datetime,
        status: str,
        error: str | None = None,
    ) -> BacktestResult:
        """Finalize the backtest result and update DB."""
        ended_at = datetime.now(timezone.utc)

        self._conn.execute(
            """
            UPDATE backtest_runs
            SET ended_at = ?, status = ?, error = ?
            WHERE backtest_id = ?
            """,
            [ended_at, status, error, self._backtest_id],
        )

        return BacktestResult(
            backtest_id=self._backtest_id,
            config=self._config,
            predictions=self._predictions,
            started_at=started_at,
            ended_at=ended_at,
            status=status,
            error=error,
        )
