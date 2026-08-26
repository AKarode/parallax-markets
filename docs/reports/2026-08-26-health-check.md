# Parallax Health Check — 2026-08-26

**Status: YELLOW**

## Summary

No source code changes landed since the 2026-08-25 check — the two commits since then are documentation only (tech research report, prior health check). All previously-flagged HIGH and MEDIUM issues remain open. A new issue surfaced: four test files fail to collect due to missing `numpy`/`pandas` in the CI/dev environment despite both being declared in `pyproject.toml`, silently suppressing 48 tests.

---

## Changes Since Yesterday

| Area | Change |
|---|---|
| Source code | **None** — zero commits touching `src/` or `tests/` |
| Documentation | Tech research report (DuckDB 1.5, Batch API, PMXT) added |
| Open issues from 2026-08-25 | **All unresolved** |

---

## Issues Found

### [HIGH] Connection leak in `run_brief()` — no try/finally (carry-over)

- `cli/brief.py:535`: `conn = duckdb.connect(runtime.db_path)` is opened with no `try/finally`. Any exception in the 200+ lines before `conn.close()` at line 778 leaves the file handle open.
- Subsequent scheduled runs will see `database is locked` until the process exits.
- **Still unresolved from 2026-08-25.**

### [HIGH] DuckDB single-writer pattern not enforced (carry-over)

- `db/writer.py` implements the asyncio.Queue correctly, but `enqueue()` is never called anywhere in production code.
- All writes bypass the queue via direct `conn.execute()` in: `cli/brief.py`, `scoring/ledger.py`, `scoring/prediction_log.py`, `scoring/tracker.py`, `scoring/scorecard.py`, `scoring/resolution.py`, `ops/alerts.py`, `budget/tracker.py`, `contracts/registry.py`, `ingestion/crisis_ingester.py`, `backtest/runner.py`.
- Risk is low today (single-process CLI) but will cause `database is locked` crashes as soon as FastAPI background tasks run concurrently.
- **Still unresolved from 2026-08-25.**

### [HIGH] 4 test files fail to collect — `numpy`/`pandas` not installed

- **New issue.** `test_bench_forecast.py`, `test_calibration_metrics.py`, `test_recalibrators.py`, `test_selective.py` all fail at import with `ModuleNotFoundError`.
- Both `numpy>=1.26` and `pandas>=2.0` are declared in `pyproject.toml` but are absent from the installed environment.
- 48 tests (8 + 22 + 9 + 9) are silently suppressed — the main suite reports 433 passed / 13 skipped but this gap is invisible without the collection-error output.
- Affected production modules: `scoring/recalibrators.py`, `scoring/calibration_metrics.py`, `scoring/selective.py`, `bench/forecast.py`, `bench/kalshibench.py`, `cli/kalshibench.py`.
- **Fix:** `pip install numpy pandas` (or confirm the install step runs `pip install -e ".[dev]"` before tests).

### [MEDIUM] No indexes on any DuckDB tables (carry-over)

- `db/schema.py` defines 20+ tables — including high-frequency append tables (`signal_ledger`, `prediction_log`, `market_prices`) — with zero `CREATE INDEX` statements.
- Hot query columns (`run_id`, `model_id`, `created_at`, `contract_ticker`) are all unindexed.
- **Still unresolved from 2026-08-25.**

### [MEDIUM] `_migrate_legacy_tables()` runs on every startup without a version guard (carry-over)

- `db/schema.py:528` is called unconditionally on every `create_tables()` invocation (every `run_brief()` call). Executes bulk `UPDATE` statements against `signal_ledger` each time.
- Should be guarded by a `schema_version` check and skipped once applied.
- **Still unresolved from 2026-08-25.**

### [LOW] Per-row market price inserts without transaction (carry-over)

- `cli/brief.py`: Market prices inserted one-by-one in a `for` loop, each its own implicit transaction. Should be `executemany` or wrapped in `BEGIN`/`COMMIT`.
- **Still unresolved from 2026-08-25.**

### [LOW] `CURRENT_DATE` without timezone in portfolio query (carry-over)

- `cli/brief.py`: `WHERE closed_at >= CURRENT_DATE` compares against the host's local date — silently includes/excludes records near midnight depending on the execution environment.
- **Still unresolved from 2026-08-25.**

### [LOW] `db/queries.py` absent (carry-over)

- Plan specifies a central read-only query layer. Query logic remains scattered across `dashboard/data.py`, `scoring/calibration.py`, and `cli/brief.py`.
- **Still unresolved from 2026-08-25.**

---

## Test Suite Status

| Scope | Count |
|---|---|
| Tests passing | 433 |
| Tests skipped | 13 |
| Test files with collection errors (numpy/pandas missing) | 4 |
| Tests suppressed by collection errors | ~48 |

---

## Architecture Drift (unchanged)

The project has pivoted from the original Phase 1 spec (H3 hex simulator + 50-agent swarm) to a prediction-market edge-finder. All plan-expected modules (`agents/`, `spatial/`, `eval/`) remain absent. The pivot modules (`markets/`, `prediction/`, `divergence/`, `scoring/`, `contracts/`, `portfolio/`) are well-tested and match the CLAUDE.md description. The original spec/plan docs still describe the old product without a pivot notice.

---

## Recommendations

1. **Fix the connection leak** (HIGH, 30 min): Wrap `run_brief()` body in `try/finally: conn.close()`. Single highest-impact quick fix — this is a latent scheduler-killer.

2. **Fix the missing numpy/pandas in dev environment** (HIGH, 5 min): Run `pip install numpy pandas` in the dev/CI environment, or verify the `pip install -e ".[dev]"` step is executing before the test runner. Restores 48 suppressed tests.

3. **Add DuckDB indexes** (MEDIUM, 1 hr): `CREATE INDEX` on `signal_ledger(run_id, created_at)`, `prediction_log(run_id, model_id)`, `market_prices(contract_ticker, fetched_at)`.

4. **Guard migrations with a version check** (MEDIUM, 1 hr): Add a `schema_version` key to `simulation_state` table. Run `_migrate_legacy_tables()` only when the stored version is below the current version, then bump it.

5. **Wire DbWriter or delete it** (MEDIUM, 2-4 hrs): Either route all writes through the `enqueue()` queue, or remove `db/writer.py` and document that the system is single-process CLI-safe.

6. **Archive or annotate the original spec/plan docs** (INFO, 15 min): Add a pivot notice to `docs/superpowers/specs/2026-03-30-parallax-phase1-design.md` and `docs/superpowers/plans/2026-03-30-parallax-phase1.md` pointing to CLAUDE.md as the authoritative description of what was built.
