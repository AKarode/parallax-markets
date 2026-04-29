# Parallax Health Check — 2026-04-29

**Status: YELLOW**

The last merged health check on main was 2026-04-24. No code changes have landed on main since then. All three chronic failure clusters persist: 12 test failures from missing `pytz` (unfixed for **13+ days**), 10 from stale mapping-policy test assertions, and 4 from a calibration-curve predicate mismatch. The system is in maintenance/analysis mode post-validation-window (April 7–21).

---

## Test Results

- **341 passed, 26 failed** (identical to 2026-04-28)
- All failures are pre-existing; no new regressions

| Failure Cluster | Tests | Root Cause |
|---|---|---|
| `test_scorecard.py` | 10 | Missing `pytz` — DuckDB TIMESTAMPTZ queries fail |
| `test_mapping_policy.py` | 10 | Stale assertions expect old proxy-discount model |
| `test_recalibration.py` | 4 | Count gate vs calibration-curve predicate mismatch |
| `test_llm_usage.py` | 1 | Missing `pytz` — TIMESTAMPTZ column query fails |
| `test_ops_events.py` | 1 | Missing `pytz` — TIMESTAMPTZ column query fails |

---

## Issues Found

### HIGH — `pytz` Missing from `pyproject.toml` (12 test failures, **13 days unfixed**)

DuckDB raises `InvalidInputException: Required module 'pytz' failed to import` on any query returning a `TIMESTAMPTZ` value. Affected tables: `runs.started_at/ended_at`, `daily_scorecard.computed_at`, `ops_events.created_at`, `llm_usage.created_at`.

The `--scorecard` CLI flag is **broken in any environment that doesn't have `pytz` pre-installed**. This has been flagged in every health report since 2026-04-16 with no action taken.

- **Fix**: Add `"pytz>=2024.1"` to `[project] dependencies` in `backend/pyproject.toml`. One line.

---

### HIGH — `effective_edge` Semantics Mismatch in Mapping Policy Tests (10 failures, persistent)

`MappingPolicy.evaluate()` computes `effective_edge = net_edge = gross_edge - transaction_costs`. Tests were written under the old model where `effective_edge = raw_edge × confidence_discount`, so they expect `effective_edge ≈ raw_edge` for a DIRECT proxy with `discount=1.0`. The delta is the 2% cost rate (e.g., `abs(0.14 − 0.16) = 0.02 ≫ 1e-9`).

Production code is correct. Tests are stale and are testing a removed model.

- **Fix**: Update `test_mapping_policy.py` assertions to reflect cost-aware semantics: `effective_edge = raw_edge - expected_total_cost` for DIRECT proxy.

---

### MEDIUM — Calibration Curve Returns Empty (4 recalibration test failures, persistent)

`recalibrate_probability()` counts resolved signals from `signal_ledger` using `model_was_correct IS NOT NULL`. The count gate passes (≥10 signals), but `calibration_curve()` queries from the `signal_quality_evaluation` view, which additionally requires `resolution_price IS NOT NULL`. Test fixtures set `model_was_correct` but not `resolution_price`, so the view returns no rows, the function short-circuits, and the probability is returned unchanged.

This is a logic bug: the activation threshold and the calibration-data source use inconsistent predicates.

- **Fix (option A)**: Change the count query in `recalibrate_probability()` to also require `resolution_price IS NOT NULL`. 
- **Fix (option B)**: Update test fixtures to set `resolution_price` on all inserted rows so the view includes them.

---

### MEDIUM — Direct DB Writes Bypass `DbWriter` (unchanged)

The single-writer requirement from the spec mandates all mutable writes go through `asyncio.Queue → DbWriter`. In practice, these modules write directly via `conn.execute()`:

- `ops/alerts.py:106` — INSERT into `ops_events`
- `scoring/ledger.py:227, 258` — INSERT/UPDATE into `signal_ledger`
- `scoring/resolution.py:60, 124` — UPDATE `signal_ledger`
- `budget/tracker.py:43` — INSERT into `llm_usage`
- `scoring/scorecard.py` — INSERT into `daily_scorecard` (all metrics)

Current risk is low because the CLI runs sequentially and the FastAPI server has no live write endpoints. Risk rises to **HIGH** if any write endpoint is ever enabled while the API server holds an open connection to the same DuckDB file.

- **Recommendation**: Either wire `DbWriter` everywhere or document the single-connection assumption with a `# SINGLE_PROCESS_ONLY` comment in the relevant modules.

---

### LOW — Python Version Requirement Weaker Than Spec (unchanged)

`pyproject.toml` declares `requires-python = ">=3.11"`. Spec and `CLAUDE.md` both state Python 3.12. The test runner is Python 3.11.15. No 3.12-specific syntax is in use, so this is not a current bug, but the mismatch should be resolved.

- **Fix**: Update to `requires-python = ">=3.12"`.

---

### LOW — Multiple `duckdb.connect()` Calls in `brief.py` (unchanged)

`run_brief()` and its three helper functions (`_run_calibration`, `_run_report_card`, `_run_scorecard`) each open separate DuckDB connections. Running `brief.py` while the FastAPI server holds a read-write connection to the same file will deadlock.

- **Recommendation**: Open one connection at the top of each CLI entrypoint and thread it through as a parameter.

---

### LOW — `CLAUDE.md` Tech Stack Contains Stale Entries (unchanged)

`CLAUDE.md` lists `deck.gl`, `MapLibre GL`, `h3-js`, `react-map-gl`, `sentence-transformers`, `searoute`, `shapely`, `google-cloud-bigquery`, and `websockets` as active dependencies. None appear in `pyproject.toml` or `frontend/package.json`. The project pivoted to a Recharts trading dashboard with no geospatial layer.

- **Fix**: Rewrite the tech stack section of `CLAUDE.md` to reflect the actual implementation.

---

## Spec / Plan Consistency

The original Phase 1 spec described ~50 LLM agents in a country/sub-actor hierarchy with H3 spatial visualization and GDELT BigQuery integration. The implementation deliberately pivoted to 3 Claude Sonnet prediction models + Kalshi/Polymarket market comparison + paper-trading signal ledger. This pivot was intentional and is documented in `docs/SESSION-2026-04-08.md`.

| Spec Item | Status |
|---|---|
| `agents/` — 50-agent country/sub-actor swarm | Out of scope (pivot) |
| `spatial/` — H3 hexagon model, deck.gl | Out of scope (pivot) |
| `eval/` — prompt versioning, A/B scoring | Partially replaced by `scoring/scorecard.py` |
| `api/auth.py` — invite codes, admin password middleware | Not implemented |
| `api/websocket.py` — real-time push | Not implemented; frontend uses polling |
| `simulation/circuit_breaker.py` — escalation limits | Not implemented |
| `ingestion/dedup.py` — semantic deduplication | Not implemented |
| Prediction models (oil_price, ceasefire, hormuz) | **Implemented and tested** |
| Kalshi + Polymarket clients | **Implemented and tested** |
| Signal ledger, paper trading, portfolio allocator | **Implemented and tested** |
| Divergence detector | **Implemented and tested** |
| Contract registry + mapping policy | **Implemented and tested** |
| Daily scorecard ETL | **Implemented, but pytz bug blocks runtime** |

---

## Dependency Audit

| Package | `pyproject.toml` | Actually Used | Action |
|---|---|---|---|
| `pytz>=2024.1` | **MISSING** | Yes (DuckDB TIMESTAMPTZ) | **Add immediately** |
| `h3>=4.1` | Missing | No | Defer to Phase 2 |
| `sentence-transformers>=3.4` | Missing | No | Defer |
| `searoute>=1.3` | Missing | No | Defer |
| `shapely>=2.0` | Missing | No | Defer |
| `google-cloud-bigquery>=3.27` | Missing | No | Defer |
| `websockets>=14.0` | Missing | No | Not used |
| `truthbrush>=0.2` | Present | Yes (`truth_social.py`) | OK |
| `cryptography>=44.0` | Present | Yes (Kalshi RSA-PSS auth) | OK |

No CVEs identified in declared dependencies at their minimum declared versions.

---

## Positive Findings

- **341/367 tests pass** — 92.9% pass rate; all 26 failures are pre-existing known issues.
- **No new regressions** since 2026-04-24 (last merged commit on main).
- **No secrets in repo** — `.env.example` uses placeholders only; no live keys committed.
- **Schema migration helpers** in `schema.py` allow additive upgrades without breaking existing databases.
- **Cascade engine + scenario config** fully implemented and unit-tested.
- **Budget guard** (`ops/runtime.py`) and alert dispatcher (`ops/alerts.py`) are wired and tested.
- **Contract registry, divergence detector, portfolio simulator** all function correctly per test suite.

---

## Recommendations (Priority Order)

1. **Add `pytz>=2024.1`** to `pyproject.toml` dependencies — one line, unblocks 12 failures immediately. This has been open **13+ days**.
2. **Fix `test_mapping_policy.py` assertions** — update to expect `effective_edge = raw_edge - expected_total_cost` per the cost-aware model the production code already implements.
3. **Fix `recalibrate_probability()` predicate** — align the activation-count query with the calibration-curve data source (both should require `resolution_price IS NOT NULL`, or test fixtures should set it).
4. **Update `pyproject.toml`** `requires-python` to `>=3.12` to match spec.
5. **Wire `DbWriter` or document the assumption** — add `# SINGLE_PROCESS_ONLY` guards in `SignalLedger`, `BudgetTracker`, `AlertDispatcher`, and `scorecard.py`.
6. **Update `CLAUDE.md`** to reflect the actual architecture (no deck.gl, no H3, no geospatial layer; Recharts polling dashboard).
