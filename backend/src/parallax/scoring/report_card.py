"""Trading report card based only on real paper-trade lifecycle records."""

from __future__ import annotations

import math

import duckdb


def generate_report_card(conn: duckdb.DuckDBPyConnection) -> str:
    row = conn.execute(
        """
        SELECT COUNT(*)
        FROM trade_evaluation
        WHERE closed_at IS NOT NULL
          AND realized_pnl IS NOT NULL
        """
    ).fetchone()
    total = int(row[0]) if row else 0
    if total == 0:
        return "Insufficient closed traded positions for report card."

    stats = conn.execute("""
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN realized_pnl > 0 THEN 1 ELSE 0 END) AS wins,
            SUM(realized_pnl) AS total_pnl,
            AVG(realized_pnl) AS avg_pnl,
            STDDEV_SAMP(realized_pnl) AS std_pnl
        FROM trade_evaluation
        WHERE closed_at IS NOT NULL
          AND realized_pnl IS NOT NULL
    """).fetchone()

    total_trades = int(stats[0])
    wins = int(stats[1])
    total_pnl = float(stats[2])
    avg_pnl = float(stats[3])
    std_pnl = float(stats[4]) if stats[4] is not None and stats[4] > 0 else 0.0
    win_rate = wins / total_trades if total_trades else 0.0

    if std_pnl > 0:
        sharpe_str = f"{(avg_pnl / std_pnl):.3f}"
    else:
        sharpe_str = "N/A"

    if total_trades > 0:
        z_score = (wins - total_trades * 0.5) / math.sqrt(total_trades * 0.25)
        sig_str = "YES (p < 0.05)" if abs(z_score) > 1.96 else "NO (p >= 0.05)"
    else:
        z_score = 0.0
        sig_str = "N/A"

    hold_row = conn.execute("""
        SELECT AVG(EPOCH(closed_at) - EPOCH(opened_at))
        FROM trade_evaluation
        WHERE closed_at IS NOT NULL
    """).fetchone()
    avg_hold_hours = (float(hold_row[0]) if hold_row and hold_row[0] is not None else 0.0) / 3600.0

    lines = [
        "=== PARALLAX TRADING REPORT CARD ===",
        "Uses only actually filled and later closed paper positions.",
        "",
        "--- TOTAL P&L ---",
        f"  Total Positions: {total_trades}",
        f"  Total P&L:      ${total_pnl:+.4f}",
        f"  Avg P&L:        ${avg_pnl:+.4f}",
        f"  Win Rate:       {win_rate:.1%} ({wins}/{total_trades})",
        f"  Sharpe Ratio:   {sharpe_str}",
        f"  Z-Score:        {z_score:+.3f}",
        f"  Significance:   {sig_str}",
        f"  Avg Hold:       {avg_hold_hours:.1f}h",
        "",
        "--- BY PROXY CLASS ---",
    ]

    proxy_rows = conn.execute("""
        SELECT
            COALESCE(proxy_class, 'unknown') AS proxy_class,
            COUNT(*) AS total,
            SUM(CASE WHEN realized_pnl > 0 THEN 1 ELSE 0 END) AS wins,
            SUM(realized_pnl) AS total_pnl,
            AVG(realized_pnl) AS avg_pnl,
            AVG(ABS(effective_edge)) AS avg_edge,
            AVG(EPOCH(closed_at) - EPOCH(opened_at)) AS avg_hold_sec
        FROM trade_evaluation
        WHERE closed_at IS NOT NULL
          AND realized_pnl IS NOT NULL
        GROUP BY COALESCE(proxy_class, 'unknown')
        ORDER BY proxy_class
    """).fetchall()

    if proxy_rows:
        lines.append(f"  {'Class':<15} {'N':>4} {'Wins':>4} {'P&L':>9} {'Win%':>6} {'AvgEdge':>8} {'Hold':>8}")
        for row in proxy_rows:
            hold_h = (float(row[6]) if row[6] is not None else 0.0) / 3600.0
            win_rate_proxy = int(row[2]) / int(row[1]) if row[1] else 0.0
            lines.append(
                f"  {row[0]:<15} {int(row[1]):>4} {int(row[2]):>4} {float(row[3]):>+9.4f} {win_rate_proxy:>5.1%} {float(row[5] or 0):>8.3f} {hold_h:>6.1f}h"
            )
    else:
        lines.append("  No proxy-class trading data.")
    lines.append("")

    lines.append("--- PER-MODEL TRADING ---")
    model_rows = conn.execute("""
        SELECT
            COALESCE(model_id, 'unknown') AS model_id,
            COUNT(*) AS total,
            SUM(CASE WHEN realized_pnl > 0 THEN 1 ELSE 0 END) AS wins,
            SUM(realized_pnl) AS total_pnl
        FROM trade_evaluation
        WHERE closed_at IS NOT NULL
          AND realized_pnl IS NOT NULL
        GROUP BY COALESCE(model_id, 'unknown')
        ORDER BY model_id
    """).fetchall()
    if model_rows:
        lines.append(f"  {'Model':<20} {'Wins':>5} {'Total':>5} {'P&L':>10}")
        for row in model_rows:
            lines.append(
                f"  {row[0]:<20} {int(row[2]):>5} {int(row[1]):>5} {float(row[3]):>+10.4f}"
            )
    else:
        lines.append("  No per-model trading data.")
    lines.append("")

    lines.append("--- BIGGEST WINS ---")
    wins = conn.execute("""
        SELECT contract_ticker, model_id, realized_pnl, side
        FROM trade_evaluation
        WHERE closed_at IS NOT NULL
          AND realized_pnl > 0
        ORDER BY realized_pnl DESC
        LIMIT 3
    """).fetchall()
    if wins:
        for row in wins:
            lines.append(f"  {row[0]:<30} {str(row[1] or 'unknown'):<18} {row[3]:<4} PnL: ${float(row[2]):+.4f}")
    else:
        lines.append("  No winning traded positions yet.")
    lines.append("")

    lines.append("--- WORST MISSES ---")
    misses = conn.execute("""
        SELECT contract_ticker, model_id, realized_pnl, side
        FROM trade_evaluation
        WHERE closed_at IS NOT NULL
          AND realized_pnl < 0
        ORDER BY realized_pnl ASC
        LIMIT 3
    """).fetchall()
    if misses:
        for row in misses:
            lines.append(f"  {row[0]:<30} {str(row[1] or 'unknown'):<18} {row[3]:<4} PnL: ${float(row[2]):+.4f}")
    else:
        lines.append("  No losing traded positions yet.")
    lines.append("")

    return "\n".join(lines)
