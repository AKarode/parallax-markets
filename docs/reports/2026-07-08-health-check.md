# Parallax Health Check — 2026-07-08

**Status: YELLOW**

The core prediction-market trading pipeline is implemented and tested, but the codebase has significantly pivoted away from the original Phase 1 spec (agent swarm + spatial simulation) toward a leaner market edge-finder. Three high-severity bugs exist that can corrupt DB state or cause runtime crashes on the live hot path. Missing pyproject.toml dependencies will break fresh installs of the Streamlit dashboard.

---

## Summary

The original Phase 1 design described a 50-agent LLM swarm, H3 hexagonal spatial visualization (deck.gl/MapLibre), a WebSocket-driven 3-panel dashboard, and an eval framework. What was built instead is a focused prediction market signal engine: 3 Claude prediction models compare against Kalshi/Polymarket prices and fire paper trades on divergences. This pivot appears deliberate and commercially practical, but represents near-total architectural departure from the spec. 47 tests exist covering the actual implementation, but coverage for several plan-specified modules is entirely absent because those modules were never built.

---

## Issues Found

### HIGH Severity

- **[BUG] DB/memory divergence in signal deconfliction** (`cli/brief.py:493–499`)
  `_deconflict_oil_signals()` mutates `SignalRecord` objects in-memory (setting `.signal = "HOLD"`) _after_ they have already been written to DuckDB via `ledger.record_signal()`. The DB retains the original `BUY_YES`/`BUY_NO` signal while in-memory objects show `HOLD`. The subsequent `ledger.get_signals()` read at line 747 re-queries the DB, returning the un-deconflicted rows. Paper trade decisions are therefore based on contradictory state.

- **[BUG] TypeError crash when no resolved signals exist** (`scoring/ledger.py:274`)
  `_compute_suggested_size()` runs `SUM(CASE WHEN model_was_correct THEN 1 ELSE 0 END) AS wins`. When `model_was_correct` is always NULL (no resolved signals yet — the normal state for a new deployment), SUM returns NULL. The subsequent `int(row[1]) / int(row[0])` call then throws `TypeError: int() argument must be a string, a bytes-like object or a real number, not 'NoneType'`. Fix: use `int(row[1] or 0)`.

- **[DEP] Streamlit dashboard uninstallable on fresh deploy** (`dashboard/app.py:7,9`)
  `import streamlit` and `import plotly.graph_objects` appear at module level but neither `streamlit` nor `plotly` is listed in `pyproject.toml` dependencies. Any fresh install (`pip install -e .`) will fail to import the dashboard. These are production dependencies, not dev-only.

### MEDIUM Severity

- **[PERF] New HTTP client created per Kalshi API request** (`markets/kalshi.py:154`)
  `_request()` creates a new `httpx.AsyncClient` on every call. A brief run fetches prices for 12+ tickers, incurring 12+ TCP handshakes. A persistent client (initialized at startup and closed in lifespan) would eliminate this overhead.

- **[BUG] `update_execution()` trade_id/position_id can never be updated** (`scoring/ledger.py:259`)
  The SQL uses `COALESCE(?, trade_id)` but passes `None` as the parameter, so `COALESCE(NULL, trade_id)` always returns the existing value. The trade_id field cannot be set after initial insert via this method. Same issue applies to `position_id`.

- **[CONFIG] Cascade constants hardcoded despite ScenarioConfig** (`simulation/cascade.py:35–36`)
  `PRICE_ELASTICITY = 3.0` and `INSURANCE_THREAT_MULTIPLIER = 5.0` are class-level constants. `ScenarioConfig` was specifically designed to hold all tunable parameters — these belong there, not hardcoded.

- **[CONFIG] Validation window dates expired** (`portfolio/simulator.py:15–16`)
  `VALIDATION_START = date(2026, 4, 1)` and `VALIDATION_END = date(2026, 4, 21)` are hardcoded. As of 2026-07-08, `days_remaining` always returns 0, making that output metric a dead field.

### LOW Severity

- **[SMELL] DB constraint enforced by comment, not schema** (`db/schema.py:491–492`)
  The `crisis_events` table has `-- de-facto NOT NULL (always set by CrisisIngester)` inline in the DDL. The column should be declared `NOT NULL` if the invariant is real.

- **[SMELL] LLM pricing hardcoded in budget tracker** (`budget/tracker.py:11–14`)
  Rates for `opus`/`sonnet`/`haiku` are hardcoded constants. If model IDs or pricing tiers change, the $20/day cap enforcement silently uses stale rates with no warning.

- **[SMELL] Monkey-patch pattern in backtest engine** (`backtest/engine.py:187–226`)
  `ctx.get_crisis_context` is patched at module level inside an async for-loop. The `finally` block restores it, but any exception that bypasses `finally` would leave the module permanently mutated. A context manager or dependency injection would be safer.

---

## Spec / Plan Consistency

### Implemented (deviating from spec, but present)
| Component | Plan Says | Reality |
|-----------|-----------|---------|
| Frontend | deck.gl + MapLibre 3-panel dashboard | React + Recharts polling dashboard |
| Data ingestion | GDELT BigQuery (15 min) | GDELT DOC API + Google News RSS + Truth Social |
| LLM layer | 50-agent swarm (country→sub-actor) | 3 monolithic predictors (oil, ceasefire, Hormuz) |
| Eval framework | Per-agent accuracy + prompt versioning | Signal ledger + scorecard + calibration metrics |
| Markets | Not in spec | Kalshi + Polymarket clients (core addition) |

### Not Implemented (in plan, absent in code)
- `simulation/engine.py` — DES event loop with heapq priority queue
- `simulation/circuit_breaker.py` — Escalation cooldowns and exogenous shock override
- `agents/` package — Entire 50-agent country/sub-actor swarm
- `eval/` package — Ground truth fetcher, prompt versioning, improvement pipeline
- `spatial/` package — H3 utilities, route-to-cell conversion, resolution bands
- `ingestion/dedup.py` — Semantic dedup via sentence-transformers (spec §6 Stage 3)
- `api/` package — Routes live in monolithic `main.py` (functional but not modular)

### Beyond Plan (not in spec, present in code)
- KalshiBench harness (`bench/`) — calibration against HuggingFace resolved questions
- Truth Social ingestion (`ingestion/truth_social.py`)
- Mechanical recalibration (`scoring/recalibration.py`)
- Kill-switch system with 3-layer safety gate (`ops/runtime.py`)
- Portfolio simulator with Quarter-Kelly + equity curve (`portfolio/simulator.py`)
- Backtest engine with look-ahead guard (`backtest/`)
- Streamlit dashboard (`dashboard/app.py`) alongside the React frontend — both serve overlapping purposes

---

## Test Coverage Gaps

Tests from the original plan that are absent because the modules were never built:
- `test_h3_utils.py` — spatial package not implemented
- `test_gdelt_filter.py` — volume gate + entity override not implemented (GDELT DOC fetcher exists but without the 4-stage filter pipeline)
- `test_dedup.py` — semantic dedup not implemented
- `test_agent_schemas.py`, `test_agent_router.py`, `test_agent_runner.py` — agents package not built
- `test_scoring.py`, `test_predictions.py`, `test_prompt_versioning.py` — eval package not built
- `test_auth.py` — invite code + admin auth middleware not implemented
- `test_circuit_breaker.py` — circuit breaker not built
- `test_engine.py` — DES engine not built

Tests that exist for actual implemented modules (sample): `test_cascade.py`, `test_world_state.py`, `test_config.py`, `test_writer.py`, `test_schema.py`, `test_ledger.py`, `test_kalshi.py`, `test_divergence.py`, `test_scorecard.py`, `test_brief.py`, `test_ensemble.py`, `test_crisis_context.py`, `test_backtest_look_ahead.py`.

---

## Recommendations

1. **Fix the deconfliction bug first** (`cli/brief.py`). The DB/memory divergence means the paper trade log may show `BUY_YES` on oil contracts that were intended to be `HOLD`. Roll up a fix: either deconflict before writing to the ledger, or add an `UPDATE` call to flip the DB record.

2. **Fix the TypeError crash** (`scoring/ledger.py:274`). Any run before the first resolution event will hit this. Change `int(row[1])` to `int(row[1] or 0)`.

3. **Add streamlit + plotly to pyproject.toml** or move the Streamlit dashboard to an optional `[project.optional-dependencies]` group (e.g., `pip install -e ".[dashboard]"`). Failing imports on a fresh clone are bad signals.

4. **Reuse the httpx client** in `KalshiClient`. Initialize it in `__init__` and close in a `aclose()` method called from FastAPI lifespan.

5. **Move `PRICE_ELASTICITY` and `INSURANCE_THREAT_MULTIPLIER` into `scenario_hormuz.yaml`** and the `ScenarioConfig` dataclass.

6. **Update the validation window** in `portfolio/simulator.py` to reflect the current trading period (e.g., June–July 2026).

7. **Decide on dashboard strategy**: the Streamlit and React dashboards overlap. If React is the long-term UI, the Streamlit dashboard can be deprecated (but move its plotly dependency into an optional group first).
