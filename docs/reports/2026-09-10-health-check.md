# Parallax Health Check — 2026-09-10

**Status: YELLOW**

## Summary

No production code changes since the 2026-09-09 check — the two commits since the last report are docs only (tech research + health check). All HIGH-severity bugs flagged since 2026-08-26 remain unaddressed for **15+ consecutive days**. One active test failure (`np.trapz` removed in NumPy 2.0) persists. The codebase is architecturally stable; the same correctness defects carry over unchanged.

---

## What Changed Since Yesterday

- `1dffe53` — Daily tech research report 2026-09-09 (docs only)
- `5150c9e` — Daily health check 2026-09-09 (docs only)

**No Python or TypeScript files modified.**

---

## Test Suite (Expected — not re-run, no code changes)

| Run | Result |
|-----|--------|
| Collected | 507 |
| Passed | 490 |
| Skipped | 13 |
| Failed | **1** (`test_selective.py::test_risk_coverage_perfect_ranking`) |

---

## Issues Found

All issues below are carry-overs. Day count since first report is noted.

### HIGH — DuckDB Single-Writer Violations (Day 15+)

`db/writer.py` implements the correct asyncio queue pattern but has zero production call sites. Every write path uses direct `conn.execute()`, risking `database is locked` under concurrent API + CLI usage.

Violating modules (unchanged):
- `[HIGH]` `scoring/ledger.py` — signal record `INSERT`/`UPDATE`
- `[HIGH]` `scoring/tracker.py` — paper trade lifecycle writes
- `[HIGH]` `scoring/scorecard.py` — daily ETL `INSERT ON CONFLICT`
- `[HIGH]` `scoring/resolution.py` — settlement `UPDATE`s
- `[HIGH]` `scoring/prediction_log.py` — prediction `INSERT`
- `[HIGH]` `contracts/registry.py` — contract `INSERT`/`UPDATE`
- `[HIGH]` `budget/tracker.py` — LLM usage `INSERT` (highest frequency)
- `[HIGH]` `ingestion/crisis_ingester.py` — ingestion `INSERT`
- `[HIGH]` `ops/alerts.py` — alert `INSERT`
- `[HIGH]` `backtest/runner.py` — 4 write methods
- `[HIGH]` `cli/brief.py` — run lifecycle writes

### HIGH — Deconfliction Write-Back Bug (Day 15+)

`cli/brief.py` calls `ledger.record_signal()` in a loop (recording signals to DuckDB) and then calls `_deconflict_oil_signals(all_signals)` which only mutates the in-memory list. The `HOLD` mutation is never persisted. Downstream DB reads return stale `BUY_YES`/`BUY_NO` signals, silently allowing correlated oil double-entry.

**Fix:** Move `_deconflict_oil_signals(all_signals)` before the `record_signal()` loop, or issue `UPDATE signal_ledger SET signal = 'HOLD' WHERE signal_id = ?` after each HOLD mutation.

### HIGH — TypeError Crash on NULL Win-Rate (Day 15+)

`scoring/ledger.py:283`: `int(row[1]) / int(row[0])` raises `TypeError` when `model_was_correct` is NULL before the first resolution cycle.

**Fix:** `int(row[1] or 0) / int(row[0] or 0)` (guard the division too).

### MEDIUM — `np.trapz` Removed in NumPy 2.0 (Active Test Failure, Day 15+)

`scoring/selective.py:106`: `np.trapz(risk, coverage)` — removed in NumPy 2.0. Causes `AttributeError` at runtime and an active test failure.

**Fix:** `np.trapz` → `np.trapezoid`.

### MEDIUM — `POST /api/brief/run` Hardcodes `dry_run=True` (Day 15+)

`main.py:252` forces `dry_run=True, no_trade=True` on every API-triggered brief. A live run cannot be initiated via the API.

### MEDIUM — numpy/pandas Missing from Dev Deps (Persistent)

`numpy`, `pandas`, `scikit-learn` required by 4 test files but absent from `[project.optional-dependencies.dev]`. Fresh CI installs fail without manual intervention.

### LOW — anthropic SDK Version Drift (Persistent)

`pyproject.toml` lower bound `>=0.52`; installed SDK is `1.4.0` (two major versions ahead of the pinned floor).

### LOW — Python Version Mismatch (Persistent)

`pyproject.toml` requires `>=3.11`; CLAUDE.md documents Python 3.12; runtime is Python 3.11.15.

### LOW — Spec Architecture Drift (Acknowledged, No Action Required)

Phase 1 spec modules absent by deliberate pivot (agents/, spatial/, eval/, simulation/engine.py, api/websocket.py, api/auth.py). The product is a 3-model prediction market signal engine, not the 50-agent swarm in the original spec.

---

## Spec / Plan Consistency (Unchanged)

| Component | Spec | Reality |
|-----------|------|---------|
| LLM layer | 50-agent country/sub-actor swarm | 3 predictors (oil, ceasefire, Hormuz) |
| Frontend | deck.gl + MapLibre H3 hex map + WebSocket | React + Recharts polling dashboard |
| Data ingestion | GDELT BigQuery (15 min) + ACLED | GDELT DOC API + Google News RSS + Truth Social |
| Eval framework | Per-agent accuracy + prompt versioning | Signal ledger + scorecard + calibration |
| Markets | Not in spec | Kalshi + Polymarket (core addition) |

---

## Recommendations (Same as Days 1–15)

**Priority 1 — 1–2 line fixes each, 15 days overdue:**

1. `scoring/ledger.py:283` — `int(row[1] or 0)` / `int(row[0] or 0)` — prevents TypeError crash before first resolution cycle.
2. `scoring/selective.py:106` — `np.trapz` → `np.trapezoid` — unblocks the active test failure.
3. `cli/brief.py` — move `_deconflict_oil_signals` before the `record_signal()` loop — prevents silent double-entry of correlated oil positions.

**Priority 2:**

4. Add `numpy>=1.26`, `pandas>=2.0`, `scikit-learn>=1.3` to `[project.optional-dependencies.dev]`.
5. Route all writes through `DbWriter` across the 11 violating modules.
6. Add `backtest/runner.py` test coverage.
7. Expose `dry_run` param on `POST /api/brief/run`.

**Priority 3:**

8. `pyproject.toml`: `anthropic>=0.52` → `>=1.0`; `requires-python = ">=3.11"` → `">=3.12"`.
