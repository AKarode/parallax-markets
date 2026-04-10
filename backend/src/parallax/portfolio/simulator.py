"""Portfolio simulator — replay signal_ledger to build equity curve."""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from datetime import date, datetime
from typing import Any

import duckdb

logger = logging.getLogger(__name__)

VALIDATION_START = date(2026, 4, 1)
VALIDATION_END = date(2026, 4, 21)

# Trading cost assumptions
FEE_RATE = 0.02
SLIPPAGE_RATE = 0.0075
EDGE_THRESHOLD = 0.05
MAX_POSITION_PCT = 0.25
CASH_RESERVE_PCT = 0.10
QUARTER_KELLY = 0.25
DEFAULT_HIT_RATE = 0.5


class PortfolioSimulator:
    """Replay signal_ledger chronologically, size with Quarter-Kelly, track equity."""

    def __init__(
        self,
        conn: duckdb.DuckDBPyConnection,
        starting_capital: float = 1000.0,
    ) -> None:
        self._conn = conn
        self._starting_capital = starting_capital

    def run(self) -> dict[str, Any]:
        """Execute full simulation and return portfolio summary."""
        hit_rates = self._load_hit_rates()
        signals = self._load_signals()

        cash = self._starting_capital
        positions: dict[str, dict[str, Any]] = {}  # ticker -> position
        closed_trades: list[dict[str, Any]] = []
        equity_curve: list[dict[str, Any]] = []
        total_fees = 0.0
        peak_value = self._starting_capital

        # Group signals by run_id, preserving chronological order
        runs = self._group_by_run(signals)

        for _run_id, run_signals in runs:
            # Aggregate signals per contract using weighted ensemble
            aggregated = self._aggregate_signals(run_signals, hit_rates)

            run_date = run_signals[0]["created_at"]

            for ticker, agg in aggregated.items():
                combined_signal = agg["signal"]
                combined_edge = agg["edge"]
                entry_side = agg["entry_side"]
                entry_price = agg["entry_price"]

                if combined_signal == "HOLD" or entry_price is None or entry_side is None:
                    continue

                # Check for resolved positions first
                resolution_price = agg.get("resolution_price")
                if ticker in positions and resolution_price is not None:
                    pos = positions.pop(ticker)
                    payout = self._compute_payout(
                        pos["side"], pos["quantity"], resolution_price,
                    )
                    fees = pos["quantity"] * entry_price * FEE_RATE
                    total_fees += fees
                    pnl = payout - fees
                    cash += payout - fees + (pos["quantity"] * pos["entry_price"])
                    closed_trades.append({
                        "ticker": ticker,
                        "side": pos["side"],
                        "quantity": pos["quantity"],
                        "entry_price": pos["entry_price"],
                        "exit_price": resolution_price,
                        "pnl": pnl,
                        "return_pct": pnl / (pos["quantity"] * pos["entry_price"]) if pos["quantity"] * pos["entry_price"] > 0 else 0.0,
                        "fees": fees,
                    })

                # Don't open duplicate positions
                if ticker in positions:
                    continue

                # Quarter-Kelly sizing
                if entry_price <= 0 or entry_price >= 1:
                    continue

                odds = (1.0 - entry_price) / entry_price if entry_side == "yes" else entry_price / (1.0 - entry_price)
                if odds <= 0:
                    continue

                kelly_fraction = combined_edge / odds
                if kelly_fraction <= 0:
                    continue

                quarter_kelly = kelly_fraction * QUARTER_KELLY

                # Apply position limits
                available_capital = cash - (self._starting_capital * CASH_RESERVE_PCT)
                if available_capital <= 0:
                    continue

                max_notional = min(
                    available_capital,
                    self._portfolio_value(cash, positions) * MAX_POSITION_PCT,
                )

                # Account for fees and slippage in sizing
                effective_price = entry_price * (1 + FEE_RATE + SLIPPAGE_RATE)
                notional = min(
                    quarter_kelly * self._portfolio_value(cash, positions),
                    max_notional,
                )
                if notional <= 0:
                    continue

                quantity = max(1, math.floor(notional / effective_price))

                # Recheck that we can afford it
                cost = quantity * effective_price
                if cost > available_capital:
                    quantity = max(1, math.floor(available_capital / effective_price))
                    cost = quantity * effective_price

                if cost > available_capital:
                    continue

                entry_fees = quantity * entry_price * FEE_RATE
                total_fees += entry_fees
                cash -= cost

                positions[ticker] = {
                    "ticker": ticker,
                    "side": entry_side,
                    "quantity": quantity,
                    "entry_price": entry_price,
                    "opened_at": run_date,
                }

            # Record equity curve point
            portfolio_val = self._portfolio_value(cash, positions)
            equity_curve.append({
                "date": run_date.isoformat() if isinstance(run_date, datetime) else str(run_date),
                "value": portfolio_val,
            })
            peak_value = max(peak_value, portfolio_val)

        # Settle any remaining positions with resolution data
        settle_cash, settle_fees = self._settle_remaining(positions, closed_trades)
        cash += settle_cash
        total_fees += settle_fees

        # Update mark-to-market from latest market_prices
        self._update_mark_to_market(positions)

        # Compute final metrics
        portfolio_val = self._portfolio_value(cash, positions)
        deployed = sum(
            p["quantity"] * p["entry_price"] for p in positions.values()
        )

        # Max drawdown from equity curve
        max_drawdown, max_drawdown_pct = self._compute_max_drawdown(equity_curve)

        # Sharpe ratio (annualized)
        sharpe = self._compute_sharpe(equity_curve)

        # Win rate
        win_rate = None
        if closed_trades:
            wins = sum(1 for t in closed_trades if t["pnl"] > 0)
            win_rate = wins / len(closed_trades)

        # Max concentration
        max_concentration_pct = 0.0
        if positions and portfolio_val > 0:
            max_concentration_pct = max(
                (p["quantity"] * p["entry_price"]) / portfolio_val
                for p in positions.values()
            )

        # Days remaining in validation window
        today = date.today()
        days_remaining = max(0, (VALIDATION_END - today).days)

        # Format positions for output
        position_list = []
        for p in positions.values():
            current_price = p.get("current_price", p["entry_price"])
            notional = p["quantity"] * p["entry_price"]
            unrealized = self._compute_unrealized_pnl(p, current_price)
            weight_pct = notional / portfolio_val if portfolio_val > 0 else 0.0
            position_list.append({
                "ticker": p["ticker"],
                "side": p["side"],
                "quantity": p["quantity"],
                "entry_price": p["entry_price"],
                "current_price": current_price,
                "notional": notional,
                "unrealized_pnl": unrealized,
                "weight_pct": weight_pct,
            })

        return {
            "portfolio_value": portfolio_val,
            "portfolio_return_pct": (portfolio_val - self._starting_capital) / self._starting_capital,
            "cash": cash,
            "cash_pct": cash / portfolio_val if portfolio_val > 0 else 1.0,
            "deployed": deployed,
            "positions": position_list,
            "closed_trades": closed_trades,
            "equity_curve": equity_curve,
            "max_drawdown": max_drawdown,
            "max_drawdown_pct": max_drawdown_pct,
            "sharpe": sharpe,
            "total_fees": total_fees,
            "days_remaining": days_remaining,
            "win_rate": win_rate,
            "max_concentration_pct": max_concentration_pct,
        }

    def _load_signals(self) -> list[dict[str, Any]]:
        """Load all signals from signal_ledger ordered chronologically."""
        rows = self._conn.execute("""
            SELECT
                signal_id, run_id, created_at, model_id,
                contract_ticker, proxy_class, model_probability,
                effective_edge, signal, entry_side, entry_price,
                resolution_price, resolved_at, model_was_correct,
                market_yes_price, market_no_price
            FROM signal_ledger
            ORDER BY created_at ASC, signal_id ASC
        """).fetchall()

        columns = [
            "signal_id", "run_id", "created_at", "model_id",
            "contract_ticker", "proxy_class", "model_probability",
            "effective_edge", "signal", "entry_side", "entry_price",
            "resolution_price", "resolved_at", "model_was_correct",
            "market_yes_price", "market_no_price",
        ]
        return [dict(zip(columns, row)) for row in rows]

    def _load_hit_rates(self) -> dict[tuple[str, str], float]:
        """Load hit rate per (model_id, proxy_class) from signal_quality_evaluation."""
        try:
            rows = self._conn.execute("""
                SELECT
                    model_id,
                    proxy_class,
                    COUNT(*) AS total,
                    SUM(CASE WHEN model_was_correct THEN 1 ELSE 0 END) AS wins
                FROM signal_quality_evaluation
                GROUP BY model_id, proxy_class
            """).fetchall()
        except duckdb.CatalogException:
            return {}

        hit_rates: dict[tuple[str, str], float] = {}
        for model_id, proxy_class, total, wins in rows:
            if total > 0:
                hit_rates[(model_id, proxy_class)] = wins / total
        return hit_rates

    def _group_by_run(
        self, signals: list[dict[str, Any]],
    ) -> list[tuple[str | None, list[dict[str, Any]]]]:
        """Group signals by run_id preserving chronological order."""
        seen_runs: dict[str | None, list[dict[str, Any]]] = {}
        run_order: list[str | None] = []
        for sig in signals:
            rid = sig["run_id"]
            if rid not in seen_runs:
                seen_runs[rid] = []
                run_order.append(rid)
            seen_runs[rid].append(sig)
        return [(rid, seen_runs[rid]) for rid in run_order]

    def _aggregate_signals(
        self,
        signals: list[dict[str, Any]],
        hit_rates: dict[tuple[str, str], float],
    ) -> dict[str, dict[str, Any]]:
        """Weighted ensemble aggregation per contract within a run."""
        by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for sig in signals:
            by_ticker[sig["contract_ticker"]].append(sig)

        aggregated: dict[str, dict[str, Any]] = {}
        for ticker, sigs in by_ticker.items():
            total_weight = 0.0
            weighted_edge = 0.0
            best_entry_price = None
            best_entry_side = None
            resolution_price = None

            for sig in sigs:
                weight = hit_rates.get(
                    (sig["model_id"], sig["proxy_class"]),
                    DEFAULT_HIT_RATE,
                )
                edge = sig["effective_edge"] or 0.0
                total_weight += weight
                weighted_edge += weight * edge

                # Use the entry info from any BUY signal
                if sig["signal"] in ("BUY_YES", "BUY_NO") and sig["entry_price"] is not None:
                    best_entry_price = sig["entry_price"]
                    best_entry_side = sig["entry_side"]

                if sig["resolution_price"] is not None:
                    resolution_price = sig["resolution_price"]

            combined_edge = weighted_edge / total_weight if total_weight > 0 else 0.0

            if combined_edge >= EDGE_THRESHOLD and best_entry_side is not None:
                combined_signal = f"BUY_{best_entry_side.upper()}"
            else:
                combined_signal = "HOLD"

            aggregated[ticker] = {
                "signal": combined_signal,
                "edge": combined_edge,
                "entry_side": best_entry_side,
                "entry_price": best_entry_price,
                "resolution_price": resolution_price,
            }

        return aggregated

    def _portfolio_value(
        self,
        cash: float,
        positions: dict[str, dict[str, Any]],
    ) -> float:
        """Mark-to-market portfolio value."""
        position_value = sum(
            p["quantity"] * p.get("current_price", p["entry_price"])
            for p in positions.values()
        )
        return cash + position_value

    def _compute_payout(
        self,
        side: str,
        quantity: int,
        resolution_price: float,
    ) -> float:
        """Binary contract settlement payout."""
        if side == "yes":
            return quantity * resolution_price
        else:
            return quantity * (1.0 - resolution_price)

    def _compute_unrealized_pnl(
        self,
        position: dict[str, Any],
        current_price: float,
    ) -> float:
        """Unrealized P&L based on current mark-to-market."""
        side = position["side"]
        quantity = position["quantity"]
        entry_price = position["entry_price"]
        if side == "yes":
            return quantity * (current_price - entry_price)
        else:
            return quantity * ((1.0 - current_price) - (1.0 - entry_price))

    def _settle_remaining(
        self,
        positions: dict[str, dict[str, Any]],
        closed_trades: list[dict[str, Any]],
    ) -> tuple[float, float]:
        """Settle positions that have resolution data in signal_ledger.

        Returns (cash_delta, fees_delta) to add to the caller's running totals.
        """
        cash_delta = 0.0
        fees_delta = 0.0
        resolved_tickers = []
        for ticker, pos in positions.items():
            row = self._conn.execute(
                """
                SELECT resolution_price
                FROM signal_ledger
                WHERE contract_ticker = ?
                  AND resolution_price IS NOT NULL
                ORDER BY resolved_at DESC
                LIMIT 1
                """,
                [ticker],
            ).fetchone()
            if row and row[0] is not None:
                resolution_price = row[0]
                payout = self._compute_payout(
                    pos["side"], pos["quantity"], resolution_price,
                )
                fees = pos["quantity"] * pos["entry_price"] * FEE_RATE
                pnl = payout - fees
                # Return entry capital via payout (settlement replaces position)
                cash_delta += payout - fees
                fees_delta += fees
                entry_notional = pos["quantity"] * pos["entry_price"]
                closed_trades.append({
                    "ticker": ticker,
                    "side": pos["side"],
                    "quantity": pos["quantity"],
                    "entry_price": pos["entry_price"],
                    "exit_price": resolution_price,
                    "pnl": pnl,
                    "return_pct": pnl / entry_notional if entry_notional > 0 else 0.0,
                    "fees": fees,
                })
                resolved_tickers.append(ticker)

        for ticker in resolved_tickers:
            del positions[ticker]

        return cash_delta, fees_delta

    def _update_mark_to_market(
        self, positions: dict[str, dict[str, Any]],
    ) -> None:
        """Update position current_price from latest market_prices."""
        for ticker, pos in positions.items():
            row = self._conn.execute(
                """
                SELECT yes_price, no_price
                FROM market_prices
                WHERE ticker = ?
                ORDER BY fetched_at DESC
                LIMIT 1
                """,
                [ticker],
            ).fetchone()
            if row:
                if pos["side"] == "yes" and row[0] is not None:
                    pos["current_price"] = row[0]
                elif pos["side"] == "no" and row[1] is not None:
                    pos["current_price"] = row[1]

    def _compute_max_drawdown(
        self, equity_curve: list[dict[str, Any]],
    ) -> tuple[float, float]:
        """Max drawdown in dollars and percentage."""
        if not equity_curve:
            return 0.0, 0.0

        peak = equity_curve[0]["value"]
        max_dd = 0.0
        max_dd_pct = 0.0

        for point in equity_curve:
            val = point["value"]
            peak = max(peak, val)
            dd = peak - val
            dd_pct = dd / peak if peak > 0 else 0.0
            if dd > max_dd:
                max_dd = dd
                max_dd_pct = dd_pct

        return max_dd, max_dd_pct

    def _compute_sharpe(
        self, equity_curve: list[dict[str, Any]],
    ) -> float | None:
        """Annualized Sharpe ratio from equity curve returns."""
        if len(equity_curve) < 2:
            return None

        returns = []
        for i in range(1, len(equity_curve)):
            prev = equity_curve[i - 1]["value"]
            curr = equity_curve[i]["value"]
            if prev > 0:
                returns.append((curr - prev) / prev)

        if not returns:
            return None

        mean_ret = sum(returns) / len(returns)
        if len(returns) < 2:
            return None

        variance = sum((r - mean_ret) ** 2 for r in returns) / (len(returns) - 1)
        std_ret = math.sqrt(variance)

        if std_ret == 0:
            return None

        # Annualize assuming 2 runs per day (8am + 8pm)
        runs_per_year = 365 * 2
        return (mean_ret / std_ret) * math.sqrt(runs_per_year)
