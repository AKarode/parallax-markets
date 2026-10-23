# Parallax Health Check — 2026-10-22

**Status: YELLOW**

Yesterday's 9 test failures in the resolution/report-card scoring path are fully resolved. However, 6 new failures remain in the recalibration and selective-risk modules — driven by a missing `scikit-learn` dependency and a `numpy 2.0` API break (`np.trapz` removed). Three structural issues from prior reports (DuckDB write violations, missing `cryptography`, numpy in wrong extras group) are unchanged.

---

## Summary

| Category | Status | Δ vs Yesterday |
|----------|--------|---------------|
| Test suite | ⚠️ 6 failures, 485 passed | ✅ Improved (was 9 failures) |
| Dependency audit | ⚠️ `cryptography` + `scikit-learn` undeclared | ↔ Same |
| Code quality | ⚠️ numpy 2.0 API break in `selective.py` | 🔴 New |
| DuckDB single-writer | ⚠️ 3 modules violate | ↔ Same |
| Architecture/spec | ⚠️ Spec docs stale (intentional pivot) | ↔ Same |

---

## Issues Found

### [HIGH] `np.trapz` removed in numpy 2.0 — `selective.py:106` breaks

- `scoring/selective.py:106` calls `np.trapz(risk, coverage)`.
- `numpy.trapz` was removed in numpy 2.0. Installed version is **2.5.3**.
- Result: `AttributeError: module 'numpy' has no attribute 'trapz'` → `test_selective.py::test_risk_coverage_perfect_ranking` fails.
- **Fix**: Replace `np.trapz(risk, coverage)` with `np.trapezoid(risk, coverage)` (numpy 2.0+ replacement). One-line change.

### [HIGH] `scikit-learn` not installed — 5 tests fail in `test_recalibrators.py`

- `scoring/recalibrators.py:111` does a lazy `from sklearn.isotonic import IsotonicRegression`.
- `scikit-learn` is declared only in the `[bench]` optional extras group in `pyproject.toml`, not in core deps.
- Running the test suite without installing `[bench]` extras causes `ModuleNotFoundError: No module named 'sklearn'` on 5 tests.
- `recalibrators.py` is a core scoring module (not bench-only), so `scikit-learn` belongs in `[project.dependencies]`.
- **Fix**: Move `scikit-learn>=1.3` from `[bench]` to `[project.dependencies]`.

### [MEDIUM] DuckDB single-writer violations — 3 modules bypass `asyncio.Queue`

Unchanged from prior reports. The spec mandates all writes go through `db/writer.py`'s `asyncio.Queue`. Direct writes risk `database is locked` errors under concurrent async load:

- `ops/alerts.py:108` — `INSERT INTO ops_events` via `self.db_conn.execute()`
- `budget/tracker.py:45` — `INSERT INTO llm_usage` via `self._db_conn.execute()`
- `cli/brief.py:132,151,433` — `INSERT INTO runs` / `UPDATE runs` / `INSERT INTO market_prices` via bare `conn.execute()`

The `backtest/runner.py` writes use a separate offline connection and are acceptable by design.

### [MEDIUM] `cryptography` not declared in `pyproject.toml`

Unchanged. `markets/kalshi.py` uses RSA-PSS signing which requires `cryptography`. It is not in `[project.dependencies]`. A fresh install without this package pre-installed will fail at Kalshi auth.

- **Fix**: Add `cryptography>=42.0` to `[project.dependencies]`.

### [MEDIUM] `numpy`/`pandas`/`scikit-learn` in `[bench]` extras but imported in core scoring

- `scoring/calibration_metrics.py`, `scoring/recalibrators.py`, `scoring/selective.py` all import `numpy` and/or `sklearn` at module level or at runtime.
- These are not bench-only; they are part of the live scoring pipeline (`scorecard.py`, `calibration.py` both call into them).
- **Fix**: Move `numpy>=1.26`, `pandas>=2.0`, `scikit-learn>=1.3` into `[project.dependencies]`.

### [LOW] Architecture pivot — Phase 1 spec docs are stale

Unchanged. `docs/superpowers/specs/2026-03-30-parallax-phase1-design.md` describes a geopolitical cascade simulator with ~50 LLM agents, H3 hex visualization, and GDELT BigQuery ingestion. The shipped codebase is a prediction market edge-finder (3 Claude models → Kalshi/Polymarket divergence → paper trades). CLAUDE.md accurately reflects the current architecture. The spec documents are historical artifacts.

- **Recommendation**: Add a header note to the spec marking it as the original pre-pivot design to prevent future confusion.

---

## Progress Since Yesterday

- ✅ **9 test failures resolved** — `test_resolution.py` (5 failures) and `test_report_card.py` (3 failures) in the resolution/P&L scoring path are all passing today.

---

## Recommendations

1. **Fix `np.trapz` → `np.trapezoid`** in `scoring/selective.py:106` — one-line fix, unblocks `test_selective.py`.
2. **Move `scikit-learn`, `numpy`, `pandas` to core deps** in `pyproject.toml` — these are already runtime dependencies of the scoring pipeline.
3. **Add `cryptography>=42.0`** to `[project.dependencies]` — required for Kalshi RSA-PSS auth.
4. **Wrap `ops/alerts.py` and `budget/tracker.py` writes** through `DbWriter.enqueue()` — low risk today (synchronous CLI path) but needed before any multi-tasking async refactor.
