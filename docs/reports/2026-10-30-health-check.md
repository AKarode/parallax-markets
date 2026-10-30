# Parallax Health Check — 2026-10-30

**Status: YELLOW**

No code commits since 2026-10-29. Both HIGH-severity fixes from yesterday (`np.trapezoid`, `scikit-learn`/`numpy` to base deps) are confirmed landed and correct. The DuckDB single-writer violations in the live scoring/alerting path enter Day 5 unresolved, and `streamlit`/`plotly` remain absent from `pyproject.toml`. No regressions introduced.

---

## Summary

Yesterday's two HIGH fixes are verified: `scoring/selective.py:106` correctly calls `np.trapezoid`, and `pyproject.toml` has `scikit-learn>=1.3` and `numpy>=1.26` in base dependencies. Confirmed live test run: **491 passed, 13 skipped, 0 failed** (105s). The project is architecturally stable — the prediction-market signal pipeline remains coherent. The only actionable items are the persistent MEDIUM concurrency risk (`conn.execute()` in live-path modules) and two LOW housekeeping items.

---

## Fixes Verified From 2026-10-29

| Fix | File | Status |
|---|---|---|
| `np.trapz` → `np.trapezoid` | `scoring/selective.py:106` | ✓ Confirmed |
| `scikit-learn>=1.3` in base deps | `pyproject.toml:15` | ✓ Confirmed |
| `numpy>=1.26` in base deps | `pyproject.toml:16` | ✓ Confirmed |

---

## Issues Found

### MEDIUM Severity — Carry-Over (Day 5)

- **[BUG] DuckDB single-writer violations in live-path modules**
  Six modules write to DuckDB directly via `conn.execute()` / `_conn.execute()` outside the `asyncio.Queue → DbWriter` pattern. Under concurrent FastAPI request handling (e.g., `/api/brief/run` + `/api/scorecard` hitting simultaneously), these paths contend and can raise `database is locked` non-deterministically.
  
  Confirmed violators in live pipeline paths:
  - `scoring/ledger.py` (lines 225, 256) — signal persistence
  - `scoring/prediction_log.py` (line 79) — prediction persistence
  - `scoring/resolution.py` (lines 60, 124) — settlement write-back
  - `scoring/tracker.py` (lines 460, 516, 672, 711, 744) — trade lifecycle
  - `ops/alerts.py` (line 106) — **highest risk; executed on every alert dispatch**
  
  Lower-risk (offline/non-concurrent context — acceptable as-is):
  - `backtest/runner.py`, `backtest/look_ahead_guard.py`
  - `scoring/scorecard.py`, `scoring/track_record.py`, `scoring/report_card.py`
  - `scoring/calibration.py`, `scoring/recalibration.py`
  
  **Fix:** Route all live-path writes through `DbWriter.enqueue()`. The `DbWriter` class is correctly implemented in `db/writer.py` — it just needs to be wired in.

### LOW Severity — Carry-Over

- **[DEP] `streamlit` and `plotly` missing from `pyproject.toml`**
  `dashboard/app.py:16–17` imports both at module level. Neither appears in any dependency group in `pyproject.toml`. Fresh `pip install -e "."` (without manual extras) will raise `ModuleNotFoundError` for any code path touching `dashboard/app.py`.
  **Fix:** Add `dashboard = ["streamlit>=1.36", "plotly>=5.22"]` to `[project.optional-dependencies]` in `pyproject.toml`.

- **[CONFIG] `requires-python = ">=3.11"` vs CLAUDE.md Python 3.12 target**
  No functional impact, but misleading. The runtime environment and CLAUDE.md both specify Python 3.12+.
  **Fix:** Change `requires-python = ">=3.12"` in `pyproject.toml:4`.

- **[SMELL] 13 permanently skipped tests**
  6 from `test_mapping_policy.py` (pre-refactor stubs) plus others. Erode coverage signal without CI alerts. Recommend removing stubs or marking with `pytest.mark.xfail` and a reason string.

---

## Spec / Plan Consistency

No changes since 2026-10-29. The intentional product pivot from the 50-agent swarm spec to a 3-model prediction market signal engine remains stable and documented in `CLAUDE.md`. Absent modules (`agents/`, `simulation/engine.py`, `simulation/circuit_breaker.py`, `spatial/`, `ingestion/dedup.py`, `eval/`) are unbuilt by design, not regressions.

| Component | Spec | Reality |
|---|---|---|
| LLM layer | 50-agent country/sub-actor swarm | 3 predictors (oil, ceasefire, Hormuz) |
| Frontend | deck.gl + MapLibre H3 hex map + WebSocket | React + Recharts polling dashboard |
| Data ingestion | GDELT BigQuery + ACLED | GDELT DOC API + Google News RSS + Truth Social |
| Eval framework | Per-agent accuracy + prompt versioning | Signal ledger + scorecard + calibration |
| Markets | Not in spec | Kalshi + Polymarket (core addition) |

---

## Test Coverage

47 test files — unchanged. Confirmed live run: **491 passed, 13 skipped, 0 failed** (105s). The two HIGH fixes from yesterday are confirmed working — the 6 previously failing calibration/recalibrator tests now pass.

No new test coverage added. The DuckDB single-writer path in `ops/alerts.py` and live scoring modules remains untested for concurrent-write behaviour.

---

## What's Working Well

- **Core pipeline stable** — prediction → market → divergence → paper-trade lifecycle
- **47 test files** covering simulation, cascade, calibration, divergence, scoring, and dashboard
- **`DbWriter` pattern correctly implemented** in `db/writer.py` — needs wiring to live-path modules
- **Schema comprehensive** — 26+ DuckDB tables covering the full prediction-market lifecycle
- **Budget tracking and kill-switch** operational
- **Signal ledger + scorecard ETL** covers the full eval loop
- **Two HIGH bugs fixed yesterday** — `np.trapezoid` + sklearn/numpy in base deps

---

## Recommendations (Priority Order)

1. **[Short-term, Day 5 MEDIUM]** Route `ops/alerts.py:106` and `scoring/ledger.py:225,256` through `DbWriter.enqueue()` — `ops/alerts.py` is the highest concurrency risk since it fires on every alert dispatch under live load.
2. **[Housekeeping]** Add `streamlit`/`plotly` to optional deps in `pyproject.toml` (one-line fix).
3. **[Housekeeping]** Update `requires-python = ">=3.12"` in `pyproject.toml`.
4. **[Cleanup]** Remove or properly annotate the 13 permanently skipped tests.
