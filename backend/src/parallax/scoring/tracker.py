"""Paper trade tracker — places trades on Kalshi sandbox and tracks P&L.

Records all trades for scoring model predictions against market resolution.
Persists to DuckDB via DbWriter when available.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from pydantic import BaseModel

from parallax.db.writer import DbWriter
from parallax.divergence.detector import Divergence
from parallax.markets.kalshi import KalshiClient

logger = logging.getLogger(__name__)


class TradeRecord(BaseModel):
    """A paper trade record with P&L tracking."""

    trade_id: str
    ticker: str
    side: str  # "yes" or "no"
    quantity: int
    entry_price: float  # cents
    current_price: float | None = None
    exit_price: float | None = None
    pnl: float = 0.0  # realized P&L in USD
    status: str = "open"  # open, won, lost, expired
    opened_at: datetime
    closed_at: datetime | None = None
    divergence_edge: float  # edge at time of entry
    model_id: str  # which model generated the signal


class PaperTradeTracker:
    """Track paper trades and compute P&L against Kalshi sandbox."""

    def __init__(
        self,
        kalshi_client: KalshiClient,
        db_writer: DbWriter | None = None,
    ) -> None:
        self._kalshi = kalshi_client
        self._writer = db_writer
        self._trades: list[TradeRecord] = []

    async def open_trade(
        self, divergence: Divergence, quantity: int = 10,
    ) -> TradeRecord:
        """Place a paper trade on Kalshi sandbox based on divergence signal.

        Args:
            divergence: The detected divergence with signal direction.
            quantity: Number of contracts to trade.

        Returns:
            TradeRecord for the placed trade.
        """
        side = "yes" if divergence.signal == "BUY_YES" else "no"
        price = int(divergence.market_probability * 100)

        # Place order on Kalshi sandbox
        try:
            result = await self._kalshi.place_order(
                ticker=divergence.market_price.ticker,
                side=side,
                quantity=quantity,
                price=price,
            )
            order_id = result.get("order", {}).get("order_id")
        except Exception:
            logger.exception("Failed to place order on Kalshi sandbox")
            order_id = None

        trade = TradeRecord(
            trade_id=str(uuid.uuid4()),
            ticker=divergence.market_price.ticker,
            side=side,
            quantity=quantity,
            entry_price=float(price),
            current_price=float(price),
            divergence_edge=divergence.edge,
            model_id=divergence.model_id,
            opened_at=datetime.now(timezone.utc),
        )

        self._trades.append(trade)
        await self._persist_trade(trade)
        return trade

    async def update_positions(self) -> list[TradeRecord]:
        """Fetch current positions from Kalshi and update current prices."""
        try:
            positions = await self._kalshi.get_positions()
        except Exception:
            logger.exception("Failed to fetch positions")
            return self._trades

        pos_by_ticker = {p.ticker: p for p in positions}
        for trade in self._trades:
            if trade.status != "open":
                continue
            pos = pos_by_ticker.get(trade.ticker)
            if pos:
                trade.current_price = pos.market_price * 100
                # Unrealized P&L: (current - entry) * quantity / 100
                if trade.side == "yes":
                    trade.pnl = (trade.current_price - trade.entry_price) * trade.quantity / 100
                else:
                    trade.pnl = (trade.entry_price - trade.current_price) * trade.quantity / 100

        return self._trades

    async def check_resolutions(self) -> list[TradeRecord]:
        """Check if any open trades have resolved (market settled)."""
        resolved = []
        try:
            positions = await self._kalshi.get_positions()
        except Exception:
            logger.exception("Failed to check resolutions")
            return resolved

        pos_by_ticker = {p.ticker: p for p in positions}
        for trade in self._trades:
            if trade.status != "open":
                continue

            # If position no longer exists, market may have settled
            pos = pos_by_ticker.get(trade.ticker)
            if pos is None and trade.current_price is not None:
                # Assume resolved
                trade.status = "won" if trade.pnl > 0 else "lost"
                trade.exit_price = trade.current_price
                trade.closed_at = datetime.now(timezone.utc)
                resolved.append(trade)
                await self._persist_trade(trade)

        return resolved

    def summary(self) -> dict:
        """Return P&L summary statistics."""
        total = len(self._trades)
        wins = sum(1 for t in self._trades if t.status == "won")
        losses = sum(1 for t in self._trades if t.status == "lost")
        open_count = sum(1 for t in self._trades if t.status == "open")
        total_pnl = sum(t.pnl for t in self._trades)
        avg_edge = (
            sum(abs(t.divergence_edge) for t in self._trades) / total
            if total > 0 else 0.0
        )
        win_rate = wins / (wins + losses) if (wins + losses) > 0 else 0.0

        return {
            "total_trades": total,
            "open": open_count,
            "wins": wins,
            "losses": losses,
            "total_pnl_usd": total_pnl,
            "win_rate": win_rate,
            "avg_edge": avg_edge,
        }

    def to_table(self) -> str:
        """Format trades as ASCII table for CLI output."""
        if not self._trades:
            return "No trades recorded."

        header = f"{'Ticker':<25} {'Side':<5} {'Qty':>4} {'Entry':>6} {'Current':>8} {'P&L':>8} {'Status':<8} {'Edge':>6}"
        sep = "-" * len(header)
        lines = [header, sep]

        for t in self._trades:
            current = f"{t.current_price:.0f}c" if t.current_price else "N/A"
            lines.append(
                f"{t.ticker:<25} {t.side:<5} {t.quantity:>4} "
                f"{t.entry_price:>5.0f}c {current:>8} "
                f"${t.pnl:>7.2f} {t.status:<8} {t.divergence_edge:>5.1%}"
            )

        s = self.summary()
        lines.append(sep)
        lines.append(
            f"Total P&L: ${s['total_pnl_usd']:.2f} | "
            f"Win Rate: {s['win_rate']:.0%} | "
            f"Open: {s['open']} | Closed: {s['wins'] + s['losses']}"
        )
        return "\n".join(lines)

    async def _persist_trade(self, trade: TradeRecord) -> None:
        """Write trade to DuckDB if writer is available."""
        if self._writer is None:
            return
        sql = """
            INSERT OR REPLACE INTO paper_trades
            (trade_id, ticker, side, quantity, entry_price, current_price,
             exit_price, pnl, status, opened_at, closed_at, divergence_edge, model_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            trade.trade_id, trade.ticker, trade.side, trade.quantity,
            trade.entry_price, trade.current_price, trade.exit_price,
            trade.pnl, trade.status, trade.opened_at.isoformat(),
            trade.closed_at.isoformat() if trade.closed_at else None,
            trade.divergence_edge, trade.model_id,
        )
        await self._writer.enqueue(sql, list(params))
