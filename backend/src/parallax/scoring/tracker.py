"""Paper trade journal with explicit order, fill, and position lifecycle."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import duckdb
from pydantic import BaseModel

from parallax.markets.kalshi import KalshiClient
from parallax.scoring.ledger import SignalLedger, SignalRecord

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_ts(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    text = str(value)
    if text.endswith("Z"):
        text = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


class OrderAttempt(BaseModel):
    order_id: str
    signal_id: str
    run_id: str | None = None
    ticker: str
    venue: str
    venue_environment: str
    side: str
    quantity: int
    intended_price: float | None = None
    intended_price_kind: str | None = None
    executable_reference_price: float | None = None
    order_type: str = "limit"
    status: str
    venue_order_id: str | None = None
    submitted_at: datetime
    accepted_at: datetime | None = None
    rejected_at: datetime | None = None
    rejected_reason: str | None = None
    cancelled_at: datetime | None = None
    cancellation_reason: str | None = None
    last_update_at: datetime | None = None
    filled_quantity: int = 0
    avg_fill_price: float | None = None
    raw_response: dict | None = None


class FillRecord(BaseModel):
    fill_id: str
    order_id: str
    signal_id: str
    position_id: str
    ticker: str
    venue: str
    venue_environment: str
    side: str
    quantity: int
    fill_price: float | None = None
    fee_amount: float | None = None
    liquidity: str | None = None
    filled_at: datetime
    venue_fill_id: str | None = None


class PositionRecord(BaseModel):
    position_id: str
    signal_id: str
    run_id: str | None = None
    ticker: str
    venue: str
    venue_environment: str
    side: str
    quantity: int
    open_quantity: int
    entry_price: float
    opened_at: datetime
    exit_price: float | None = None
    settlement_price: float | None = None
    closed_at: datetime | None = None
    status: str
    realized_pnl: float | None = None
    unrealized_pnl: float | None = None
    resolution_price: float | None = None
    resolution_source: str | None = None


class PaperTradeTracker:
    """Persist sandbox order attempts and resulting positions."""

    def __init__(
        self,
        conn: duckdb.DuckDBPyConnection,
        ledger: SignalLedger,
        kalshi_client: KalshiClient,
    ) -> None:
        self._conn = conn
        self._ledger = ledger
        self._kalshi = kalshi_client

    async def execute_signal(
        self,
        signal: SignalRecord,
        *,
        quantity: int = 10,
    ) -> OrderAttempt:
        order = OrderAttempt(
            order_id=str(uuid.uuid4()),
            signal_id=signal.signal_id,
            run_id=signal.run_id,
            ticker=signal.contract_ticker,
            venue=signal.venue or "kalshi",
            venue_environment=self._kalshi.venue_environment,
            side=signal.entry_side or ("yes" if signal.signal == "BUY_YES" else "no"),
            quantity=quantity,
            intended_price=signal.entry_price,
            intended_price_kind=signal.entry_price_kind,
            executable_reference_price=signal.entry_price,
            status="attempted",
            submitted_at=_now(),
        )
        self._insert_order(order)

        if signal.signal not in ("BUY_YES", "BUY_NO"):
            return self._reject_order(order, "Signal is not actionable")
        if not signal.entry_price_is_executable or signal.entry_price is None:
            return self._reject_order(order, "No executable entry quote available")

        try:
            response = await self._kalshi.place_order(
                ticker=signal.contract_ticker,
                side=order.side,
                quantity=quantity,
                price=round(signal.entry_price * 100),
            )
        except Exception as exc:
            logger.exception("Failed to place order for %s", signal.contract_ticker)
            return self._reject_order(order, f"Venue error: {exc}")

        venue_order = response.get("order", response)
        order.raw_response = venue_order
        order.venue_order_id = venue_order.get("order_id")
        order.last_update_at = _parse_ts(venue_order.get("last_update_time")) or _now()

        venue_status = str(venue_order.get("status", "")).lower()
        fill_count = int(venue_order.get("fill_count", 0) or 0)
        avg_fill_price = self._derive_average_fill_price(venue_order, order.side, fill_count)
        order.avg_fill_price = avg_fill_price
        order.filled_quantity = fill_count

        if venue_status in {"rejected", "error"}:
            order.status = "rejected"
            order.rejected_at = _now()
            order.rejected_reason = venue_order.get("error") or "Venue rejected order"
            self._update_order(order)
            self._ledger.update_execution(
                signal.signal_id,
                execution_status="rejected",
                entry_order_id=order.order_id,
                traded=False,
                trade_refused_reason=order.rejected_reason,
            )
            return order

        order.accepted_at = _parse_ts(venue_order.get("created_time")) or _now()
        order.status = "accepted"

        if venue_status in {"filled", "executed", "matched"} or fill_count > 0:
            position = self._open_position(signal, order, fill_count, avg_fill_price)
            fill = FillRecord(
                fill_id=str(uuid.uuid4()),
                order_id=order.order_id,
                signal_id=signal.signal_id,
                position_id=position.position_id,
                ticker=signal.contract_ticker,
                venue=order.venue,
                venue_environment=order.venue_environment,
                side=order.side,
                quantity=fill_count or quantity,
                fill_price=avg_fill_price,
                fee_amount=self._derive_fee_amount(venue_order),
                liquidity="taker",
                filled_at=_parse_ts(venue_order.get("last_update_time")) or _now(),
            )
            self._insert_fill(fill)
            order.status = "filled"
            self._update_order(order)
            self._ledger.update_execution(
                signal.signal_id,
                execution_status="filled",
                entry_order_id=order.order_id,
                position_id=position.position_id,
                traded=True,
            )
            return order

        if venue_status in {"cancelled", "canceled"}:
            order.status = "cancelled"
            order.cancelled_at = _now()
            order.cancellation_reason = venue_order.get("cancel_reason")
            self._update_order(order)
            self._ledger.update_execution(
                signal.signal_id,
                execution_status="cancelled",
                entry_order_id=order.order_id,
                traded=False,
                trade_refused_reason=order.cancellation_reason,
            )
            return order

        self._update_order(order)
        self._ledger.update_execution(
            signal.signal_id,
            execution_status="accepted",
            entry_order_id=order.order_id,
            traded=False,
        )
        return order

    def get_open_positions(self) -> list[PositionRecord]:
        rows = self._conn.execute(
            """
            SELECT position_id, signal_id, run_id, ticker, venue, venue_environment,
                   side, quantity, open_quantity, entry_price, opened_at, exit_price,
                   settlement_price, closed_at, status, realized_pnl, unrealized_pnl,
                   resolution_price, resolution_source
            FROM trade_positions
            WHERE status = 'open'
            ORDER BY opened_at DESC
            """
        ).fetchall()
        return [PositionRecord(**self._position_row_to_dict(row)) for row in rows]

    def get_trade_journal(self) -> list[dict]:
        rows = self._conn.execute(
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
                p.realized_pnl
            FROM trade_orders AS o
            LEFT JOIN trade_positions AS p
              ON p.signal_id = o.signal_id
            ORDER BY o.submitted_at DESC
            """
        ).fetchall()
        return [
            {
                "order_id": row[0],
                "signal_id": row[1],
                "ticker": row[2],
                "side": row[3],
                "quantity": row[4],
                "intended_price": row[5],
                "order_status": row[6],
                "submitted_at": row[7],
                "accepted_at": row[8],
                "rejected_at": row[9],
                "cancelled_at": row[10],
                "avg_fill_price": row[11],
                "position_id": row[12],
                "position_status": row[13],
                "realized_pnl": row[14],
            }
            for row in rows
        ]

    def _reject_order(self, order: OrderAttempt, reason: str) -> OrderAttempt:
        order.status = "rejected"
        order.rejected_at = _now()
        order.rejected_reason = reason
        order.last_update_at = order.rejected_at
        self._update_order(order)
        self._ledger.update_execution(
            order.signal_id,
            execution_status="rejected",
            entry_order_id=order.order_id,
            traded=False,
            trade_refused_reason=reason,
        )
        return order

    def _open_position(
        self,
        signal: SignalRecord,
        order: OrderAttempt,
        fill_count: int,
        avg_fill_price: float | None,
    ) -> PositionRecord:
        quantity = fill_count or order.quantity
        if avg_fill_price is None:
            raise ValueError("Filled orders must have an average fill price")
        position = PositionRecord(
            position_id=str(uuid.uuid4()),
            signal_id=signal.signal_id,
            run_id=signal.run_id,
            ticker=signal.contract_ticker,
            venue=order.venue,
            venue_environment=order.venue_environment,
            side=order.side,
            quantity=quantity,
            open_quantity=quantity,
            entry_price=avg_fill_price,
            opened_at=order.accepted_at or _now(),
            status="open",
            unrealized_pnl=0.0,
        )
        self._conn.execute(
            """
            INSERT INTO trade_positions
            (position_id, signal_id, run_id, ticker, venue, venue_environment, side,
             quantity, open_quantity, entry_price, opened_at, exit_price,
             settlement_price, closed_at, status, realized_pnl, unrealized_pnl,
             resolution_price, resolution_source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                position.position_id,
                position.signal_id,
                position.run_id,
                position.ticker,
                position.venue,
                position.venue_environment,
                position.side,
                position.quantity,
                position.open_quantity,
                position.entry_price,
                position.opened_at,
                position.exit_price,
                position.settlement_price,
                position.closed_at,
                position.status,
                position.realized_pnl,
                position.unrealized_pnl,
                position.resolution_price,
                position.resolution_source,
            ],
        )
        return position

    def _insert_order(self, order: OrderAttempt) -> None:
        self._conn.execute(
            """
            INSERT INTO trade_orders
            (order_id, signal_id, run_id, ticker, venue, venue_environment, side,
             quantity, intended_price, intended_price_kind, executable_reference_price,
             order_type, status, venue_order_id, submitted_at, accepted_at,
             rejected_at, rejected_reason, cancelled_at, cancellation_reason,
             last_update_at, filled_quantity, avg_fill_price, raw_response)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                order.order_id,
                order.signal_id,
                order.run_id,
                order.ticker,
                order.venue,
                order.venue_environment,
                order.side,
                order.quantity,
                order.intended_price,
                order.intended_price_kind,
                order.executable_reference_price,
                order.order_type,
                order.status,
                order.venue_order_id,
                order.submitted_at,
                order.accepted_at,
                order.rejected_at,
                order.rejected_reason,
                order.cancelled_at,
                order.cancellation_reason,
                order.last_update_at,
                order.filled_quantity,
                order.avg_fill_price,
                json.dumps(order.raw_response) if order.raw_response is not None else None,
            ],
        )

    def _update_order(self, order: OrderAttempt) -> None:
        self._conn.execute(
            """
            UPDATE trade_orders
            SET status = ?,
                venue_order_id = ?,
                accepted_at = ?,
                rejected_at = ?,
                rejected_reason = ?,
                cancelled_at = ?,
                cancellation_reason = ?,
                last_update_at = ?,
                filled_quantity = ?,
                avg_fill_price = ?,
                raw_response = ?
            WHERE order_id = ?
            """,
            [
                order.status,
                order.venue_order_id,
                order.accepted_at,
                order.rejected_at,
                order.rejected_reason,
                order.cancelled_at,
                order.cancellation_reason,
                order.last_update_at,
                order.filled_quantity,
                order.avg_fill_price,
                json.dumps(order.raw_response) if order.raw_response is not None else None,
                order.order_id,
            ],
        )

    def _insert_fill(self, fill: FillRecord) -> None:
        self._conn.execute(
            """
            INSERT INTO trade_fills
            (fill_id, order_id, signal_id, position_id, ticker, venue, venue_environment,
             side, quantity, fill_price, fee_amount, liquidity, filled_at, venue_fill_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                fill.fill_id,
                fill.order_id,
                fill.signal_id,
                fill.position_id,
                fill.ticker,
                fill.venue,
                fill.venue_environment,
                fill.side,
                fill.quantity,
                fill.fill_price,
                fill.fee_amount,
                fill.liquidity,
                fill.filled_at,
                fill.venue_fill_id,
            ],
        )

    def _position_row_to_dict(self, row: tuple) -> dict[str, Any]:
        return {
            "position_id": row[0],
            "signal_id": row[1],
            "run_id": row[2],
            "ticker": row[3],
            "venue": row[4],
            "venue_environment": row[5],
            "side": row[6],
            "quantity": row[7],
            "open_quantity": row[8],
            "entry_price": row[9],
            "opened_at": row[10],
            "exit_price": row[11],
            "settlement_price": row[12],
            "closed_at": row[13],
            "status": row[14],
            "realized_pnl": row[15],
            "unrealized_pnl": row[16],
            "resolution_price": row[17],
            "resolution_source": row[18],
        }

    @staticmethod
    def _derive_average_fill_price(
        venue_order: dict[str, Any],
        side: str,
        fill_count: int,
    ) -> float | None:
        if fill_count <= 0:
            return None
        fill_cost = venue_order.get("taker_fill_cost") or venue_order.get("maker_fill_cost")
        if fill_cost is not None:
            return (float(fill_cost) / 100.0) / fill_count
        fill_cost_dollars = venue_order.get("taker_fill_cost_dollars") or venue_order.get("maker_fill_cost_dollars")
        if fill_cost_dollars is not None:
            return float(fill_cost_dollars) / fill_count
        priced_field = venue_order.get("yes_price_dollars" if side == "yes" else "no_price_dollars")
        if priced_field is not None:
            return float(priced_field)
        return None

    @staticmethod
    def _derive_fee_amount(venue_order: dict[str, Any]) -> float | None:
        fee = venue_order.get("taker_fees") or venue_order.get("maker_fees")
        if fee is None:
            return None
        return float(fee) / 100.0
