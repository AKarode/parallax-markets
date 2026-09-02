# Parallax Health Check — 2026-09-02

**Status: YELLOW**

## Summary

No production code changes since yesterday — all recent commits are automated health checks and tech research reports. The existing bugs carry forward unchanged (day 7+ for the DbWriter bypass, day 2+ for the deconfliction write-back). A new active test failure was confirmed today: `scoring/selective.py` uses `np.trapz`, which was removed in NumPy 2.0; the installed environment now runs NumPy 2.4.6, producing an `AttributeError` in `test_selective.py`. Test suite: **6 failed, 445 passed, 13 skipped** (excluding bench extras).

---

## Issues Found

### HIGH — DuckDB Single-Writer Violations (Unaddressed, Day 7+)

`db/writer.py` is correctly implemented but has **zero production call sites**. Every write path executes direct `conn.execute()` calls instead of routing through `DbWriter.enqueue()`. Under concurrent FastAPI async handlers or parallel CLI + API invocations, DuckDB file locking will produce `database is locked` errors.

- **`[HIGH]`** `cli/brief.py` — direct `INSERT`/`UPDATE` in `_persist_run_start`, `_persist_run_end`, `_persist_market_prices`
- **`[HIGH]`** `scoring/ledger.py` — direct `INSERT`/`UPDATE` on every signal record
- **`[HIGH]`** `scoring/tracker.py` — 3 direct writes across paper trade lifecycle
- **`[HIGH]`** `scoring/scorecard.py` — direct `INSERT ON CONFLICT` for daily ETL
- **`[HIGH]`** `scoring/resolution.py` — direct `UPDATE`s during settlement polling
- **`[HIGH]`** `scoring/prediction_log.py` — direct `INSERT` for prediction persistence
- **`[HIGH]`** `contracts/registry.py` — direct `INSERT`/`UPDATE`s for contract upserts
- **`[HIGH]`** `budget/tracker.py` — direct `INSERT` on every LLM call (highest frequency)
- **`[HIGH]`** `ingestion/crisis_ingester.py` — direct `INSERT` during ingestion
- **`[HIGH]`** `ops/alerts.py` — direct `INSERT` for alert logging

### HIGH — Deconfliction Write-Back Bug (Unaddressed, Day 7+)

`cli/brief.py:699` calls `ledger.record_signal()` before `_deconflict_oil_signals()` runs at line 714. The in-memory `.signal = "HOLD"` mutation is never written back to DuckDB. Downstream reads from `ledger.get_signals()` (which re-query the DB) return the pre-deconfliction `BUY_YES`/`BUY_NO` signals, silently double-entering correlated oil contract positions.

**Fix:** Move `_deconflict_oil_signals(all_signals)` to before the `record_signal()` loop, or issue a `UPDATE signal_ledger SET signal = 'HOLD' WHERE signal_id = ?` after mutation.

### HIGH — TypeError Crash on NULL Win-Rate (Unaddressed, Day 7+)

`scoring/ledger.py:283`: `int(row[1])` raises `TypeError` when `model_was_correct` is NULL for all rows (possible before the first resolution cycle when 5+ signals are already recorded).

**Fix:** `int(row[1] or 0)` and `int(row[0] or 0)`.

### MEDIUM — `np.trapz` Removed in NumPy 2.0 — Active Test Failure (NEW)

`scoring/selective.py:106` uses `np.trapz(risk, coverage)`. `np.trapz` was deprecated in NumPy 1.x and **removed in NumPy 2.0**. With the current environment (NumPy 2.4.6), `test_selective.py::test_risk_coverage_perfect_ranking` fails with `AttributeError: module 'numpy' has no attribute 'trapz'`. This is in the main test suite, not the bench extras group.

**Fix:** Replace `np.trapz` with `np.trapezoid` (the NumPy 2.0+ name).

### MEDIUM — `sklearn` / `scikit-learn` Not in `pyproject.toml` — 5 Active Test Failures

`scoring/recalibrators.py:111` does a deferred `from sklearn.isotonic import IsotonicRegression` at runtime. `scikit-learn` is not declared in `pyproject.toml` under any dependency group. With a clean install, all 5 `test_recalibrators.py` tests fail with `ModuleNotFoundError: No module named 'sklearn'`. This is a main-suite module, not bench.

**Fix:** Add `scikit-learn>=1.3` to `[project.dependencies]` or a new `[project.optional-dependencies]` group (`scoring`), and guard the import at module level.

### MEDIUM — `POST /api/brief/run` Hardcodes `dry_run=True` (Unaddressed, Day 7+)

`main.py:252` forces `dry_run=True, no_trade=True` on every API-triggered brief regardless of runtime config. The endpoint cannot initiate a live prediction run from the API.

**Fix:** Accept a `dry_run` query parameter, or add a comment explaining intentional sandboxing.

### MEDIUM — `streamlit` / `plotly` Missing from `pyproject.toml` (Unaddressed, Day 7+)

`dashboard/app.py` imports both at module level but neither is declared in any `pyproject.toml` dependency group. A fresh `pip install -e .` will fail on any import path touching `dashboard/app.py`.

**Fix:** Add `dashboard = ["streamlit>=1.36", "plotly>=5.22"]` to `[project.optional-dependencies]`.

### MEDIUM — `PRICE_ELASTICITY` and `INSURANCE_THREAT_MULTIPLIER` Hardcoded in `simulation/cascade.py` (Unaddressed)

Both constants bypass `ScenarioConfig`, which was explicitly designed to hold all tunable parameters. Scenario sensitivity analysis will silently ignore YAML overrides.

**Fix:** Add fields to `ScenarioConfig` / `scenario_hormuz.yaml` and pass through `CascadeEngine.__init__`.

### LOW — `portfolio/` Missing `__init__.py` (Unaddressed)

`backend/src/parallax/portfolio/` has no `__init__.py`. Works with `src/` layout but is inconsistent with every other package.

### LOW — `np.trapz` Comment Mentions Deprecated Behavior as a Feature

`scoring/selective.py:101` says "`np.trapz would collapse it to a misleading 0.0`" — this comment implies the code intentionally relies on a deprecated API behavior. Once `np.trapz` is replaced with `np.trapezoid` the comment should be updated accordingly.

### LOW — Schema Migration UPDATEs Run Unconditionally on Every Startup

`db/schema.py`'s `_migrate_legacy_tables()` runs data-backfill `UPDATE` statements on every `create_tables()` call. No `schema_version` guard means repeated no-op writes at scale.

### LOW — Private `KalshiClient._request()` Called from `cli/brief.py`

Direct call to a private method risks silent breaks if the internal signature changes.

---

## Test Suite Results (2026-09-02)

| Category | Count |
|---|---|
| Passed | 445 |
| Failed | 6 |
| Skipped | 13 |
| Collection errors | 2 (bench: `pandas`, `numpy` not installed in `[dev]`) |

**Failing tests:**
- `test_recalibrators.py` — 5 failures (`sklearn` not installed)
- `test_selective.py::test_risk_coverage_perfect_ranking` — `AttributeError: module 'numpy' has no attribute 'trapz'` (**newly surfaced with NumPy 2.x**)

---

## Spec / Plan Consistency

Architecture remains intentionally pivoted from the Phase 1 spec. Spec documents are stale but the actual product is internally coherent. No regressions to report.

| Spec Component | Status |
|---|---|
| `agents/` — 50-agent LLM swarm (country → sub-actor hierarchy) | Not built; replaced by 3 focused prediction models |
| `spatial/` — H3 hexagonal grid + Searoute | Not built |
| Frontend H3 hex map (deck.gl + MapLibre GL) | Not built; Recharts polling dashboard used |
| WebSocket streaming | Not built; polling used |
| `eval/` — GDELT semantic dedup + prediction eval pipeline | Not built; replaced by `scoring/` subsystem |
| `ingestion/dedup.py` — sentence-transformers semantic dedup | Not built |
| Prediction market trading layer (Kalshi + Polymarket) | **Added** — not in spec, core value-add |

---

## Recommendations

**Priority 1 — Fix active test failures this session:**
1. Replace `np.trapz` with `np.trapezoid` in `scoring/selective.py:106` — one-line fix, unblocks the test immediately.
2. Add `scikit-learn>=1.3` to `pyproject.toml` — unblocks 5 recalibrator tests.

**Priority 2 — Correctness bugs affecting live trading:**
3. Fix deconfliction write-back (`cli/brief.py`): move `_deconflict_oil_signals()` before `record_signal()` loop, or issue DB `UPDATE` after mutation.
4. Fix TypeError in win-rate computation (`scoring/ledger.py:283`): `int(row[1] or 0)`.
5. Fix `update_execution()` COALESCE: `CASE WHEN ? IS NOT NULL THEN ? ELSE trade_id END`.

**Priority 3 — Infrastructure debt:**
6. Route all writes through `DbWriter.enqueue()` — the single-writer contract is a core architecture requirement (spec §9) and is violated across 10 modules.
7. Add `streamlit`/`plotly` to optional deps in `pyproject.toml`.
8. Add `portfolio/__init__.py`.
9. Move `PRICE_ELASTICITY` and `INSURANCE_THREAT_MULTIPLIER` into `ScenarioConfig`.
