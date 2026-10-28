# Parallax Health Check — 2026-10-28

**Status: YELLOW**

The codebase is functionally stable with 485 passing tests, but two HIGH-severity bugs first flagged on 2026-10-26 remain unaddressed after two days: `np.trapz` removed in NumPy 2.0+ causes a runtime crash in `scoring/selective.py`, and `scikit-learn` is absent from production dependencies despite being called in `scoring/recalibrators.py`. No new code commits landed since 2026-10-26; both issues are regression-level fixes that are one-line changes away from resolution.

---

## Summary

No new code changes since the 2026-10-26 report (only doc/health-check commits). The six test failures from the prior cycle persist unchanged — 5 due to missing `sklearn` in base deps, 1 due to `numpy.trapz` removal. The core prediction → market → divergence → paper-trade pipeline is untouched and stable. Architecture drift from the Phase 1 spec continues as a known, accepted product pivot.

---

## Test Suite

| Category | Count |
|---|---|
| Passed | 485 |
| **Failed** | **6** (unchanged from 10-26) |
| Skipped | 13 |
| **Total** | **504** |

---

## Issues Found

### [HIGH] `np.trapz` Removed in NumPy 2.0 — Persistent (Day 3)

**File:** `scoring/selective.py:106`
**Failure:** `AttributeError: module 'numpy' has no attribute 'trapz'`
**Root cause:** `np.trapz` was deprecated in NumPy 1.24 and removed in NumPy 2.0. The environment has NumPy 2.5.3 installed. Any call path that reaches `aurc()` will raise at runtime — this includes any scorecard computation or calibration metric that depends on the risk-coverage curve.

**Fix (one line):**
```python
# Line 106: change
return float(np.trapz(risk, coverage))
# to
return float(np.trapezoid(risk, coverage))
```

---

### [HIGH] `scikit-learn` Missing from Base Dependencies — Persistent (Day 3)

**Files:** `scoring/recalibrators.py:111`, `scoring/recalibrators.py:145`
**Failure:** `ModuleNotFoundError: No module named 'sklearn'` in 5 recalibrator tests
**Root cause:** `scikit-learn>=1.3` is declared under `[project.optional-dependencies] bench` in `pyproject.toml`. However, `scoring/recalibrators.py` (`IsotonicRecalibrator`, `PlattRecalibrator`) imports sklearn at fit-time. These recalibrators are production code used in the live calibration pipeline — not bench-only. A fresh install via `pip install -e "."` (without `[bench]`) will fail at runtime when either is called.

**Fix:** Move `scikit-learn>=1.3` from the `bench` extras to the base `dependencies` list in `pyproject.toml`.

---

### [MEDIUM] DuckDB Single-Writer Violations — Persistent

Multiple modules write to DuckDB directly via `conn.execute()` / `_conn.execute()` outside the `asyncio.Queue → DbWriter` pattern. Under concurrent FastAPI request handling, these contend with each other and may raise `database is locked` non-deterministically.

Confirmed violators (unchanged from prior reports):
- `scoring/ledger.py`, `scoring/tracker.py`, `scoring/prediction_log.py`, `scoring/recalibration.py`, `scoring/scorecard.py`, `scoring/track_record.py`, `scoring/report_card.py`
- `ops/alerts.py` — live pipeline path; highest concurrency risk
- `ingestion/crisis_ingester.py`
- `backtest/runner.py`, `backtest/look_ahead_guard.py` (lower risk; offline, non-concurrent)

**Recommendation:** Route all scoring and alert writes through `DbWriter.enqueue()` for the live path. Backtest modules can stay direct-write given their single-threaded execution context.

---

### [MEDIUM] Architecture Drift from Phase 1 Spec — Persistent

The spec describes a 50-agent LLM swarm with H3 spatial model, DES simulation engine, and WebSocket-driven deck.gl/MapLibre frontend. The implementation is a 3-model prediction market edge-finder (oil price, ceasefire, Hormuz) with a polling React dashboard. This is a deliberate product pivot documented in CLAUDE.md.

No new drift detected this cycle. No action needed unless the original spec is being resumed.

---

### [LOW] `requires-python` Mismatch — Persistent

- `pyproject.toml`: `requires-python = ">=3.11"`
- CLAUDE.md states Python 3.12 as the target runtime

No functional impact, but inconsistent declaration may cause confusion in CI or fresh installs.

---

### [LOW] 13 Skipped Tests

13 tests remain permanently skipped (6 from `test_mapping_policy.py` pre-refactor, plus others). These erode coverage silently without alerting CI.

---

## What's Working Well

- **485 tests passing** — core prediction, divergence detection, paper trading, scoring, and calibration modules are stable
- **`DbWriter` pattern correctly implemented** in `db/writer.py` — the architecture is right, the problem is consumers not using it
- **Schema is comprehensive** — 26+ DuckDB tables covering the full prediction-market lifecycle
- **Budget tracking** and runtime kill-switch are implemented and operational
- **Signal ledger + scorecard ETL** covers the full eval loop
- **Paper trading** via Kalshi sandbox is wired up

---

## Recommendations (Priority Order)

1. **[Immediate — 1 line]** Fix `np.trapz` → `np.trapezoid` in `scoring/selective.py:106`
2. **[Immediate — 1 line]** Move `scikit-learn>=1.3` from `bench` extras to base `dependencies` in `pyproject.toml`
3. **[Short-term]** Route `ops/alerts.py` and scoring module writes through `DbWriter.enqueue()` — the live pipeline path is the concurrency risk
4. **[Housekeeping]** Update `requires-python = ">=3.12"` in `pyproject.toml`
5. **[Documentation]** Archive or update Phase 1 spec/plan with a pivot note to avoid misleading future contributors
