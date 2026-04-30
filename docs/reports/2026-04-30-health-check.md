# Parallax Health Check — 2026-04-30

**Status: YELLOW**

No code has landed on main since 2026-04-29 (yesterday's health check commit). All 26 pre-existing test failures persist unchanged across four failure clusters. One new HIGH finding has been identified: all three production prediction models are hardcoded to `claude-opus-4-20250514`, a date-suffixed model ID from the pre-4.6 naming era that does not match any current Anthropic model alias and is likely deprecated, meaning live predictions will fail at the API boundary.

---

## Test Results

- **341 passed, 26 failed** (identical to 2026-04-28 and 2026-04-29)
- No new regressions; no fixes merged.

| Failure Cluster | Tests | Root Cause |
|---|---|---|
| `test_scorecard.py` | 10 | Missing `pytz` — DuckDB TIMESTAMPTZ queries fail |
| `test_mapping_policy.py` | 10 | Stale assertions expect removed proxy-discount model |
| `test_recalibration.py` | 4 | Count gate vs calibration-curve data source use inconsistent predicates |
| `test_llm_usage.py` | 1 | Missing `pytz` — TIMESTAMPTZ column query fails |
| `test_ops_events.py` | 1 | Missing `pytz` — TIMESTAMPTZ column query fails |

---

## Issues Found

### HIGH (NEW) — Deprecated Claude Model ID in All Three Prediction Models

`oil_price.py:133`, `ceasefire.py:106`, `hormuz.py:108`, and the `ensemble.py` docstring all reference `claude-opus-4-20250514`. This uses the date-suffix naming convention from the pre-4.6 release era. Current canonical Anthropic model IDs (per project environment) are `claude-opus-4-7`, `claude-sonnet-4-6`, and `claude-haiku-4-5-20251001` — none of which use a date suffix on Opus or Sonnet. If `claude-opus-4-20250514` has been retired or is not routed to the latest Opus 4 checkpoint, every live `run_brief` call will raise an API error and produce no predictions.

- **Fix**: Replace `"claude-opus-4-20250514"` with `"claude-opus-4-7"` in `oil_price.py`, `ceasefire.py`, `hormuz.py`, and update the docstring example in `ensemble.py`. The git commit `ca52a42` ("fix: switch ensemble predictions back to Claude Opus from Sonnet") introduced this string — confirm the model ID is still valid against the Anthropic API before the next live run.

---

### HIGH — `pytz` Missing from `pyproject.toml` (12 test failures, **14+ days unfixed**)

DuckDB raises `InvalidInputException: Required module 'pytz' failed to import` on any query returning a `TIMESTAMPTZ` value. Affected tables: `runs.started_at/ended_at`, `daily_scorecard.computed_at`, `ops_events.created_at`, `llm_usage.created_at`. The `--scorecard` CLI flag is broken in any environment that lacks `pytz` pre-installed.

- **Fix**: Add `"pytz>=2024.1"` to `[project] dependencies` in `backend/pyproject.toml`.

---

### HIGH — `test_mapping_policy.py` Stale Assertions (10 failures, persistent)

`MappingPolicy.evaluate()` computes `effective_edge = gross_edge - transaction_costs` (cost-aware model). Tests were written against the old model where `effective_edge = raw_edge × confidence_discount`. Production code is correct; tests are stale.

- **Fix**: Update assertions in `test_mapping_policy.py` to expect `effective_edge = raw_edge - expected_total_cost` for DIRECT proxy mappings.

---

### MEDIUM — Calibration Curve Predicate Mismatch (4 failures, persistent)

`recalibrate_probability()` counts resolved signals using `model_was_correct IS NOT NULL`, but `calibration_curve()` queries the `signal_quality_evaluation` view which also requires `resolution_price IS NOT NULL`. Test fixtures set the former but not the latter, causing the activation threshold to pass while the calibration data source returns zero rows.

- **Fix (A)**: Align the count query in `recalibrate_probability()` to also require `resolution_price IS NOT NULL`.
- **Fix (B)**: Update test fixtures to set `resolution_price` on inserted rows.

---

### MEDIUM — Direct DB Writes Bypass `DbWriter` (unchanged)

The single-writer requirement mandates all mutable writes go through `asyncio.Queue → DbWriter`. These modules write directly via `conn.execute()`:

- `ops/alerts.py:106` — INSERT into `ops_events`
- `scoring/ledger.py:225,256` — INSERT/UPDATE into `signal_ledger`
- `scoring/resolution.py:60,124` — UPDATE `signal_ledger`
- `budget/tracker.py:43` — INSERT into `llm_usage`
- `scoring/scorecard.py:21` — INSERT into `daily_scorecard`

Risk is currently low (CLI runs sequentially; no concurrent write endpoints). Risk becomes HIGH if any write endpoint is activated while the FastAPI server holds an open connection to the same DuckDB file.

- **Recommendation**: Wire `DbWriter` everywhere, or add `# SINGLE_PROCESS_ONLY` guards in each module.

---

### MEDIUM (NEW) — `backtest/engine.py` Has No `__init__.py` and No Tests

`backend/src/parallax/backtest/engine.py` exists as a standalone file with no `__init__.py` (the module is not importable as `parallax.backtest`), no corresponding test file, and no entry in the plan or CLAUDE.md module map. It also monkey-patches `parallax.prediction.crisis_context.get_crisis_context` with `ctx.get_crisis_context = lambda: context_text` (line 187) — a global mutation that is not restored if the function raises, creating a leak between backtest iterations.

- **Fix**: Add `backend/src/parallax/backtest/__init__.py`, add basic smoke tests, and use `unittest.mock.patch` or a try/finally block instead of direct module-level mutation.

---

### LOW — Multiple `duckdb.connect()` Calls in `brief.py` (unchanged)

`run_brief()` and three helper functions (`_run_calibration`, `_run_report_card`, `_run_scorecard`) each open separate DuckDB connections at lines 454, 631, 662, 672, and 682. Running `brief.py` concurrently with the FastAPI server will deadlock on DuckDB's exclusive writer lock.

- **Recommendation**: Open one connection at the top of each CLI entrypoint and thread it through as a parameter.

---

### LOW — Python Version Requirement Weaker Than Spec (unchanged)

`pyproject.toml` declares `requires-python = ">=3.11"`. Spec and `CLAUDE.md` both state Python 3.12.

- **Fix**: Update to `requires-python = ">=3.12"`.

---

### LOW — `CLAUDE.md` Tech Stack Contains Stale Entries (unchanged)

`CLAUDE.md` lists `deck.gl`, `MapLibre GL`, `h3-js`, `react-map-gl`, `sentence-transformers`, `searoute`, `shapely`, `google-cloud-bigquery`, and `websockets` as active dependencies. None appear in `pyproject.toml` or `frontend/package.json`. The frontend pivoted to a Recharts polling dashboard with no geospatial layer.

- **Fix**: Rewrite the tech stack section of `CLAUDE.md` to reflect the actual stack.

---

## Spec / Plan Consistency

The original Phase 1 spec described ~50 LLM agents with H3 spatial visualization. The implementation deliberately pivoted to 3 Claude prediction models + Kalshi/Polymarket + paper-trading signal ledger. The pivot remains intentional and documented.

| Spec Item | Status |
|---|---|
| `agents/` — 50-agent country/sub-actor swarm | Out of scope (pivot) |
| `spatial/` — H3 hexagon model, deck.gl | Out of scope (pivot) |
| `api/auth.py` — invite codes, admin password | Not implemented |
| `api/websocket.py` — real-time push | Not implemented; frontend uses polling |
| `simulation/circuit_breaker.py` — escalation limits | Not implemented |
| `ingestion/dedup.py` — semantic deduplication | Not implemented |
| Prediction models (oil_price, ceasefire, hormuz) | Implemented, but model ID may be deprecated |
| Kalshi + Polymarket clients | Implemented and tested |
| Signal ledger, paper trading, portfolio allocator | Implemented and tested |
| Divergence detector | Implemented and tested |
| Contract registry + mapping policy | Implemented; tests stale |
| Daily scorecard ETL | Implemented; pytz bug blocks runtime |

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
- **No new regressions** since 2026-04-24 (last substantive code commit on main).
- **No secrets in repo** — `.env.example` uses placeholders only.
- **AsyncAnthropic client** used everywhere (no accidental sync client instantiations).
- **Cascade engine + scenario config** fully implemented and unit-tested.
- **Budget guard and alert dispatcher** wired and tested.
- **Contract registry, divergence detector, portfolio simulator** all function correctly per test suite.

---

## Recommendations (Priority Order)

1. **Verify and update Claude model ID** — confirm whether `claude-opus-4-20250514` still resolves to an active model endpoint; if not, update to `claude-opus-4-7` in `oil_price.py`, `ceasefire.py`, and `hormuz.py`. This is a silent runtime blocker.
2. **Add `pytz>=2024.1`** to `pyproject.toml` dependencies — one line, unblocks 12 failures. Open **14+ days**.
3. **Fix `test_mapping_policy.py` assertions** — update to expect cost-aware `effective_edge` semantics.
4. **Fix `recalibrate_probability()` predicate** — align count gate with calibration-curve data source.
5. **Add `backtest/__init__.py`** and replace the monkey-patch in `engine.py` with `unittest.mock.patch`.
6. **Update `pyproject.toml`** `requires-python` to `>=3.12`.
7. **Wire `DbWriter` or document the assumption** — add `# SINGLE_PROCESS_ONLY` guards where applicable.
8. **Update `CLAUDE.md`** to reflect the actual architecture.
