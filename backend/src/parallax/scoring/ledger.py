"""Append-only signal ledger backed by DuckDB."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

import duckdb
from pydantic import BaseModel

from parallax.contracts.schemas import MappingResult
from parallax.markets.schemas import MarketPrice
from parallax.prediction.schemas import PredictionOutput

logger = logging.getLogger(__name__)


class SignalRecord(BaseModel):
    """Immutable signal decision with execution context."""

    signal_id: str
    run_id: str | None = None
    created_at: datetime
    data_environment: str = "live"
    execution_environment: str = "none"
    venue: str | None = None
    model_id: str
    model_claim: str
    model_probability: float
    raw_probability: float | None = None
    model_timeframe: str
    model_reasoning: str | None = None
    contract_ticker: str
    contract_title: str | None = None
    proxy_class: str
    confidence_discount: float
    market_best_yes_bid: float | None = None
    market_best_yes_ask: float | None = None
    market_best_no_bid: float | None = None
    market_best_no_ask: float | None = None
    market_yes_spread: float | None = None
    market_no_spread: float | None = None
    market_yes_price: float | None = None
    market_no_price: float | None = None
    market_derived_yes_price: float | None = None
    market_derived_no_price: float | None = None
    market_derived_price_kind: str | None = None
    market_volume: float | None = None
    market_quote_timestamp: datetime | None = None
    buy_yes_edge: float | None = None
    buy_no_edge: float | None = None
    raw_edge: float | None = None
    effective_edge: float | None = None
    signal: str
    tradeability_status: str = "unknown"
    entry_side: str | None = None
    entry_price: float | None = None
    entry_price_kind: str | None = None
    entry_price_is_executable: bool = False
    entry_order_id: str | None = None
    trade_id: str | None = None
    position_id: str | None = None
    traded: bool = False
    trade_refused_reason: str | None = None
    execution_status: str = "not_attempted"
    suggested_size: str | None = None
    resolution_price: float | None = None
    resolved_at: datetime | None = None
    realized_pnl: float | None = None
    counterfactual_pnl: float | None = None
    model_was_correct: bool | None = None
    proxy_was_aligned: bool | None = None


class SignalLedger:
    """Append-only signal ledger backed by DuckDB."""

    SIGNAL_COLUMNS = [
        "signal_id",
        "run_id",
        "created_at",
        "data_environment",
        "execution_environment",
        "venue",
        "model_id",
        "model_claim",
        "model_probability",
        "raw_probability",
        "model_timeframe",
        "model_reasoning",
        "contract_ticker",
        "contract_title",
        "proxy_class",
        "confidence_discount",
        "market_best_yes_bid",
        "market_best_yes_ask",
        "market_best_no_bid",
        "market_best_no_ask",
        "market_yes_spread",
        "market_no_spread",
        "market_yes_price",
        "market_no_price",
        "market_derived_yes_price",
        "market_derived_no_price",
        "market_derived_price_kind",
        "market_volume",
        "market_quote_timestamp",
        "buy_yes_edge",
        "buy_no_edge",
        "raw_edge",
        "effective_edge",
        "signal",
        "tradeability_status",
        "entry_side",
        "entry_price",
        "entry_price_kind",
        "entry_price_is_executable",
        "entry_order_id",
        "trade_id",
        "position_id",
        "traded",
        "trade_refused_reason",
        "execution_status",
        "suggested_size",
        "resolution_price",
        "resolved_at",
        "realized_pnl",
        "counterfactual_pnl",
        "model_was_correct",
        "proxy_was_aligned",
    ]

    def __init__(self, conn: duckdb.DuckDBPyConnection) -> None:
        self._conn = conn

    def record_signal(
        self,
        prediction: PredictionOutput,
        mapping: MappingResult,
        market_price: MarketPrice,
        *,
        contract_title: str | None = None,
        run_id: str | None = None,
        raw_probability: float | None = None,
        data_environment: str = "live",
        execution_environment: str = "none",
    ) -> SignalRecord:
        signal_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        if mapping.tradeability_status == "non_tradable":
            signal = "REFUSED"
            trade_refused_reason = mapping.reason
        elif not mapping.should_trade:
            signal = "HOLD"
            trade_refused_reason = mapping.reason
        elif mapping.entry_side == "yes":
            signal = "BUY_YES"
            trade_refused_reason = None
        elif mapping.entry_side == "no":
            signal = "BUY_NO"
            trade_refused_reason = None
        else:
            signal = "REFUSED"
            trade_refused_reason = mapping.reason

        model_claim = (
            f"{prediction.model_id}: {prediction.direction} "
            f"with P={prediction.probability:.2f} over {prediction.timeframe}"
        )

        suggested_size = None
        if signal in ("BUY_YES", "BUY_NO"):
            suggested_size = self._compute_suggested_size(
                prediction.model_id,
                mapping.proxy_class.value,
            )

        record = SignalRecord(
            signal_id=signal_id,
            run_id=run_id,
            created_at=now,
            data_environment=data_environment,
            execution_environment=execution_environment,
            venue=market_price.source,
            model_id=prediction.model_id,
            model_claim=model_claim,
            model_probability=prediction.probability,
            raw_probability=raw_probability,
            model_timeframe=prediction.timeframe,
            model_reasoning=prediction.reasoning,
            contract_ticker=mapping.contract_ticker,
            contract_title=contract_title,
            proxy_class=mapping.proxy_class.value,
            confidence_discount=mapping.confidence_discount,
            market_best_yes_bid=market_price.best_yes_bid,
            market_best_yes_ask=market_price.best_yes_ask,
            market_best_no_bid=market_price.best_no_bid,
            market_best_no_ask=market_price.best_no_ask,
            market_yes_spread=market_price.yes_bid_ask_spread,
            market_no_spread=market_price.no_bid_ask_spread,
            market_yes_price=market_price.yes_price,
            market_no_price=market_price.no_price,
            market_derived_yes_price=market_price.yes_price,
            market_derived_no_price=market_price.no_price,
            market_derived_price_kind=market_price.derived_price_kind,
            market_volume=market_price.volume,
            market_quote_timestamp=market_price.quote_timestamp,
            buy_yes_edge=mapping.buy_yes_edge,
            buy_no_edge=mapping.buy_no_edge,
            raw_edge=mapping.raw_edge or 0.0,
            effective_edge=mapping.effective_edge or 0.0,
            signal=signal,
            tradeability_status=mapping.tradeability_status,
            entry_side=mapping.entry_side,
            entry_price=mapping.entry_price,
            entry_price_kind=mapping.entry_price_kind,
            entry_price_is_executable=mapping.entry_price_is_executable,
            trade_refused_reason=trade_refused_reason,
            suggested_size=suggested_size,
        )

        placeholders = ", ".join(["?"] * len(self.SIGNAL_COLUMNS))
        self._conn.execute(
            f"""
            INSERT INTO signal_ledger ({", ".join(self.SIGNAL_COLUMNS)})
            VALUES ({placeholders})
            """,
            [
                getattr(record, column)
                for column in self.SIGNAL_COLUMNS
            ],
        )

        logger.debug(
            "Recorded signal %s: %s %s (exec=%s @ %s)",
            signal_id[:8],
            signal,
            mapping.contract_ticker,
            record.entry_price_kind,
            record.entry_price,
        )
        return record

    def update_execution(
        self,
        signal_id: str,
        *,
        execution_status: str,
        entry_order_id: str | None = None,
        position_id: str | None = None,
        traded: bool | None = None,
        trade_refused_reason: str | None = None,
    ) -> None:
        self._conn.execute(
            """
            UPDATE signal_ledger
            SET execution_status = ?,
                entry_order_id = COALESCE(?, entry_order_id),
                trade_id = COALESCE(?, trade_id),
                position_id = COALESCE(?, position_id),
                traded = COALESCE(?, traded),
                trade_refused_reason = COALESCE(?, trade_refused_reason)
            WHERE signal_id = ?
            """,
            [execution_status, entry_order_id, position_id, position_id, traded, trade_refused_reason, signal_id],
        )

    def _compute_suggested_size(self, model_id: str, proxy_class: str) -> str:
        row = self._conn.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN model_was_correct THEN 1 ELSE 0 END) AS wins
            FROM signal_quality_evaluation
            WHERE model_id = ?
              AND proxy_class = ?
            """,
            [model_id, proxy_class],
        ).fetchone()

        if row and int(row[0]) >= 5 and int(row[1]) / int(row[0]) > 0.5:
            return "full"
        return "half"

    def get_signals(
        self,
        model_id: str | None = None,
        limit: int = 100,
    ) -> list[SignalRecord]:
        columns = ", ".join(self.SIGNAL_COLUMNS)
        if model_id is not None:
            rows = self._conn.execute(
                f"""
                SELECT {columns}
                FROM signal_ledger
                WHERE model_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                [model_id, limit],
            ).fetchall()
        else:
            rows = self._conn.execute(
                f"""
                SELECT {columns}
                FROM signal_ledger
                ORDER BY created_at DESC
                LIMIT ?
                """,
                [limit],
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def get_actionable_signals(self) -> list[SignalRecord]:
        columns = ", ".join(self.SIGNAL_COLUMNS)
        rows = self._conn.execute(
            f"""
            SELECT {columns}
            FROM signal_ledger
            WHERE signal IN ('BUY_YES', 'BUY_NO')
              AND entry_price_is_executable = true
              AND traded = false
              AND execution_status IN ('not_attempted', 'rejected', 'cancelled')
            ORDER BY abs(COALESCE(effective_edge, 0.0)) DESC
            """
        ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def mark_traded(self, signal_id: str, trade_id: str) -> None:
        self.update_execution(
            signal_id,
            execution_status="filled",
            position_id=trade_id,
            traded=True,
        )

    def _row_to_record(self, row: tuple) -> SignalRecord:
        values = {
            column: row[index]
            for index, column in enumerate(self.SIGNAL_COLUMNS)
        }
        return SignalRecord(**values)
