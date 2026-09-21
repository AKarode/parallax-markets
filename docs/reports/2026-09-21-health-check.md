# Parallax Health Check — 2026-09-21

**Status: YELLOW**

## Summary

No code has been committed to `backend/src/` since **2026-08-26** (26 days). All bugs flagged in previous reports remain open. The three HIGH-severity issues (np.trapz removal, DuckDB single-writer violations, bench import guards) have been open 10+ days with no fixes. The project is in a documentation/observation loop with no active development. Test suite could not be executed in today's health check container (duckdb not installed via pip in the sandbox environment); prior run counts remain the best reference (433 passed, 13 skipped as of 2026-09-20).

---

## Issues Found

### HIGH Severity — Open 10+ Days

- **[BUG] `np.trapz` removed in NumPy 2.x** (`scoring/selective.py:106`)
  `np.trapz(risk, coverage)` raises `AttributeError` in NumPy ≥ 2.0. Replacement: `np.trapezoid`. Latent until `pip install ".[bench]"` is run.
  **Fix:** One-line change: `s/np.trapz/np.trapezoid/` at line 106.

- **[BUG] DuckDB single-writer violation** (`ops/alerts.py:106`)
  `DuckDBAlertSink.send()` calls `conn.execute(INSERT INTO ops_events …)` directly from an `async` method, bypassing the `DbWriter` asyncio.Queue. Risks `database is locked` under live-pipeline concurrency.
  **Fix:** Inject `DbWriter` and replace direct `conn.execute` with `await self._db_writer.enqueue(...)`.

- **[INFRA] 4 bench test files fail to collect** (`test_bench_forecast.py`, `test_calibration_metrics.py`, `test_recalibrators.py`, `test_selective.py`)
  Raise `ModuleNotFoundError` for `pandas`/`numpy`/`sklearn` on `pip install -e ".[dev]"`. Blocks clean `pytest tests/` run.
  **Fix:** Add `pytest.importorskip("pandas")` / `pytest.importorskip("numpy")` at top of each file (4 lines).

### HIGH Severity — Carry-Over (Open Since ≥ 2026-07-09)

- **[BUG] Deconfliction DB/memory split** (`cli/brief.py:491,714`)
  `ledger.record_signal()` persists signals at line 699 _before_ `_deconflict_oil_signals()` runs at line 714. In-memory `.signal = "HOLD"` mutations never write back to DuckDB. Downstream reads from `ledger.get_signals()` return the original `BUY_YES`/`BUY_NO`, bypassing deconfliction. Paper trades may double-enter correlated oil contracts.
  **Fix:** Move deconfliction before `record_signal()` loop, or issue `UPDATE signal_ledger SET signal = 'HOLD' WHERE signal_id = ?` after mutation.

- **[BUG] TypeError crash on NULL win-rate** (`scoring/ledger.py:283`)
  `int(row[1])` raises `TypeError` when `model_was_correct` is NULL for all rows (before first resolution cycle with 5+ signals). Guard `int(row[0]) >= 5` does not prevent crash when count ≥ 5 but win-count is NULL.
  **Fix:** Change `int(row[1])` → `int(row[1] or 0)` and `int(row[0])` → `int(row[0] or 0)`.

### MEDIUM Severity — Carry-Over

- **[BUG] `update_execution()` COALESCE never updates** (`scoring/ledger.py:259–264`)
  `COALESCE(?, trade_id)` receives `None` as first arg, so `trade_id`, `position_id`, etc. are always write-once. FK sync needed for P&L tracking cannot occur via this method.
  **Fix:** Replace `COALESCE(?, field)` with `CASE WHEN ? IS NOT NULL THEN ? ELSE field END`.

- **[DEP] `streamlit` and `plotly` missing from `pyproject.toml`** (`dashboard/app.py:16–17`)
  Both imported at module-level but absent from all dependency groups. Fresh `pip install -e .` causes `ModuleNotFoundError` for any path touching `dashboard/app.py`.
  **Fix:** Add `dashboard = ["streamlit>=1.36", "plotly>=5.22"]` optional group.

- **[PERF] New `httpx.AsyncClient` per Kalshi request** (`markets/kalshi.py:154`)
  12+ API calls per brief run × new TCP+TLS handshake each = ~500ms wasted per run.
  **Fix:** Initialize persistent `AsyncClient` in `__init__`, close in FastAPI lifespan.

- **[CONFIG] `PRICE_ELASTICITY` and `INSURANCE_THREAT_MULTIPLIER` hardcoded** (`simulation/cascade.py:35,38`)
  Both bypass `ScenarioConfig`. Scenario comparisons silently ignore YAML overrides.
  **Fix:** Move constants to `scenario_hormuz.yaml` and read via `ScenarioConfig`.

- **[CONFIG] Validation window dates expired** (`portfolio/simulator.py:15–16`)
  `VALIDATION_END = date(2026, 4, 21)` is 153 days past. `days_remaining` always returns 0. Misleading scorecard metric.
  **Fix:** Update to a rolling 30-day window relative to `date.today()`.

- **[DB] `scoring/tracker.py` + `scoring/ledger.py` — direct DuckDB writes**
  Both call `self._conn.execute(INSERT/UPDATE …)` directly on live code paths, bypassing `DbWriter`. Concurrent async activity risks locking.

- **[DB] `contracts/registry.py` — direct DuckDB writes at startup**
  `ContractRegistry` issues `INSERT OR REPLACE` and `UPDATE` directly at init. Inconsistent with single-writer convention; hazard if registry refresh fires mid-run.

### LOW Severity — Carry-Over

- **[SCHEMA] `crisis_events.headline_hash` NOT NULL enforced by comment only** (`db/schema.py:491`)
  `-- de-facto NOT NULL (always set by CrisisIngester)`. Declare column `NOT NULL` in DDL.

- **[SMELL] LLM pricing hardcoded in budget tracker** (`budget/tracker.py:11–14`)
  Hardcoded price dict for Haiku/Sonnet. Pricing has changed during project lifetime. Silent miscounting of $20/day cap.

- **[CONFIG] `pyproject.toml` `requires-python = ">=3.11"`** (production uses 3.12-slim)
  Should be `>=3.12` to match Dockerfile.

- **[SMELL] Monkey-patch pattern in backtest engine** (`backtest/engine.py:187–226`)
  Module-level function patched inside async for-loop with `finally` restore. Exception bypassing `finally` permanently corrupts module state.

---

## Spec / Plan Consistency

No change from prior reports. The implemented codebase is a stable pivot from the Phase 1 spec to a 3-model prediction market signal engine. The following spec components remain unbuilt (intentional pivot, not regression):

| Component | Spec | Reality |
|---|---|---|
| LLM layer | 50-agent swarm (12 countries + sub-actors) | 3 predictors (oil, ceasefire, Hormuz) |
| Frontend | deck.gl + MapLibre H3 hex map + WebSocket | React + Recharts polling dashboard |
| Data ingestion | GDELT BigQuery (15 min) + ACLED | GDELT DOC API + Google News RSS + Truth Social |
| Eval framework | Per-agent accuracy + prompt versioning | Signal ledger + scorecard + calibration |
| Markets | Not in spec | Kalshi + Polymarket (core addition) |

**Modules absent (unbuilt):** `agents/`, `eval/`, `spatial/`, `simulation/engine.py`, `simulation/circuit_breaker.py`, `ingestion/dedup.py`, `api/` (routes live in `main.py`)

---

## Test Coverage

Prior reference: 433 passed, 13 skipped (2026-09-20). Suite could not be executed in today's container (duckdb unavailable via pip). Code inspection confirms no new test files or source changes since 2026-08-26. The 4 bench test files remain uncollectable without `--ignore` or `pytest.importorskip` guards.

**Missing test coverage (persistent):**
- Deconfliction write-back path in `cli/brief.py` — `test_brief.py` mocks ledger, masking the DB/memory split bug
- `ops/alerts.py` DuckDB write path under concurrent load
- `update_execution()` COALESCE failure mode

---

## Recommendations

**Priority 1 — 5-minute fixes, high impact:**
1. `s/np.trapz/np.trapezoid/` in `scoring/selective.py:106` — prevents AttributeError in NumPy 2.x
2. `int(row[1] or 0)` in `scoring/ledger.py:283` — prevents TypeError on NULL win-rate
3. Add `pytest.importorskip` guards to 4 bench test files — restores clean `pytest tests/` collection

**Priority 2 — Active bugs affecting trading correctness:**
4. Fix deconfliction write-back (`cli/brief.py`) — open since July 9, affects live paper trade correctness
5. Fix `update_execution()` COALESCE (`scoring/ledger.py:259`) — P&L tracking broken
6. Add `streamlit`/`plotly` to `pyproject.toml` optional deps — one line

**Priority 3 — Architecture hygiene:**
7. Refactor `ops/alerts.py`, `scoring/tracker.py`, `scoring/ledger.py`, `contracts/registry.py` to use `DbWriter`
8. Update `VALIDATION_END` to rolling window in `portfolio/simulator.py`
9. Move `PRICE_ELASTICITY` / `INSURANCE_THREAT_MULTIPLIER` into `scenario_hormuz.yaml`

**Note:** No code commits have landed in 26 days (since 2026-08-26). The 5 highest-impact bugs listed above each require fewer than 15 minutes to fix. Continued observation without fixing Priority 1 items is not cost-free — the np.trapz bug will silently crash any bench run, and the deconfliction bug may cause incorrect paper trade signals to persist undetected.
