# Parallax Health Check — 2026-07-10

**Status: YELLOW**

No code was committed since the 2026-07-09 check — only yesterday's tech research scout landed. All three HIGH-severity bugs are now 8+ consecutive days unresolved. The test suite is unchanged at 433 pass / 13 skip / 4 collection errors. No regressions introduced; no bugs fixed.

---

## Summary

The project remains in steady-state maintenance with no forward movement on known defects. The prediction market signal pipeline is functional and heavily tested. The three HIGH-severity bugs (deconfliction write-back, TypeError on NULL win-rate, missing streamlit/plotly deps) have accumulated for over a week and now represent genuine technical debt that risks silently corrupting live signal records and crashing the dashboard. The 2026-04-01–21 validation window expired 80 days ago; the days-remaining metric in the scorecard has been permanently zero since April 21.

---

## Issues Found

### HIGH Severity — Carry-Over (Unresolved 8+ Days)

- **[BUG] Deconfliction mutates in-memory objects after DB write** (`cli/brief.py:699,714`)
  `ledger.record_signal()` persists all signals to DuckDB at line 699, then `_deconflict_oil_signals()` runs at line 714 and mutates in-memory `.signal = "HOLD"`. The mutation never propagates back to the DB. Downstream reads via `ledger.get_signals()` re-query DuckDB and return the original `BUY_YES`/`BUY_NO`, silently bypassing deconfliction. Double entry of correlated oil positions is the likely consequence.
  **Fix:** Move `_deconflict_oil_signals()` to run *before* the `record_signal()` loop, or follow the loop with `UPDATE signal_ledger SET signal = 'HOLD' WHERE signal_id = ?` for each suppressed signal.

- **[BUG] TypeError crash on NULL win-rate** (`scoring/ledger.py:283`)
  `_compute_suggested_size()` calls `int(row[1])` on a SUM that returns NULL when `model_was_correct` is NULL for all rows in `signal_quality_evaluation`. The guard `int(row[0]) >= 5` only protects when count < 5; once count reaches 5 with all-NULL correctness values, `int(None)` raises `TypeError`. Likely to fire on the first run after resolution data clears.
  **Fix:** Change `int(row[1])` to `int(row[1] or 0)` and similarly guard `int(row[0] or 0)`.

- **[DEP] `streamlit` and `plotly` not in `pyproject.toml`** (`dashboard/app.py:16–17`)
  Both are imported at module level. `pip install -e .` on a clean environment produces `ModuleNotFoundError` for any code path touching `dashboard/app.py`.
  **Fix:** Add `[project.optional-dependencies] dashboard = ["streamlit>=1.36", "plotly>=5.22"]`.

### MEDIUM Severity — Carry-Over

- **[PERF] New `httpx.AsyncClient` per Kalshi request** (`markets/kalshi.py:154`)
  A fresh TCP+TLS connection is opened for each market fetch. A standard brief run fetches 12+ tickers (~12 handshakes). Use a persistent client initialized in `__init__` and closed via FastAPI lifespan.

- **[BUG] `update_execution()` trade_id/position_id never update** (`scoring/ledger.py:259`)
  `COALESCE(?, trade_id)` with `None` as first arg always resolves to the existing value. These fields are effectively write-once. Resolution and P&L tracking may be broken for positions that need FK correction post-insert.
  **Fix:** Use `CASE WHEN ? IS NOT NULL THEN ? ELSE trade_id END` pattern.

- **[CONFIG] `PRICE_ELASTICITY` and `INSURANCE_THREAT_MULTIPLIER` hardcoded** (`simulation/cascade.py:35–36`)
  Both bypass `ScenarioConfig` and ignore YAML overrides. Sensitivity analysis silently uses hardcoded values.

- **[CONFIG] Validation window expired 80 days ago** (`portfolio/simulator.py:15–16`)
  `VALIDATION_END = date(2026, 4, 21)` — `days_remaining` has been 0 since April 21. This metric is misleading in scorecard output.

### LOW Severity — Carry-Over

- **[SMELL] `crisis_events.headline_hash` NOT NULL enforced by comment only** (`db/schema.py:491`)
  Declare `NOT NULL` in DDL rather than relying on application-side invariant documented in a comment.

- **[SMELL] LLM pricing hardcoded in budget tracker** (`budget/tracker.py:11–14`)
  Static dict does not reflect current Haiku 4.5 / Sonnet 5 pricing changes. Silent miscounting of the $20/day cap.

- **[SMELL] Monkey-patch pattern in backtest engine** (`backtest/engine.py:187–226`)
  Module-level function patched in an async for-loop with a `finally` restore. An exception bypassing `finally` permanently corrupts the module state. Use dependency injection or a context manager instead.

---

## New from Yesterday's Tech Research

Yesterday's tech research scout (2026-07-09) identified three high-ROI opportunities worth tracking:

- **Claude Structured Outputs (GA):** Replaces manual JSON parsing + retry logic in agent calls. Estimated 5-10% throughput improvement, LOW effort. Immediately applicable to `prediction/` module LLM calls.
- **AIS Vessel Tracking:** Direct Hormuz shipping observation via Datalastic/AISstream.io. Validates model without waiting for downstream oil price signal. MEDIUM effort, $100–500/month.
- **DuckDB 1.5 + Parquet:** CRS support in core + Parquet for historical deltas reduces scorecard compute time. Defer to after Phase 1 stabilizes.

---

## Spec / Plan Consistency

No changes since 2026-07-09. The 50-agent swarm, H3 spatial simulation, DES engine, circuit breaker, and eval framework remain unbuilt. The current codebase is a stable, intentional pivot to a 3-model prediction market signal engine.

| Component | Phase 1 Plan | Current Reality |
|---|---|---|
| LLM layer | 50-agent country/sub-actor swarm | 3 predictors (oil, ceasefire, Hormuz) |
| Frontend | deck.gl + MapLibre H3 hex map + WebSocket | React + Recharts polling dashboard |
| Data ingestion | GDELT BigQuery (15 min) + ACLED | GDELT DOC API + Google News RSS + Truth Social |
| Eval framework | Per-agent accuracy + prompt versioning | Signal ledger + scorecard + calibration |
| Markets | Not in spec | Kalshi + Polymarket (core addition) |

**Modules absent (never built, not regressed):**
`agents/`, `eval/`, `spatial/`, `simulation/engine.py`, `simulation/circuit_breaker.py`, `ingestion/dedup.py`, `api/` (routes live in `main.py`)

---

## Test Coverage

- **433 passed, 13 skipped** (unchanged from 2026-07-09)
- **4 collection errors** (`test_bench_forecast.py`, `test_calibration_metrics.py`, `test_recalibrators.py`, `test_selective.py`) — missing `bench` optional deps (pandas, numpy, scikit-learn, matplotlib). Not installed in dev environment. Install with `pip install -e ".[bench]"` to collect these tests.
- No test coverage for the deconfliction write-back path in `cli/brief.py`.

---

## Recommendations

**Priority 1 — Fix this week (correctness risk):**
1. **Deconfliction write-back** (`cli/brief.py`): Move `_deconflict_oil_signals()` before `record_signal()` loop or add `UPDATE` after mutation. Highest-impact correctness bug.
2. **TypeError in win-rate** (`scoring/ledger.py:283`): `int(row[1] or 0)` — one-line fix.
3. **Missing dashboard deps** (`pyproject.toml`): Add `streamlit`/`plotly` to optional group — one-line fix.

**Priority 2 — This sprint:**
4. Reuse `httpx.AsyncClient` in `KalshiClient` — reduce per-brief latency.
5. Fix `update_execution()` COALESCE bug (`scoring/ledger.py:259`) — needed for accurate P&L tracking.
6. Update validation window in `portfolio/simulator.py` to current period (or remove if analysis window is closed).
7. Implement Claude Structured Outputs in prediction model calls — LOW effort, HIGH value per yesterday's research.

**Priority 3 — Backlog:**
8. Move `PRICE_ELASTICITY` into `scenario_hormuz.yaml` / `ScenarioConfig`.
9. Declare `crisis_events` columns NOT NULL in schema DDL.
10. Evaluate AIS vessel tracking integration (Datalastic/AISstream.io) for Phase 1b.
