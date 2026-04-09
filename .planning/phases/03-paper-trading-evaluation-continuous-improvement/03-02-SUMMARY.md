---
phase: 03-paper-trading-evaluation-continuous-improvement
plan: 02
subsystem: scoring-dashboard
tags: [report-card, dashboard, calibration, proxy-alignment, cli]
dependency_graph:
  requires: [scoring/calibration.py, scoring/resolution.py, scoring/ledger.py, db/schema.py, cli/brief.py]
  provides: [scoring/report_card.py, dashboard/data.py, dashboard/app.py, --report-card CLI]
  affects: [scoring/resolution.py, cli/brief.py]
tech_stack:
  added: [streamlit, plotly]
  patterns: [data-layer-separation, read-only-db, tdd]
key_files:
  created:
    - backend/src/parallax/scoring/report_card.py
    - backend/src/parallax/dashboard/__init__.py
    - backend/src/parallax/dashboard/data.py
    - backend/src/parallax/dashboard/app.py
    - backend/tests/test_report_card.py
    - backend/tests/test_dashboard_data.py
  modified:
    - backend/src/parallax/scoring/resolution.py
    - backend/src/parallax/cli/brief.py
decisions:
  - Manual z-test formula (no scipy dependency) for statistical significance
  - Dashboard data layer returns plain dicts (no Streamlit coupling)
  - DuckDB read-only mode for dashboard (T-03-04 threat mitigation)
  - Plotly optional import with graceful fallback in Streamlit app
metrics:
  duration: 7m
  completed: 2026-04-08
  tasks_completed: 2
  tasks_total: 2
  tests_added: 23
  tests_total: 245
---

# Phase 03 Plan 02: Report Card, Dashboard Data Layer, and Streamlit App Summary

P&L report card with Sharpe ratio and z-test significance, proxy_was_aligned backfill in resolution checker, reusable dashboard data layer with 4 query functions, and Streamlit single-page dashboard with expandable sections.

## Task Completion

| Task | Name | Commits | Files |
|------|------|---------|-------|
| 1 | Report card module + proxy_was_aligned | 93cb404, 448c826 | report_card.py, resolution.py, test_report_card.py |
| 2 | Dashboard data layer + Streamlit + CLI | 47c8e03 | dashboard/__init__.py, dashboard/data.py, dashboard/app.py, brief.py, test_dashboard_data.py |

## What Was Built

### Report Card (scoring/report_card.py)
- `generate_report_card(conn)` returns formatted text with:
  - Total P&L, avg P&L, win rate
  - Sharpe-like ratio (mean/std of realized_pnl)
  - Z-test significance (manual formula, no scipy)
  - BY PROXY CLASS segmentation with per-class P&L, win rate, avg edge, avg hold duration
  - Per-model accuracy (correct/total, hit rate)
  - Biggest wins (top 3) and worst misses (bottom 3)

### Resolution Checker (scoring/resolution.py)
- `_backfill_signal()` now sets `proxy_was_aligned`:
  - True when BUY_YES and resolution_price > 0.5
  - True when BUY_NO and resolution_price <= 0.5
  - False otherwise

### Dashboard Data Layer (dashboard/data.py)
- `get_latest_brief(conn)` -- latest prediction_log entries by run_id
- `get_calibration_data(conn)` -- reuses calibration.py functions (no duplicate SQL)
- `get_signal_history(conn)` -- recent signal_ledger entries
- `get_market_prices(conn)` -- latest market_prices entries

### Streamlit App (dashboard/app.py)
- 4 expandable sections: Today's Brief, Track Record, Signal History, Market Prices
- DuckDB opened with `read_only=True` (T-03-04 mitigation)
- Plotly calibration chart with graceful import fallback

### CLI (cli/brief.py)
- `--report-card` flag wired to `_run_report_card()` following `_run_calibration()` pattern

## Deviations from Plan

None - plan executed exactly as written.

## Verification Results

- 245 tests passing (23 new tests added)
- All acceptance criteria verified via grep checks
- `from parallax.dashboard.data import get_latest_brief` imports successfully
- `--report-card` flag recognized by CLI argparse

## Self-Check: PASSED

All 6 created files verified on disk. All 3 commits verified in git log.
