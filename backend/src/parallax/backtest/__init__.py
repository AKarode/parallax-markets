"""Backtest harness for historical prediction validation.

Replays predictions against historical data with strict look-ahead prevention.
"""

from parallax.backtest.look_ahead_guard import LookAheadGuard, look_ahead_safe
from parallax.backtest.report import BacktestReport, generate_backtest_report
from parallax.backtest.runner import BacktestConfig, BacktestRunner

__all__ = [
    "BacktestConfig",
    "BacktestRunner",
    "BacktestReport",
    "LookAheadGuard",
    "generate_backtest_report",
    "look_ahead_safe",
]
