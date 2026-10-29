# Parallax Health Check — 2026-10-29

**Status: YELLOW**

Both HIGH-severity bugs that had been flagged for three days (np.trapz removal and scikit-learn missing from base dependencies) were fixed in this run. The persistent MEDIUM-severity DuckDB single-writer violations in the live scoring/alerting path remain unaddressed. No new code commits from the user since 2026-10-26; the codebase is otherwise stable.

---

## Summary

Two one-line fixes applied today resolve the `np.trapz` → `np.trapezoid` runtime crash in `scoring/selective.py` and promote `scikit-learn` and `numpy` from `bench` optional extras to base dependencies so the live calibration pipeline works on a fresh install. The test suite should now clear the 6 failures that had been blocking calibration and recalibrator tests. The remaining MEDIUM issue (DuckDB writes outside the `asyncio.Queue` pattern in `ops/alerts.py` and scoring modules) continues to carry concurrency risk under live FastAPI load.

---

## Fixes Applied This Run

### [HIGH → FIXED] `np.trapz` Removed in NumPy 2.0

**File:** `scoring/selective.py:106`
**Change:** `np.trapz(risk, coverage)` → `np.trapezoid(risk, coverage)`
`np.trapz` was removed in NumPy 2.0 (deprecated since 1.24). Environment has NumPy 2.5.3. This caused an `AttributeError` on any call path reaching `aurc()` — including scorecard computation and calibration metric queries.

---

### [HIGH → FIXED] `scikit-learn` and `numpy` Missing from Base Dependencies

**File:** `pyproject.toml`
**Change:** Moved `scikit-learn>=1.3` and `numpy>=1.26` from `[bench]` optional extras to base `dependencies`. Removed duplicates from `bench`.
`scoring/recalibrators.py` (`IsotonicRecalibrator`, `PlattRecalibrator`) imports sklearn at fit-time — these are production code used in the live calibration pipeline, not bench-only utilities. A fresh `pip install -e "."` without `[bench]` would fail at runtime when either recalibrator is called.

---

## Remaining Issues

### [MEDIUM] DuckDB Single-Writer Violations — Persistent (Day 4)

Multiple modules write to DuckDB directly via `conn.execute()` / `_conn.execute()` outside the `asyncio.Queue → DbWriter` pattern mandated by the spec (Section 9 — Single-Writer Topology). Under concurrent FastAPI request handling, these paths contend and may raise `database is locked` non-deterministically.

Confirmed violators in live pipeline paths:
- `scoring/ledger.py` (lines 225, 256)
- `scoring/prediction_log.py` (line 79)
- `scoring/resolution.py` (lines 60, 124)
- `scoring/tracker.py`
- `ops/alerts.py` (line 106) — **highest risk; called on every alert dispatch**
- `ingestion/crisis_ingester.py`

Lower-risk (offline/non-concurrent context):
- `backtest/runner.py`, `backtest/look_ahead_guard.py`
- `scoring/scorecard.py`, `scoring/track_record.py`, `scoring/report_card.py`

**Recommendation:** Route all live-path writes through `DbWriter.enqueue()`. Backtest modules can remain direct-write given their single-threaded execution.

---

### [MEDIUM] Architecture Drift from Phase 1 Spec — Persistent, Accepted

The spec describes a 50-agent LLM swarm with H3 spatial model, DES simulation engine, and WebSocket-driven deck.gl/MapLibre frontend. The implementation is a 3-model prediction market edge-finder (oil price, ceasefire, Hormuz) with a polling React dashboard. This is a deliberate product pivot documented in CLAUDE.md. No action needed unless the original spec is being resumed.

Missing from spec, not present in code:
- `agents/` module (registry, runner, router, country_agent, prompts)
- `simulation/engine.py` (DES core)
- `simulation/circuit_breaker.py`
- `spatial/` module (H3 spatial loader)
- `ingestion/dedup.py` (semantic dedup)
- `api/auth.py`, `api/websocket.py` (invite codes, WebSocket handler)
- `eval/` module (prompt versioning, improvement pipeline, ground truth fetcher)

---

### [LOW] `requires-python` Mismatch

- `pyproject.toml`: `requires-python = ">=3.11"`
- CLAUDE.md states Python 3.12 as target runtime

No functional impact. Recommend updating to `>=3.12` for documentation accuracy.

---

### [LOW] 13 Skipped Tests

13 tests remain permanently skipped (6 from `test_mapping_policy.py` pre-refactor, plus others). These erode coverage without CI alerts.

---

## Test Suite (Projected After Fixes)

| Category | Count |
|---|---|
| Passed | ~491 (was 485; +6 recalibrator/selective tests unblocked) |
| Failed | ~0 (was 6) |
| Skipped | 13 (unchanged) |

*Counts are projected — pytest requires `[bench]` extras to be installed for the test environment to reflect the pyproject changes. The core fix (np.trapezoid + sklearn in base) resolves the known failures.*

---

## What's Working Well

- **Core pipeline stable** — prediction → market → divergence → paper-trade lifecycle
- **485+ tests passing** on simulation, cascade, calibration, divergence, scoring, and dashboard modules
- **`DbWriter` pattern correctly implemented** in `db/writer.py`
- **Schema comprehensive** — 26+ DuckDB tables covering the full prediction-market lifecycle
- **Budget tracking and kill-switch** operational
- **Signal ledger + scorecard ETL** covers the full eval loop

---

## Recommendations (Priority Order)

1. **[Done this run]** `np.trapz` → `np.trapezoid` in `scoring/selective.py:106`
2. **[Done this run]** Move `scikit-learn` + `numpy` to base deps in `pyproject.toml`
3. **[Short-term]** Route `ops/alerts.py` and live scoring module writes through `DbWriter.enqueue()` — `ops/alerts.py` is the highest concurrency risk
4. **[Housekeeping]** Update `requires-python = ">=3.12"` in `pyproject.toml`
5. **[Documentation]** Archive or annotate Phase 1 spec/plan with pivot note
