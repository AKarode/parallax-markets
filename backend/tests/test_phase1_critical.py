"""Integration tests for Phase 1 critical fixes.

Covers two issues called out in docs/REVIEW-POST-IMPLEMENTATION-2026-05-06.md:

1. ``LookAheadGuard`` previously injected WHERE clauses by string mangling
   and ``BacktestRunner`` bypassed it entirely. Replaced with sim-date-bounded
   views; this file verifies the runner now reads through those views and that
   ``_backfill_resolutions`` no longer pulls future-dated outcomes.
2. ``compute_staleness_penalty`` was computed but never wired into the
   prediction pipeline. The ``ensemble_predict`` call path now receives
   ``context_age_hours`` from each predictor; this file verifies the wiring
   end-to-end via mocked predictors.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import duckdb
import pytest

from parallax.backtest.look_ahead_guard import LookAheadGuard, look_ahead_safe
from parallax.backtest.runner import BacktestConfig, BacktestRunner
from parallax.contracts.schemas import ProxyClass
from parallax.db.schema import create_tables
from parallax.prediction.crisis_context import (
    SEED_EVENTS,
    _latest_seed_event_time,
    get_crisis_context_with_metadata,
)
from parallax.prediction.ensemble import (
    apply_context_staleness_penalty,
    ensemble_predict,
)


@pytest.fixture()
def conn() -> duckdb.DuckDBPyConnection:
    conn = duckdb.connect(":memory:")
    create_tables(conn)
    return conn


# ---------------------------------------------------------------------------
# Section 1: Bounded-view look-ahead guard
# ---------------------------------------------------------------------------


class TestBoundedViews:
    """Bounded views replace string-injection filtering."""

    def test_view_for_returns_prefixed_name(self, conn: duckdb.DuckDBPyConnection) -> None:
        sim_date = date(2026, 4, 10)
        with LookAheadGuard(conn, sim_date) as guard:
            assert guard.view_for("market_prices") == "lookahead_market_prices"
            assert guard.view_for("crisis_events") == "lookahead_crisis_events"

    def test_view_for_outside_active_raises(self, conn: duckdb.DuckDBPyConnection) -> None:
        guard = LookAheadGuard(conn, date(2026, 4, 10))
        with pytest.raises(RuntimeError, match="not active"):
            guard.view_for("market_prices")

    def test_view_for_unknown_table_raises(self, conn: duckdb.DuckDBPyConnection) -> None:
        with LookAheadGuard(conn, date(2026, 4, 10)) as guard:
            with pytest.raises(KeyError):
                guard.view_for("not_a_temporal_table")

    def test_views_dropped_on_exit(self, conn: duckdb.DuckDBPyConnection) -> None:
        sim_date = date(2026, 4, 10)
        with LookAheadGuard(conn, sim_date):
            row = conn.execute(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_name = 'lookahead_market_prices'"
            ).fetchone()
            assert row[0] == 1

        row = conn.execute(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_name = 'lookahead_market_prices'"
        ).fetchone()
        assert row[0] == 0

    def test_bounded_view_excludes_future_rows(self, conn: duckdb.DuckDBPyConnection) -> None:
        sim_date = date(2026, 4, 10)
        past = datetime.combine(sim_date, datetime.min.time(), tzinfo=timezone.utc)
        future = past + timedelta(days=2)
        conn.execute(
            """
            INSERT INTO market_prices
            (ticker, source, data_environment, fetched_at, yes_price, no_price, volume)
            VALUES
              ('PAST', 'test', 'backtest', ?, 0.4, 0.6, 1),
              ('FUTURE', 'test', 'backtest', ?, 0.5, 0.5, 1)
            """,
            [past, future],
        )

        with LookAheadGuard(conn, sim_date) as guard:
            view = guard.view_for("market_prices")
            tickers = [r[0] for r in conn.execute(f"SELECT ticker FROM {view}").fetchall()]
        assert "PAST" in tickers
        assert "FUTURE" not in tickers

    def test_bounded_view_handles_joins(self, conn: duckdb.DuckDBPyConnection) -> None:
        """The previous string-mangler couldn't filter joined tables — bounded views can."""
        sim_date = date(2026, 4, 10)
        past = datetime.combine(sim_date, datetime.min.time(), tzinfo=timezone.utc)
        future = past + timedelta(days=2)

        conn.execute(
            """
            INSERT INTO market_prices
            (ticker, source, data_environment, fetched_at, yes_price, no_price, volume)
            VALUES
              ('TKR', 'test', 'backtest', ?, 0.5, 0.5, 1)
            """,
            [past],
        )
        conn.execute(
            """
            INSERT INTO crisis_events (id, event_time, headline, source, category)
            VALUES
              ('past-evt', ?, 'past headline', 'test', 'general'),
              ('fut-evt', ?, 'future headline', 'test', 'general')
            """,
            [past, future],
        )

        with LookAheadGuard(conn, sim_date) as guard:
            mp_view = guard.view_for("market_prices")
            ce_view = guard.view_for("crisis_events")
            rows = conn.execute(
                f"""
                SELECT m.ticker, c.headline FROM {mp_view} m
                CROSS JOIN {ce_view} c
                """
            ).fetchall()

        headlines = {row[1] for row in rows}
        assert "past headline" in headlines
        assert "future headline" not in headlines

    def test_execute_rewrites_bare_table_names(self, conn: duckdb.DuckDBPyConnection) -> None:
        """Backwards-compat: ``guard.execute`` rewrites bare table refs to views."""
        sim_date = date(2026, 4, 10)
        past = datetime.combine(sim_date, datetime.min.time(), tzinfo=timezone.utc)
        future = past + timedelta(days=2)
        conn.execute(
            """
            INSERT INTO crisis_events (id, event_time, headline, source, category)
            VALUES ('p', ?, 'past', 'test', 'g'), ('f', ?, 'future', 'test', 'g')
            """,
            [past, future],
        )
        with look_ahead_safe(conn, sim_date) as guard:
            rows = guard.execute("SELECT headline FROM crisis_events").fetchall()
        headlines = [r[0] for r in rows]
        assert "past" in headlines
        assert "future" not in headlines


# ---------------------------------------------------------------------------
# Section 2: BacktestRunner uses bounded views
# ---------------------------------------------------------------------------


class TestRunnerUsesBoundedViews:
    """The runner must route helper queries through bounded views."""

    def _seed_runner_data(
        self,
        conn: duckdb.DuckDBPyConnection,
        ticker: str,
        sim_date: date,
        past_prob: float,
        future_prob: float,
    ) -> None:
        past = datetime.combine(sim_date, datetime.min.time(), tzinfo=timezone.utc)
        future = past + timedelta(days=3)

        conn.execute(
            """
            INSERT INTO contract_proxy_map (ticker, model_type, proxy_class, confidence_discount)
            VALUES (?, 'oil_price', 'direct', 1.0)
            """,
            [ticker],
        )
        conn.execute(
            """
            INSERT INTO market_prices
            (ticker, source, data_environment, fetched_at, yes_price, no_price, volume)
            VALUES
              (?, 'test', 'backtest', ?, 0.40, 0.60, 1),
              (?, 'test', 'backtest', ?, 0.99, 0.01, 1)
            """,
            [ticker, past, ticker, future],
        )
        conn.execute(
            """
            INSERT INTO prediction_log
            (log_id, run_id, model_id, probability, direction, confidence,
             reasoning, timeframe, data_environment, created_at)
            VALUES
              ('past-log', 'r1', 'oil_price', ?, 'increase', 0.7, 'past', '7d', 'live', ?),
              ('future-log', 'r2', 'oil_price', ?, 'increase', 0.7, 'future', '7d', 'live', ?)
            """,
            [past_prob, past, future_prob, future],
        )

    def test_runner_does_not_see_future_market_price(self, conn: duckdb.DuckDBPyConnection) -> None:
        sim_date = date(2026, 4, 10)
        ticker = "OILY"
        self._seed_runner_data(conn, ticker, sim_date, past_prob=0.6, future_prob=0.99)

        config = BacktestConfig(
            date_range_start=sim_date,
            date_range_end=sim_date,
            contract_tickers=[ticker],
            model_ids=["oil_price"],
        )
        runner = BacktestRunner(conn, config)
        result = runner.run()

        assert result.status == "completed"
        assert len(result.predictions) == 1
        pred = result.predictions[0]
        # past market price was 0.40, past prediction was 0.6 -> edge = 0.20
        assert pred.predicted_probability == pytest.approx(0.6)
        assert pred.edge_predicted == pytest.approx(0.20)

    def test_runner_does_not_see_future_prediction_log(self, conn: duckdb.DuckDBPyConnection) -> None:
        """A prediction_log row with future ``created_at`` is invisible at sim_date.

        Negative control: even if the prediction_log row's DATE matches the
        sim_date, if its created_at timestamp is after end-of-day on sim_date
        the bounded view excludes it.
        """
        sim_date = date(2026, 4, 10)
        ticker = "FUTURELOG"
        # Insert a row whose DATE(created_at) = sim_date but timestamp is
        # AFTER sim_date end-of-day (impossible in practice, but a clear
        # test of view boundedness). We achieve this by using a created_at
        # whose date is later than the sim_date entirely.
        later_date = sim_date + timedelta(days=2)
        later_ts = datetime.combine(later_date, datetime.min.time(), tzinfo=timezone.utc)

        conn.execute(
            """
            INSERT INTO contract_proxy_map (ticker, model_type, proxy_class, confidence_discount)
            VALUES (?, 'oil_price', 'direct', 1.0)
            """,
            [ticker],
        )
        conn.execute(
            """
            INSERT INTO prediction_log
            (log_id, run_id, model_id, probability, direction, confidence,
             reasoning, timeframe, data_environment, created_at)
            VALUES ('future-log', 'r2', 'oil_price', 0.99, 'increase', 0.7,
                    'future', '7d', 'live', ?)
            """,
            [later_ts],
        )
        config = BacktestConfig(
            date_range_start=sim_date,
            date_range_end=sim_date,
            contract_tickers=[ticker],
            model_ids=["oil_price"],
        )
        runner = BacktestRunner(conn, config)
        result = runner.run()

        # The future-dated prediction_log row must NOT bleed back into sim_date.
        assert len(result.predictions) == 0


class TestBackfillResolutions:
    """Multi-resolution contracts must not bleed future outcomes into past predictions."""

    def test_picks_earliest_resolution_at_or_after_sim_date(
        self, conn: duckdb.DuckDBPyConnection,
    ) -> None:
        sim_date = date(2026, 4, 10)
        ticker = "WEEKLY"
        self._seed_two_resolutions(conn, ticker)

        config = BacktestConfig(
            date_range_start=sim_date,
            date_range_end=sim_date,
            contract_tickers=[ticker],
            model_ids=["oil_price"],
        )
        # Seed minimal data so the predictor branch finds a probability.
        past = datetime.combine(sim_date, datetime.min.time(), tzinfo=timezone.utc)
        conn.execute(
            """
            INSERT INTO contract_proxy_map (ticker, model_type, proxy_class, confidence_discount)
            VALUES (?, 'oil_price', 'direct', 1.0)
            """,
            [ticker],
        )
        conn.execute(
            """
            INSERT INTO market_prices
            (ticker, source, data_environment, fetched_at, yes_price, no_price, volume)
            VALUES (?, 'test', 'backtest', ?, 0.50, 0.50, 1)
            """,
            [ticker, past],
        )
        conn.execute(
            """
            INSERT INTO prediction_log
            (log_id, run_id, model_id, probability, direction, confidence,
             reasoning, timeframe, data_environment, created_at)
            VALUES ('p', 'r', 'oil_price', 0.55, 'increase', 0.5, 'r', '7d', 'live', ?)
            """,
            [past],
        )

        runner = BacktestRunner(conn, config)
        result = runner.run()
        assert len(result.predictions) == 1
        pred = result.predictions[0]
        # The earliest resolution after sim_date is the one priced at 0.0,
        # NOT the latest (0.99) — that's the look-ahead defect we fixed.
        assert pred.resolution_price == pytest.approx(0.0)

    def test_skips_resolutions_before_sim_date(self, conn: duckdb.DuckDBPyConnection) -> None:
        """A resolution dated BEFORE the sim_date can't apply to that prediction."""
        sim_date = date(2026, 4, 10)
        ticker = "OLDONLY"
        before = datetime.combine(
            sim_date - timedelta(days=5), datetime.min.time(), tzinfo=timezone.utc,
        )
        conn.execute(
            """
            INSERT INTO signal_ledger
            (signal_id, run_id, created_at, model_id, model_claim, model_probability,
             model_timeframe, contract_ticker, proxy_class, confidence_discount,
             signal, tradeability_status, resolution_price, resolved_at)
            VALUES (?, 'r', ?, 'oil_price', 'm', 0.5, '7d', ?, 'direct', 1.0,
                    'BUY_YES', 'tradable', 1.0, ?)
            """,
            [f"sig-old-{ticker}", before, ticker, before],
        )
        conn.execute(
            """
            INSERT INTO contract_proxy_map (ticker, model_type, proxy_class, confidence_discount)
            VALUES (?, 'oil_price', 'direct', 1.0)
            """,
            [ticker],
        )
        past = datetime.combine(sim_date, datetime.min.time(), tzinfo=timezone.utc)
        conn.execute(
            """
            INSERT INTO market_prices
            (ticker, source, data_environment, fetched_at, yes_price, no_price, volume)
            VALUES (?, 'test', 'backtest', ?, 0.50, 0.50, 1)
            """,
            [ticker, past],
        )
        conn.execute(
            """
            INSERT INTO prediction_log
            (log_id, run_id, model_id, probability, direction, confidence,
             reasoning, timeframe, data_environment, created_at)
            VALUES ('p2', 'r', 'oil_price', 0.55, 'increase', 0.5, 'r', '7d', 'live', ?)
            """,
            [past],
        )
        config = BacktestConfig(
            date_range_start=sim_date,
            date_range_end=sim_date,
            contract_tickers=[ticker],
            model_ids=["oil_price"],
        )
        runner = BacktestRunner(conn, config)
        result = runner.run()
        assert len(result.predictions) == 1
        # Only resolution is dated before sim_date, so backfill must skip it.
        assert result.predictions[0].resolution_price is None

    @staticmethod
    def _seed_two_resolutions(conn: duckdb.DuckDBPyConnection, ticker: str) -> None:
        sim_date = date(2026, 4, 10)
        early = datetime.combine(
            sim_date + timedelta(days=2), datetime.min.time(), tzinfo=timezone.utc,
        )
        late = datetime.combine(
            sim_date + timedelta(days=20), datetime.min.time(), tzinfo=timezone.utc,
        )
        conn.execute(
            """
            INSERT INTO signal_ledger
            (signal_id, run_id, created_at, model_id, model_claim, model_probability,
             model_timeframe, contract_ticker, proxy_class, confidence_discount,
             signal, tradeability_status, resolution_price, resolved_at)
            VALUES
              (?, 'r', ?, 'oil_price', 'm', 0.5, '7d', ?, 'direct', 1.0,
               'BUY_YES', 'tradable', 0.0, ?),
              (?, 'r', ?, 'oil_price', 'm', 0.5, '7d', ?, 'direct', 1.0,
               'BUY_YES', 'tradable', 0.99, ?)
            """,
            [
                f"sig-early-{ticker}", early, ticker, early,
                f"sig-late-{ticker}", late, ticker, late,
            ],
        )


# ---------------------------------------------------------------------------
# Section 3: Staleness penalty wired through the prediction path
# ---------------------------------------------------------------------------


class TestStalenessFallbackAge:
    """Hardcoded fallback context now reports a real age, not 0.0."""

    def test_fallback_age_matches_seed_events(self) -> None:
        result = get_crisis_context_with_metadata(None)
        latest = _latest_seed_event_time()
        expected = (datetime.now(timezone.utc) - latest).total_seconds() / 3600
        assert result.context_age_hours == pytest.approx(expected, abs=1.0)
        assert result.is_from_db is False
        assert result.event_count == len(SEED_EVENTS)


class TestEnsemblePenaltyWiring:
    """``ensemble_predict`` shrinks ``parsed["confidence"]`` when context is stale."""

    @pytest.mark.asyncio
    async def test_stale_context_reduces_parsed_confidence(self) -> None:
        client = self._fake_anthropic_client(probability=0.7, confidence=0.9)
        budget = MagicMock()
        budget.record = MagicMock()

        result = await ensemble_predict(
            client=client,
            model="claude-test",
            prompt="ignored",
            budget=budget,
            max_tokens=100,
            context_age_hours=48.0,
        )

        # apply_context_staleness_penalty(0.9, 48) == 0.45
        assert result["parsed"]["confidence"] == pytest.approx(0.45)
        assert result["parsed"]["staleness_penalty_applied"] is True
        assert result["context_age_hours"] == 48.0

    @pytest.mark.asyncio
    async def test_fresh_context_preserves_confidence(self) -> None:
        client = self._fake_anthropic_client(probability=0.7, confidence=0.9)
        budget = MagicMock()
        budget.record = MagicMock()

        result = await ensemble_predict(
            client=client,
            model="claude-test",
            prompt="ignored",
            budget=budget,
            max_tokens=100,
            context_age_hours=12.0,
        )
        assert result["parsed"]["confidence"] == pytest.approx(0.9)
        assert "staleness_penalty_applied" not in result["parsed"]

    @staticmethod
    def _fake_anthropic_client(probability: float, confidence: float) -> MagicMock:
        """Build a mock AsyncAnthropic with `messages.create` returning a parseable payload."""
        client = MagicMock()
        client.messages = MagicMock()

        async def _create(**_kwargs):
            response = MagicMock()
            response.usage = MagicMock(input_tokens=10, output_tokens=10)
            content = MagicMock()
            content.text = (
                '{"probability": %s, "confidence": %s, "direction": "increase", '
                '"magnitude_range": [1, 2], "reasoning": "x", "evidence": ["e1"]}'
                % (probability, confidence)
            )
            response.content = [content]
            return response

        client.messages.create = AsyncMock(side_effect=_create)
        return client


class TestPredictorPassesContextAge:
    """End-to-end: predictors call ``ensemble_predict`` with ``context_age_hours``."""

    @pytest.mark.asyncio
    async def test_oil_price_predictor_passes_context_age(
        self, conn: duckdb.DuckDBPyConnection, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from parallax.prediction import oil_price as oil_mod
        from parallax.simulation.world_state import WorldState

        captured: dict[str, object] = {}

        async def _fake_ensemble(**kwargs):
            captured.update(kwargs)
            return {
                "ensemble": {
                    "probability": 0.5,
                    "std_dev": 0.0,
                    "is_unstable": False,
                    "individual_probabilities": [0.5],
                },
                "parsed": {
                    "probability": 0.5, "direction": "stable",
                    "magnitude_range": [0, 1], "reasoning": "r",
                    "evidence": [], "confidence": 0.8,
                },
                "all_parsed": [],
                "call_count": 1,
                "context_age_hours": kwargs.get("context_age_hours"),
            }

        monkeypatch.setattr(oil_mod, "ensemble_predict", _fake_ensemble)

        cascade = MagicMock()
        cascade.activate_bypass.return_value = {"bypass_flow": 0.0}
        cascade.compute_price_shock.return_value = 100.0
        ws = WorldState()
        predictor = oil_mod.OilPricePredictor(cascade, MagicMock(), MagicMock())
        await predictor.predict(
            recent_events=[], current_prices=[], world_state=ws, db_conn=conn,
        )

        assert "context_age_hours" in captured
        assert captured["context_age_hours"] is not None
        # DB is empty so we get the SEED_EVENTS-based age (months old).
        assert captured["context_age_hours"] > 0.0

    @pytest.mark.asyncio
    async def test_ceasefire_predictor_passes_context_age(
        self, conn: duckdb.DuckDBPyConnection, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from parallax.prediction import ceasefire as ceasefire_mod

        captured: dict[str, object] = {}

        async def _fake_ensemble(**kwargs):
            captured.update(kwargs)
            return {
                "ensemble": {
                    "probability": 0.5, "std_dev": 0.0, "is_unstable": False,
                    "individual_probabilities": [0.5],
                },
                "parsed": {
                    "probability": 0.5, "direction": "stable",
                    "magnitude_range": [0, 1], "reasoning": "r",
                    "evidence": [], "confidence": 0.8,
                },
                "all_parsed": [],
                "call_count": 1,
                "context_age_hours": kwargs.get("context_age_hours"),
            }

        monkeypatch.setattr(ceasefire_mod, "ensemble_predict", _fake_ensemble)
        predictor = ceasefire_mod.CeasefirePredictor(MagicMock(), MagicMock())
        await predictor.predict(recent_events=[], db_conn=conn)
        assert captured.get("context_age_hours", None) is not None

    @pytest.mark.asyncio
    async def test_hormuz_predictor_passes_context_age(
        self, conn: duckdb.DuckDBPyConnection, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from parallax.prediction import hormuz as hormuz_mod
        from parallax.simulation.world_state import WorldState

        captured: dict[str, object] = {}

        async def _fake_ensemble(**kwargs):
            captured.update(kwargs)
            return {
                "ensemble": {
                    "probability": 0.5, "std_dev": 0.0, "is_unstable": False,
                    "individual_probabilities": [0.5],
                },
                "parsed": {
                    "probability": 0.5, "direction": "stable",
                    "magnitude_range": [0, 1], "reasoning": "r",
                    "evidence": [], "confidence": 0.8,
                },
                "all_parsed": [],
                "call_count": 1,
                "context_age_hours": kwargs.get("context_age_hours"),
            }

        monkeypatch.setattr(hormuz_mod, "ensemble_predict", _fake_ensemble)
        cascade = MagicMock()
        # _estimate_recovery accesses cascade._config.hormuz_daily_flow via getattr
        cascade._config = MagicMock(hormuz_daily_flow=21_000_000)
        predictor = hormuz_mod.HormuzReopeningPredictor(cascade, MagicMock(), MagicMock())
        await predictor.predict(recent_events=[], world_state=WorldState(), db_conn=conn)
        assert captured.get("context_age_hours", None) is not None

    @pytest.mark.asyncio
    async def test_predictor_uses_db_age_when_events_present(
        self, conn: duckdb.DuckDBPyConnection, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When DB has fresh events, age should be from the DB, not the seed list."""
        from parallax.prediction import oil_price as oil_mod
        from parallax.simulation.world_state import WorldState

        recent = datetime.now(timezone.utc) - timedelta(hours=2)
        conn.execute(
            """
            INSERT INTO crisis_events (id, event_time, headline, source, category)
            VALUES ('fresh', ?, 'fresh headline', 'test', 'general')
            """,
            [recent],
        )

        captured: dict[str, object] = {}

        async def _fake_ensemble(**kwargs):
            captured.update(kwargs)
            return {
                "ensemble": {
                    "probability": 0.5, "std_dev": 0.0, "is_unstable": False,
                    "individual_probabilities": [0.5],
                },
                "parsed": {
                    "probability": 0.5, "direction": "stable",
                    "magnitude_range": [0, 1], "reasoning": "r",
                    "evidence": [], "confidence": 0.8,
                },
                "all_parsed": [],
                "call_count": 1,
                "context_age_hours": kwargs.get("context_age_hours"),
            }

        monkeypatch.setattr(oil_mod, "ensemble_predict", _fake_ensemble)

        cascade = MagicMock()
        cascade.activate_bypass.return_value = {"bypass_flow": 0.0}
        cascade.compute_price_shock.return_value = 100.0
        predictor = oil_mod.OilPricePredictor(cascade, MagicMock(), MagicMock())
        await predictor.predict(
            recent_events=[], current_prices=[], world_state=WorldState(), db_conn=conn,
        )

        age = captured.get("context_age_hours")
        assert age is not None
        # 2 hours old, give some tolerance
        assert age == pytest.approx(2.0, abs=0.5)


class TestApplyStalenessPenalty:
    """Sanity checks for the penalty function used by the wiring above."""

    def test_within_24_hours_unchanged(self) -> None:
        assert apply_context_staleness_penalty(0.9, 24) == 0.9

    def test_at_48_hours_halved(self) -> None:
        assert apply_context_staleness_penalty(0.9, 48) == pytest.approx(0.45)

    def test_at_72_hours_zero(self) -> None:
        assert apply_context_staleness_penalty(0.9, 72) == pytest.approx(0.0)

    def test_none_age_unchanged(self) -> None:
        assert apply_context_staleness_penalty(0.9, None) == 0.9
