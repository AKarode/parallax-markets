# Parallax Health Check — 2026-08-09

**Status: YELLOW**

## Summary

Test suite improved to 433 passed / 13 skipped (zero failures) after DuckDB upgraded implicitly to 1.5.5, which natively supports the `DATE()` scalar function that was breaking 11 scorecard tests yesterday — the underlying code was not changed, so a future install pinned to 1.2.x will reintroduce those failures. Five medium-severity bugs from the prior report remain unresolved: the DbWriter single-writer pattern is still dead code, signal deconfliction does not persist HOLD status to the database, BudgetTracker does not write to `llm_usage` during brief runs, PredictionLogger silently drops staleness metadata on read-back, and four tests still fail to collect because numpy/scikit-learn are declared bench-only but used in production scoring modules.

---

## Test Results

```
433 passed, 13 skipped, 1 warning in 110s
4 collection errors (test_bench_forecast, test_calibration_metrics, test_recalibrators, test_selective — numpy/pandas not installed)
```

**Change since 2026-08-08:** 21 previously failing tests now pass. Root cause is DuckDB 1.5.5 (installed) supports `DATE()` as a scalar function; pyproject.toml pins `duckdb>=1.2` with no upper bound, so a clean install on a 1.2.x release would restore 11 scorecard failures and 3 phase1_critical failures. No code fixes were committed.

---

## Issues Found

### [HIGH] DbWriter asyncio queue is dead code — single-writer pattern not enforced

- **File:** `backend/src/parallax/db/writer.py` (implemented, tested in isolation, never imported by production code)
- **Affected write paths:** `cli/brief.py` (runs INSERT/UPDATE on 3 tables), `scoring/ledger.py`, `scoring/tracker.py`, `scoring/resolution.py`, `scoring/prediction_log.py`, `contracts/registry.py`, `ops/alerts.py`, `budget/tracker.py`, `ingestion/crisis_ingester.py`, `backtest/runner.py`
- **Impact:** All production writes go directly to `conn.execute()`. Concurrent access (e.g., CLI brief alongside API server using the same DuckDB file) risks `IOException: Could not set lock on file`. The spec's single-writer architectural commitment exists only on paper.
- **Carry-over from:** 2026-08-08

### [HIGH] `KalshiClient._request()` has no try/except for network errors

- **File:** `backend/src/parallax/markets/kalshi.py:154–165`
- **Code:** `resp = await client.request(...)` with no surrounding exception handler
- **Impact:** `httpx.TimeoutException`, `httpx.ConnectError`, or `httpx.RemoteProtocolError` from a Kalshi API timeout or DNS failure propagate uncaught through all callers (`get_markets`, `get_market_price`, `place_order`, etc.) and abort the entire brief run with an unhandled exception. Only non-2xx HTTP status is handled via `KalshiAPIError`.
- **Fix:** Wrap the `await client.request(...)` block in `except (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError) as e: raise KalshiAPIError(0, str(e)) from e`.

### [MEDIUM] Signal deconflict mutates in-memory objects without updating `signal_ledger`

- **File:** `backend/src/parallax/cli/brief.py` — `_deconflict_oil_signals()`
- **Bug:** `ledger.record_signal()` persists every signal before deconfliction; then `_deconflict_oil_signals()` sets `s.signal = "HOLD"` on Python objects but issues no `UPDATE signal_ledger SET signal = 'HOLD' WHERE signal_id = ?`. The database permanently stores the pre-deconflict `BUY_YES`/`BUY_NO` values.
- **Impact:** Scorecard, resolution checker, and dashboard all read stale signals. P&L attribution is corrupted for conflicted oil signals.
- **Carry-over from:** 2026-08-08

### [MEDIUM] `BudgetTracker` never writes to `llm_usage` in the brief pipeline

- **File:** `backend/src/parallax/cli/brief.py:532` — `BudgetTracker(daily_cap_usd=20.0)` (no `db_conn` argument)
- **Impact:** `llm_usage` table is always empty during normal brief runs. The `ops_llm_cost_usd` scorecard metric is always 0. The $20/day in-memory cap enforcement works but spend is invisible in the database for historical analysis.
- **Carry-over from:** 2026-08-08

### [MEDIUM] `PredictionLogger.get_predictions()` silently drops staleness metadata

- **File:** `backend/src/parallax/scoring/prediction_log.py` — `_row_to_entry()`
- **Bug:** SELECT returns columns 0–12 but `prediction_log` has 5 additional staleness columns (`is_fallback`, `fallback_source_run_id`, `staleness_penalty_applied`, `context_age_hours`, `penalty_factor`). All revert to Pydantic defaults on read-back.
- **Impact:** Any downstream analysis of staleness corrections (dashboard, backtest) reads incorrect data silently.
- **Carry-over from:** 2026-08-08

### [MEDIUM] numpy and scikit-learn declared bench-only but used in production scoring

- **File:** `backend/pyproject.toml`
- **Issue:** `scoring/selective.py`, `scoring/recalibrators.py`, `scoring/calibration_metrics.py` import numpy and scikit-learn, but these are declared under `[bench]` optional extras only. Default `pip install -e ".[dev]"` leaves them absent, causing 4 test collection errors and potential ImportError in production if the brief pipeline ever calls these modules.
- **Fix:** Move `numpy>=1.26` and `scikit-learn>=1.3` to core `dependencies`.
- **Carry-over from:** 2026-08-08

### [LOW] DuckDB version dependency is underspecified — `DATE()` regression risk

- **File:** `backend/pyproject.toml` — `duckdb>=1.2`
- **Issue:** The `DATE()` scalar function only exists in DuckDB ≥1.3+. `scorecard.py` and `backtest/runner.py` use `DATE(column)` in 19 places. A new install on a 1.2.x release (e.g., in CI, Docker, or a new team member's machine) will fail 21 tests. The fix that worked is the installed DuckDB version, not a code change.
- **Fix:** Either bump the lower bound to `duckdb>=1.3` or replace `DATE(column)` with `CAST(column AS DATE)` in `scorecard.py` and `backtest/runner.py`.

### [LOW] `cryptography` package not declared in `pyproject.toml`

- **File:** `backend/src/parallax/markets/kalshi.py` — uses `cryptography.hazmat.primitives.asymmetric.padding.PSS` for RSA-PSS signing
- **Issue:** `cryptography` is an undeclared transitive dependency (arrives via `truthbrush`). If `truthbrush` updates to drop it or is replaced, Kalshi auth will break with an ImportError.
- **Fix:** Add `cryptography>=42.0` to core dependencies.

### [LOW] `ensemble.py` hardcodes `"opus"` model tag for budget accounting

- **File:** `backend/src/parallax/prediction/ensemble.py`
- **Issue:** `budget.record(resp.usage.input_tokens, resp.usage.output_tokens, "opus")` always logs costs at Opus pricing regardless of the actual model used. Cost estimates in BudgetTracker are inflated if a cheaper model is selected.
- **Carry-over from:** 2026-08-08

### [LOW] `mapping_policy.py` `update_discounts_from_history()` is a no-op

- **File:** `backend/src/parallax/contracts/mapping_policy.py`
- **Issue:** Method logs "Skipping discount update: not yet implemented" and returns. Called in the brief pipeline, creating the appearance of an active adaptive-discount feedback loop.
- **Carry-over from:** 2026-08-08

### [LOW] Missing `__init__.py` in `config/` and `portfolio/` subpackages

- **Paths:** `backend/src/parallax/config/` and `backend/src/parallax/portfolio/`
- **Issue:** All other subpackages have explicit `__init__.py`. These two rely on implicit namespace package behavior, which can produce surprising import resolution in edge cases.
- **Carry-over from:** 2026-08-08

### [LOW] `conftest.py` requires live network for DuckDB extension installs

- **File:** `backend/tests/conftest.py`
- **Issue:** `INSTALL spatial` and `INSTALL h3 FROM community` hit the DuckDB extension registry on every test session start. Firewalled or offline CI will fail all `db`-fixture tests.
- **Carry-over from:** 2026-08-08

---

## Architecture Drift from Spec

The Phase 1 spec describes a ~50-agent LLM swarm simulator with H3 spatial model, GDELT pipeline, WebSocket dashboard, and a prompt-improvement eval loop. The actual codebase is a prediction-market edge-finder: ingest news + EIA prices → 3 Claude prediction models → compare Kalshi/Polymarket prices → flag divergences → paper-trade. This is an intentional, coherent pivot reflected accurately in CLAUDE.md. The following spec modules were never built and are not planned:

| Spec Module | Status |
|---|---|
| `agents/` — 50-agent country/sub-actor hierarchy | Not built; product pivot |
| `spatial/` — H3 resolution bands, route-to-cell | Not built; H3 schema cols unused |
| `eval/` — prompt versioning, improvement pipeline | Not built; replaced by `scoring/` |
| `api/` — separate WebSocket API layer | Not built; routes inline in `main.py` |
| `simulation/engine.py` — DES core | Not built; only cascade/world_state |
| `simulation/circuit_breaker.py` | Not built |

---

## Dependency Audit

| Dependency | Declared | Concern |
|---|---|---|
| `duckdb>=1.2` | ✓ core | Lower bound too low — 1.2.x lacks `DATE()` scalar; bump to `>=1.3` |
| `cryptography` | ✗ missing | Used for RSA-PSS in kalshi.py; undeclared transitive dep |
| `numpy>=1.26` | bench only | Used in production scoring modules; move to core deps |
| `scikit-learn>=1.3` | bench only | Used in production recalibrators; move to core deps |
| `pytest>=8.3,<9` | dev | Installed pytest is 9.x — upper bound stale |
| `truthbrush>=0.2` | core | Niche library, no upper bound, not widely maintained |
| `anthropic>=0.52` | core | No upper bound; breaking changes could silently break inference |

---

## Recommendations

1. **[Immediate]** Add `except (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError)` in `KalshiClient._request()` — prevents Kalshi timeouts from aborting entire brief runs.
2. **[Immediate]** Bump `duckdb>=1.3` in `pyproject.toml` (or replace `DATE()` with `CAST(column AS DATE)`) — prevents 21 test failures on clean installs.
3. **[High]** Fix `_deconflict_oil_signals()` to emit `UPDATE signal_ledger SET signal = 'HOLD' WHERE signal_id = ?` after deconfliction — prevents P&L attribution corruption.
4. **[High]** Move `numpy>=1.26` and `scikit-learn>=1.3` to core dependencies — unblocks 4 test collection errors and prevents production ImportError.
5. **[Medium]** Pass `db_conn` to `BudgetTracker` in `cli/brief.py` so `llm_usage` is populated.
6. **[Medium]** Fix `PredictionLogger._row_to_entry()` to deserialize all 5 staleness columns.
7. **[Low]** Add `cryptography>=42.0` to declared dependencies.
8. **[Low]** Pre-install DuckDB extensions in CI; remove network-required `INSTALL` from `conftest.py`.
9. **[Low]** Add `__init__.py` to `config/` and `portfolio/` subpackages.
10. **[Low]** Update `pytest<9` bound or remove the upper cap.
