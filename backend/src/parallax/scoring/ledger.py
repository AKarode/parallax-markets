"""Append-only signal ledger backed by DuckDB.

Records every mapping evaluation (BUY_YES, BUY_NO, HOLD, REFUSED) with
full provenance: model claim, contract, proxy class, market state, and
trade decision. Immutable after creation -- only trade_id/traded/resolution
fields are updatable via mark_traded().
"""

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
    """Immutable record of a signal event -- the evaluation ledger entry."""

    signal_id: str
    run_id: str | None = None
    created_at: datetime
    model_id: str
    model_claim: str
    model_probability: float
    model_timeframe: str
    model_reasoning: str | None = None
    contract_ticker: str
    contract_title: str | None = None
    proxy_class: str
    confidence_discount: float
    market_yes_price: float
    market_no_price: float
    market_volume: float | None = None
    raw_edge: float
    effective_edge: float
    signal: str  # "BUY_YES" / "BUY_NO" / "HOLD" / "REFUSED"
    trade_id: str | None = None
    traded: bool = False
    trade_refused_reason: str | None = None
    raw_probability: float | None = None
    suggested_size: str | None = None
    resolution_price: float | None = None
    resolved_at: datetime | None = None
    realized_pnl: float | None = None
    model_was_correct: bool | None = None
    proxy_was_aligned: bool | None = None


class SignalLedger:
    """Append-only signal ledger backed by DuckDB."""

    def __init__(self, conn: duckdb.DuckDBPyConnection) -> None:
        self._conn = conn

    def record_signal(
        self,
        prediction: PredictionOutput,
        mapping: MappingResult,
        market_price: MarketPrice,
        contract_title: str | None = None,
        run_id: str | None = None,
        raw_probability: float | None = None,
    ) -> SignalRecord:
        """Create and persist a signal record from a mapping evaluation.

        Determines signal direction:
        - not should_trade -> REFUSED (with reason from mapping)
        - effective_edge > 0 and should_trade -> BUY_YES
        - effective_edge < 0 and should_trade -> BUY_NO
        - should_trade but abs(effective_edge) too small -> HOLD
        """
        signal_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        # Determine signal
        if not mapping.should_trade:
            signal = "REFUSED"
            trade_refused_reason = mapping.reason
        elif mapping.effective_edge > 0:
            signal = "BUY_YES"
            trade_refused_reason = None
        elif mapping.effective_edge < 0:
            signal = "BUY_NO"
            trade_refused_reason = None
        else:
            signal = "HOLD"
            trade_refused_reason = None

        model_claim = (
            f"{prediction.model_id}: {prediction.direction} "
            f"with P={prediction.probability:.2f} over {prediction.timeframe}"
        )

        # Compute suggested_size advisory for actionable signals
        suggested_size = None
        if signal in ("BUY_YES", "BUY_NO"):
            suggested_size = self._compute_suggested_size(
                prediction.model_id, mapping.proxy_class.value,
            )

        record = SignalRecord(
            signal_id=signal_id,
            run_id=run_id,
            created_at=now,
            model_id=prediction.model_id,
            model_claim=model_claim,
            model_probability=prediction.probability,
            model_timeframe=prediction.timeframe,
            model_reasoning=prediction.reasoning,
            contract_ticker=mapping.contract_ticker,
            contract_title=contract_title,
            proxy_class=mapping.proxy_class.value,
            confidence_discount=mapping.confidence_discount,
            market_yes_price=market_price.yes_price,
            market_no_price=market_price.no_price,
            market_volume=market_price.volume,
            raw_edge=mapping.raw_edge,
            effective_edge=mapping.effective_edge,
            signal=signal,
            trade_refused_reason=trade_refused_reason,
            raw_probability=raw_probability,
            suggested_size=suggested_size,
        )

        self._conn.execute(
            """
            INSERT INTO signal_ledger
            (signal_id, run_id, created_at, model_id, model_claim, model_probability,
             model_timeframe, model_reasoning, contract_ticker, contract_title,
             proxy_class, confidence_discount, market_yes_price, market_no_price,
             market_volume, raw_edge, effective_edge, signal,
             trade_refused_reason, raw_probability, suggested_size)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                record.signal_id,
                record.run_id,
                record.created_at.isoformat(),
                record.model_id,
                record.model_claim,
                record.model_probability,
                record.model_timeframe,
                record.model_reasoning,
                record.contract_ticker,
                record.contract_title,
                record.proxy_class,
                record.confidence_discount,
                record.market_yes_price,
                record.market_no_price,
                record.market_volume,
                record.raw_edge,
                record.effective_edge,
                record.signal,
                record.trade_refused_reason,
                record.raw_probability,
                record.suggested_size,
            ],
        )

        logger.debug(
            "Recorded signal %s: %s %s (edge=%+.1f%%)",
            signal_id[:8], signal, mapping.contract_ticker,
            mapping.effective_edge * 100,
        )
        return record

    def _compute_suggested_size(self, model_id: str, proxy_class: str) -> str:
        """Compute advisory position size based on historical performance.

        Returns 'full' for historically reliable model+proxy combos (5+ resolved,
        win_rate > 0.5), 'half' for untested or underperforming combos.
        """
        row = self._conn.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN model_was_correct THEN 1 ELSE 0 END) AS wins
            FROM signal_ledger
            WHERE model_id = ?
              AND proxy_class = ?
              AND model_was_correct IS NOT NULL
            """,
            [model_id, proxy_class],
        ).fetchone()

        if row and int(row[0]) >= 5 and int(row[1]) / int(row[0]) > 0.5:
            return "full"
        return "half"

    def get_signals(
        self, model_id: str | None = None, limit: int = 100,
    ) -> list[SignalRecord]:
        """Return signals from the ledger, optionally filtered by model_id.

        Results ordered by created_at descending.
        """
        if model_id is not None:
            rows = self._conn.execute(
                """
                SELECT * FROM signal_ledger
                WHERE model_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                [model_id, limit],
            ).fetchall()
        else:
            rows = self._conn.execute(
                """
                SELECT * FROM signal_ledger
                ORDER BY created_at DESC
                LIMIT ?
                """,
                [limit],
            ).fetchall()

        return [self._row_to_record(row) for row in rows]

    def get_actionable_signals(self) -> list[SignalRecord]:
        """Return signals that are actionable: BUY_YES or BUY_NO, not yet traded.

        Ordered by abs(effective_edge) descending.
        """
        rows = self._conn.execute(
            """
            SELECT * FROM signal_ledger
            WHERE signal IN ('BUY_YES', 'BUY_NO')
              AND traded = false
            ORDER BY abs(effective_edge) DESC
            """
        ).fetchall()

        return [self._row_to_record(row) for row in rows]

    def mark_traded(self, signal_id: str, trade_id: str) -> None:
        """Mark a signal as traded with the given trade ID."""
        self._conn.execute(
            """
            UPDATE signal_ledger
            SET traded = true, trade_id = ?
            WHERE signal_id = ?
            """,
            [trade_id, signal_id],
        )
        logger.debug("Marked signal %s as traded (trade=%s)", signal_id[:8], trade_id[:8])

    def _row_to_record(self, row: tuple) -> SignalRecord:
        """Convert a DuckDB row tuple to a SignalRecord.

        Column order matches signal_ledger CREATE TABLE in db/schema.py.
        """
        return SignalRecord(
            signal_id=row[0],
            run_id=row[1],
            created_at=row[2],
            model_id=row[3],
            model_claim=row[4],
            model_probability=row[5],
            raw_probability=row[6],
            model_timeframe=row[7],
            model_reasoning=row[8],
            contract_ticker=row[9],
            contract_title=row[10],
            proxy_class=row[11],
            confidence_discount=row[12],
            market_yes_price=row[13],
            market_no_price=row[14],
            market_volume=row[15],
            raw_edge=row[16],
            effective_edge=row[17],
            signal=row[18],
            trade_id=row[19],
            traded=bool(row[20]) if row[20] is not None else False,
            trade_refused_reason=row[21],
            suggested_size=row[22],
            resolution_price=row[23],
            resolved_at=row[24],
            realized_pnl=row[25],
            model_was_correct=row[26],
            proxy_was_aligned=row[27],
        )
