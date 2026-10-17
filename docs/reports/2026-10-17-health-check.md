# Parallax Health Check — 2026-10-17

**Status: YELLOW**

No code changes in the backend source since 2026-10-08 (tenth consecutive no-change day). All issues from the Oct 16 report carry forward unchanged. The `DbWriter` single-writer abstraction remains bypassed in all production write paths, and three HIGH-severity correctness bugs (`np.trapz`, deconfliction write-back, NULL win-rate crash) are unresolved.

---

## Changes Since Last Report (2026-10-16)

**None.** Only `docs/reports/2026-10-16-tech-research.md` was committed since the last health check. No backend source files modified.

---

## Issues Found

### CRITICAL Severity

- **[ARCH] `DbWriter` bypassed by all production write paths [UNRESOLVED, DAY 9].**
  `db/writer.py` is never instantiated in `main.py` or any production module. All writes go directly via `conn.execute()`:
  - `ops/alerts.py:106`, `budget/tracker.py:43`, `cli/brief.py:130,149,433`
  - `scoring/ledger.py:225,256`, `scoring/tracker.py:460,516,672,711,744`
  - `scoring/prediction_log.py:81`, `scoring/resolution.py:62,126`
  - `contracts/registry.py:106,116,199`, `ingestion/crisis_ingester.py:81`
  Violates the spec's single-writer topology. Under concurrent async writes in the FastAPI process this risks `database is locked` errors.

### HIGH Severity

- **[BUG] `np.trapz` removed in NumPy 2.x — `scoring/selective.py:106` [UNRESOLVED, DAY 6].**
  Raises `AttributeError` on NumPy ≥ 2.0 (env: 2.5.3). Breaks `test_selective.py::test_risk_coverage_perfect_ranking` and the selective-trading AUC calculation in production.
  **Fix (2 lines):** Replace both `np.trapz` calls with `np.trapezoid`.

- **[BUG] Deconfliction write-back never persists to DB — `cli/brief.py:699,714` [UNRESOLVED, DAY 81+].**
  `ledger.record_signal()` inserts signals before `_deconflict_oil_signals()` runs. In-memory `.signal = "HOLD"` mutation is never written back to DuckDB; live trade execution ignores deconfliction entirely.
  **Fix:** Move `_deconflict_oil_signals()` before the `record_signal()` loop, or add an `UPDATE signal_ledger SET signal='HOLD'` after mutation.

- **[BUG] TypeError crash on NULL win-rate — `scoring/ledger.py:283` [UNRESOLVED, DAY 81+].**
  `int(row[1])` raises `TypeError` when `SUM(CASE WHEN model_was_correct ...)` returns NULL (before first resolution cycle).
  **Fix (1 line):** `int(row[1] or 0)`.

- **[DEP] `scikit-learn` not in dev extras — `scoring/recalibrators.py:111,145` [UNRESOLVED, DAY 6].**
  5 tests in `test_recalibrators.py` fail on `pip install -e ".[dev]"` with `ModuleNotFoundError: No module named 'sklearn'`.
  **Fix:** Add `scikit-learn>=1.3` to `[project.optional-dependencies].dev`.

- **[DEP] `streamlit` and `plotly` missing from `pyproject.toml` — `dashboard/app.py:16,17` [UNRESOLVED, DAY 81+].**
  Both imported at module level; absent from all dependency groups.
  **Fix:** Add `dashboard = ["streamlit>=1.36", "plotly>=5.22"]` to optional extras.

### MEDIUM Severity

- **[CONFIG] `PRICE_ELASTICITY` and `INSURANCE_THREAT_MULTIPLIER` hardcoded — `simulation/cascade.py:35,38` [UNRESOLVED, DAY 81+].**
  Both bypass `ScenarioConfig`, making scenario comparisons silently ignore YAML overrides. Spec requires all numeric values come from config.

- **[CONFIG] Validation window dates expired — `portfolio/simulator.py:15,16` [UNRESOLVED, DAY 81+].**
  `VALIDATION_START = date(2026, 4, 1)` / `VALIDATION_END = date(2026, 4, 21)` are 179 days in the past. `days_remaining` always 0.

- **[DEP] `pyproject.toml` requires Python ≥ 3.11 but spec requires ≥ 3.12.**
  Low-impact: no 3.12-only syntax used in current code, but drifts from spec.

- **[DEP] Plan deps missing: `h3>=4.1`, `websockets>=14.0`, `sentence-transformers>=3.4`, `searoute>=1.3`, `shapely>=2.0`, `google-cloud-bigquery>=3.27`.**
  These are absent because the corresponding modules (`agents/`, `spatial/`, `eval/`) were never implemented. Not a blocking issue for the current prediction-market pipeline but reflects the architectural pivot.

- **[ARCH] `DATE()` calls in `scorecard.py` — only compatible with DuckDB ≥ 1.5.x.**
  `pyproject.toml` lower-bounds at `duckdb>=1.2`, but the 16 `DATE()` calls only work in 1.5+. Any deploy on 1.2.x breaks 18 scorecard tests.

### LOW Severity

- **[ARCH] `simulation/engine.py` and `simulation/circuit_breaker.py` absent.**
  `ScenarioConfig` fields `max_escalation_per_tick`, `escalation_cooldown_ticks`, `exogenous_shock_goldstein_threshold` have no consuming code.

- **[ARCH] Nine orphaned schema tables** (`agent_memory`, `agent_prompts`, `decisions`, `world_state_delta`, `predictions`, `curated_events`, `raw_gdelt`, `eval_results`, `simulation_state`) in `db/schema.py` with no corresponding modules. Created at startup, never written to.

---

## Spec / Plan Consistency

The codebase is a stable, intentional architectural pivot from Phase 1's simulation engine to a prediction-market signal pipeline. No regressions in this direction.

| Component | Phase 1 Spec | Current Reality |
|---|---|---|
| LLM layer | 50-agent country/sub-actor swarm | 3 predictors (oil, ceasefire, Hormuz) |
| Frontend | deck.gl + H3 hex map + WebSocket | React + Recharts polling dashboard |
| Data ingestion | GDELT BigQuery (15 min) + ACLED | GDELT DOC API + Google News RSS + Truth Social |
| Eval framework | Per-agent accuracy + prompt versioning | Signal ledger + scorecard + calibration |
| Markets | Not in spec | Kalshi + Polymarket (core addition) |

Absent plan modules: `agents/`, `eval/`, `spatial/`, `simulation/engine.py`, `simulation/circuit_breaker.py`, `ingestion/dedup.py`, `api/` (flat in `main.py`). Frontend spec components absent; `deck.gl`/`maplibre-gl`/`h3-js` installed but unused (~4MB dead weight in `frontend/package.json`).

---

## Test Coverage Gaps

Plan specified 17 test files; actual count is 47. Tests exceed the plan but the following plan-specified files are absent:
- `test_writer.py` — exists ✓ (but writer is never used in production)
- `test_gdelt_filter.py` — absent (replaced by `test_gdelt_doc.py`)
- `test_dedup.py` — absent (semantic dedup module never implemented)
- `test_h3_utils.py` — absent (spatial module never implemented)
- `test_agent_schemas.py`, `test_agent_router.py`, `test_agent_runner.py` — absent (agents module never implemented)
- `test_predictions.py` — exists ✓ (but tests the market-prediction variant, not eval framework variant)
- `test_prompt_versioning.py` — absent (eval module never implemented)
- `test_auth.py` — absent (auth is env-var only, no test)

---

## Trend

| Date | Status | Failed Tests | Code Changes |
|------|--------|-------------|--------------|
| 2026-10-08 | RED | ~21 | Yes (last change) |
| 2026-10-09–15 | YELLOW | ~21 | No |
| 2026-10-16 | YELLOW | 6 | No |
| **2026-10-17** | **YELLOW** | **6 (unchanged)** | **No** |

Test failure count unchanged from yesterday. The improvement from ~21→6 on Oct 16 reflects the DuckDB 1.5.6 environment resolving false `DATE()` failures; actual code bugs are unchanged.

---

## Recommendations (Priority Order)

1. **`selective.py:106` — `np.trapz` → `np.trapezoid`** (2-line fix, restores 1 test, fixes production AUC).
2. **`scoring/ledger.py:283` — `int(row[1] or 0)`** (1-line fix, prevents TypeError crash in live trading).
3. **`cli/brief.py` — move `_deconflict_oil_signals()` before `record_signal()` loop** — highest-impact correctness bug.
4. **Add `scikit-learn>=1.3` to dev extras in `pyproject.toml`** — restores 5 failing recalibrators tests.
5. **Add `duckdb>=1.5` lower-bound to `pyproject.toml`** — makes the `DATE()` compatibility assumption explicit.
6. **Add `dashboard = ["streamlit>=1.36", "plotly>=5.22"]` to optional extras** — prevents import failures.
7. **Wire `DbWriter` into `main.py` lifespan** or remove the dead abstraction and document direct-write as intentional.
8. **Update `VALIDATION_END` in `portfolio/simulator.py`** to current period or make it a config value.
