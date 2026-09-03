# Parallax Health Check — 2026-09-03

**Status: YELLOW**

## Summary

No production code changes since the previous check — all commits since 2026-09-02 are automated health and research reports. All known bugs carry forward unchanged (DbWriter bypass violations for 8+ days, deconfliction write-back bug, TypeError on NULL win-rate). Test suite: **433 passed, 13 skipped** from the main suite; 3 test files fail at collection due to `numpy` not installed in the current environment (`test_recalibrators.py`, `test_selective.py`, `test_calibration_metrics.py`) and 1 additional bench file similarly fails.

---

## Issues Found

### HIGH — DuckDB Single-Writer Violations (Unaddressed, Day 8+)

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

### HIGH — Deconfliction Write-Back Bug (Unaddressed, Day 8+)

`cli/brief.py:699` calls `ledger.record_signal()` before `_deconflict_oil_signals()` runs at line 714. The in-memory `.signal = "HOLD"` mutation is never written back to DuckDB. Downstream reads from `ledger.get_signals()` (which re-query the DB) return the pre-deconfliction `BUY_YES`/`BUY_NO` signals, silently double-entering correlated oil contract positions.

**Fix:** Move `_deconflict_oil_signals(all_signals)` before the `record_signal()` loop, or issue `UPDATE signal_ledger SET signal = 'HOLD' WHERE signal_id = ?` after mutation.

### HIGH — TypeError Crash on NULL Win-Rate (Unaddressed, Day 8+)

`scoring/ledger.py:283`: `int(row[1])` raises `TypeError` when `model_was_correct` is NULL for all rows (possible before the first resolution cycle when 5+ signals are already recorded).

**Fix:** `int(row[1] or 0)` and `int(row[0] or 0)`.

### MEDIUM — numpy Not Installed — 3+ Active Test Collection Failures (Worsened)

`numpy` is not available in the current environment (`ModuleNotFoundError: No module named 'numpy'`), causing collection failures for `test_recalibrators.py`, `test_selective.py`, `test_calibration_metrics.py`, and `test_bench_forecast.py`. Yesterday these ran but failed at test execution; today they fail at import, suggesting an environment regression (numpy may have been uninstalled or a clean env was used). This masks the `np.trapz` → `np.trapezoid` bug inside `selective.py` since the file can't even be imported.

**Fix:** Ensure `numpy` is in `[dev]` dependencies in `pyproject.toml`. Also replace `np.trapz` with `np.trapezoid` (NumPy 2.0+) and add `scikit-learn>=1.3` to deps.

### MEDIUM — `np.trapz` Removed in NumPy 2.0 (Unaddressed)

`scoring/selective.py:106` uses `np.trapz(risk, coverage)`. This was removed in NumPy 2.0. When numpy is available and ≥2.0, this produces `AttributeError`.

**Fix:** Replace `np.trapz` with `np.trapezoid`.

### MEDIUM — `sklearn` / `scikit-learn` Not in `pyproject.toml` (Unaddressed)

`scoring/recalibrators.py:111` does a deferred `from sklearn.isotonic import IsotonicRegression`. `scikit-learn` is not declared in `pyproject.toml`. Clean installs fail with `ModuleNotFoundError`.

**Fix:** Add `scikit-learn>=1.3` to `[project.dependencies]` or a new optional group.

### MEDIUM — `POST /api/brief/run` Hardcodes `dry_run=True` (Unaddressed, Day 8+)

`main.py:252` forces `dry_run=True, no_trade=True` on every API-triggered brief. The endpoint cannot initiate a live prediction run from the API.

**Fix:** Accept a `dry_run` query parameter, or add a comment explaining intentional sandboxing.

### MEDIUM — `streamlit` / `plotly` Missing from `pyproject.toml` (Unaddressed, Day 8+)

`dashboard/app.py` imports both at module level but neither is declared in any dependency group.

**Fix:** Add `dashboard = ["streamlit>=1.36", "plotly>=5.22"]` to `[project.optional-dependencies]`.

### MEDIUM — `PRICE_ELASTICITY` and `INSURANCE_THREAT_MULTIPLIER` Hardcoded in `simulation/cascade.py`

Both constants bypass `ScenarioConfig`. Scenario sensitivity analysis silently ignores YAML overrides.

**Fix:** Add fields to `ScenarioConfig` / `scenario_hormuz.yaml` and pass through `CascadeEngine.__init__`.

### LOW — `portfolio/` Missing `__init__.py`

`backend/src/parallax/portfolio/` has no `__init__.py`. Works with `src/` layout but inconsistent with every other package.

### LOW — Schema Migration UPDATEs Run Unconditionally on Every Startup

`db/schema.py`'s `_migrate_legacy_tables()` runs data-backfill `UPDATE` statements on every `create_tables()` call. No `schema_version` guard means repeated no-op writes at scale.

### LOW — Private `KalshiClient._request()` Called from `cli/brief.py`

Direct call to a private method risks silent breaks if the internal signature changes.

---

## Test Suite Results (2026-09-03)

| Category | Count |
|---|---|
| Passed | 433 |
| Failed | 0 (in runnable subset) |
| Skipped | 13 |
| Collection errors | 4 (`numpy` not installed: `test_recalibrators.py`, `test_selective.py`, `test_calibration_metrics.py`, `test_bench_forecast.py`) |

**Note:** Yesterday's 6 failures (5 sklearn + 1 np.trapz) are now collection errors because numpy itself is missing from the environment. The underlying bugs remain.

---

## Spec / Plan Consistency

Architecture remains intentionally pivoted from the Phase 1 spec. No new regressions.

| Spec Component | Status |
|---|---|
| `agents/` — 50-agent LLM swarm | Not built; replaced by 3 focused prediction models |
| `spatial/` — H3 hexagonal grid + Searoute | Not built |
| Frontend H3 hex map (deck.gl + MapLibre GL) | Not built; Recharts polling dashboard used |
| WebSocket streaming | Not built; polling used |
| `eval/` — GDELT semantic dedup + prediction eval | Not built; replaced by `scoring/` subsystem |
| `ingestion/dedup.py` — sentence-transformers semantic dedup | Not built |
| Prediction market trading layer | **Added** — not in spec, core value-add |

---

## Recommendations

**Priority 1 — Restore test suite visibility (environment fix):**
1. Add `numpy>=1.26`, `scikit-learn>=1.3` to `[project.optional-dependencies.dev]` in `pyproject.toml` so clean install restores all test modules.
2. Replace `np.trapz` with `np.trapezoid` in `scoring/selective.py:106` — one-line fix.

**Priority 2 — Correctness bugs affecting live trading:**
3. Fix deconfliction write-back (`cli/brief.py`): move `_deconflict_oil_signals()` before `record_signal()` loop.
4. Fix TypeError in win-rate computation (`scoring/ledger.py:283`): `int(row[1] or 0)`.

**Priority 3 — Infrastructure debt:**
5. Route all writes through `DbWriter.enqueue()` — the single-writer contract is a core architecture requirement (spec §9) and is violated across 10 modules.
6. Add `streamlit`/`plotly` to optional deps in `pyproject.toml`.
7. Add `portfolio/__init__.py`.
8. Move `PRICE_ELASTICITY` and `INSURANCE_THREAT_MULTIPLIER` into `ScenarioConfig`.
