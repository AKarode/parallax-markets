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

ACTIVE_ORDER_STATUSES = ("attempted", "accepted", "resting", "partially_filled", "pending_cancel")
TERMINAL_ORDER_STATUSES = {"filled", "cancelled", "rejected"}


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
        return self._reconcile_order_snapshot(order, venue_order)

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

    async def poll_resting_orders(
        self,
        *,
        limit: int | None = None,
    ) -> list[OrderAttempt]:
        reconciled: list[OrderAttempt] = []
        for order in self._get_active_orders(limit=limit):
            if not order.venue_order_id:
                logger.warning("Skipping active order %s without venue_order_id", order.order_id)
                continue
            try:
                response = await self._kalshi.get_order(order.venue_order_id)
            except Exception:
                logger.exception("Failed to poll venue order %s", order.venue_order_id)
                continue
            venue_order = response.get("order", response)
            reconciled.append(self._reconcile_order_snapshot(order, venue_order))
        return reconciled

    async def cancel_order(
        self,
        order_id: str,
        *,
        reason: str | None = None,
    ) -> OrderAttempt:
        order = self._get_order(order_id)
        if order is None:
            raise ValueError(f"Unknown order_id: {order_id}")

        if order.status in TERMINAL_ORDER_STATUSES:
            return order

        if not order.venue_order_id:
            order.status = "cancelled"
            order.cancelled_at = _now()
            order.cancellation_reason = reason or "Cancelled before venue acknowledgement"
            order.last_update_at = order.cancelled_at
            self._update_order(order)
            self._sync_ledger(order)
            return order

        response = await self._kalshi.cancel_order(order.venue_order_id)
        venue_order = response.get("order", response)
        reduced_by = self._derive_contract_count(
            response.get(
                "reduced_by_fp",
                venue_order.get("reduced_by_fp", response.get("reduced_by", venue_order.get("reduced_by"))),
            ),
        )
        fill_count = self._derive_fill_count(venue_order)
        remaining_count = self._derive_remaining_count(venue_order, order.quantity, fill_count)
        force_cancelled = reduced_by > 0 or (remaining_count == 0 and fill_count < order.quantity)
        return self._reconcile_order_snapshot(
            order,
            venue_order,
            cancellation_reason=reason,
            force_cancelled=force_cancelled,
        )

    async def cancel_stale_orders(
        self,
        *,
        max_age_seconds: float,
        limit: int | None = None,
        reason: str | None = None,
    ) -> list[OrderAttempt]:
        now = _now()
        cancelled: list[OrderAttempt] = []
        for order in self._get_active_orders(limit=limit):
            age = now - self._order_activity_ts(order)
            if age.total_seconds() < max_age_seconds:
                continue
            cancelled.append(
                await self.cancel_order(
                    order.order_id,
                    reason=reason or f"Resting order exceeded {max_age_seconds:.0f}s age limit",
                )
            )
        return cancelled

    def _reject_order(self, order: OrderAttempt, reason: str) -> OrderAttempt:
        order.status = "rejected"
        order.rejected_at = _now()
        order.rejected_reason = reason
        order.last_update_at = order.rejected_at
        self._update_order(order)
        self._sync_ledger(order)
        return order

    def _reconcile_order_snapshot(
        self,
        order: OrderAttempt,
        venue_order: dict[str, Any],
        *,
        cancellation_reason: str | None = None,
        force_cancelled: bool = False,
    ) -> OrderAttempt:
        prior_filled_quantity = order.filled_quantity
        prior_avg_fill_price = order.avg_fill_price

        order.raw_response = venue_order
        order.venue_order_id = str(venue_order.get("order_id") or order.venue_order_id or "")
        if not order.venue_order_id:
            order.venue_order_id = None

        created_at = _parse_ts(venue_order.get("created_time"))
        if created_at and order.accepted_at is None:
            order.accepted_at = created_at

        order.last_update_at = (
            _parse_ts(venue_order.get("last_update_time"))
            or _parse_ts(venue_order.get("updated_time"))
            or _now()
        )

        fill_count = self._derive_fill_count(venue_order)
        remaining_count = self._derive_remaining_count(venue_order, order.quantity, fill_count)
        order.filled_quantity = max(fill_count, order.filled_quantity)

        avg_fill_price = self._derive_average_fill_price(venue_order, order.side, fill_count)
        if avg_fill_price is not None:
            order.avg_fill_price = avg_fill_price

        venue_status = str(venue_order.get("status", "")).lower()
        order.status = self._normalize_order_status(
            venue_status,
            fill_count=fill_count,
            remaining_count=remaining_count,
            order_quantity=order.quantity,
            force_cancelled=force_cancelled,
        )

        if order.status == "rejected":
            order.rejected_at = order.rejected_at or order.last_update_at or _now()
            order.rejected_reason = (
                venue_order.get("error")
                or venue_order.get("reject_reason")
                or venue_order.get("reason")
                or order.rejected_reason
                or "Venue rejected order"
            )

        if order.status == "cancelled":
            order.cancelled_at = order.cancelled_at or order.last_update_at or _now()
            order.cancellation_reason = (
                cancellation_reason
                or venue_order.get("cancel_reason")
                or venue_order.get("reason")
                or order.cancellation_reason
            )

        position_id: str | None = None
        if order.filled_quantity > 0:
            position = self._upsert_position(
                order,
                total_filled=order.filled_quantity,
                avg_fill_price=order.avg_fill_price,
                opened_at=order.accepted_at or order.last_update_at or _now(),
            )
            position_id = position.position_id

        fill_delta = max(order.filled_quantity - prior_filled_quantity, 0)
        if fill_delta > 0 and position_id is not None:
            fill_record = self._build_fill_record(
                order,
                venue_order,
                fill_delta=fill_delta,
                cumulative_fill_count=order.filled_quantity,
                previous_fill_count=prior_filled_quantity,
                previous_avg_fill_price=prior_avg_fill_price,
                position_id=position_id,
            )
            self._insert_fill_if_missing(fill_record)

        self._update_order(order)
        self._sync_ledger(order, position_id=position_id)
        return order

    def _sync_ledger(
        self,
        order: OrderAttempt,
        *,
        position_id: str | None = None,
    ) -> None:
        if position_id is None and order.filled_quantity > 0:
            position = self._get_position(order.signal_id)
            position_id = position.position_id if position else None

        if order.filled_quantity > 0:
            self._ledger.update_execution(
                order.signal_id,
                execution_status="filled",
                entry_order_id=order.order_id,
                position_id=position_id,
                traded=True,
            )
            return

        if order.status == "rejected":
            self._ledger.update_execution(
                order.signal_id,
                execution_status="rejected",
                entry_order_id=order.order_id,
                traded=False,
                trade_refused_reason=order.rejected_reason,
            )
            return

        if order.status == "cancelled":
            self._ledger.update_execution(
                order.signal_id,
                execution_status="cancelled",
                entry_order_id=order.order_id,
                traded=False,
                trade_refused_reason=order.cancellation_reason,
            )
            return

        self._ledger.update_execution(
            order.signal_id,
            execution_status="accepted",
            entry_order_id=order.order_id,
            traded=False,
        )

    def _upsert_position(
        self,
        order: OrderAttempt,
        *,
        total_filled: int,
        avg_fill_price: float | None,
        opened_at: datetime,
    ) -> PositionRecord:
        quantity = total_filled or order.quantity
        if avg_fill_price is None:
            raise ValueError("Filled orders must have an average fill price")
        existing = self._get_position(order.signal_id)
        if existing is not None:
            self._conn.execute(
                """
                UPDATE trade_positions
                SET quantity = ?,
                    open_quantity = ?,
                    entry_price = ?,
                    opened_at = ?,
                    status = ?
                WHERE position_id = ?
                """,
                [
                    quantity,
                    quantity,
                    avg_fill_price,
                    existing.opened_at or opened_at,
                    "open",
                    existing.position_id,
                ],
            )
            return PositionRecord(
                position_id=existing.position_id,
                signal_id=existing.signal_id,
                run_id=existing.run_id,
                ticker=existing.ticker,
                venue=existing.venue,
                venue_environment=existing.venue_environment,
                side=existing.side,
                quantity=quantity,
                open_quantity=quantity,
                entry_price=avg_fill_price,
                opened_at=existing.opened_at or opened_at,
                exit_price=existing.exit_price,
                settlement_price=existing.settlement_price,
                closed_at=existing.closed_at,
                status="open",
                realized_pnl=existing.realized_pnl,
                unrealized_pnl=existing.unrealized_pnl,
                resolution_price=existing.resolution_price,
                resolution_source=existing.resolution_source,
            )

        position = PositionRecord(
            position_id=str(uuid.uuid4()),
            signal_id=order.signal_id,
            run_id=order.run_id,
            ticker=order.ticker,
            venue=order.venue,
            venue_environment=order.venue_environment,
            side=order.side,
            quantity=quantity,
            open_quantity=quantity,
            entry_price=avg_fill_price,
            opened_at=opened_at,
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

    def _get_order(self, order_id: str) -> OrderAttempt | None:
        row = self._conn.execute(
            """
            SELECT order_id, signal_id, run_id, ticker, venue, venue_environment,
                   side, quantity, intended_price, intended_price_kind,
                   executable_reference_price, order_type, status, venue_order_id,
                   submitted_at, accepted_at, rejected_at, rejected_reason,
                   cancelled_at, cancellation_reason, last_update_at,
                   filled_quantity, avg_fill_price, raw_response
            FROM trade_orders
            WHERE order_id = ? OR venue_order_id = ?
            ORDER BY CASE WHEN order_id = ? THEN 0 ELSE 1 END
            LIMIT 1
            """,
            [order_id, order_id, order_id],
        ).fetchone()
        return OrderAttempt(**self._order_row_to_dict(row)) if row else None

    def _get_active_orders(self, *, limit: int | None = None) -> list[OrderAttempt]:
        params: list[Any] = list(ACTIVE_ORDER_STATUSES)
        query = f"""
            SELECT order_id, signal_id, run_id, ticker, venue, venue_environment,
                   side, quantity, intended_price, intended_price_kind,
                   executable_reference_price, order_type, status, venue_order_id,
                   submitted_at, accepted_at, rejected_at, rejected_reason,
                   cancelled_at, cancellation_reason, last_update_at,
                   filled_quantity, avg_fill_price, raw_response
            FROM trade_orders
            WHERE status IN ({", ".join(["?"] * len(ACTIVE_ORDER_STATUSES))})
            ORDER BY COALESCE(last_update_at, accepted_at, submitted_at) ASC
        """
        if limit is not None:
            query += "\nLIMIT ?"
            params.append(limit)
        rows = self._conn.execute(query, params).fetchall()
        return [OrderAttempt(**self._order_row_to_dict(row)) for row in rows]

    def _get_position(self, signal_id: str) -> PositionRecord | None:
        row = self._conn.execute(
            """
            SELECT position_id, signal_id, run_id, ticker, venue, venue_environment,
                   side, quantity, open_quantity, entry_price, opened_at, exit_price,
                   settlement_price, closed_at, status, realized_pnl, unrealized_pnl,
                   resolution_price, resolution_source
            FROM trade_positions
            WHERE signal_id = ?
            ORDER BY opened_at DESC
            LIMIT 1
            """,
            [signal_id],
        ).fetchone()
        return PositionRecord(**self._position_row_to_dict(row)) if row else None

    def _order_row_to_dict(self, row: tuple[Any, ...]) -> dict[str, Any]:
        raw_response = row[23]
        if isinstance(raw_response, str):
            raw_response = json.loads(raw_response)
        return {
            "order_id": row[0],
            "signal_id": row[1],
            "run_id": row[2],
            "ticker": row[3],
            "venue": row[4],
            "venue_environment": row[5],
            "side": row[6],
            "quantity": row[7],
            "intended_price": row[8],
            "intended_price_kind": row[9],
            "executable_reference_price": row[10],
            "order_type": row[11],
            "status": row[12],
            "venue_order_id": row[13],
            "submitted_at": row[14],
            "accepted_at": row[15],
            "rejected_at": row[16],
            "rejected_reason": row[17],
            "cancelled_at": row[18],
            "cancellation_reason": row[19],
            "last_update_at": row[20],
            "filled_quantity": row[21],
            "avg_fill_price": row[22],
            "raw_response": raw_response,
        }

    def _build_fill_record(
        self,
        order: OrderAttempt,
        venue_order: dict[str, Any],
        *,
        fill_delta: int,
        cumulative_fill_count: int,
        previous_fill_count: int,
        previous_avg_fill_price: float | None,
        position_id: str,
    ) -> FillRecord:
        fill_price = self._derive_incremental_fill_price(
            venue_order,
            side=order.side,
            fill_delta=fill_delta,
            cumulative_fill_count=cumulative_fill_count,
            previous_fill_count=previous_fill_count,
            previous_avg_fill_price=previous_avg_fill_price,
        )
        fee_amount = self._derive_incremental_fee_amount(order.order_id, venue_order)
        fill_marker = f"{order.order_id}:{cumulative_fill_count}"
        return FillRecord(
            fill_id=fill_marker,
            order_id=order.order_id,
            signal_id=order.signal_id,
            position_id=position_id,
            ticker=order.ticker,
            venue=order.venue,
            venue_environment=order.venue_environment,
            side=order.side,
            quantity=fill_delta,
            fill_price=fill_price,
            fee_amount=fee_amount,
            liquidity="taker",
            filled_at=_parse_ts(venue_order.get("last_update_time")) or _now(),
            venue_fill_id=fill_marker,
        )

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

    def _insert_fill_if_missing(self, fill: FillRecord) -> None:
        existing = self._conn.execute(
            "SELECT 1 FROM trade_fills WHERE fill_id = ?",
            [fill.fill_id],
        ).fetchone()
        if existing:
            return
        self._insert_fill(fill)

    def _get_recorded_fee_amount(self, order_id: str) -> float:
        row = self._conn.execute(
            """
            SELECT COALESCE(SUM(fee_amount), 0.0)
            FROM trade_fills
            WHERE order_id = ?
            """,
            [order_id],
        ).fetchone()
        return float(row[0] or 0.0)

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
        fill_cost = PaperTradeTracker._first_present(venue_order, "taker_fill_cost", "maker_fill_cost")
        if fill_cost is not None:
            return (float(fill_cost) / 100.0) / fill_count
        fill_cost_dollars = PaperTradeTracker._first_present(
            venue_order,
            "taker_fill_cost_dollars",
            "maker_fill_cost_dollars",
        )
        if fill_cost_dollars is not None:
            return float(fill_cost_dollars) / fill_count
        priced_field = venue_order.get("yes_price_dollars" if side == "yes" else "no_price_dollars")
        if priced_field is not None:
            return float(priced_field)
        return None

    def _derive_incremental_fee_amount(
        self,
        order_id: str,
        venue_order: dict[str, Any],
    ) -> float | None:
        fee = self._derive_total_fee_amount(venue_order)
        if fee is None:
            return None
        recorded_fee = self._get_recorded_fee_amount(order_id)
        return max(fee - recorded_fee, 0.0)

    @staticmethod
    def _derive_total_fill_cost(venue_order: dict[str, Any]) -> float | None:
        fill_cost = PaperTradeTracker._first_present(venue_order, "taker_fill_cost", "maker_fill_cost")
        if fill_cost is not None:
            return float(fill_cost) / 100.0
        fill_cost_dollars = PaperTradeTracker._first_present(
            venue_order,
            "taker_fill_cost_dollars",
            "maker_fill_cost_dollars",
        )
        if fill_cost_dollars is not None:
            return float(fill_cost_dollars)
        return None

    @staticmethod
    def _derive_total_fee_amount(venue_order: dict[str, Any]) -> float | None:
        fee = PaperTradeTracker._first_present(venue_order, "taker_fees", "maker_fees")
        if fee is not None:
            return float(fee) / 100.0
        fee_dollars = PaperTradeTracker._first_present(
            venue_order,
            "taker_fees_dollars",
            "maker_fees_dollars",
        )
        if fee_dollars is not None:
            return float(fee_dollars)
        return None

    @classmethod
    def _derive_incremental_fill_price(
        cls,
        venue_order: dict[str, Any],
        *,
        side: str,
        fill_delta: int,
        cumulative_fill_count: int,
        previous_fill_count: int,
        previous_avg_fill_price: float | None,
    ) -> float | None:
        if fill_delta <= 0:
            return None
        total_fill_cost = cls._derive_total_fill_cost(venue_order)
        if total_fill_cost is not None and previous_avg_fill_price is not None:
            prior_total_cost = previous_avg_fill_price * previous_fill_count
            delta_cost = total_fill_cost - prior_total_cost
            if delta_cost >= 0:
                return delta_cost / fill_delta
        return cls._derive_average_fill_price(venue_order, side, cumulative_fill_count)

    @staticmethod
    def _derive_fill_count(venue_order: dict[str, Any]) -> int:
        return PaperTradeTracker._derive_contract_count(
            venue_order.get("fill_count_fp", venue_order.get("fill_count")),
        )

    @staticmethod
    def _derive_remaining_count(
        venue_order: dict[str, Any],
        order_quantity: int,
        fill_count: int,
    ) -> int:
        remaining = venue_order.get("remaining_count_fp", venue_order.get("remaining_count"))
        if remaining is not None:
            return PaperTradeTracker._derive_contract_count(remaining)
        return max(order_quantity - fill_count, 0)

    @staticmethod
    def _derive_contract_count(value: Any) -> int:
        if value in (None, ""):
            return 0
        return max(int(round(float(value))), 0)

    @staticmethod
    def _first_present(payload: dict[str, Any], *keys: str) -> Any:
        for key in keys:
            if key in payload and payload[key] is not None:
                return payload[key]
        return None

    @staticmethod
    def _normalize_order_status(
        venue_status: str,
        *,
        fill_count: int,
        remaining_count: int,
        order_quantity: int,
        force_cancelled: bool = False,
    ) -> str:
        if venue_status in {"rejected", "error", "failed"}:
            return "rejected"
        if fill_count >= order_quantity and order_quantity > 0:
            return "filled"
        if force_cancelled or venue_status in {"cancelled", "canceled"}:
            return "cancelled"
        if fill_count > 0:
            return "partially_filled" if remaining_count > 0 else "filled"
        if venue_status in {"accepted", "pending", "resting", "open", "queued"}:
            return "resting"
        if venue_status in {"filled", "executed", "matched"}:
            return "filled"
        return venue_status or "accepted"

    @staticmethod
    def _order_activity_ts(order: OrderAttempt) -> datetime:
        return order.last_update_at or order.accepted_at or order.submitted_at
