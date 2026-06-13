# Parallax Health Check — 2026-06-13

**Status: YELLOW**

## Summary

The project remains a stable prediction-market edge-finder that has cleanly diverged from the original Phase 1 geospatial/agent-swarm spec — the pivot is documented and intentional. The [CRITICAL] `pytz` dependency gap from yesterday's report does not appear resolved (it was not present in today's dependency scan). Two additional HIGH-severity issues are newly identified: missing exception handlers on external API calls in `oil_prices.py` and `polymarket.py`, and a hardcoded price elasticity constant in `cascade.py` that the spec requires to be a config parameter. Single-writer DuckDB violations across 10+ modules remain open from yesterday.

---

## Issues Found

### CRITICAL

- **[CRITICAL] `pytz` still missing from `pyproject.toml`** *(carried from 2026-06-12)*
  DuckDB 1.5.x requires `pytz` for `DATE()` / `TIMESTAMPTZ` comparisons. Not listed in `pyproject.toml` — not observed in today's dependency scan either. Affects `scoring/scorecard.py`, `scoring/ledger.py`, `ops/alerts.py`, `budget/tracker.py`, `prediction/crisis_context.py`. 17 test failures remain unresolved. Production `--scorecard` runs and dashboard queries will silently error.
  - **Fix**: Add `pytz>=2024.1` to `dependencies` in `backend/pyproject.toml`.

---

### HIGH

- **[HIGH] Single-writer pattern violated in 10+ modules** *(carried from 2026-06-12)*
  Modules calling `.execute(INSERT/UPDATE ...)` directly on raw `duckdb.DuckDBPyConnection` instead of routing through `DbWriter.enqueue()`: `ops/alerts.py`, `budget/tracker.py`, `scoring/ledger.py`, `scoring/tracker.py`, `scoring/resolution.py`, `scoring/prediction_log.py`, `scoring/scorecard.py`, `ingestion/crisis_ingester.py`, `contracts/registry.py`, `cli/brief.py`. `DbWriter` exists and is correctly implemented but is not wired to these modules. Risk materializes when FastAPI background tasks and live API requests both trigger writes concurrently.
  - Confirmed still present today in `budget/tracker.py:43-56` and `ingestion/crisis_ingester.py:79-84`.

- **[HIGH] Missing error handling at external API boundaries** *(new today)*
  Two modules call `raise_for_status()` on HTTP responses without `try/except`, meaning any transient network error or 4xx/5xx response from an external service propagates as an unhandled exception that crashes the pipeline:
  - `ingestion/oil_prices.py:49-55` — EIA API fetcher uses `try/finally` with no `except`. `httpx.HTTPStatusError` and `json.JSONDecodeError` propagate uncaught.
  - `markets/polymarket.py:85-99` — `search_markets()`, `get_event()`, `get_market()` all call `raise_for_status()` with no surrounding `try/except`. A Polymarket 429 or 5xx will crash the brief run.
  - **Fix**: Wrap external calls in `try/except (httpx.HTTPStatusError, httpx.RequestError)` and return `None` / empty list with a logged warning.

---

### MEDIUM

- **[MEDIUM] `PRICE_ELASTICITY = 3.0` hardcoded in `cascade.py`** *(new today)*
  The spec (§4) explicitly states: "All numeric values are calibrated scenario parameters loaded from a config file, not hard-coded constants." `cascade.py:35` defines `PRICE_ELASTICITY = 3.0` as a module-level constant. It is not present in `backend/config/scenario_hormuz.yaml` and cannot be tuned without a code change. The eval framework cannot flag when this assumption diverges from observed behavior.
  - **Fix**: Add `price_elasticity: 3.0` to `scenario_hormuz.yaml`, add the field to `ScenarioConfig`, and replace the constant in `CascadeEngine.compute_price_shock()` with `self._config.price_elasticity`.

- **[MEDIUM] `simulation/circuit_breaker.py` not implemented** *(carried from 2026-06-12)*
  Spec §4 defines the escalation circuit breaker (max 1 level/tick, 3-tick cooldown, Goldstein-scale exogenous override). Module and `test_circuit_breaker.py` both absent. `ScenarioConfig` already carries the required parameters (`max_escalation_per_tick`, `escalation_cooldown_ticks`, `exogenous_shock_goldstein_threshold`).

- **[MEDIUM] `ingestion/dedup.py` not implemented** *(carried from 2026-06-12)*
  Semantic deduplication (`SemanticDeduplicator` via `all-MiniLM-L6-v2`) is absent from the pipeline. Google News and GDELT DOC may surface duplicate events to prediction models. `sentence-transformers` is not in `pyproject.toml`.

- **[MEDIUM] Architectural drift: agents/, eval/, spatial/, api/ modules never built**
  Original Phase 1 plan specified an H3 hex map, 50-agent LLM swarm, eval/prompt-versioning pipeline, and REST/WebSocket API layer. None of these exist. The pivot to a prediction-market edge-finder is documented in `CLAUDE.md` and is intentional — flagged only because the spec/plan documents still describe the old design.

- **[MEDIUM] Frontend diverges from plan**
  The plan's deck.gl / MapLibre geospatial dashboard (HexMap, AgentFeed, LiveIndicators, Timeline, HexPopover) was not built. The actual frontend is a market-facing dashboard (ContractDetail, KpiBar, MarketsTable, ModelCards, PortfolioPanel, PriceChart). Geospatial deps `deck.gl`, `maplibre-gl`, `react-map-gl`, `h3-js` are absent from `package.json`. Intentional pivot.

---

### LOW

- **[LOW] 6 spec-required backend deps absent from `pyproject.toml`**
  `h3`, `sentence-transformers`, `searoute`, `shapely`, `google-cloud-bigquery`, `websockets` — all from the original Phase 1 spec for the geospatial pipeline that was never built. No operational risk today, but the gap documents unimplemented scope.

- **[LOW] 10 of 16 plan-specified test files missing**
  Missing: `test_h3_utils`, `test_gdelt_filter`, `test_dedup`, `test_circuit_breaker`, `test_agent_schemas`, `test_agent_router`, `test_agent_runner`, `test_scoring` (generic), `test_prompt_versioning`, `test_auth`, `test_budget_tracker` (standalone), `test_integration`. 39 replacement test files exist for the actual pivot scope — overall coverage is healthy, but modules carried from Phase 1 (circuit breaker, dedup) have no tests.

- **[LOW] `requires-python = ">=3.11"` vs spec's Python 3.12**
  No 3.11-incompatible syntax found, but the pin allows environments where subtle 3.12-only behavior may differ.

- **[LOW] No linter or formatter enforced**
  No `ruff`, `black`, or `pre-commit` hook configured. Style is consistent by convention only.

---

## Dependency Snapshot

| Package | Required by Spec | Actual Status |
|---------|-----------------|---------------|
| fastapi ≥0.115 | ✓ | present |
| uvicorn[standard] ≥0.34 | ✓ | present |
| duckdb ≥1.2 | ✓ | present |
| anthropic ≥0.52 | ✓ | present |
| pydantic ≥2.10 | ✓ | present |
| pyyaml ≥6.0 | ✓ | present |
| httpx ≥0.28 | ✓ | present |
| h3 ≥4.1 | ✓ | **missing** |
| websockets ≥14.0 | ✓ | **missing** |
| sentence-transformers ≥3.4 | ✓ | **missing** |
| searoute ≥1.3 | ✓ | **missing** |
| shapely ≥2.0 | ✓ | **missing** |
| google-cloud-bigquery ≥3.27 | ✓ | **missing** |
| pytz (runtime req of DuckDB 1.5.x) | implied | **missing** |
| cryptography ≥44.0 | not in spec | present (Kalshi RSA auth) |
| truthbrush ≥0.2 | not in spec | present (Truth Social feed) |

---

## Recommendations (Priority Order)

1. **Immediate**: Add `pytz>=2024.1` to `backend/pyproject.toml`. Resolves 17 test failures in one line.

2. **Short-term**: Add `try/except (httpx.HTTPStatusError, httpx.RequestError)` in `oil_prices.py:49-55` and `polymarket.py:85-99`. Return `None`/empty with `logger.warning(...)`. Prevents brief run crashes on transient API errors.

3. **Short-term**: Add `price_elasticity: 3.0` to `scenario_hormuz.yaml` and `ScenarioConfig`, remove the `PRICE_ELASTICITY` constant from `cascade.py`. Makes the model tunable without code changes, as the spec requires.

4. **Medium-term**: Wire `DbWriter` into the six async-path modules (`ops/alerts.py`, `budget/tracker.py`, `scoring/ledger.py`, `scoring/prediction_log.py`, `ingestion/crisis_ingester.py`, `contracts/registry.py`). Pass the `DbWriter` instance at construction time and call `await writer.enqueue(...)`. CLI-only modules (`cli/brief.py`, `scoring/scorecard.py`) are lower priority.

5. **Medium-term**: Implement `simulation/circuit_breaker.py` (parameters already in `ScenarioConfig`) and add `test_circuit_breaker.py`.
