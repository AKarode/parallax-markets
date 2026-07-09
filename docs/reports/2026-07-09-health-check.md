# Parallax Health Check — 2026-07-09

**Status: YELLOW**

The core trading pipeline is functional and test coverage is broad (47 files), but the same three HIGH-severity bugs flagged on 2026-07-08 remain unresolved after zero code commits today. The project has been continuously YELLOW for at least 7 consecutive days. No regressions introduced; no bugs fixed.

---

## Summary

No code was committed to `main` since the 2026-07-08 health check — only documentation and the daily tech research scout landed. The three HIGH-severity defects (deconfliction DB/memory split, TypeError on NULL win-rate, missing dashboard dependencies) persist unchanged. At 7+ days unresolved these are no longer "newly discovered bugs" — they are technical debt requiring prioritized attention. The project has stabilized architecturally: the 50-agent simulation vision remains unbuilt while the prediction-market signal engine is coherent and heavily tested.

---

## Issues Found

### HIGH Severity — Carry-Over (Unresolved 2+ Days)

- **[BUG] Deconfliction mutates in-memory objects after DB write** (`cli/brief.py:491,714`)
  `ledger.record_signal()` persists signals at line 699 _before_ `_deconflict_oil_signals()` runs at line 714. The in-memory `.signal = "HOLD"` mutation never propagates back to DuckDB. Downstream reads from `ledger.get_signals()` re-query the DB and return the original `BUY_YES`/`BUY_NO`, bypassing the deconfliction entirely. Paper trade positions may be double-entered on correlated oil contracts.
  **Fix:** Move deconfliction to before the `record_signal()` loop, or issue an `UPDATE signal_ledger SET signal = 'HOLD' WHERE signal_id = ?` after mutation.

- **[BUG] TypeError crash on NULL win-rate** (`scoring/ledger.py:283`)
  `_compute_suggested_size()` computes `SUM(CASE WHEN model_was_correct THEN 1 ELSE 0 END)`. If `model_was_correct` is set to NULL for all rows in `signal_quality_evaluation` (which can happen before the first resolution cycle completes but after 5+ signals are recorded), `int(row[1])` raises `TypeError: int() argument must be … not 'NoneType'`. The guard `int(row[0]) >= 5` only short-circuits the crash when count < 5.
  **Fix:** Change `int(row[1])` to `int(row[1] or 0)` and `int(row[0])` to `int(row[0] or 0)`.

- **[DEP] `streamlit` and `plotly` missing from `pyproject.toml`** (`dashboard/app.py:7,9`)
  Both are imported at module level but absent from `[project.dependencies]` and all optional groups. Fresh `pip install -e .` produces `ModuleNotFoundError` for any import path touching `dashboard/app.py`, including any test or API endpoint that transitively loads it.
  **Fix:** Add to `[project.optional-dependencies]` as `dashboard = ["streamlit>=1.36", "plotly>=5.22"]`.

### MEDIUM Severity — Carry-Over

- **[PERF] New `httpx.AsyncClient` per Kalshi request** (`markets/kalshi.py:154`)
  `_request()` opens and closes a fresh TCP connection per API call. A brief run fetches 12+ tickers, incurring 12+ handshakes and TLS negotiations per run. Initialize a persistent client in `KalshiClient.__init__` and add `aclose()` called from FastAPI lifespan.

- **[BUG] `update_execution()` trade_id can never be set** (`scoring/ledger.py:259`)
  `COALESCE(?, trade_id)` receives `None` as the first argument, so the expression always resolves to the existing `trade_id` value. The field is write-once at insert time and cannot be updated via this method. Same issue for `position_id`. If the FK sync is needed for resolution/P&L tracking, the query must use a conditional (`CASE WHEN ? IS NOT NULL THEN ? ELSE trade_id END`).

- **[CONFIG] `PRICE_ELASTICITY` and `INSURANCE_THREAT_MULTIPLIER` hardcoded** (`simulation/cascade.py:35–36`)
  Both constants bypass the `ScenarioConfig` dataclass that was explicitly designed to hold all tunable parameters. Scenario comparison/sensitivity analysis will silently use the hardcoded values regardless of YAML overrides.

- **[CONFIG] Validation window dates expired** (`portfolio/simulator.py:15–16`)
  `VALIDATION_START = date(2026, 4, 1)` and `VALIDATION_END = date(2026, 4, 21)` are 79 days in the past. `days_remaining` always evaluates to 0. The metric is stale and misleading in the scorecard output.

### LOW Severity — Carry-Over

- **[SMELL] `crisis_events` NOT NULL enforced by comment only** (`db/schema.py`)
  The column DDL has `-- de-facto NOT NULL (always set by CrisisIngester)`. Declare it `NOT NULL` in schema.

- **[SMELL] LLM pricing hardcoded in budget tracker** (`budget/tracker.py:11–14`)
  Model pricing is a constant dict. Haiku 4.5 / Sonnet pricing has changed during the project lifetime. Silent miscounting of the $20/day cap.

- **[SMELL] Monkey-patch pattern in backtest engine** (`backtest/engine.py:187–226`)
  Module-level function is patched inside an async for-loop with a `finally` restore. An exception bypassing `finally` permanently corrupts the module. Use dependency injection or a context manager.

---

## Spec / Plan Consistency

No changes since 2026-07-08. See that report for the full table. Summary: the 50-agent swarm, H3 spatial simulation, DES engine, circuit breaker, and eval framework remain unbuilt. The current codebase is a stable, intentional pivot to a 3-model prediction market signal engine.

### Architecture Status (unchanged)

| Component | Plan | Reality |
|---|---|---|
| LLM layer | 50-agent country/sub-actor swarm | 3 predictors (oil, ceasefire, Hormuz) |
| Frontend | deck.gl + MapLibre H3 hex map + WebSocket | React + Recharts polling dashboard |
| Data ingestion | GDELT BigQuery (15 min) + ACLED | GDELT DOC API + Google News RSS + Truth Social |
| Eval framework | Per-agent accuracy + prompt versioning | Signal ledger + scorecard + calibration |
| Markets | Not in spec | Kalshi + Polymarket (core addition) |

### Modules Absent (unbuilt, not regressed)

`agents/`, `eval/`, `spatial/`, `simulation/engine.py`, `simulation/circuit_breaker.py`, `ingestion/dedup.py`, `api/` (routes live in `main.py`)

---

## Test Coverage

47 test files, unchanged from yesterday. Coverage is comprehensive for all implemented modules. Tests for unbuilt modules (`test_agent_schemas.py`, `test_h3_utils.py`, `test_dedup.py`, `test_engine.py`, `test_circuit_breaker.py`, `test_auth.py`, `test_prompt_versioning.py`) are absent because the corresponding modules were never implemented.

No test coverage for the deconfliction path in `cli/brief.py` — `test_brief.py` and `test_brief_resilience.py` exist but likely mock the ledger, masking the DB/memory split bug.

---

## Recommendations

**Priority 1 (fix this week — blocking live trading correctness):**
1. Fix deconfliction write-back (`cli/brief.py`): deconflict before `record_signal()` or issue an `UPDATE` after mutation. This is the highest-impact correctness bug.
2. Fix TypeError in win-rate computation (`scoring/ledger.py:283`): `int(row[1] or 0)`.
3. Add `streamlit`/`plotly` to optional deps (`pyproject.toml`): one-line fix.

**Priority 2 (this sprint):**
4. Reuse `httpx.AsyncClient` in `KalshiClient` — reduce per-brief latency by ~500ms.
5. Fix `update_execution()` COALESCE bug (`scoring/ledger.py:259`) — needed for accurate P&L tracking.
6. Update validation window in `portfolio/simulator.py` to current period.

**Priority 3 (backlog):**
7. Move `PRICE_ELASTICITY` into `scenario_hormuz.yaml` / `ScenarioConfig`.
8. Declare `crisis_events` columns NOT NULL in schema.
9. Evaluate GDELT Cloud (per yesterday's tech research) — if pricing is favorable, replaces stages 1-3 of the GDELT filter pipeline and eliminates the `ingestion/dedup.py` debt entirely.
