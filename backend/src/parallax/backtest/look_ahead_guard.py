"""Look-ahead guard to prevent future data from contaminating backtests.

Materializes sim-date-bounded views over each temporal table on enter and
drops them on exit. Backtest code queries the views (e.g.
``lookahead_market_prices``) instead of the raw tables, so the date bound is
enforced by the database rather than by string manipulation of the SQL.

The previous implementation tried to inject ``WHERE`` clauses with regex/string
mangling. That approach silently mishandled JOINs, ``OR`` precedence, aliases,
CTEs, and anything beyond a flat ``SELECT``. Bounded views push the bound into
the query plan so every consumer sees the same filtered slice without each
caller having to remember to apply the filter.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from datetime import date, datetime, timezone
from typing import Any, Iterator

import duckdb

logger = logging.getLogger(__name__)


class LookAheadGuard:
    """Context manager that exposes sim-date-bounded views over temporal tables.

    Usage::

        with LookAheadGuard(conn, sim_date) as guard:
            view_name = guard.view_for("market_prices")  # "lookahead_market_prices"
            rows = conn.execute(f"SELECT * FROM {view_name}").fetchall()

    For each table in ``TEMPORAL_TABLES`` a temporary view is created on enter
    and dropped on exit. The view name is ``lookahead_<table>``.
    """

    TEMPORAL_TABLES = {
        "prediction_log": "created_at",
        "market_prices": "fetched_at",
        "crisis_events": "event_time",
        "signal_ledger": "created_at",
        "curated_events": "ingested_at",
        "raw_gdelt": "fetched_at",
    }
    VIEW_PREFIX = "lookahead_"

    def __init__(
        self,
        conn: duckdb.DuckDBPyConnection,
        sim_date: date,
    ) -> None:
        """Initialize the look-ahead guard.

        Args:
            conn: DuckDB connection on which to create/drop views.
            sim_date: Simulated date - bounded views will only expose rows
                whose temporal column is <= end-of-day on this date.
        """
        self._conn = conn
        self._sim_date = sim_date
        self._sim_datetime = datetime.combine(
            sim_date, datetime.max.time(), tzinfo=timezone.utc
        )
        self._active = False
        self._created_views: list[str] = []

    def __enter__(self) -> "LookAheadGuard":
        if self._active:
            raise RuntimeError("LookAheadGuard is already active")

        self._active = True
        self._create_bounded_views()
        logger.debug(
            "LookAheadGuard activated: sim_date=%s views=%s",
            self._sim_date, self._created_views,
        )
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        try:
            self._drop_bounded_views()
        finally:
            self._active = False
            logger.debug("LookAheadGuard deactivated for sim_date=%s", self._sim_date)

    def _create_bounded_views(self) -> None:
        """Create one temporary view per temporal table, bounded by sim_date."""
        sim_iso = self._sim_datetime.isoformat()
        for table_name, time_column in self.TEMPORAL_TABLES.items():
            if not self._table_exists(table_name):
                continue
            view_name = f"{self.VIEW_PREFIX}{table_name}"
            self._conn.execute(
                f"""
                CREATE OR REPLACE TEMP VIEW {view_name} AS
                SELECT * FROM {table_name}
                WHERE {time_column} <= TIMESTAMP '{sim_iso}'
                """
            )
            self._created_views.append(view_name)

    def _drop_bounded_views(self) -> None:
        """Drop all views created on enter."""
        for view_name in self._created_views:
            try:
                self._conn.execute(f"DROP VIEW IF EXISTS {view_name}")
            except Exception:
                logger.exception("Failed to drop bounded view %s", view_name)
        self._created_views.clear()

    def _table_exists(self, table_name: str) -> bool:
        row = self._conn.execute(
            """
            SELECT COUNT(*) FROM information_schema.tables
            WHERE table_name = ?
            """,
            [table_name],
        ).fetchone()
        return bool(row and row[0])

    def view_for(self, table_name: str) -> str:
        """Return the bounded view name for a temporal table.

        Raises:
            KeyError: If the table is not in ``TEMPORAL_TABLES``.
            RuntimeError: If the guard is not active.
        """
        if not self._active:
            raise RuntimeError("LookAheadGuard is not active")
        if table_name not in self.TEMPORAL_TABLES:
            raise KeyError(f"{table_name!r} is not a temporal table")
        return f"{self.VIEW_PREFIX}{table_name}"

    def execute(
        self,
        query: str,
        parameters: list[Any] | None = None,
    ) -> Any:
        """Execute a query with bounded-view substitution.

        For SELECT queries that reference any temporal table by bare name, the
        bare name is rewritten to the bounded view name. This is best-effort
        and exists for backwards compatibility with callers that haven't been
        migrated to use ``view_for(...)`` directly.

        Non-SELECT queries (INSERT/UPDATE/DELETE) and queries that don't touch
        a temporal table are passed through unchanged.
        """
        if not self._active:
            return self._conn.execute(query, parameters)

        rewritten = self._rewrite_to_views(query)
        return self._conn.execute(rewritten, parameters)

    def _rewrite_to_views(self, query: str) -> str:
        """Substitute bare temporal-table names with bounded view names.

        Only rewrites SELECT statements. Uses simple word-boundary matching;
        callers needing complex SQL should query views by name via ``view_for``.
        """
        import re

        stripped = query.lstrip().upper()
        if not stripped.startswith(("SELECT", "WITH")):
            return query

        rewritten = query
        for table_name in self.TEMPORAL_TABLES:
            view_name = f"{self.VIEW_PREFIX}{table_name}"
            pattern = rf"\b{re.escape(table_name)}\b"
            rewritten = re.sub(pattern, view_name, rewritten)
        return rewritten

    @property
    def sim_date(self) -> date:
        """Return the simulated date."""
        return self._sim_date

    @property
    def is_active(self) -> bool:
        """Return whether the guard is currently active."""
        return self._active


@contextmanager
def look_ahead_safe(
    conn: duckdb.DuckDBPyConnection,
    sim_date: date,
) -> Iterator[LookAheadGuard]:
    """Context manager for look-ahead-safe query execution.

    Use ``guard.view_for(table)`` to obtain the bounded view name, or call
    ``guard.execute(...)`` to have bare temporal-table names rewritten.

    Example::

        with look_ahead_safe(conn, date(2026, 4, 10)) as guard:
            view = guard.view_for("market_prices")
            rows = conn.execute(f"SELECT * FROM {view}").fetchall()
    """
    guard = LookAheadGuard(conn, sim_date)
    with guard:
        yield guard
