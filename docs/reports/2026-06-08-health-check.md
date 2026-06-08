# Parallax Health Check — 2026-06-08

**Status: YELLOW**

The codebase is functional and well-tested, with good coverage across prediction, scoring, and market modules. Two new data-integrity bugs surfaced in today's deeper code scan: a confirmed parameter reuse bug in `signal_ledger` that silently corrupts `trade_id` on every execution update, and an un-transacted DELETE+INSERT in `ContractRegistry.upsert()` that can leave contracts with no proxy mappings on partial failure. The persistent HIGH-severity DuckDB single-writer violation from yesterday's report remains unresolved.

---

## Issues Found

### [HIGH — NEW] Data Integrity Bug: `ledger.py` line 267 — `trade_id` always overwritten with `position_id`

**File:** `backend/src/parallax/scoring/ledger.py:246–268`

`update_execution()` accepts `entry_order_id`, `position_id`, `traded`, and `trade_refused_reason` but **not** `trade_id`. The SQL updates six columns including `trade_id`, but the params list passes `position_id` twice — once for `trade_id` and once for `position_id`:

```python
# Function signature has no trade_id parameter
[execution_status, entry_order_id, position_id, position_id, traded, trade_refused_reason, signal_id]
#                                  ↑ maps to trade_id      ↑ maps to position_id
```

Every call that supplies a `position_id` silently sets `trade_id = position_id` in the signal ledger. Downstream queries that join on `trade_id` (e.g., P&L attribution, fill reconciliation) will produce wrong results.

**Fix:** Add `trade_id: str | None = None` to the function signature and use it as the third parameter, or remove `trade_id` from the SQL if it should not be updated via this path.

---

### [HIGH — NEW] Race Condition: `contracts/registry.py` upsert not wrapped in transaction

**File:** `backend/src/parallax/contracts/registry.py:85–122`

`ContractRegistry.upsert()` executes three separate `conn.execute()` calls in sequence:
1. `INSERT OR REPLACE INTO contract_registry` — upserts the main contract row
2. `DELETE FROM contract_proxy_map WHERE ticker = ?` — wipes all proxy mappings
3. A loop of `INSERT INTO contract_proxy_map` — writes new mappings one by one

If any iteration of step 3 fails (network glitch, constraint violation), the contract exists in `contract_registry` with **zero proxy mappings**. All downstream divergence detection and signal generation for that contract silently produces no output — no error, just missing signals.

**Fix:** Wrap all three operations in an explicit DuckDB transaction (`BEGIN`/`COMMIT`/`ROLLBACK`) so failure in the loop rolls back the DELETE.

---

### [HIGH — CARRIED] DuckDB Single-Writer Pattern Violated in 7+ Modules

Identified in the 2026-06-07 report; no change in status. Direct `conn.execute()` INSERT/UPDATE calls outside the `DbWriter` queue exist in:

- `scoring/ledger.py`, `scoring/resolution.py`, `scoring/prediction_log.py`
- `scoring/tracker.py`, `ops/alerts.py`
- `backtest/runner.py`, `ingestion/crisis_ingester.py`

Under concurrent FastAPI request handling or simultaneous background tasks, these contend with `DbWriter` and with each other, risking non-deterministic `database is locked` failures. **The two new HIGH issues above both live inside this pattern.**

---

### [MEDIUM — NEW] Missing error handling for external API failures at batch boundary

**File:** `backend/src/parallax/markets/kalshi.py` and `backend/src/parallax/ingestion/oil_prices.py`

- `oil_prices.py`: `resp.json()` is called without a `try/except` — a malformed EIA API response (e.g. 200 with HTML error page) raises an unhandled `JSONDecodeError` that propagates to the caller and aborts the full brief run.
- `kalshi.py`: `_request()` loses response context on non-2xx status — the raised exception includes the status code but not the response body, making auth errors (401/403) very hard to diagnose in logs.

**Fix:** Wrap `resp.json()` in `oil_prices.py`; log response body on non-2xx in `kalshi.py`.

---

### [MEDIUM — CARRIED] Architecture Drift from Phase 1 Spec

The project pivoted from a 50-agent geopolitical swarm with H3 hex visualization to a 3-model prediction-market edge finder. CLAUDE.md reflects the current system correctly. The plan doc (`docs/superpowers/plans/2026-03-30-parallax-phase1.md`) still describes the old architecture and is misleading as implementation guidance.

**Recommendation:** Add a `> [PIVOTED YYYY-MM-DD]` notice at the top of the plan doc.

---

### [MEDIUM — CARRIED] `h3` package not in `pyproject.toml`

`simulation/world_state.py` and `simulation/cascade.py` use H3 cell IDs (`BIGINT`) in the schema. The `h3` Python library is absent from `pyproject.toml`. Any future code importing `h3` directly will raise `ImportError` in a fresh install.

**Recommendation:** Add `h3>=4.1` to `pyproject.toml` dependencies.

---

### [LOW — CARRIED] 6 Tests Permanently Skipped in `test_mapping_policy.py`

Tests marked `@pytest.mark.skip(reason=_PRE_REFACTOR_REASON)` silently reduce coverage without CI failure. Either complete the refactor or delete these tests.

---

### [LOW — NEW] `ensemble.py` missing input guards on statistical helpers

**File:** `backend/src/parallax/prediction/ensemble.py`

- `trimmed_mean([])` will raise `statistics.StatisticsError` (mean of empty sequence) if all model calls fail. Callers use `return_exceptions=True` in `asyncio.gather` but don't check whether the resulting list is empty before passing to `trimmed_mean`.
- `compute_ensemble()` does not validate that input probabilities are in `[0, 1]`. An LLM returning `"0.85 (high confidence)"` that survives JSON parsing as a float above 1.0 would produce an ensemble probability > 1.

**Fix:** Guard `trimmed_mean` against empty input; clamp probabilities to `[0.0, 1.0]` in `compute_ensemble`.

---

## What's Working Well

- **`DbWriter` pattern is correctly implemented** — the architecture is right; violations are in consumers.
- **43 test files, 312 test functions** — coverage is thorough for prediction, scoring, and market modules.
- **`scorecard.py` ETL** provides the 15+ metric daily eval loop; idempotency tests pass.
- **`BudgetTracker` + runtime kill-switch** are wired up and tested.
- **`scenario_hormuz.yaml`** matches spec parameters.
- **Kalshi RSA-PSS auth** is correctly implemented and tested with key verification.
- **`ContractRegistry` proxy classification** (DIRECT / NEAR_PROXY / LOOSE_PROXY) is solid and well-tested.

---

## Recommendations (Priority Order)

| # | Priority | Action | File |
|---|----------|--------|------|
| 1 | HIGH | Fix `trade_id` parameter bug — add `trade_id` param or remove column from SQL | `scoring/ledger.py:267` |
| 2 | HIGH | Wrap `ContractRegistry.upsert()` in a transaction | `contracts/registry.py:85–122` |
| 3 | HIGH | Route direct writes in `scoring/`, `ops/`, `backtest/`, `ingestion/` through `DbWriter` | multiple |
| 4 | MEDIUM | Wrap `resp.json()` in try/except in `oil_prices.py`; log body on non-2xx in `kalshi.py` | ingestion, markets |
| 5 | MEDIUM | Add `h3>=4.1` to `pyproject.toml` | `pyproject.toml` |
| 6 | MEDIUM | Add pivot note to Phase 1 plan doc | `docs/superpowers/plans/` |
| 7 | LOW | Guard `trimmed_mean` against empty input; clamp probabilities in `compute_ensemble` | `prediction/ensemble.py` |
| 8 | LOW | Delete or fix 6 skipped tests in `test_mapping_policy.py` | `tests/` |
