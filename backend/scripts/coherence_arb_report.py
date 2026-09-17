#!/usr/bin/env python3
"""Summarize the running coherence-arb probe's collected data.

Usage: python3 coherence_arb_report.py [path-to-sqlite]
Reads the probe's sqlite DB and prints a compact status: poll count, time span,
distribution of net-taker and maker gaps, any paper fills, and the live verdict.
"""
from __future__ import annotations

import os
import sqlite3
import sys

DEFAULT = os.path.join(os.path.dirname(__file__), "..", "..", "data", "coherence_probe.sqlite")
EDGE_THRESHOLD = 0.005


def main() -> int:
    path = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else DEFAULT)
    if not os.path.exists(path):
        print(f"no DB at {path}")
        return 1
    c = sqlite3.connect(path)

    polls = c.execute("SELECT COUNT(*) FROM poll_meta").fetchone()[0]
    span = c.execute("SELECT MIN(ts), MAX(ts) FROM poll_meta").fetchone()
    incomplete = c.execute("SELECT COUNT(*) FROM poll_meta WHERE note!='ok'").fetchone()[0]
    print(f"polls={polls}  incomplete={incomplete}")
    print(f"span: {span[0]}  ->  {span[1]}")

    print("\nper identity/direction (net taker gap = gross - politics fee):")
    rows = c.execute(
        "SELECT identity, direction, COUNT(*), ROUND(AVG(net_gap),4), ROUND(MAX(net_gap),4), "
        "ROUND(AVG(maker_mid_gap),4), ROUND(MAX(maker_mid_gap),4), ROUND(MIN(maker_mid_gap),4) "
        "FROM arb_log GROUP BY identity, direction ORDER BY identity, direction"
    ).fetchall()
    print(f"  {'id/dir':<16}{'n':>5}{'net_avg':>10}{'net_max':>10}{'mk_avg':>9}{'mk_max':>9}{'mk_min':>9}")
    for r in rows:
        print(f"  {r[0]+'/'+r[1]:<16}{r[2]:>5}{r[3]:>10}{r[4]:>10}{r[5]:>9}{r[6]:>9}{r[7]:>9}")

    best_net = c.execute("SELECT MAX(net_gap) FROM arb_log").fetchone()[0]
    best_maker = c.execute("SELECT MAX(maker_mid_gap) FROM arb_log").fetchone()[0]
    # how often did maker best-case clear a full tick?
    over_tick = c.execute("SELECT COUNT(*) FROM arb_log WHERE maker_mid_gap >= 0.01").fetchone()[0]
    total = c.execute("SELECT COUNT(*) FROM arb_log").fetchone()[0]

    n_trades = c.execute("SELECT COUNT(*) FROM arb_trades").fetchone()[0]
    locked = c.execute("SELECT COALESCE(SUM(locked_profit),0) FROM arb_trades").fetchone()[0]
    deployed = c.execute("SELECT COALESCE(SUM(capital_deployed),0) FROM arb_trades").fetchone()[0]

    print(f"\nbest NET taker gap ever: {best_net:+.4f}  (>{EDGE_THRESHOLD} => riskless arb)")
    print(f"best MAKER mid gap ever: {best_maker:+.4f}  (tick=0.01); maker>=1 tick in {over_tick}/{total} obs")
    print(f"paper fills: {n_trades}  capital deployed: ${deployed:.2f}  locked riskless profit: ${locked:.2f}")
    print(f"pretend bankroll: $1000.00  ->  ${1000.0 - deployed + locked:.2f} (cash+locked)")

    if best_net is not None and best_net >= EDGE_THRESHOLD:
        print("VERDICT (live): a riskless fillable arb appeared -> inspect arb_trades.")
    elif best_maker is not None and best_maker >= 0.01:
        print("VERDICT (live): no taker arb; maker best-case cleared a tick at times -> leg/fill-risk gated.")
    else:
        print("VERDICT (live): book coherent to the price grid -> thesis NULL (expected modal outcome).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
