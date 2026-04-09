"""P&L report card with proxy class segmentation and statistical significance.

Generates a formatted report showing:
- Total P&L, win rate, avg P&L per trade
- Sharpe-like ratio (mean pnl / std pnl)
- Z-test significance (is win rate meaningfully above 50%?)
- P&L segmented by proxy class (DIRECT, NEAR_PROXY, LOOSE_PROXY)
- Avg hold duration per proxy class
- Per-model accuracy breakdown
- Biggest wins and misses (top/bottom 3 by realized_pnl)
"""

from __future__ import annotations

import logging
import math

import duckdb

logger = logging.getLogger(__name__)


def generate_report_card(conn: duckdb.DuckDBPyConnection) -> str:
    """Generate P&L report card from resolved signals in signal_ledger.

    Returns:
        Formatted text report, or insufficient data message.
    """
    # Check for resolved signals
    row = conn.execute(
        "SELECT COUNT(*) FROM signal_ledger WHERE realized_pnl IS NOT NULL"
    ).fetchone()
    total = int(row[0])

    if total == 0:
        return "Insufficient resolved signals for report card."

    # Overall stats
    stats = conn.execute("""
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN realized_pnl > 0 THEN 1 ELSE 0 END) AS wins,
            SUM(realized_pnl) AS total_pnl,
            AVG(realized_pnl) AS avg_pnl,
            STDDEV_SAMP(realized_pnl) AS std_pnl
        FROM signal_ledger
        WHERE realized_pnl IS NOT NULL
    """).fetchone()

    total_trades = int(stats[0])
    wins = int(stats[1])
    total_pnl = float(stats[2])
    avg_pnl = float(stats[3])
    std_pnl = float(stats[4]) if stats[4] is not None and stats[4] > 0 else 0.0

    win_rate = wins / total_trades if total_trades > 0 else 0.0

    # Sharpe-like ratio
    if std_pnl > 0:
        sharpe = avg_pnl / std_pnl
        sharpe_str = f"{sharpe:.3f}"
    else:
        sharpe_str = "N/A"

    # Z-test significance: z = (wins - n * 0.5) / sqrt(n * 0.25)
    if total_trades > 0:
        z_score = (wins - total_trades * 0.5) / math.sqrt(total_trades * 0.25)
        significant = abs(z_score) > 1.96
        sig_str = "YES (p < 0.05)" if significant else "NO (p >= 0.05)"
    else:
        z_score = 0.0
        sig_str = "N/A"

    # Overall avg hold duration
    hold_row = conn.execute("""
        SELECT AVG(EPOCH(resolved_at) - EPOCH(created_at)) AS avg_hold_sec
        FROM signal_ledger
        WHERE realized_pnl IS NOT NULL
          AND resolved_at IS NOT NULL
          AND created_at IS NOT NULL
    """).fetchone()
    avg_hold_sec = float(hold_row[0]) if hold_row[0] is not None else 0.0
    avg_hold_hours = avg_hold_sec / 3600.0

    lines = [
        "=== PARALLAX REPORT CARD ===",
        "",
        "--- TOTAL P&L ---",
        f"  Total Trades:  {total_trades}",
        f"  Total P&L:     ${total_pnl:+.4f}",
        f"  Avg P&L:       ${avg_pnl:+.4f}",
        f"  WIN RATE:      {win_rate:.1%} ({wins}/{total_trades})",
        f"  Sharpe Ratio:  {sharpe_str}",
        f"  Z-Score:       {z_score:+.3f}",
        f"  Significance:  {sig_str}",
        f"  Avg Hold:      {avg_hold_hours:.1f}h avg hold",
        "",
    ]

    # BY PROXY CLASS
    lines.append("--- BY PROXY CLASS ---")
    proxy_rows = conn.execute("""
        SELECT
            proxy_class,
            COUNT(*) AS total,
            SUM(CASE WHEN realized_pnl > 0 THEN 1 ELSE 0 END) AS wins,
            SUM(realized_pnl) AS total_pnl,
            AVG(realized_pnl) AS avg_pnl,
            AVG(ABS(effective_edge)) AS avg_edge,
            AVG(EPOCH(resolved_at) - EPOCH(created_at)) AS avg_hold_sec
        FROM signal_ledger
        WHERE realized_pnl IS NOT NULL
        GROUP BY proxy_class
        ORDER BY proxy_class
    """).fetchall()

    if proxy_rows:
        lines.append(f"  {'Class':<15} {'N':>4} {'Wins':>4} {'P&L':>9} {'Win%':>6} {'AvgEdge':>8} {'Hold':>8}")
        for row in proxy_rows:
            pc = row[0]
            n = int(row[1])
            w = int(row[2])
            pnl = float(row[3])
            wr = w / n if n > 0 else 0.0
            ae = float(row[5]) if row[5] is not None else 0.0
            hold_sec = float(row[6]) if row[6] is not None else 0.0
            hold_h = hold_sec / 3600.0
            lines.append(
                f"  {pc:<15} {n:>4} {w:>4} {pnl:>+9.4f} {wr:>5.1%} {ae:>8.3f} {hold_h:>6.1f}h"
            )
    else:
        lines.append("  No data by proxy class.")
    lines.append("")

    # PER-MODEL ACCURACY
    lines.append("--- PER-MODEL ACCURACY ---")
    model_rows = conn.execute("""
        SELECT
            model_id,
            COUNT(*) AS total,
            SUM(CASE WHEN model_was_correct THEN 1 ELSE 0 END) AS correct
        FROM signal_ledger
        WHERE model_was_correct IS NOT NULL
        GROUP BY model_id
        ORDER BY model_id
    """).fetchall()

    if model_rows:
        lines.append(f"  {'Model':<20} {'Correct':>7} {'Total':>5} {'Hit Rate':>8}")
        for row in model_rows:
            mid = row[0]
            n = int(row[1])
            c = int(row[2])
            hr = c / n if n > 0 else 0.0
            lines.append(f"  {mid:<20} {c:>7} {n:>5} {hr:>8.1%}")
    else:
        lines.append("  No model accuracy data.")
    lines.append("")

    # BIGGEST WINS
    lines.append("--- BIGGEST WINS ---")
    win_rows = conn.execute("""
        SELECT contract_ticker, model_id, realized_pnl, signal
        FROM signal_ledger
        WHERE realized_pnl IS NOT NULL AND realized_pnl > 0
        ORDER BY realized_pnl DESC
        LIMIT 3
    """).fetchall()

    if win_rows:
        for row in win_rows:
            lines.append(f"  {row[0]:<30} {row[1]:<18} {row[3]:<8} PnL: ${float(row[2]):+.4f}")
    else:
        lines.append("  No winning trades yet.")
    lines.append("")

    # BIGGEST MISSES
    lines.append("--- WORST MISSES ---")
    miss_rows = conn.execute("""
        SELECT contract_ticker, model_id, realized_pnl, signal
        FROM signal_ledger
        WHERE realized_pnl IS NOT NULL AND realized_pnl < 0
        ORDER BY realized_pnl ASC
        LIMIT 3
    """).fetchall()

    if miss_rows:
        for row in miss_rows:
            lines.append(f"  {row[0]:<30} {row[1]:<18} {row[3]:<8} PnL: ${float(row[2]):+.4f}")
    else:
        lines.append("  No losing trades yet.")
    lines.append("")

    lines.append("=" * 30)
    return "\n".join(lines)
