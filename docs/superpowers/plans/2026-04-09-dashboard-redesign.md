# Dashboard Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the simulation-focused frontend with a React trading intelligence dashboard that surfaces P&L, model performance, market edges, and ops health from the existing FastAPI + DuckDB backend.

**Architecture:** Backend-first — add 7 new API endpoints to `main.py` backed by new query functions in `dashboard/data.py` and a new `portfolio/simulator.py` module. Then build a React SPA (Vite + TypeScript) with dark terminal aesthetic consuming those endpoints via 5-minute polling. No UI framework — custom CSS with sharp edges and monospace fonts.

**Tech Stack:** Python/FastAPI/DuckDB (backend), React 18 + Vite + TypeScript + Recharts (frontend)

---

## File Structure

### Backend (new/modified)

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/src/parallax/portfolio/simulator.py` | Create | Portfolio simulator — replays signal_ledger, weighted ensemble, equity curve, position tracking |
| `backend/src/parallax/dashboard/data.py` | Modify | Add 6 new query functions for dashboard endpoints |
| `backend/src/parallax/main.py` | Modify | Add 7 new GET endpoints |
| `backend/tests/test_simulator.py` | Create | Tests for portfolio simulator |
| `backend/tests/test_dashboard_endpoints.py` | Create | Tests for new API endpoints |

### Frontend (all new)

| File | Responsibility |
|------|---------------|
| `frontend/package.json` | Dependencies: react, react-dom, recharts, typescript, vite |
| `frontend/tsconfig.json` | TypeScript config |
| `frontend/vite.config.ts` | Vite config with API proxy |
| `frontend/index.html` | Entry HTML |
| `frontend/src/main.tsx` | React mount |
| `frontend/src/App.tsx` | Single-page layout, data fetching orchestrator |
| `frontend/src/types.ts` | TypeScript interfaces for all API responses |
| `frontend/src/styles.css` | Global styles — dark terminal aesthetic, design system |
| `frontend/src/hooks/usePolling.ts` | Generic polling hook |
| `frontend/src/lib/format.ts` | Formatting utils: USD, percentages, dates, edges |
| `frontend/src/lib/colors.ts` | Color constants |
| `frontend/src/components/KpiBar.tsx` | Sticky header: P&L, hit rate, signals, last run, budget |
| `frontend/src/components/ModelCards.tsx` | 3-across model probability cards with sparklines |
| `frontend/src/components/Sparkline.tsx` | Reusable SVG sparkline |
| `frontend/src/components/MarketsTable.tsx` | Expandable contract table sorted by edge |
| `frontend/src/components/ContractDetail.tsx` | Expanded row: resolution, order book, charts, reasoning |
| `frontend/src/components/PriceChart.tsx` | Model vs market probability chart (Recharts) |
| `frontend/src/components/ModelHealth.tsx` | Brier score, calibration, edge quality metrics |
| `frontend/src/components/PortfolioPanel.tsx` | Equity curve, positions, closed trades, risk |
| `frontend/src/components/OpsFooter.tsx` | Pipeline status bar |

---

## Task 1: Portfolio Simulator Core

**Files:**
- Create: `backend/src/parallax/portfolio/simulator.py`
- Create: `backend/tests/test_simulator.py`

This is the most complex new backend module. It replays signal_ledger chronologically, applies weighted ensemble aggregation, sizes positions with Quarter-Kelly, tracks equity curve.

- [ ] **Step 1: Write failing test for empty portfolio initialization**

Create `backend/tests/test_simulator.py`:

```python
"""Tests for portfolio simulator."""

import duckdb
import pytest

from parallax.db.schema import create_tables
from parallax.portfolio.simulator import PortfolioSimulator


@pytest.fixture
def conn():
    c = duckdb.connect(":memory:")
    create_tables(c)
    return c


def test_empty_portfolio(conn):
    sim = PortfolioSimulator(conn, starting_capital=1000.0)
    result = sim.run()
    assert result["portfolio_value"] == 1000.0
    assert result["cash"] == 1000.0
    assert result["deployed"] == 0.0
    assert result["positions"] == []
    assert result["closed_trades"] == []
    assert result["equity_curve"] == []
    assert result["max_drawdown"] == 0.0
    assert result["total_fees"] == 0.0
    assert result["days_remaining"] >= 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_simulator.py::test_empty_portfolio -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'parallax.portfolio.simulator'`

- [ ] **Step 3: Write minimal PortfolioSimulator to pass empty test**

Create `backend/src/parallax/portfolio/simulator.py`:

```python
"""Server-side portfolio simulator.

Replays signal_ledger chronologically with weighted ensemble aggregation
and Quarter-Kelly position sizing. Hold-to-settlement strategy.
$1,000 fake capital, Apr 1 - Apr 21 validation window.
"""

from __future__ import annotations

import logging
import math
from datetime import date, datetime, timezone
from typing import Any

import duckdb

logger = logging.getLogger(__name__)

STARTING_CAPITAL = 1000.0
VALIDATION_START = date(2026, 4, 1)
VALIDATION_END = date(2026, 4, 21)
DEFAULT_FEE_RATE = 0.02
DEFAULT_SLIPPAGE = 0.0075
MAX_POSITION_FRACTION = 0.25  # max 25% of portfolio in one position
KELLY_FRACTION = 0.25  # quarter-Kelly


class PortfolioSimulator:
    """Replay signal_ledger to produce simulated portfolio state."""

    def __init__(
        self,
        conn: duckdb.DuckDBPyConnection,
        starting_capital: float = STARTING_CAPITAL,
    ) -> None:
        self._conn = conn
        self._starting_capital = starting_capital

    def run(self) -> dict[str, Any]:
        signals = self._load_signals()
        if not signals:
            return self._empty_result()

        hit_rates = self._load_hit_rates()
        cash = self._starting_capital
        positions: list[dict] = []
        closed_trades: list[dict] = []
        equity_points: list[dict] = []
        total_fees = 0.0
        peak_value = self._starting_capital

        # Group signals by run_id for ensemble aggregation
        runs = self._group_by_run(signals)

        for run_id, run_signals in runs:
            # Aggregate signals per contract using weighted ensemble
            aggregated = self._aggregate_signals(run_signals, hit_rates)

            for agg in aggregated:
                ticker = agg["contract_ticker"]
                signal = agg["signal"]
                edge = agg["effective_edge"]

                # Check for settlements on existing positions
                cash, closed = self._check_settlements(
                    positions, run_signals, cash,
                )
                closed_trades.extend(closed)
                total_fees += sum(c.get("fees", 0.0) for c in closed)

                # Skip if already have position in this contract
                if any(p["ticker"] == ticker for p in positions):
                    continue

                if signal not in ("BUY_YES", "BUY_NO"):
                    continue

                # Quarter-Kelly sizing
                side = "yes" if signal == "BUY_YES" else "no"
                entry_price = agg["entry_price"]
                if entry_price is None or entry_price <= 0 or entry_price >= 1:
                    continue

                size = self._kelly_size(
                    edge, entry_price, cash, self._starting_capital,
                )
                if size <= 0:
                    continue

                notional = size * entry_price
                fee = notional * DEFAULT_FEE_RATE
                if notional + fee > cash:
                    continue

                cash -= notional + fee
                total_fees += fee
                positions.append({
                    "ticker": ticker,
                    "side": side,
                    "quantity": size,
                    "entry_price": entry_price,
                    "current_price": entry_price,
                    "notional": notional,
                    "opened_at": agg["created_at"],
                    "model_ids": agg["model_ids"],
                })

            # Record equity point
            mtm = sum(p["quantity"] * p["current_price"] for p in positions)
            portfolio_value = cash + mtm
            peak_value = max(peak_value, portfolio_value)
            equity_points.append({
                "date": run_signals[0]["created_at"].isoformat() if run_signals else None,
                "value": round(portfolio_value, 2),
            })

        # Final settlement check using resolution prices
        cash, final_closed = self._settle_all(positions, cash)
        closed_trades.extend(final_closed)
        total_fees += sum(c.get("fees", 0.0) for c in final_closed)

        # Update current prices for open positions
        self._update_mark_to_market(positions)

        mtm = sum(p["quantity"] * p["current_price"] for p in positions)
        portfolio_value = cash + mtm
        deployed = sum(p["quantity"] * p["entry_price"] for p in positions)
        peak_value = max(peak_value, portfolio_value)
        max_drawdown = self._starting_capital - min(
            (ep["value"] for ep in equity_points), default=self._starting_capital,
        )
        max_drawdown = max(0.0, max_drawdown)

        # Sharpe ratio from equity curve
        sharpe = self._compute_sharpe(equity_points)

        days_remaining = max(0, (VALIDATION_END - date.today()).days)

        return {
            "portfolio_value": round(portfolio_value, 2),
            "portfolio_return_pct": round(
                (portfolio_value - self._starting_capital) / self._starting_capital * 100, 2,
            ),
            "cash": round(cash, 2),
            "cash_pct": round(cash / portfolio_value * 100, 1) if portfolio_value > 0 else 100.0,
            "deployed": round(deployed, 2),
            "positions": [
                {
                    "ticker": p["ticker"],
                    "side": p["side"],
                    "quantity": p["quantity"],
                    "entry_price": round(p["entry_price"], 4),
                    "current_price": round(p["current_price"], 4),
                    "notional": round(p["quantity"] * p["entry_price"], 2),
                    "unrealized_pnl": round(
                        p["quantity"] * (p["current_price"] - p["entry_price"])
                        if p["side"] == "yes"
                        else p["quantity"] * (p["entry_price"] - p["current_price"]),
                        2,
                    ),
                    "weight_pct": round(
                        p["quantity"] * p["entry_price"] / portfolio_value * 100, 1,
                    ) if portfolio_value > 0 else 0.0,
                }
                for p in positions
            ],
            "closed_trades": [
                {
                    "ticker": c["ticker"],
                    "side": c["side"],
                    "quantity": c["quantity"],
                    "entry_price": round(c["entry_price"], 4),
                    "exit_price": round(c["exit_price"], 4),
                    "pnl": round(c["pnl"], 2),
                    "return_pct": round(c["return_pct"], 2),
                    "fees": round(c.get("fees", 0.0), 2),
                }
                for c in closed_trades
            ],
            "equity_curve": equity_points,
            "max_drawdown": round(max_drawdown, 2),
            "max_drawdown_pct": round(
                max_drawdown / self._starting_capital * 100, 2,
            ),
            "sharpe": round(sharpe, 2) if sharpe is not None else None,
            "total_fees": round(total_fees, 2),
            "days_remaining": days_remaining,
            "win_rate": self._win_rate(closed_trades),
            "max_concentration_pct": self._max_concentration(positions, portfolio_value),
        }

    def _empty_result(self) -> dict[str, Any]:
        days_remaining = max(0, (VALIDATION_END - date.today()).days)
        return {
            "portfolio_value": self._starting_capital,
            "portfolio_return_pct": 0.0,
            "cash": self._starting_capital,
            "cash_pct": 100.0,
            "deployed": 0.0,
            "positions": [],
            "closed_trades": [],
            "equity_curve": [],
            "max_drawdown": 0.0,
            "max_drawdown_pct": 0.0,
            "sharpe": None,
            "total_fees": 0.0,
            "days_remaining": days_remaining,
            "win_rate": None,
            "max_concentration_pct": 0.0,
        }

    def _load_signals(self) -> list[dict]:
        rows = self._conn.execute("""
            SELECT
                signal_id, run_id, created_at, model_id, contract_ticker,
                proxy_class, model_probability, effective_edge, signal,
                entry_side, entry_price, entry_price_kind,
                resolution_price, resolved_at, model_was_correct
            FROM signal_ledger
            WHERE signal IN ('BUY_YES', 'BUY_NO', 'HOLD')
              AND effective_edge IS NOT NULL
            ORDER BY created_at ASC
        """).fetchall()
        cols = [
            "signal_id", "run_id", "created_at", "model_id", "contract_ticker",
            "proxy_class", "model_probability", "effective_edge", "signal",
            "entry_side", "entry_price", "entry_price_kind",
            "resolution_price", "resolved_at", "model_was_correct",
        ]
        return [dict(zip(cols, row)) for row in rows]

    def _load_hit_rates(self) -> dict[str, dict[str, float]]:
        """Load hit rates per model per proxy class for ensemble weights."""
        rows = self._conn.execute("""
            SELECT model_id, proxy_class, 
                   COUNT(*) AS total,
                   SUM(CASE WHEN model_was_correct THEN 1 ELSE 0 END) AS correct
            FROM signal_quality_evaluation
            WHERE model_was_correct IS NOT NULL
            GROUP BY model_id, proxy_class
        """).fetchall()
        rates: dict[str, dict[str, float]] = {}
        for model_id, proxy_class, total, correct in rows:
            if model_id not in rates:
                rates[model_id] = {}
            rates[model_id][proxy_class] = correct / total if total > 0 else 0.5
        return rates

    def _group_by_run(
        self, signals: list[dict],
    ) -> list[tuple[str, list[dict]]]:
        from collections import OrderedDict
        runs: OrderedDict[str, list[dict]] = OrderedDict()
        for sig in signals:
            rid = sig["run_id"] or "unknown"
            if rid not in runs:
                runs[rid] = []
            runs[rid].append(sig)
        return list(runs.items())

    def _aggregate_signals(
        self,
        run_signals: list[dict],
        hit_rates: dict[str, dict[str, float]],
    ) -> list[dict]:
        """Weighted ensemble: combine signals for same contract from multiple models."""
        from collections import defaultdict
        by_contract: dict[str, list[dict]] = defaultdict(list)
        for sig in run_signals:
            by_contract[sig["contract_ticker"]].append(sig)

        aggregated = []
        for ticker, sigs in by_contract.items():
            if len(sigs) == 1:
                s = sigs[0]
                aggregated.append({
                    "contract_ticker": ticker,
                    "signal": s["signal"],
                    "effective_edge": float(s["effective_edge"]) if s["effective_edge"] else 0.0,
                    "entry_price": float(s["entry_price"]) if s["entry_price"] else None,
                    "created_at": s["created_at"],
                    "model_ids": [s["model_id"]],
                    "agreement_count": 1,
                    "total_models": 1,
                })
                continue

            # Weighted ensemble
            total_weight = 0.0
            weighted_edge = 0.0
            buy_weight = 0.0
            sell_weight = 0.0
            model_ids = []
            best_entry = None
            created_at = sigs[0]["created_at"]

            for s in sigs:
                proxy = s["proxy_class"] or "DIRECT"
                weight = hit_rates.get(s["model_id"], {}).get(proxy, 0.5)
                edge = float(s["effective_edge"]) if s["effective_edge"] else 0.0
                total_weight += weight
                weighted_edge += weight * edge
                model_ids.append(s["model_id"])

                if s["signal"] == "BUY_YES":
                    buy_weight += weight
                elif s["signal"] == "BUY_NO":
                    sell_weight += weight

                if s["entry_price"] is not None:
                    if best_entry is None or weight > (hit_rates.get(best_entry[1], {}).get(proxy, 0.5)):
                        best_entry = (float(s["entry_price"]), s["model_id"])

            avg_edge = weighted_edge / total_weight if total_weight > 0 else 0.0

            # Determine consensus signal
            if buy_weight > sell_weight and avg_edge >= 0.05:
                signal = "BUY_YES"
            elif sell_weight > buy_weight and avg_edge >= 0.05:
                signal = "BUY_NO"
            else:
                signal = "HOLD"

            aggregated.append({
                "contract_ticker": ticker,
                "signal": signal,
                "effective_edge": avg_edge,
                "entry_price": best_entry[0] if best_entry else None,
                "created_at": created_at,
                "model_ids": model_ids,
                "agreement_count": sum(
                    1 for s in sigs if s["signal"] == signal
                ),
                "total_models": len(sigs),
            })

        return aggregated

    def _kelly_size(
        self,
        edge: float,
        entry_price: float,
        cash: float,
        total_capital: float,
    ) -> int:
        """Quarter-Kelly position sizing."""
        if edge <= 0 or entry_price <= 0 or entry_price >= 1:
            return 0

        # Kelly fraction = edge / odds
        # For binary: odds = (1 - entry_price) / entry_price for YES side
        odds = (1.0 - entry_price) / entry_price
        if odds <= 0:
            return 0

        kelly = edge / odds
        quarter_kelly = kelly * KELLY_FRACTION
        bet_amount = total_capital * quarter_kelly

        # Cap at max position fraction
        max_bet = total_capital * MAX_POSITION_FRACTION
        bet_amount = min(bet_amount, max_bet, cash * 0.9)  # keep 10% cash reserve
        if bet_amount < entry_price:
            return 0

        return int(bet_amount / entry_price)

    def _check_settlements(
        self,
        positions: list[dict],
        run_signals: list[dict],
        cash: float,
    ) -> tuple[float, list[dict]]:
        """Check if any positions have resolution prices in current signals."""
        closed = []
        resolved_tickers = set()
        for sig in run_signals:
            if sig["resolution_price"] is not None:
                resolved_tickers.add(
                    (sig["contract_ticker"], float(sig["resolution_price"])),
                )

        remaining = []
        for pos in positions:
            res = next(
                (rp for t, rp in resolved_tickers if t == pos["ticker"]),
                None,
            )
            if res is not None:
                if pos["side"] == "yes":
                    pnl = pos["quantity"] * (res - pos["entry_price"])
                else:
                    pnl = pos["quantity"] * (pos["entry_price"] - res)
                cash += pos["quantity"] * res + pnl  # return capital + pnl
                # Actually: settlement pays $1 per contract if YES, $0 if NO
                # Simplified: pnl = quantity * (settlement - entry) for YES
                if pos["side"] == "yes":
                    payout = pos["quantity"] * res
                else:
                    payout = pos["quantity"] * (1.0 - res)
                cash_return = payout
                pnl = payout - (pos["quantity"] * pos["entry_price"])
                cash += cash_return
                entry_notional = pos["quantity"] * pos["entry_price"]
                closed.append({
                    "ticker": pos["ticker"],
                    "side": pos["side"],
                    "quantity": pos["quantity"],
                    "entry_price": pos["entry_price"],
                    "exit_price": res,
                    "pnl": pnl,
                    "return_pct": (pnl / entry_notional * 100) if entry_notional > 0 else 0.0,
                })
            else:
                remaining.append(pos)

        positions.clear()
        positions.extend(remaining)
        return cash, closed

    def _settle_all(
        self, positions: list[dict], cash: float,
    ) -> tuple[float, list[dict]]:
        """Settle all positions that have resolution prices in DB."""
        closed = []
        remaining = []
        for pos in positions:
            row = self._conn.execute(
                """
                SELECT resolution_price FROM signal_ledger
                WHERE contract_ticker = ? AND resolution_price IS NOT NULL
                ORDER BY resolved_at DESC LIMIT 1
                """,
                [pos["ticker"]],
            ).fetchone()
            if row and row[0] is not None:
                res = float(row[0])
                if pos["side"] == "yes":
                    payout = pos["quantity"] * res
                else:
                    payout = pos["quantity"] * (1.0 - res)
                pnl = payout - (pos["quantity"] * pos["entry_price"])
                cash += payout
                entry_notional = pos["quantity"] * pos["entry_price"]
                closed.append({
                    "ticker": pos["ticker"],
                    "side": pos["side"],
                    "quantity": pos["quantity"],
                    "entry_price": pos["entry_price"],
                    "exit_price": res,
                    "pnl": pnl,
                    "return_pct": (pnl / entry_notional * 100) if entry_notional > 0 else 0.0,
                })
            else:
                remaining.append(pos)
        positions.clear()
        positions.extend(remaining)
        return cash, closed

    def _update_mark_to_market(self, positions: list[dict]) -> None:
        """Update current prices for open positions from latest market data."""
        for pos in positions:
            row = self._conn.execute(
                """
                SELECT yes_price, no_price FROM market_prices
                WHERE ticker = ?
                ORDER BY fetched_at DESC LIMIT 1
                """,
                [pos["ticker"]],
            ).fetchone()
            if row:
                if pos["side"] == "yes":
                    pos["current_price"] = float(row[0]) if row[0] else pos["entry_price"]
                else:
                    pos["current_price"] = float(row[1]) if row[1] else pos["entry_price"]

    def _compute_sharpe(self, equity_points: list[dict]) -> float | None:
        if len(equity_points) < 2:
            return None
        values = [ep["value"] for ep in equity_points]
        returns = [
            (values[i] - values[i - 1]) / values[i - 1]
            for i in range(1, len(values))
            if values[i - 1] > 0
        ]
        if len(returns) < 2:
            return None
        mean_ret = sum(returns) / len(returns)
        var = sum((r - mean_ret) ** 2 for r in returns) / (len(returns) - 1)
        std = math.sqrt(var) if var > 0 else 0.001
        # Annualize: assume ~2 observations/day, 252 trading days
        annualization = math.sqrt(2 * 252)
        return (mean_ret / std) * annualization

    def _win_rate(self, closed_trades: list[dict]) -> float | None:
        if not closed_trades:
            return None
        wins = sum(1 for c in closed_trades if c["pnl"] > 0)
        return round(wins / len(closed_trades) * 100, 1)

    def _max_concentration(
        self, positions: list[dict], portfolio_value: float,
    ) -> float:
        if not positions or portfolio_value <= 0:
            return 0.0
        max_notional = max(p["quantity"] * p["entry_price"] for p in positions)
        return round(max_notional / portfolio_value * 100, 1)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_simulator.py::test_empty_portfolio -v`
Expected: PASS

- [ ] **Step 5: Write test for signal replay with positions**

Add to `backend/tests/test_simulator.py`:

```python
from datetime import datetime, timezone
import uuid


def _insert_signal(conn, **kwargs):
    """Helper to insert a signal_ledger row."""
    defaults = {
        "signal_id": str(uuid.uuid4()),
        "run_id": "run-001",
        "created_at": datetime(2026, 4, 8, 8, 0, tzinfo=timezone.utc),
        "data_environment": "live",
        "execution_environment": "none",
        "model_id": "oil_price",
        "model_claim": "oil up",
        "model_probability": 0.7,
        "model_timeframe": "7d",
        "contract_ticker": "KXWTIMAX-26DEC31",
        "proxy_class": "NEAR_PROXY",
        "confidence_discount": 0.6,
        "effective_edge": 0.12,
        "signal": "BUY_YES",
        "tradeability_status": "tradeable",
        "entry_side": "yes",
        "entry_price": 0.35,
        "entry_price_kind": "executable_ask",
    }
    defaults.update(kwargs)
    cols = ", ".join(defaults.keys())
    placeholders = ", ".join(["?"] * len(defaults))
    conn.execute(
        f"INSERT INTO signal_ledger ({cols}) VALUES ({placeholders})",
        list(defaults.values()),
    )


def test_single_buy_signal(conn):
    """A single BUY_YES signal should open a position."""
    _insert_signal(conn, signal="BUY_YES", effective_edge=0.12, entry_price=0.35)
    sim = PortfolioSimulator(conn, starting_capital=1000.0)
    result = sim.run()

    assert result["portfolio_value"] > 0
    assert len(result["positions"]) == 1
    pos = result["positions"][0]
    assert pos["ticker"] == "KXWTIMAX-26DEC31"
    assert pos["side"] == "yes"
    assert pos["entry_price"] == 0.35
    assert result["cash"] < 1000.0  # spent some cash
    assert result["deployed"] > 0


def test_hold_signal_no_position(conn):
    """A HOLD signal should not open any position."""
    _insert_signal(conn, signal="HOLD", effective_edge=0.02)
    sim = PortfolioSimulator(conn, starting_capital=1000.0)
    result = sim.run()
    assert result["positions"] == []
    assert result["cash"] == 1000.0


def test_kelly_sizing_respects_capital(conn):
    """Position size should be proportional to edge and respect max limits."""
    _insert_signal(conn, signal="BUY_YES", effective_edge=0.20, entry_price=0.30)
    sim = PortfolioSimulator(conn, starting_capital=1000.0)
    result = sim.run()
    assert len(result["positions"]) == 1
    pos = result["positions"][0]
    # Quarter-Kelly on 20% edge should not exceed 25% of capital
    assert pos["notional"] <= 250.0
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_simulator.py -v`
Expected: PASS (all 4 tests)

- [ ] **Step 7: Commit**

```bash
git add backend/src/parallax/portfolio/simulator.py backend/tests/test_simulator.py
git commit -m "feat: add portfolio simulator with weighted ensemble and Quarter-Kelly sizing"
```

---

## Task 2: Dashboard Query Functions

**Files:**
- Modify: `backend/src/parallax/dashboard/data.py`

Add 6 new query functions needed by the dashboard API endpoints. These build on existing tables and the new simulator.

- [ ] **Step 1: Write tests for new query functions**

Create `backend/tests/test_dashboard_queries.py`:

```python
"""Tests for new dashboard data query functions."""

import uuid
from datetime import datetime, timezone

import duckdb
import pytest

from parallax.db.schema import create_tables
from parallax.dashboard.data import (
    get_scorecard_metrics,
    get_signals_for_contract,
    get_active_contracts,
    get_edge_decay_for_contract,
    get_price_history,
    get_prediction_history,
)


@pytest.fixture
def conn():
    c = duckdb.connect(":memory:")
    create_tables(c)
    return c


def test_get_scorecard_metrics_empty(conn):
    result = get_scorecard_metrics(conn)
    assert isinstance(result, dict)
    assert "signal_hit_rate" in result
    assert "signal_brier_score" in result


def test_get_signals_for_contract_empty(conn):
    result = get_signals_for_contract(conn, "NONEXISTENT")
    assert result == []


def test_get_active_contracts_empty(conn):
    result = get_active_contracts(conn)
    assert isinstance(result, list)


def test_get_price_history_empty(conn):
    result = get_price_history(conn, "NONEXISTENT")
    assert result == []


def test_get_prediction_history_empty(conn):
    result = get_prediction_history(conn)
    assert isinstance(result, dict)


def test_get_scorecard_metrics_with_data(conn):
    """Insert scorecard data and verify retrieval."""
    conn.execute(
        """
        INSERT INTO daily_scorecard (score_date, metric_name, metric_value, dimensions)
        VALUES
            ('2026-04-08', 'signal_hit_rate', 0.6, NULL),
            ('2026-04-08', 'signal_brier_score', 0.21, NULL),
            ('2026-04-08', 'ops_llm_cost_usd', 5.23, NULL),
            ('2026-04-08', 'ops_run_count', 2.0, NULL)
        """,
    )
    result = get_scorecard_metrics(conn)
    assert result["signal_hit_rate"] == 0.6
    assert result["signal_brier_score"] == 0.21


def test_get_price_history_with_data(conn):
    conn.execute(
        """
        INSERT INTO market_prices (ticker, source, yes_price, no_price, volume, fetched_at, data_environment)
        VALUES
            ('KXTEST', 'kalshi', 0.45, 0.55, 100.0, '2026-04-08 08:00:00', 'live'),
            ('KXTEST', 'kalshi', 0.47, 0.53, 120.0, '2026-04-08 20:00:00', 'live')
        """,
    )
    result = get_price_history(conn, "KXTEST")
    assert len(result) == 2
    assert result[0]["yes_price"] == 0.45  # oldest first
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_dashboard_queries.py -v`
Expected: FAIL — `ImportError: cannot import name 'get_scorecard_metrics'`

- [ ] **Step 3: Implement query functions**

Add to `backend/src/parallax/dashboard/data.py` (append after existing functions):

```python
def get_scorecard_metrics(
    conn: duckdb.DuckDBPyConnection,
    date_str: str | None = None,
) -> dict:
    """Return latest scorecard metrics as a flat dict.

    If date_str is None, uses the most recent score_date in the table.
    """
    if date_str is None:
        row = conn.execute(
            "SELECT MAX(score_date) FROM daily_scorecard",
        ).fetchone()
        if not row or row[0] is None:
            return {
                "signal_hit_rate": None,
                "signal_brier_score": None,
                "signal_calibration_max_gap": None,
                "ops_llm_cost_usd": None,
                "ops_run_count": None,
                "ops_run_success_rate": None,
                "ops_error_alert_count": None,
                "score_date": None,
            }
        date_str = str(row[0])

    rows = conn.execute(
        """
        SELECT metric_name, metric_value, dimensions
        FROM daily_scorecard
        WHERE score_date = ?
        """,
        [date_str],
    ).fetchall()

    metrics = {r[0]: r[1] for r in rows}
    metrics["score_date"] = date_str
    return metrics


def get_signals_for_contract(
    conn: duckdb.DuckDBPyConnection,
    contract_ticker: str,
    limit: int = 20,
) -> list[dict]:
    """Return signal history for a specific contract, most recent first."""
    rows = conn.execute(
        """
        SELECT signal_id, created_at, model_id, effective_edge, signal,
               model_probability, entry_price, entry_side, resolution_price,
               model_was_correct, run_id
        FROM signal_ledger
        WHERE contract_ticker = ?
        ORDER BY created_at DESC
        LIMIT ?
        """,
        [contract_ticker, limit],
    ).fetchall()

    return [
        {
            "signal_id": r[0],
            "created_at": r[1],
            "model_id": r[2],
            "effective_edge": float(r[3]) if r[3] is not None else 0.0,
            "signal": r[4],
            "model_probability": float(r[5]) if r[5] is not None else None,
            "entry_price": float(r[6]) if r[6] is not None else None,
            "entry_side": r[7],
            "resolution_price": float(r[8]) if r[8] is not None else None,
            "model_was_correct": r[9],
            "run_id": r[10],
        }
        for r in rows
    ]


def get_active_contracts(conn: duckdb.DuckDBPyConnection) -> list[dict]:
    """Return all active contracts with proxy mappings."""
    rows = conn.execute(
        """
        SELECT
            cr.ticker, cr.source, cr.event_ticker, cr.title,
            cr.resolution_criteria, cr.resolution_date, cr.contract_family,
            cr.expected_fee_rate, cr.expected_slippage_rate
        FROM contract_registry cr
        WHERE cr.is_active = true
        ORDER BY cr.ticker
        """,
    ).fetchall()

    contracts = []
    for r in rows:
        ticker = r[0]
        # Load proxy mappings
        proxy_rows = conn.execute(
            """
            SELECT model_type, proxy_class, confidence_discount, invert_probability
            FROM contract_proxy_map
            WHERE ticker = ?
            """,
            [ticker],
        ).fetchall()
        proxy_map = {pr[0]: pr[1] for pr in proxy_rows}
        best_proxy = min(
            (pr[1] for pr in proxy_rows),
            key=lambda p: {"DIRECT": 0, "NEAR_PROXY": 1, "LOOSE_PROXY": 2, "NONE": 3}.get(p, 4),
            default="NONE",
        )
        contracts.append({
            "ticker": ticker,
            "source": r[1],
            "event_ticker": r[2],
            "title": r[3],
            "resolution_criteria": r[4],
            "resolution_date": r[5],
            "contract_family": r[6],
            "expected_fee_rate": float(r[7]) if r[7] is not None else None,
            "expected_slippage_rate": float(r[8]) if r[8] is not None else None,
            "proxy_map": proxy_map,
            "best_proxy": best_proxy,
        })

    return contracts


def get_edge_decay_for_contract(
    conn: duckdb.DuckDBPyConnection,
    contract_ticker: str,
) -> dict:
    """Return edge decay analysis for a specific contract."""
    from parallax.scoring.calibration import edge_decay_over_time

    all_pairs = edge_decay_over_time(conn)
    contract_pairs = [p for p in all_pairs if p["contract_ticker"] == contract_ticker]

    if not contract_pairs:
        return {
            "n_pairs": 0,
            "avg_decay_rate": None,
            "time_to_zero_edge": None,
            "round_trip_cost": 0.055,
            "exit_profitable": False,
            "verdict": "Insufficient data",
        }

    avg_change = sum(p["edge_change"] for p in contract_pairs) / len(contract_pairs)
    hours = [p["hours_between"] for p in contract_pairs if p["hours_between"]]
    avg_hours = sum(hours) / len(hours) if hours else None
    decay_rates = [p["decay_rate_per_hour"] for p in contract_pairs if p["decay_rate_per_hour"]]
    avg_decay_rate = sum(decay_rates) / len(decay_rates) if decay_rates else None

    # Estimate time to zero edge from avg starting edge
    avg_start_edge = sum(abs(p["edge_a"]) for p in contract_pairs) / len(contract_pairs)
    time_to_zero = None
    if avg_decay_rate and avg_decay_rate < 0:
        time_to_zero = abs(avg_start_edge / avg_decay_rate)

    round_trip_cost = 0.055
    exit_profitable = abs(avg_change) > round_trip_cost if avg_change else False

    if exit_profitable:
        verdict = "Exit trading may be profitable"
    else:
        verdict = "Hold to settlement"

    return {
        "n_pairs": len(contract_pairs),
        "avg_decay_rate": round(avg_decay_rate, 6) if avg_decay_rate else None,
        "avg_edge_change": round(avg_change, 4),
        "time_to_zero_edge": round(time_to_zero, 1) if time_to_zero else None,
        "round_trip_cost": round_trip_cost,
        "exit_profitable": exit_profitable,
        "verdict": verdict,
    }


def get_price_history(
    conn: duckdb.DuckDBPyConnection,
    ticker: str,
    limit: int = 100,
) -> list[dict]:
    """Return market price history for a ticker, oldest first (for charting)."""
    rows = conn.execute(
        """
        SELECT fetched_at, yes_price, no_price, volume, best_yes_bid, best_yes_ask
        FROM market_prices
        WHERE ticker = ?
        ORDER BY fetched_at ASC
        LIMIT ?
        """,
        [ticker, limit],
    ).fetchall()

    return [
        {
            "fetched_at": r[0],
            "yes_price": float(r[1]) if r[1] is not None else None,
            "no_price": float(r[2]) if r[2] is not None else None,
            "volume": float(r[3]) if r[3] is not None else None,
            "best_yes_bid": float(r[4]) if r[4] is not None else None,
            "best_yes_ask": float(r[5]) if r[5] is not None else None,
        }
        for r in rows
    ]


def get_prediction_history(
    conn: duckdb.DuckDBPyConnection,
    limit: int = 50,
) -> dict[str, list[dict]]:
    """Return prediction history grouped by model_id, oldest first."""
    rows = conn.execute(
        """
        SELECT model_id, probability, direction, confidence, created_at, run_id
        FROM prediction_log
        ORDER BY created_at ASC
        LIMIT ?
        """,
        [limit],
    ).fetchall()

    by_model: dict[str, list[dict]] = {}
    for r in rows:
        model_id = r[0]
        if model_id not in by_model:
            by_model[model_id] = []
        by_model[model_id].append({
            "probability": float(r[1]),
            "direction": r[2],
            "confidence": float(r[3]),
            "created_at": r[4],
            "run_id": r[5],
        })

    return by_model
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_dashboard_queries.py -v`
Expected: PASS (all 8 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/src/parallax/dashboard/data.py backend/tests/test_dashboard_queries.py
git commit -m "feat: add dashboard query functions for scorecard, contracts, price history, signals"
```

---

## Task 3: New API Endpoints

**Files:**
- Modify: `backend/src/parallax/main.py`
- Create: `backend/tests/test_dashboard_endpoints.py`

Add 7 new GET endpoints to the FastAPI app.

- [ ] **Step 1: Write endpoint tests**

Create `backend/tests/test_dashboard_endpoints.py`:

```python
"""Tests for new dashboard API endpoints."""

import pytest
from fastapi.testclient import TestClient

import duckdb
from parallax.db.schema import create_tables
from parallax.main import app


@pytest.fixture(autouse=True)
def setup_app():
    """Set up app state with in-memory DuckDB."""
    conn = duckdb.connect(":memory:")
    create_tables(conn)
    app.state.db = conn

    class FakeRuntime:
        data_environment = "mock"
        requested_execution_environment = "none"
        execution_environment = "none"
        live_execution_authorized = False
        kill_switch_enabled = False

    app.state.runtime = FakeRuntime()
    app.state.last_predictions = []
    app.state.last_markets = []
    app.state.last_divergences = []
    app.state.last_brief_time = None
    app.state.kalshi = None
    app.state.polymarket = None
    yield
    conn.close()


client = TestClient(app, raise_server_exceptions=False)


def test_get_scorecard():
    resp = client.get("/api/scorecard")
    assert resp.status_code == 200
    data = resp.json()
    assert "signal_hit_rate" in data


def test_get_contracts():
    resp = client.get("/api/contracts")
    assert resp.status_code == 200
    data = resp.json()
    assert "contracts" in data
    assert isinstance(data["contracts"], list)


def test_get_signals_for_contract():
    resp = client.get("/api/signals?contract=KXTEST")
    assert resp.status_code == 200
    data = resp.json()
    assert "signals" in data


def test_get_edge_decay():
    resp = client.get("/api/edge-decay?contract=KXTEST")
    assert resp.status_code == 200
    data = resp.json()
    assert "verdict" in data


def test_get_price_history():
    resp = client.get("/api/price-history?ticker=KXTEST")
    assert resp.status_code == 200
    data = resp.json()
    assert "prices" in data


def test_get_prediction_history():
    resp = client.get("/api/prediction-history")
    assert resp.status_code == 200
    data = resp.json()
    assert "models" in data


def test_get_portfolio():
    resp = client.get("/api/portfolio")
    assert resp.status_code == 200
    data = resp.json()
    assert "portfolio_value" in data
    assert data["portfolio_value"] == 1000.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_dashboard_endpoints.py -v`
Expected: FAIL — 404 for all new endpoints

- [ ] **Step 3: Add endpoints to main.py**

Add the following endpoints to `backend/src/parallax/main.py` (append after the existing `run_brief_endpoint`):

```python
@app.get("/api/scorecard")
async def get_scorecard(date: str | None = None):
    """Return latest daily scorecard metrics."""
    from parallax.dashboard.data import get_scorecard_metrics
    try:
        return get_scorecard_metrics(app.state.db, date)
    except Exception:
        logger.exception("Scorecard query failed")
        return {"error": "scorecard query failed"}


@app.get("/api/contracts")
async def get_contracts():
    """Return active contracts with proxy classifications."""
    from parallax.dashboard.data import get_active_contracts
    try:
        return {"contracts": get_active_contracts(app.state.db)}
    except Exception:
        logger.exception("Contracts query failed")
        return {"contracts": []}


@app.get("/api/signals")
async def get_signals(contract: str, limit: int = 20):
    """Return signal history for a specific contract."""
    from parallax.dashboard.data import get_signals_for_contract
    try:
        return {"signals": get_signals_for_contract(app.state.db, contract, limit)}
    except Exception:
        logger.exception("Signals query failed")
        return {"signals": []}


@app.get("/api/edge-decay")
async def get_edge_decay(contract: str):
    """Return edge decay analysis for a specific contract."""
    from parallax.dashboard.data import get_edge_decay_for_contract
    try:
        return get_edge_decay_for_contract(app.state.db, contract)
    except Exception:
        logger.exception("Edge decay query failed")
        return {"verdict": "query failed", "n_pairs": 0}


@app.get("/api/price-history")
async def get_price_history_endpoint(ticker: str, limit: int = 100):
    """Return market price history for charting."""
    from parallax.dashboard.data import get_price_history
    try:
        return {"prices": get_price_history(app.state.db, ticker, limit)}
    except Exception:
        logger.exception("Price history query failed")
        return {"prices": []}


@app.get("/api/prediction-history")
async def get_prediction_history():
    """Return prediction probability history per model."""
    from parallax.dashboard.data import get_prediction_history as _get_pred_hist
    try:
        return {"models": _get_pred_hist(app.state.db)}
    except Exception:
        logger.exception("Prediction history query failed")
        return {"models": {}}


@app.get("/api/portfolio")
async def get_portfolio():
    """Return simulated portfolio state."""
    from parallax.portfolio.simulator import PortfolioSimulator
    try:
        sim = PortfolioSimulator(app.state.db)
        return sim.run()
    except Exception:
        logger.exception("Portfolio simulation failed")
        return {"portfolio_value": 1000.0, "error": "simulation failed"}
```

Also add this import at the top of `main.py`:

```python
from __future__ import annotations
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_dashboard_endpoints.py -v`
Expected: PASS (all 7 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/src/parallax/main.py backend/tests/test_dashboard_endpoints.py
git commit -m "feat: add 7 dashboard API endpoints (scorecard, contracts, signals, portfolio)"
```

---

## Task 4: Frontend Scaffold — Vite + React + TypeScript

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/types.ts`
- Create: `frontend/src/styles.css`
- Create: `frontend/src/lib/colors.ts`
- Create: `frontend/src/lib/format.ts`
- Create: `frontend/src/hooks/usePolling.ts`

- [ ] **Step 1: Create package.json**

Create `frontend/package.json`:

```json
{
  "name": "parallax-dashboard",
  "private": true,
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "recharts": "^2.15.0"
  },
  "devDependencies": {
    "@types/react": "^18.3.18",
    "@types/react-dom": "^18.3.5",
    "@vitejs/plugin-react": "^4.3.4",
    "typescript": "~5.6.2",
    "vite": "^6.0.0"
  }
}
```

- [ ] **Step 2: Create tsconfig.json**

Create `frontend/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "isolatedModules": true,
    "moduleDetection": "force",
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "noUncheckedIndexedAccess": true
  },
  "include": ["src"]
}
```

- [ ] **Step 3: Create vite.config.ts**

Create `frontend/vite.config.ts`:

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
```

- [ ] **Step 4: Create index.html**

Create `frontend/index.html`:

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Parallax</title>
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet" />
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 5: Create types.ts**

Create `frontend/src/types.ts`:

```typescript
/* API response types for the Parallax dashboard. */

export interface HealthResponse {
  status: string
  last_brief_time: string | null
  predictions_count: number
  markets_count: number
  divergences_count: number
  kalshi_configured: boolean
  data_environment: string
  execution_environment: string
  timestamp: string
}

export interface Prediction {
  model_id: string
  prediction_type: string
  probability: number
  direction: string
  magnitude_range: [number, number]
  unit: string
  confidence: number
  timeframe: string
  reasoning: string
  evidence: string[]
  created_at: string
  kalshi_ticker?: string
  polymarket_id?: string
}

export interface PredictionsResponse {
  predictions: Prediction[]
}

export interface MarketData {
  ticker: string
  source: string
  best_yes_bid: number | null
  best_yes_ask: number | null
  best_no_bid: number | null
  best_no_ask: number | null
  yes_price: number | null
  no_price: number | null
  derived_price_kind: string
  volume: number | null
  fetched_at: string
  data_environment: string
}

export interface MarketsResponse {
  markets: MarketData[]
}

export interface Divergence {
  model_id: string
  prediction: Prediction
  model_probability: number
  market_price: MarketData
  market_probability: number
  buy_yes_edge: number
  buy_no_edge: number
  edge: number
  edge_pct: number
  signal: string
  strength: string
  entry_side: string
  entry_price: number
  entry_price_kind: string
  entry_price_is_executable: boolean
  tradeability_status: string
  created_at: string
}

export interface DivergencesResponse {
  divergences: Divergence[]
}

export interface ScorecardMetrics {
  signal_hit_rate: number | null
  signal_brier_score: number | null
  signal_calibration_max_gap: number | null
  ops_llm_cost_usd: number | null
  ops_run_count: number | null
  ops_run_success_rate: number | null
  ops_error_alert_count: number | null
  score_date: string | null
  [key: string]: unknown
}

export interface ContractInfo {
  ticker: string
  source: string
  event_ticker: string
  title: string
  resolution_criteria: string
  resolution_date: string | null
  contract_family: string | null
  expected_fee_rate: number | null
  expected_slippage_rate: number | null
  proxy_map: Record<string, string>
  best_proxy: string
}

export interface ContractsResponse {
  contracts: ContractInfo[]
}

export interface SignalRecord {
  signal_id: string
  created_at: string
  model_id: string
  effective_edge: number
  signal: string
  model_probability: number | null
  entry_price: number | null
  entry_side: string | null
  resolution_price: number | null
  model_was_correct: boolean | null
  run_id: string
}

export interface SignalsResponse {
  signals: SignalRecord[]
}

export interface EdgeDecayAnalysis {
  n_pairs: number
  avg_decay_rate: number | null
  avg_edge_change: number | null
  time_to_zero_edge: number | null
  round_trip_cost: number
  exit_profitable: boolean
  verdict: string
}

export interface PricePoint {
  fetched_at: string
  yes_price: number | null
  no_price: number | null
  volume: number | null
  best_yes_bid: number | null
  best_yes_ask: number | null
}

export interface PriceHistoryResponse {
  prices: PricePoint[]
}

export interface PredictionPoint {
  probability: number
  direction: string
  confidence: number
  created_at: string
  run_id: string
}

export interface PredictionHistoryResponse {
  models: Record<string, PredictionPoint[]>
}

export interface PortfolioPosition {
  ticker: string
  side: string
  quantity: number
  entry_price: number
  current_price: number
  notional: number
  unrealized_pnl: number
  weight_pct: number
}

export interface ClosedTrade {
  ticker: string
  side: string
  quantity: number
  entry_price: number
  exit_price: number
  pnl: number
  return_pct: number
  fees: number
}

export interface EquityPoint {
  date: string
  value: number
}

export interface PortfolioState {
  portfolio_value: number
  portfolio_return_pct: number
  cash: number
  cash_pct: number
  deployed: number
  positions: PortfolioPosition[]
  closed_trades: ClosedTrade[]
  equity_curve: EquityPoint[]
  max_drawdown: number
  max_drawdown_pct: number
  sharpe: number | null
  total_fees: number
  days_remaining: number
  win_rate: number | null
  max_concentration_pct: number
}
```

- [ ] **Step 6: Create colors.ts and format.ts**

Create `frontend/src/lib/colors.ts`:

```typescript
export const colors = {
  bg: '#09090b',
  surface: '#111113',
  border: '#1c1c1f',
  dim: '#3f3f46',
  muted: '#52525b',
  subtle: '#71717a',
  text: '#e4e4e7',
  white: '#fafafa',
  green: '#22c55e',
  red: '#ef4444',
  amber: '#f59e0b',
  indigo: '#818cf8',
  purple: '#a78bfa',
  cyan: '#22d3ee',
} as const
```

Create `frontend/src/lib/format.ts`:

```typescript
export function pct(value: number | null | undefined, decimals = 1): string {
  if (value == null) return '—'
  return `${(value * 100).toFixed(decimals)}%`
}

export function pctRaw(value: number | null | undefined, decimals = 1): string {
  if (value == null) return '—'
  return `${value.toFixed(decimals)}%`
}

export function usd(value: number | null | undefined, decimals = 2): string {
  if (value == null) return '—'
  return `$${value.toFixed(decimals)}`
}

export function signedUsd(value: number | null | undefined, decimals = 2): string {
  if (value == null) return '—'
  const prefix = value >= 0 ? '+' : ''
  return `${prefix}$${value.toFixed(decimals)}`
}

export function signedPct(value: number | null | undefined, decimals = 1): string {
  if (value == null) return '—'
  const prefix = value >= 0 ? '+' : ''
  return `${prefix}${value.toFixed(decimals)}%`
}

export function edge(value: number | null | undefined): string {
  if (value == null) return '—'
  const prefix = value >= 0 ? '+' : ''
  return `${prefix}${(value * 100).toFixed(1)}%`
}

export function relativeTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  const now = Date.now()
  const then = new Date(iso).getTime()
  const diffMs = now - then
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 1) return 'just now'
  if (diffMin < 60) return `${diffMin}m ago`
  const diffHr = Math.floor(diffMin / 60)
  if (diffHr < 24) return `${diffHr}h ago`
  const diffDay = Math.floor(diffHr / 24)
  return `${diffDay}d ago`
}

export function shortDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  return `${d.getMonth() + 1}/${d.getDate()}`
}

export function fraction(correct: number, total: number): string {
  return `${correct}/${total} (${total > 0 ? Math.round(correct / total * 100) : 0}%)`
}
```

- [ ] **Step 7: Create usePolling hook**

Create `frontend/src/hooks/usePolling.ts`:

```typescript
import { useEffect, useRef, useState, useCallback } from 'react'

const POLL_INTERVAL = 300_000 // 5 minutes

interface UsePollingResult<T> {
  data: T | null
  error: string | null
  loading: boolean
  lastUpdated: Date | null
  refetch: () => void
}

export function usePolling<T>(url: string, interval = POLL_INTERVAL): UsePollingResult<T> {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)
  const intervalRef = useRef<number | null>(null)

  const fetchData = useCallback(async () => {
    try {
      const resp = await fetch(url)
      if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`)
      const json = await resp.json() as T
      setData(json)
      setError(null)
      setLastUpdated(new Date())
    } catch (e) {
      setError(e instanceof Error ? e.message : 'fetch failed')
    } finally {
      setLoading(false)
    }
  }, [url])

  useEffect(() => {
    fetchData()
    intervalRef.current = window.setInterval(fetchData, interval)
    return () => {
      if (intervalRef.current) window.clearInterval(intervalRef.current)
    }
  }, [fetchData, interval])

  return { data, error, loading, lastUpdated, refetch: fetchData }
}
```

- [ ] **Step 8: Create styles.css**

Create `frontend/src/styles.css`:

```css
/* Parallax Dashboard — Dark Terminal Aesthetic */

*,
*::before,
*::after {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

:root {
  --bg: #09090b;
  --surface: #111113;
  --border: #1c1c1f;
  --dim: #3f3f46;
  --muted: #52525b;
  --subtle: #71717a;
  --text: #e4e4e7;
  --white: #fafafa;
  --green: #22c55e;
  --red: #ef4444;
  --amber: #f59e0b;
  --indigo: #818cf8;
  --purple: #a78bfa;
  --cyan: #22d3ee;

  --font-sans: 'Inter', system-ui, -apple-system, sans-serif;
  --font-mono: 'JetBrains Mono', 'Fira Code', monospace;
}

html {
  background: var(--bg);
  color: var(--text);
  font-family: var(--font-mono);
  font-size: 13px;
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
}

body {
  min-height: 100vh;
}

/* Layout */
.dashboard {
  max-width: 1400px;
  margin: 0 auto;
  padding: 0;
}

/* KPI Bar */
.kpi-bar {
  position: sticky;
  top: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  gap: 0;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  padding: 0;
}

.kpi-cell {
  flex: 1;
  padding: 10px 12px;
  border-right: 1px solid var(--border);
  text-align: center;
}

.kpi-cell:last-child {
  border-right: none;
}

.kpi-label {
  font-size: 9px;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--muted);
  margin-bottom: 2px;
  font-family: var(--font-mono);
}

.kpi-value {
  font-size: 16px;
  font-weight: 700;
  font-family: var(--font-sans);
}

/* Section Labels */
.section-label {
  font-size: 9px;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--muted);
  font-family: var(--font-mono);
  padding: 10px 12px 6px;
  background: var(--bg);
  border-bottom: 1px solid var(--border);
}

/* Model Cards */
.model-cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  border-bottom: 1px solid var(--border);
}

.model-card {
  padding: 12px;
  background: var(--surface);
  border-right: 1px solid var(--border);
}

.model-card:last-child {
  border-right: none;
}

.model-name {
  font-size: 9px;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--muted);
  margin-bottom: 4px;
}

.model-probability {
  font-size: 28px;
  font-weight: 700;
  font-family: var(--font-sans);
  line-height: 1;
  margin-bottom: 4px;
}

.model-direction {
  font-size: 11px;
  color: var(--subtle);
  margin-bottom: 8px;
}

.model-hit {
  font-size: 11px;
  color: var(--subtle);
}

/* Markets Table */
.markets-table {
  width: 100%;
  border-collapse: collapse;
}

.markets-table th {
  font-size: 9px;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--muted);
  font-weight: 500;
  text-align: left;
  padding: 8px 10px;
  border-bottom: 1px solid var(--border);
  background: var(--surface);
}

.markets-table td {
  padding: 8px 10px;
  border-bottom: 1px solid var(--border);
  font-size: 12px;
}

.markets-table tr.active-signal td {
  color: var(--text);
}

.markets-table tr.hold-signal td {
  color: var(--dim);
}

.markets-table tr.expanded td {
  background: rgba(129, 140, 248, 0.04);
}

.markets-table tr:hover td {
  background: rgba(129, 140, 248, 0.03);
  cursor: pointer;
}

/* Badges */
.badge {
  display: inline-block;
  padding: 1px 6px;
  font-size: 10px;
  font-weight: 500;
  border: 1px solid;
}

.badge-buy-yes {
  color: var(--green);
  border-color: var(--green);
}

.badge-buy-no {
  color: var(--red);
  border-color: var(--red);
}

.badge-hold {
  color: var(--dim);
  border-color: var(--dim);
}

.badge-direct {
  color: var(--indigo);
  border-color: var(--indigo);
}

.badge-near {
  color: var(--purple);
  border-color: var(--purple);
}

.badge-loose {
  color: var(--dim);
  border-color: var(--dim);
}

/* Contract Detail (expanded row) */
.contract-detail {
  border-left: 2px solid var(--indigo);
  background: rgba(129, 140, 248, 0.02);
  padding: 12px;
}

.detail-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-bottom: 12px;
}

.detail-grid-3 {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 12px;
}

.detail-section {
  padding: 8px;
  border: 1px solid var(--border);
  background: var(--surface);
}

.detail-label {
  font-size: 9px;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--muted);
  margin-bottom: 6px;
}

.detail-value {
  font-size: 12px;
}

/* Two-Column Layout (Model Health + Portfolio) */
.two-col {
  display: grid;
  grid-template-columns: 1fr 1fr;
  border-bottom: 1px solid var(--border);
}

.two-col > div {
  padding: 12px;
  border-right: 1px solid var(--border);
}

.two-col > div:last-child {
  border-right: none;
}

/* Metric Rows */
.metric-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  padding: 4px 0;
  border-bottom: 1px solid var(--border);
}

.metric-row:last-child {
  border-bottom: none;
}

.metric-label {
  font-size: 11px;
  color: var(--subtle);
}

.metric-value {
  font-size: 12px;
  font-weight: 500;
}

.metric-benchmark {
  font-size: 10px;
  color: var(--dim);
  margin-left: 6px;
}

/* Portfolio Summary */
.portfolio-summary {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 0;
  border-bottom: 1px solid var(--border);
}

.portfolio-cell {
  padding: 8px 10px;
  border-right: 1px solid var(--border);
  text-align: center;
}

.portfolio-cell:last-child {
  border-right: none;
}

/* Equity Curve Chart */
.equity-chart {
  height: 160px;
  background: #0a0a0c;
  border: 1px solid var(--border);
  margin: 8px 0;
}

/* Positions Table */
.positions-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 11px;
}

.positions-table th {
  font-size: 9px;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--muted);
  font-weight: 500;
  text-align: left;
  padding: 6px 8px;
  border-bottom: 1px solid var(--border);
}

.positions-table td {
  padding: 6px 8px;
  border-bottom: 1px solid var(--border);
}

/* Ops Footer */
.ops-footer {
  display: flex;
  align-items: center;
  gap: 0;
  padding: 0;
  background: var(--surface);
  border-top: 1px solid var(--border);
  font-size: 11px;
}

.ops-cell {
  padding: 8px 12px;
  border-right: 1px solid var(--border);
  color: var(--subtle);
}

.ops-cell:last-child {
  border-right: none;
}

.status-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  margin-right: 4px;
  vertical-align: middle;
}

.status-dot.green { background: var(--green); }
.status-dot.red { background: var(--red); }
.status-dot.amber { background: var(--amber); }

/* Color utilities */
.c-green { color: var(--green); }
.c-red { color: var(--red); }
.c-amber { color: var(--amber); }
.c-indigo { color: var(--indigo); }
.c-muted { color: var(--muted); }
.c-subtle { color: var(--subtle); }

/* Sparkline */
.sparkline {
  display: inline-block;
  vertical-align: middle;
}

/* Reasoning text */
.reasoning-text {
  font-size: 11px;
  line-height: 1.6;
  color: var(--subtle);
  max-height: 200px;
  overflow-y: auto;
  white-space: pre-wrap;
}

/* Scrollbar */
::-webkit-scrollbar {
  width: 4px;
}

::-webkit-scrollbar-track {
  background: var(--bg);
}

::-webkit-scrollbar-thumb {
  background: var(--dim);
}

/* Expand arrow */
.expand-arrow {
  display: inline-block;
  transition: transform 0.15s;
  color: var(--dim);
  font-size: 10px;
}

.expand-arrow.open {
  transform: rotate(90deg);
}

/* Loading */
.loading-text {
  color: var(--dim);
  font-size: 11px;
  padding: 8px 12px;
}

/* Error indicator */
.stale-indicator {
  display: inline-block;
  width: 6px;
  height: 6px;
  background: var(--amber);
  margin-left: 4px;
  vertical-align: middle;
}
```

- [ ] **Step 9: Create main.tsx**

Create `frontend/src/main.tsx`:

```typescript
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './styles.css'
import { App } from './App'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
```

- [ ] **Step 10: Install dependencies**

Run: `cd frontend && npm install`
Expected: node_modules created, no errors

- [ ] **Step 11: Commit**

```bash
git add frontend/package.json frontend/tsconfig.json frontend/vite.config.ts frontend/index.html frontend/src/main.tsx frontend/src/types.ts frontend/src/styles.css frontend/src/lib/colors.ts frontend/src/lib/format.ts frontend/src/hooks/usePolling.ts
git commit -m "feat: scaffold frontend with Vite + React + TypeScript, design system, polling hook"
```

---

## Task 5: KPI Bar + Model Cards + Sparkline Components

**Files:**
- Create: `frontend/src/components/KpiBar.tsx`
- Create: `frontend/src/components/ModelCards.tsx`
- Create: `frontend/src/components/Sparkline.tsx`

- [ ] **Step 1: Create Sparkline component**

Create `frontend/src/components/Sparkline.tsx`:

```typescript
interface SparklineProps {
  data: number[]
  width?: number
  height?: number
  color?: string
}

export function Sparkline({ data, width = 60, height = 20, color = '#818cf8' }: SparklineProps) {
  if (data.length < 2) return null

  const min = Math.min(...data)
  const max = Math.max(...data)
  const range = max - min || 1

  const points = data
    .map((v, i) => {
      const x = (i / (data.length - 1)) * width
      const y = height - ((v - min) / range) * height
      return `${x},${y}`
    })
    .join(' ')

  return (
    <svg className="sparkline" width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
      <polyline fill="none" stroke={color} strokeWidth="1.5" points={points} />
    </svg>
  )
}
```

- [ ] **Step 2: Create KpiBar component**

Create `frontend/src/components/KpiBar.tsx`:

```typescript
import type { HealthResponse, PortfolioState, ScorecardMetrics, DivergencesResponse } from '../types'
import { usd, signedPct, relativeTime, fraction } from '../lib/format'
import { colors } from '../lib/colors'

interface KpiBarProps {
  health: HealthResponse | null
  portfolio: PortfolioState | null
  scorecard: ScorecardMetrics | null
  divergences: DivergencesResponse | null
}

export function KpiBar({ health, portfolio, scorecard, divergences }: KpiBarProps) {
  const portfolioColor = portfolio && portfolio.portfolio_return_pct >= 0
    ? colors.green : colors.red

  const activeSignals = divergences?.divergences.filter(
    d => d.signal !== 'HOLD' && d.signal !== 'REFUSED',
  ).length ?? 0

  const lastRunColor = (() => {
    if (!health?.last_brief_time) return colors.red
    const hours = (Date.now() - new Date(health.last_brief_time).getTime()) / 3600000
    return hours > 24 ? colors.red : colors.subtle
  })()

  const budgetUsed = scorecard?.ops_llm_cost_usd ?? 0
  const budgetColor = budgetUsed > 19 ? colors.red : budgetUsed > 16 ? colors.amber : colors.subtle

  return (
    <div className="kpi-bar">
      <div className="kpi-cell">
        <div className="kpi-label">Portfolio</div>
        <div className="kpi-value" style={{ color: portfolioColor }}>
          {portfolio ? `${usd(portfolio.portfolio_value)} ${signedPct(portfolio.portfolio_return_pct)}` : '—'}
        </div>
      </div>
      <div className="kpi-cell">
        <div className="kpi-label">Hit Rate</div>
        <div className="kpi-value">
          {scorecard?.signal_hit_rate != null
            ? `${(scorecard.signal_hit_rate * 100).toFixed(0)}%`
            : '—'}
        </div>
      </div>
      <div className="kpi-cell">
        <div className="kpi-label">Active Signals</div>
        <div className="kpi-value" style={{ color: colors.amber }}>
          {activeSignals} signals
        </div>
      </div>
      <div className="kpi-cell">
        <div className="kpi-label">Last Run</div>
        <div className="kpi-value" style={{ color: lastRunColor }}>
          {relativeTime(health?.last_brief_time)}
        </div>
      </div>
      <div className="kpi-cell">
        <div className="kpi-label">Budget</div>
        <div className="kpi-value" style={{ color: budgetColor }}>
          {usd(budgetUsed)}/$20
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Create ModelCards component**

Create `frontend/src/components/ModelCards.tsx`:

```typescript
import type { PredictionsResponse, PredictionHistoryResponse, ScorecardMetrics } from '../types'
import { Sparkline } from './Sparkline'
import { pct } from '../lib/format'
import { colors } from '../lib/colors'

interface ModelCardsProps {
  predictions: PredictionsResponse | null
  predictionHistory: PredictionHistoryResponse | null
  scorecard: ScorecardMetrics | null
}

const MODEL_ORDER = ['oil_price', 'ceasefire', 'hormuz_reopening']

const MODEL_LABELS: Record<string, string> = {
  oil_price: 'OIL PRICE',
  ceasefire: 'CEASEFIRE',
  hormuz_reopening: 'HORMUZ REOPENING',
}

export function ModelCards({ predictions, predictionHistory, scorecard }: ModelCardsProps) {
  return (
    <>
      <div className="section-label">Models</div>
      <div className="model-cards">
        {MODEL_ORDER.map(modelId => {
          const pred = predictions?.predictions.find(p => p.model_id === modelId)
          const history = predictionHistory?.models?.[modelId] ?? []
          const sparkData = history.slice(-10).map(h => h.probability)

          const directionColor = pred?.direction === 'increase'
            ? colors.green
            : pred?.direction === 'decrease'
              ? colors.red
              : colors.subtle

          return (
            <div key={modelId} className="model-card">
              <div className="model-name">{MODEL_LABELS[modelId] ?? modelId}</div>
              <div className="model-probability" style={{ color: directionColor }}>
                {pred ? pct(pred.probability, 0) : '—'}
              </div>
              <div className="model-direction">
                {pred ? `${pred.direction} ${pred.timeframe}` : '—'}
              </div>
              <Sparkline data={sparkData} color={directionColor} />
              <div className="model-hit">
                conf: {pred ? pct(pred.confidence, 0) : '—'}
              </div>
            </div>
          )
        })}
      </div>
    </>
  )
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/KpiBar.tsx frontend/src/components/ModelCards.tsx frontend/src/components/Sparkline.tsx
git commit -m "feat: add KpiBar, ModelCards, and Sparkline components"
```

---

## Task 6: Markets Table + Contract Detail

**Files:**
- Create: `frontend/src/components/MarketsTable.tsx`
- Create: `frontend/src/components/ContractDetail.tsx`
- Create: `frontend/src/components/PriceChart.tsx`

- [ ] **Step 1: Create PriceChart component**

Create `frontend/src/components/PriceChart.tsx`:

```typescript
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import type { PricePoint, PredictionPoint } from '../types'
import { colors } from '../lib/colors'

interface PriceChartProps {
  prices: PricePoint[]
  predictions?: PredictionPoint[]
}

export function PriceChart({ prices, predictions }: PriceChartProps) {
  // Merge price and prediction data by date
  const chartData = prices.map(p => ({
    date: new Date(p.fetched_at).toLocaleDateString(),
    market: p.yes_price,
  }))

  if (predictions) {
    for (const pred of predictions) {
      const date = new Date(pred.created_at).toLocaleDateString()
      const existing = chartData.find(d => d.date === date)
      if (existing) {
        (existing as Record<string, unknown>).model = pred.probability
      } else {
        chartData.push({ date, market: null as unknown as number | null, model: pred.probability } as typeof chartData[number])
      }
    }
    chartData.sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
  }

  if (chartData.length === 0) {
    return <div className="loading-text">No price data</div>
  }

  return (
    <div className="equity-chart">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartData} margin={{ top: 8, right: 8, bottom: 8, left: 8 }}>
          <XAxis
            dataKey="date"
            tick={{ fontSize: 9, fill: colors.dim }}
            axisLine={{ stroke: colors.border }}
            tickLine={false}
          />
          <YAxis
            domain={[0, 1]}
            tick={{ fontSize: 9, fill: colors.dim }}
            axisLine={{ stroke: colors.border }}
            tickLine={false}
            tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`}
          />
          <Tooltip
            contentStyle={{
              background: colors.surface,
              border: `1px solid ${colors.border}`,
              fontSize: 11,
              color: colors.text,
            }}
          />
          <Line
            type="monotone"
            dataKey="market"
            stroke={colors.indigo}
            dot={false}
            strokeWidth={1.5}
            name="Market"
          />
          {'model' in (chartData[0] ?? {}) && (
            <Line
              type="monotone"
              dataKey="model"
              stroke={colors.green}
              dot={false}
              strokeWidth={1.5}
              strokeDasharray="4 2"
              name="Model"
            />
          )}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
```

- [ ] **Step 2: Create ContractDetail component**

Create `frontend/src/components/ContractDetail.tsx`:

```typescript
import { usePolling } from '../hooks/usePolling'
import { PriceChart } from './PriceChart'
import type {
  ContractInfo,
  Divergence,
  MarketData,
  SignalsResponse,
  EdgeDecayAnalysis,
  PriceHistoryResponse,
  PredictionHistoryResponse,
} from '../types'
import { edge, pct, usd, relativeTime } from '../lib/format'
import { colors } from '../lib/colors'

interface ContractDetailProps {
  contract: ContractInfo
  divergence: Divergence | null
  market: MarketData | null
}

export function ContractDetail({ contract, divergence, market }: ContractDetailProps) {
  const { data: signals } = usePolling<SignalsResponse>(
    `/api/signals?contract=${contract.ticker}`,
  )
  const { data: edgeDecay } = usePolling<EdgeDecayAnalysis>(
    `/api/edge-decay?contract=${contract.ticker}`,
  )
  const { data: priceHistory } = usePolling<PriceHistoryResponse>(
    `/api/price-history?ticker=${contract.ticker}`,
  )
  const { data: predHistory } = usePolling<PredictionHistoryResponse>(
    '/api/prediction-history',
  )

  // Find matching model predictions for this contract
  const modelId = divergence?.model_id
  const modelPredictions = modelId ? predHistory?.models?.[modelId] ?? [] : []

  const fee = contract.expected_fee_rate ?? 0.02
  const slippage = contract.expected_slippage_rate ?? 0.0075
  const rawEdge = divergence?.edge ?? 0
  const effectiveEdge = rawEdge - fee - slippage

  return (
    <tr>
      <td colSpan={8} style={{ padding: 0 }}>
        <div className="contract-detail">
          {/* Row 1: Contract info + Price chart */}
          <div className="detail-grid">
            <div className="detail-section">
              <div className="detail-label">Resolution</div>
              <div className="detail-value">{contract.resolution_criteria}</div>
              <div className="detail-label" style={{ marginTop: 8 }}>Order Book</div>
              {market ? (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 4, fontSize: 11 }}>
                  <div>YES bid: <span className="c-green">{pct(market.best_yes_bid)}</span></div>
                  <div>YES ask: <span className="c-green">{pct(market.best_yes_ask)}</span></div>
                  <div>NO bid: <span className="c-red">{pct(market.best_no_bid)}</span></div>
                  <div>NO ask: <span className="c-red">{pct(market.best_no_ask)}</span></div>
                  <div className="c-subtle">Spread: {pct((market.best_yes_ask ?? 0) - (market.best_yes_bid ?? 0))}</div>
                  <div className="c-subtle">Vol: {market.volume?.toFixed(0) ?? '—'}</div>
                </div>
              ) : (
                <div className="c-muted">No market data</div>
              )}
              <div className="detail-label" style={{ marginTop: 8 }}>Edge Math</div>
              <div style={{ fontSize: 11 }}>
                <div>Raw edge: {edge(rawEdge)}</div>
                <div>- Fee: {pct(fee)}</div>
                <div>- Slippage: {pct(slippage)}</div>
                <div style={{ borderTop: `1px solid ${colors.border}`, paddingTop: 2, fontWeight: 500 }}>
                  = Effective: <span className={effectiveEdge > 0 ? 'c-green' : 'c-red'}>{edge(effectiveEdge)}</span>
                </div>
              </div>
            </div>
            <div className="detail-section">
              <div className="detail-label">Price History</div>
              <PriceChart
                prices={priceHistory?.prices ?? []}
                predictions={modelPredictions}
              />
            </div>
          </div>

          {/* Row 2: Reasoning + Signal History + Exit Analysis */}
          <div className="detail-grid-3">
            <div className="detail-section">
              <div className="detail-label">Model Reasoning</div>
              <div className="reasoning-text">
                {divergence?.prediction?.reasoning ?? 'No reasoning available'}
              </div>
            </div>
            <div className="detail-section">
              <div className="detail-label">Signal History (last 5)</div>
              {(signals?.signals ?? []).slice(0, 5).map((s, i) => (
                <div key={i} className="metric-row">
                  <span className="metric-label">{relativeTime(s.created_at)}</span>
                  <span>
                    <span className={`badge badge-${s.signal.toLowerCase().replace('_', '-')}`}>
                      {s.signal}
                    </span>
                    {' '}
                    <span className={s.effective_edge >= 0 ? 'c-green' : 'c-red'}>
                      {edge(s.effective_edge)}
                    </span>
                  </span>
                </div>
              ))}
              {(!signals?.signals || signals.signals.length === 0) && (
                <div className="c-muted">No signal history</div>
              )}
            </div>
            <div className="detail-section">
              <div className="detail-label">Exit Analysis</div>
              {edgeDecay ? (
                <>
                  <div className="metric-row">
                    <span className="metric-label">Avg decay rate</span>
                    <span className="metric-value">{edgeDecay.avg_decay_rate?.toFixed(4) ?? '—'}/hr</span>
                  </div>
                  <div className="metric-row">
                    <span className="metric-label">Time to zero edge</span>
                    <span className="metric-value">{edgeDecay.time_to_zero_edge ? `${edgeDecay.time_to_zero_edge}h` : '—'}</span>
                  </div>
                  <div className="metric-row">
                    <span className="metric-label">Round-trip cost</span>
                    <span className="metric-value">{pct(edgeDecay.round_trip_cost)}</span>
                  </div>
                  <div className="metric-row">
                    <span className="metric-label">Verdict</span>
                    <span className="metric-value" style={{
                      color: edgeDecay.exit_profitable ? colors.amber : colors.green,
                    }}>
                      {edgeDecay.verdict}
                    </span>
                  </div>
                </>
              ) : (
                <div className="c-muted">Loading...</div>
              )}
            </div>
          </div>
        </div>
      </td>
    </tr>
  )
}
```

- [ ] **Step 3: Create MarketsTable component**

Create `frontend/src/components/MarketsTable.tsx`:

```typescript
import { useState } from 'react'
import type {
  DivergencesResponse,
  MarketsResponse,
  ContractsResponse,
  PredictionsResponse,
  PredictionHistoryResponse,
} from '../types'
import { ContractDetail } from './ContractDetail'
import { pct, edge } from '../lib/format'

interface MarketsTableProps {
  divergences: DivergencesResponse | null
  markets: MarketsResponse | null
  contracts: ContractsResponse | null
  predictions: PredictionsResponse | null
  predictionHistory: PredictionHistoryResponse | null
}

function proxyBadgeClass(proxy: string): string {
  switch (proxy) {
    case 'DIRECT': return 'badge-direct'
    case 'NEAR_PROXY': return 'badge-near'
    case 'LOOSE_PROXY': return 'badge-loose'
    default: return 'badge-hold'
  }
}

function proxyLabel(proxy: string): string {
  switch (proxy) {
    case 'DIRECT': return 'DIRECT'
    case 'NEAR_PROXY': return 'NEAR'
    case 'LOOSE_PROXY': return 'LOOSE'
    default: return proxy
  }
}

function signalBadgeClass(signal: string): string {
  switch (signal) {
    case 'BUY_YES': return 'badge-buy-yes'
    case 'BUY_NO': return 'badge-buy-no'
    default: return 'badge-hold'
  }
}

interface TableRow {
  ticker: string
  title: string
  marketPrice: number | null
  modelPrice: number | null
  edgeValue: number
  proxy: string
  signal: string
  volume: number | null
  divergenceIndex: number
  contractIndex: number
}

export function MarketsTable({
  divergences,
  markets,
  contracts,
}: MarketsTableProps) {
  const [expandedTicker, setExpandedTicker] = useState<string | null>(null)

  // Build rows from divergences (primary) and contracts (for metadata)
  const rows: TableRow[] = (divergences?.divergences ?? []).map((d, i) => {
    const contract = contracts?.contracts?.find(c => c.ticker === d.market_price?.ticker)
    const market = markets?.markets?.find(m => m.ticker === d.market_price?.ticker)
    return {
      ticker: d.market_price?.ticker ?? d.model_id,
      title: contract?.title ?? d.market_price?.ticker ?? d.model_id,
      marketPrice: d.market_probability,
      modelPrice: d.model_probability,
      edgeValue: d.edge,
      proxy: contract?.best_proxy ?? 'NONE',
      signal: d.signal,
      volume: market?.volume ?? null,
      divergenceIndex: i,
      contractIndex: contracts?.contracts?.findIndex(c => c.ticker === d.market_price?.ticker) ?? -1,
    }
  })

  // Sort by absolute edge descending
  rows.sort((a, b) => Math.abs(b.edgeValue) - Math.abs(a.edgeValue))

  return (
    <>
      <div className="section-label">Markets</div>
      <table className="markets-table">
        <thead>
          <tr>
            <th style={{ width: '2.2fr' }}>Contract</th>
            <th style={{ width: '0.6fr' }}>Market</th>
            <th style={{ width: '0.6fr' }}>Model</th>
            <th style={{ width: '0.6fr' }}>Edge</th>
            <th style={{ width: '0.5fr' }}>Proxy</th>
            <th style={{ width: '0.6fr' }}>Signal</th>
            <th style={{ width: '0.4fr' }}>Volume</th>
            <th style={{ width: '0.2fr' }}></th>
          </tr>
        </thead>
        <tbody>
          {rows.map(row => {
            const isExpanded = expandedTicker === row.ticker
            const isActive = row.signal === 'BUY_YES' || row.signal === 'BUY_NO'
            const rowClass = isActive ? 'active-signal' : 'hold-signal'

            const divergence = divergences?.divergences[row.divergenceIndex] ?? null
            const contract = contracts?.contracts?.[row.contractIndex] ?? null
            const market = markets?.markets?.find(m => m.ticker === row.ticker) ?? null

            return (
              <>
                <tr
                  key={row.ticker}
                  className={`${rowClass} ${isExpanded ? 'expanded' : ''}`}
                  onClick={() => setExpandedTicker(isExpanded ? null : row.ticker)}
                >
                  <td>
                    <span style={{ fontWeight: 500 }}>{row.ticker}</span>
                    <br />
                    <span className="c-subtle" style={{ fontSize: 10 }}>{row.title}</span>
                  </td>
                  <td>{pct(row.marketPrice)}</td>
                  <td>{pct(row.modelPrice)}</td>
                  <td>
                    <span className={row.edgeValue > 0 ? 'c-green' : row.edgeValue < 0 ? 'c-red' : ''}>
                      {edge(row.edgeValue)}
                    </span>
                  </td>
                  <td><span className={`badge ${proxyBadgeClass(row.proxy)}`}>{proxyLabel(row.proxy)}</span></td>
                  <td><span className={`badge ${signalBadgeClass(row.signal)}`}>{row.signal.replace('_', ' ')}</span></td>
                  <td className="c-subtle">{row.volume?.toFixed(0) ?? '—'}</td>
                  <td><span className={`expand-arrow ${isExpanded ? 'open' : ''}`}>▸</span></td>
                </tr>
                {isExpanded && contract && (
                  <ContractDetail
                    key={`${row.ticker}-detail`}
                    contract={contract}
                    divergence={divergence}
                    market={market}
                  />
                )}
              </>
            )
          })}
          {rows.length === 0 && (
            <tr>
              <td colSpan={8} className="loading-text">No divergence data</td>
            </tr>
          )}
        </tbody>
      </table>
    </>
  )
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/MarketsTable.tsx frontend/src/components/ContractDetail.tsx frontend/src/components/PriceChart.tsx
git commit -m "feat: add MarketsTable with expandable ContractDetail and PriceChart"
```

---

## Task 7: Model Health + Portfolio Panel + Ops Footer

**Files:**
- Create: `frontend/src/components/ModelHealth.tsx`
- Create: `frontend/src/components/PortfolioPanel.tsx`
- Create: `frontend/src/components/OpsFooter.tsx`

- [ ] **Step 1: Create ModelHealth component**

Create `frontend/src/components/ModelHealth.tsx`:

```typescript
import type { ScorecardMetrics } from '../types'
import { colors } from '../lib/colors'

interface ModelHealthProps {
  scorecard: ScorecardMetrics | null
}

function metricColor(value: number | null, good: number, bad: number, lowerIsBetter = false): string {
  if (value == null) return colors.dim
  if (lowerIsBetter) {
    return value <= good ? colors.green : value >= bad ? colors.red : colors.amber
  }
  return value >= good ? colors.green : value <= bad ? colors.red : colors.amber
}

export function ModelHealth({ scorecard }: ModelHealthProps) {
  if (!scorecard) return <div className="loading-text">Loading scorecard...</div>

  const brier = scorecard.signal_brier_score
  const hitRate = scorecard.signal_hit_rate
  const calGap = scorecard.signal_calibration_max_gap
  const edgeDecayData = scorecard.signal_edge_decay as number | null | undefined

  return (
    <div>
      <div className="section-label">Model Health</div>

      <div className="metric-row">
        <span className="metric-label">Brier Score</span>
        <span>
          <span className="metric-value" style={{ color: metricColor(brier as number | null, 0.22, 0.25, true) }}>
            {brier != null ? (brier as number).toFixed(3) : '—'}
          </span>
          <span className="metric-benchmark">good &lt;0.22, random=0.25</span>
        </span>
      </div>

      <div className="metric-row">
        <span className="metric-label">Overall Hit Rate</span>
        <span>
          <span className="metric-value" style={{ color: metricColor(hitRate as number | null, 0.5, 0.4) }}>
            {hitRate != null ? `${((hitRate as number) * 100).toFixed(0)}%` : '—'}
          </span>
          <span className="metric-benchmark">&gt;50%</span>
        </span>
      </div>

      <div className="metric-row">
        <span className="metric-label">Calibration Gap</span>
        <span>
          <span className="metric-value" style={{ color: metricColor(calGap as number | null, 0.10, 0.20, true) }}>
            {calGap != null ? `${((calGap as number) * 100).toFixed(0)}%` : '—'}
          </span>
          <span className="metric-benchmark">&lt;10%</span>
        </span>
      </div>

      <div className="metric-row">
        <span className="metric-label">Edge Buckets</span>
        <span className="metric-value c-subtle">
          {edgeDecayData != null ? `${edgeDecayData} buckets` : '—'}
        </span>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Create PortfolioPanel component**

Create `frontend/src/components/PortfolioPanel.tsx`:

```typescript
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts'
import type { PortfolioState } from '../types'
import { usd, signedUsd, signedPct, pctRaw } from '../lib/format'
import { colors } from '../lib/colors'

interface PortfolioPanelProps {
  portfolio: PortfolioState | null
}

export function PortfolioPanel({ portfolio }: PortfolioPanelProps) {
  if (!portfolio) return <div className="loading-text">Loading portfolio...</div>

  return (
    <div>
      <div className="section-label">Simulated Portfolio ($1,000 starting Apr 1)</div>

      {/* Summary Row */}
      <div className="portfolio-summary">
        <div className="portfolio-cell">
          <div className="kpi-label">Value</div>
          <div className="kpi-value" style={{
            color: portfolio.portfolio_return_pct >= 0 ? colors.green : colors.red,
            fontSize: 14,
          }}>
            {usd(portfolio.portfolio_value)} ({signedPct(portfolio.portfolio_return_pct)})
          </div>
        </div>
        <div className="portfolio-cell">
          <div className="kpi-label">Cash</div>
          <div className="kpi-value" style={{ fontSize: 14 }}>
            {usd(portfolio.cash)} ({pctRaw(portfolio.cash_pct)})
          </div>
        </div>
        <div className="portfolio-cell">
          <div className="kpi-label">Deployed</div>
          <div className="kpi-value" style={{ fontSize: 14 }}>
            {usd(portfolio.deployed)} ({portfolio.positions.length} pos)
          </div>
        </div>
        <div className="portfolio-cell">
          <div className="kpi-label">Max Drawdown</div>
          <div className="kpi-value" style={{ fontSize: 14, color: colors.red }}>
            {signedUsd(-portfolio.max_drawdown)} ({signedPct(-portfolio.max_drawdown_pct)})
          </div>
        </div>
        <div className="portfolio-cell">
          <div className="kpi-label">Sharpe (ann.)</div>
          <div className="kpi-value" style={{ fontSize: 14 }}>
            {portfolio.sharpe?.toFixed(1) ?? '—'}
          </div>
        </div>
      </div>

      {/* Equity Curve */}
      {portfolio.equity_curve.length > 0 && (
        <div className="equity-chart">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={portfolio.equity_curve} margin={{ top: 8, right: 8, bottom: 8, left: 8 }}>
              <XAxis
                dataKey="date"
                tick={{ fontSize: 9, fill: colors.dim }}
                axisLine={{ stroke: colors.border }}
                tickLine={false}
                tickFormatter={(v: string) => {
                  const d = new Date(v)
                  return `${d.getMonth() + 1}/${d.getDate()}`
                }}
              />
              <YAxis
                tick={{ fontSize: 9, fill: colors.dim }}
                axisLine={{ stroke: colors.border }}
                tickLine={false}
                tickFormatter={(v: number) => `$${v}`}
              />
              <Tooltip
                contentStyle={{
                  background: colors.surface,
                  border: `1px solid ${colors.border}`,
                  fontSize: 11,
                  color: colors.text,
                }}
                formatter={(v: number) => [`$${v.toFixed(2)}`, 'Portfolio']}
              />
              <ReferenceLine y={1000} stroke={colors.dim} strokeDasharray="4 2" />
              <Line
                type="monotone"
                dataKey="value"
                stroke={colors.green}
                dot={false}
                strokeWidth={1.5}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Open Positions */}
      {portfolio.positions.length > 0 && (
        <>
          <div className="detail-label" style={{ padding: '8px 0 4px' }}>Open Positions</div>
          <table className="positions-table">
            <thead>
              <tr>
                <th>Contract</th>
                <th>Side</th>
                <th>Qty</th>
                <th>Entry</th>
                <th>Current</th>
                <th>Notional</th>
                <th>Unreal P&L</th>
                <th>Weight</th>
              </tr>
            </thead>
            <tbody>
              {portfolio.positions.map(pos => (
                <tr key={pos.ticker}>
                  <td>{pos.ticker}</td>
                  <td>{pos.side.toUpperCase()}</td>
                  <td>{pos.quantity}</td>
                  <td>{(pos.entry_price * 100).toFixed(0)}¢</td>
                  <td>{(pos.current_price * 100).toFixed(0)}¢</td>
                  <td>{usd(pos.notional)}</td>
                  <td style={{ color: pos.unrealized_pnl >= 0 ? colors.green : colors.red }}>
                    {signedUsd(pos.unrealized_pnl)}
                  </td>
                  <td>{pctRaw(pos.weight_pct)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {/* Closed Trades */}
      {portfolio.closed_trades.length > 0 && (
        <>
          <div className="detail-label" style={{ padding: '8px 0 4px' }}>Closed Trades</div>
          <table className="positions-table">
            <thead>
              <tr>
                <th>Contract</th>
                <th>Side</th>
                <th>Qty</th>
                <th>Entry</th>
                <th>Exit</th>
                <th>P&L</th>
                <th>Return</th>
              </tr>
            </thead>
            <tbody>
              {portfolio.closed_trades.map((trade, i) => (
                <tr key={i}>
                  <td>{trade.ticker}</td>
                  <td>{trade.side.toUpperCase()}</td>
                  <td>{trade.quantity}</td>
                  <td>{(trade.entry_price * 100).toFixed(0)}¢</td>
                  <td>{(trade.exit_price * 100).toFixed(0)}¢</td>
                  <td style={{ color: trade.pnl >= 0 ? colors.green : colors.red }}>
                    {signedUsd(trade.pnl)}
                  </td>
                  <td style={{ color: trade.return_pct >= 0 ? colors.green : colors.red }}>
                    {signedPct(trade.return_pct)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {/* Risk Footer */}
      <div style={{ display: 'flex', gap: 0, borderTop: `1px solid ${colors.border}`, marginTop: 8 }}>
        <div className="ops-cell">
          Max concentration: {pctRaw(portfolio.max_concentration_pct)} / 25%
        </div>
        <div className="ops-cell">
          Win rate: {portfolio.win_rate != null ? `${portfolio.win_rate}%` : '—'}
        </div>
        <div className="ops-cell">
          Total fees: {usd(portfolio.total_fees)}
        </div>
        <div className="ops-cell">
          Days remaining: {portfolio.days_remaining}
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Create OpsFooter component**

Create `frontend/src/components/OpsFooter.tsx`:

```typescript
import { useEffect, useState } from 'react'
import type { HealthResponse, ScorecardMetrics } from '../types'
import { usd, relativeTime } from '../lib/format'

interface OpsFooterProps {
  health: HealthResponse | null
  scorecard: ScorecardMetrics | null
  lastUpdated: Date | null
}

export function OpsFooter({ health, scorecard, lastUpdated }: OpsFooterProps) {
  const [countdown, setCountdown] = useState(300)

  useEffect(() => {
    const timer = setInterval(() => {
      setCountdown(prev => (prev <= 0 ? 300 : prev - 1))
    }, 1000)
    return () => clearInterval(timer)
  }, [])

  // Reset countdown when data updates
  useEffect(() => {
    setCountdown(300)
  }, [lastUpdated])

  const runCount = scorecard?.ops_run_count ?? 0
  const successRate = scorecard?.ops_run_success_rate
  const errorCount = scorecard?.ops_error_alert_count ?? 0
  const llmCost = scorecard?.ops_llm_cost_usd ?? 0
  const staleness = scorecard ? (scorecard['data_quote_staleness_rate'] as number | null) : null

  const pipelineHealthy = health?.status === 'healthy' && errorCount === 0
  const statusClass = pipelineHealthy ? 'green' : 'red'

  return (
    <div className="ops-footer">
      <div className="ops-cell">
        <span className={`status-dot ${statusClass}`}></span>
        {pipelineHealthy ? 'Healthy' : 'Issues'}
      </div>
      <div className="ops-cell">
        Runs: {runCount}{successRate != null ? ` (${(successRate * 100).toFixed(0)}% ok)` : ''}
      </div>
      <div className="ops-cell">
        Errors: {errorCount}
      </div>
      <div className="ops-cell">
        LLM: {usd(llmCost as number)}
      </div>
      <div className="ops-cell">
        Stale: {staleness != null ? `${(staleness * 100).toFixed(0)}%` : '—'}
      </div>
      <div className="ops-cell">
        Refresh: {Math.floor(countdown / 60)}:{(countdown % 60).toString().padStart(2, '0')}
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ModelHealth.tsx frontend/src/components/PortfolioPanel.tsx frontend/src/components/OpsFooter.tsx
git commit -m "feat: add ModelHealth, PortfolioPanel, and OpsFooter components"
```

---

## Task 8: App.tsx — Wire Everything Together

**Files:**
- Create: `frontend/src/App.tsx`

- [ ] **Step 1: Create App.tsx**

Create `frontend/src/App.tsx`:

```typescript
import { usePolling } from './hooks/usePolling'
import { KpiBar } from './components/KpiBar'
import { ModelCards } from './components/ModelCards'
import { MarketsTable } from './components/MarketsTable'
import { ModelHealth } from './components/ModelHealth'
import { PortfolioPanel } from './components/PortfolioPanel'
import { OpsFooter } from './components/OpsFooter'
import type {
  HealthResponse,
  PredictionsResponse,
  MarketsResponse,
  DivergencesResponse,
  ScorecardMetrics,
  ContractsResponse,
  PredictionHistoryResponse,
  PortfolioState,
} from './types'

export function App() {
  const health = usePolling<HealthResponse>('/api/health')
  const predictions = usePolling<PredictionsResponse>('/api/predictions')
  const markets = usePolling<MarketsResponse>('/api/markets')
  const divergences = usePolling<DivergencesResponse>('/api/divergences')
  const scorecard = usePolling<ScorecardMetrics>('/api/scorecard')
  const contracts = usePolling<ContractsResponse>('/api/contracts')
  const predictionHistory = usePolling<PredictionHistoryResponse>('/api/prediction-history')
  const portfolio = usePolling<PortfolioState>('/api/portfolio')

  return (
    <div className="dashboard">
      <KpiBar
        health={health.data}
        portfolio={portfolio.data}
        scorecard={scorecard.data}
        divergences={divergences.data}
      />

      <ModelCards
        predictions={predictions.data}
        predictionHistory={predictionHistory.data}
        scorecard={scorecard.data}
      />

      <MarketsTable
        divergences={divergences.data}
        markets={markets.data}
        contracts={contracts.data}
        predictions={predictions.data}
        predictionHistory={predictionHistory.data}
      />

      <div className="two-col">
        <ModelHealth scorecard={scorecard.data} />
        <PortfolioPanel portfolio={portfolio.data} />
      </div>

      <OpsFooter
        health={health.data}
        scorecard={scorecard.data}
        lastUpdated={health.lastUpdated}
      />
    </div>
  )
}
```

- [ ] **Step 2: Verify build compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors (or only minor type issues to fix)

- [ ] **Step 3: Fix any TypeScript errors from Step 2**

Address any compile errors found. Common fixes: missing optional chaining, type narrowing.

- [ ] **Step 4: Verify Vite dev server starts**

Run: `cd frontend && npx vite --open false &` then `sleep 3 && curl -s http://localhost:3000 | head -5`
Expected: HTML response with `<div id="root">`

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "feat: wire dashboard App.tsx with all components and 5-minute polling"
```

---

## Task 9: Integration Verification

**Files:** None (verification only)

- [ ] **Step 1: Run all backend tests**

Run: `cd backend && python -m pytest tests/test_simulator.py tests/test_dashboard_queries.py tests/test_dashboard_endpoints.py -v`
Expected: All tests PASS

- [ ] **Step 2: Run frontend build**

Run: `cd frontend && npm run build`
Expected: Build succeeds, output in `frontend/dist/`

- [ ] **Step 3: Start backend and verify endpoints return data**

Run: `cd backend && DUCKDB_PATH=":memory:" uvicorn parallax.main:app --port 8000 &`
Then test each new endpoint:

```bash
curl -s http://localhost:8000/api/scorecard | python -m json.tool | head -5
curl -s http://localhost:8000/api/contracts | python -m json.tool | head -5
curl -s 'http://localhost:8000/api/signals?contract=KXTEST' | python -m json.tool
curl -s 'http://localhost:8000/api/edge-decay?contract=KXTEST' | python -m json.tool
curl -s 'http://localhost:8000/api/price-history?ticker=KXTEST' | python -m json.tool
curl -s http://localhost:8000/api/prediction-history | python -m json.tool | head -5
curl -s http://localhost:8000/api/portfolio | python -m json.tool | head -5
```

Expected: All return valid JSON (empty data is fine for in-memory DB)

- [ ] **Step 4: Final commit with any fixes**

```bash
git add -A
git commit -m "feat: complete dashboard redesign — backend endpoints + React SPA"
```
