# Parallax Health Check — 2026-10-16

**Status: YELLOW**

Test failures dropped from 21 (Oct 15 estimate) to 6 confirmed today — the CRITICAL `DATE()` DuckDB incompatibility and BacktestRunner regression are not manifesting with DuckDB 1.5.6 installed in this environment. Two actionable quick fixes remain (numpy `trapz` removal, `sklearn` missing from dev extras), and three HIGH-severity correctness bugs persist unresolved since July. No code changes since 2026-10-08 (nine consecutive days).

---

## Test Run (2026-10-16)

| Result | Count |
|--------|-------|
| Passed | 485 |
| Failed | **6** |
| Skipped | 13 |

*Run with Python 3.13 + DuckDB 1.5.6 installed at system level.*

---

## Issues Found

### HIGH Severity

- **[BUG] `np.trapz` removed in NumPy 2.x — `scoring/selective.py:106` [UNRESOLVED, DAY 5].**
  `np.trapz(risk, coverage)` raises `AttributeError: module 'numpy' has no attribute 'trapz'` on NumPy ≥ 2.0 (installed: 2.5.3). Breaks `test_selective.py::test_risk_coverage_perfect_ranking` and the selective-trading AUC calculation in production.
  **Fix (2 lines):** Replace both `np.trapz` calls in `selective.py` with `np.trapezoid`.

- **[BUG] Deconfliction write-back never persists to DB — `cli/brief.py:699,714` [UNRESOLVED, DAY 80+].**
  `ledger.record_signal()` at line 699 inserts signals into DuckDB _before_ `_deconflict_oil_signals()` runs at line 714. The in-memory `.signal = "HOLD"` mutation is never written back. Downstream reads via `ledger.get_signals()` re-query DuckDB and return original `BUY_YES`/`BUY_NO` signals, bypassing deconfliction entirely. Paper trade positions may double-enter correlated oil contracts.
  **Fix:** Move `_deconflict_oil_signals()` call before the `record_signal()` loop, or issue `UPDATE signal_ledger SET signal='HOLD' WHERE signal_id=?` after mutation.

- **[BUG] TypeError crash on NULL win-rate — `scoring/ledger.py:283` [UNRESOLVED, DAY 80+].**
  `int(row[1])` raises `TypeError` when `SUM(CASE WHEN model_was_correct ...)` returns NULL (all rows have NULL `model_was_correct`, possible before first resolution cycle). The `int(row[0]) >= 5` guard only short-circuits when count < 5, not when wins is NULL.
  **Fix (1 line):** Change `int(row[1])` to `int(row[1] or 0)`.

- **[DEP] `sklearn` not in core or dev extras — `scoring/recalibrators.py:111,145` [UNRESOLVED, DAY 5].**
  `IsotonicRecalibrator.fit()` and `PlattRecalibrator.fit()` do lazy `from sklearn.*` imports. `scikit-learn` is only in `[bench]` optional group. Default `pip install -e ".[dev]"` leaves tests without it; 5 tests in `test_recalibrators.py` fail with `ModuleNotFoundError`.
  **Fix:** Add `scikit-learn>=1.3` to `[project.optional-dependencies].dev`, or add graceful `ImportError` guard with descriptive message.

- **[CRITICAL-DESIGN] `DbWriter` is defined but bypassed by all production write paths [UNRESOLVED, DAY 8].**
  The spec mandates all writes go through `asyncio.Queue → db_writer`. The `DbWriter` class in `db/writer.py` is never instantiated in `main.py`. All production modules write directly via `conn.execute()`:
  - `ops/alerts.py:106`, `budget/tracker.py:43`, `cli/brief.py:130,149,433`
  - `scoring/ledger.py:225,256`, `scoring/tracker.py:460,516,674,713,746`
  - `scoring/prediction_log.py:81`, `scoring/resolution.py:62,126`
  - `contracts/registry.py:106,116,199`, `ingestion/crisis_ingester.py:81`
  Under concurrent async writes in the FastAPI process, this risks `database is locked` errors (DuckDB single-writer constraint). `ops/alerts.py` and `budget/tracker.py` fire from the async request path.

- **[DEP] `streamlit` and `plotly` missing from `pyproject.toml` — `dashboard/app.py:16,17` [UNRESOLVED, DAY 80+].**
  Both imported at module level; absent from all dependency groups. Fresh install produces `ModuleNotFoundError` on any import path touching `dashboard/app.py`.
  **Fix:** Add `dashboard = ["streamlit>=1.36", "plotly>=5.22"]` to `[project.optional-dependencies]`.

### MEDIUM Severity

- **[CONFIG] `PRICE_ELASTICITY` and `INSURANCE_THREAT_MULTIPLIER` hardcoded — `simulation/cascade.py:35,38` [UNRESOLVED, DAY 80+].**
  Both bypass `ScenarioConfig`, making scenario comparisons silently ignore YAML overrides.

- **[CONFIG] Validation window dates expired — `portfolio/simulator.py:15,16` [UNRESOLVED, DAY 80+].**
  `VALIDATION_START = date(2026, 4, 1)` / `VALIDATION_END = date(2026, 4, 21)` are 177 days in the past. `days_remaining` always 0; the metric is stale in scorecard output.

- **[ARCH] `DATE()` calls in `scorecard.py` — compatible with DuckDB 1.5.6 but NOT 1.2.x [NOT MANIFESTING TODAY].**
  16 occurrences of `DATE(col)` exist. These pass in the current environment (DuckDB 1.5.6 accepts `DATE()` as a function). Any deployment on DuckDB 1.2.x — which the `pyproject.toml` lower-bounds allow — will break 18 scorecard tests. Consider adding `duckdb>=1.5` to `pyproject.toml` or migrating to `CAST(col AS DATE)`.

### LOW Severity

- **[ARCH] `simulation/engine.py` and `simulation/circuit_breaker.py` absent.**
  `ScenarioConfig` fields `max_escalation_per_tick`, `escalation_cooldown_ticks`, `exogenous_shock_goldstein_threshold` configure a circuit breaker that doesn't exist.

- **[ARCH] Orphaned schema tables** (`agent_memory`, `agent_prompts`, `decisions`, `world_state_delta`, `predictions`, `curated_events`, `raw_gdelt`, `eval_results`, `simulation_state`) exist in `db/schema.py` with no corresponding modules.

---

## Spec / Plan Consistency (unchanged)

The codebase is a stable, intentional pivot from the Phase 1 spec's simulation engine to a prediction-market signal pipeline. No regression in this direction — it is a known architectural divergence.

| Component | Phase 1 Spec | Current Reality |
|---|---|---|
| LLM layer | 50-agent country/sub-actor swarm | 3 predictors (oil, ceasefire, Hormuz) |
| Frontend | deck.gl + H3 hex map + WebSocket | React + Recharts polling dashboard |
| Data ingestion | GDELT BigQuery (15 min) + ACLED | GDELT DOC API + Google News RSS + Truth Social |
| Eval framework | Per-agent accuracy + prompt versioning | Signal ledger + scorecard + calibration |
| Markets | Not in spec | Kalshi + Polymarket (core addition) |

Absent modules: `agents/`, `eval/`, `spatial/`, `simulation/engine.py`, `simulation/circuit_breaker.py`, `ingestion/dedup.py`, `api/` (flat in `main.py`). Frontend spec components (HexMap, AgentFeed, Timeline, etc.) are absent; `deck.gl` / `maplibre-gl` / `h3-js` are installed but unused (~4MB dead weight).

---

## Trend

| Date | Status | Failed Tests | Code Changes |
|------|--------|-------------|--------------|
| 2026-10-08 | RED | ~21 | No |
| 2026-10-09–14 | YELLOW | ~21 | No |
| 2026-10-15 | YELLOW | ~21 (est.) | No |
| **2026-10-16** | **YELLOW** | **6** | **No** |

Test failure drop (21→6) reflects environment having DuckDB 1.5.6 and tests running for the first time since Oct 13. The `DATE()` and BacktestRunner issues did not manifest in this environment. Underlying code bugs are unchanged.

---

## Recommendations (Priority Order)

1. **`selective.py:106` — `np.trapz` → `np.trapezoid`** (2-line fix, restores 1 test, fixes production AUC).
2. **`scoring/ledger.py:283` — `int(row[1] or 0)`** (1-line fix, prevents TypeError crash in live trading).
3. **`cli/brief.py` — move `_deconflict_oil_signals()` before `record_signal()` loop** — highest-impact correctness bug for live trading accuracy.
4. **Add `scikit-learn>=1.3` to dev extras in `pyproject.toml`** — restores 5 failing tests.
5. **Add `duckdb>=1.5` lower-bound to `pyproject.toml`** — makes the `DATE()` compatibility assumption explicit.
6. **Add `dashboard = ["streamlit>=1.36", "plotly>=5.22"]` to optional extras** — prevents import failures.
7. **Wire `DbWriter` into `main.py` lifespan** or document the current direct-write architecture as intentional and remove the dead abstraction.
8. **Update `VALIDATION_END` in `portfolio/simulator.py`** to current period (or make it a config value).
