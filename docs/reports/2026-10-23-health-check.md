# Parallax Health Check — 2026-10-23

**Status: YELLOW**

No commits since yesterday. All four previously-flagged issues remain open and unaddressed: `np.trapz` removed in numpy 2.0, `scikit-learn`/`numpy`/`pandas` in wrong extras group, `cryptography` undeclared, and three DuckDB single-writer violations. The test suite could not be executed in today's cloud environment (Python 3.13 is incompatible with the duckdb wheel — `ImportError: undefined symbol: PyErr_GetRaisedException`); the reported 6 failures from 2026-10-22 are assumed unchanged.

---

## Summary

| Category | Status | Δ vs Yesterday |
|----------|--------|---------------|
| Test suite | ⚠️ Cannot run (Python 3.13 / duckdb abi3 incompatibility) | 🔴 New blocker |
| Dependency audit | ⚠️ `cryptography` + `scikit-learn`/`numpy`/`pandas` misdeclared | ↔ Same |
| Code quality | ⚠️ `np.trapz` removed in numpy 2.0 — `selective.py:106` breaks | ↔ Same |
| DuckDB single-writer | ⚠️ 3 modules violate pattern | ↔ Same |
| Architecture/spec | ⚠️ Phase 1 spec stale (intentional pivot) | ↔ Same |

---

## Issues Found

### [HIGH] Test suite blocked by Python 3.13 / duckdb wheel incompatibility

- The cloud execution environment runs **Python 3.13**.
- The duckdb abi3 wheel (`_duckdb.abi3.so`) fails to load: `ImportError: undefined symbol: PyErr_GetRaisedException`.
- `PyErr_GetRaisedException` was added in CPython 3.12 as a stable API symbol; the installed duckdb wheel (targeting 3.12 ABI) is not binary-compatible with the 3.13 runtime in this container.
- **Impact**: `conftest.py` cannot import `duckdb`, so the entire test suite fails to collect. Cannot confirm whether yesterday's 6 failures are fixed or regressed.
- **Fix**: Ensure CI/cloud execution environment uses Python 3.12. The `pyproject.toml` specifies `requires-python = ">=3.11"` which should be tightened to `">=3.12,<3.14"` until duckdb publishes 3.13-compatible wheels.

### [HIGH] `np.trapz` removed in numpy 2.0 — `selective.py:106`

Unchanged from yesterday.

- `scoring/selective.py:106`: `return float(np.trapz(risk, coverage))`
- `numpy.trapz` was removed in numpy 2.0. Installed version is **2.5.3**.
- Result: `AttributeError: module 'numpy' has no attribute 'trapz'` → `test_selective.py::test_risk_coverage_perfect_ranking` fails.
- **Fix**: Replace `np.trapz(risk, coverage)` with `np.trapezoid(risk, coverage)`.

### [HIGH] `scikit-learn`, `numpy`, `pandas` in `[bench]` extras — core scoring broken without them

Unchanged from yesterday.

- `scoring/calibration_metrics.py`, `scoring/recalibrators.py`, `scoring/selective.py` all import these at module or runtime level.
- These modules are called from `scorecard.py` and `calibration.py` — they are core pipeline code, not bench-only.
- Running `pip install -e .` (no extras) leaves 5+ scoring tests failing with `ModuleNotFoundError: No module named 'sklearn'`.
- **Fix**: Move `numpy>=1.26`, `pandas>=2.0`, `scikit-learn>=1.3` from `[bench]` into `[project.dependencies]`.

### [MEDIUM] `cryptography` not declared in `pyproject.toml`

Unchanged from yesterday.

- `markets/kalshi.py` uses RSA-PSS signing which requires `cryptography`.
- Not in `[project.dependencies]`. Fresh installs fail at Kalshi auth.
- **Fix**: Add `cryptography>=42.0` to `[project.dependencies]`.

### [MEDIUM] DuckDB single-writer violations — 3 modules bypass `asyncio.Queue`

Unchanged from prior reports. Direct `conn.execute()` writes risk `database is locked` under concurrent async load:

- `ops/alerts.py:106` — `INSERT INTO ops_events` via `self.db_conn.execute()`
- `budget/tracker.py:43` — `INSERT INTO llm_usage` via `self._db_conn.execute()`
- `cli/brief.py` — `INSERT INTO runs`, `UPDATE runs`, `INSERT INTO market_prices` via bare `conn.execute()`

The `backtest/runner.py` writes use an offline-only connection and are acceptable by design.

### [LOW] Architecture pivot — Phase 1 spec docs are stale

Unchanged. The spec in `docs/superpowers/specs/2026-03-30-parallax-phase1-design.md` describes a geopolitical cascade simulator with ~50 LLM agents, H3 hex visualization, and GDELT BigQuery ingestion. The shipped codebase is a prediction market edge-finder (3 Claude models → Kalshi/Polymarket divergence → paper trades). CLAUDE.md accurately reflects the current architecture; the spec is a historical artifact.

---

## Progress Since Yesterday

- No commits since 2026-10-22. All previously-flagged issues remain open.

---

## Recommendations

1. **Tighten `requires-python`** to `">=3.12,<3.14"` in `pyproject.toml` and ensure CI/cloud environments pin Python 3.12. This unblocks the test suite.
2. **Fix `np.trapz` → `np.trapezoid`** in `scoring/selective.py:106` — one-line fix.
3. **Move `numpy`, `pandas`, `scikit-learn` to core deps** in `pyproject.toml`.
4. **Add `cryptography>=42.0`** to `[project.dependencies]`.
5. **Wrap `ops/alerts.py` and `budget/tracker.py` writes** through `DbWriter.enqueue()`.
