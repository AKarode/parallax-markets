# Parallax Health Check — 2026-05-02

**Status: YELLOW**

The test suite regressed by one test since 2026-04-30: a time-dependent fixture in `test_google_news.py` rotted as the hardcoded `old-article` date (2026-03-31) is now 32 days in the past, past the 30-day age window the test relies on. All other pre-existing failure clusters are unchanged. The deprecated Claude model ID (`claude-opus-4-20250514`) and missing `pytz` dependency remain unresolved silent runtime blockers.

---

## Test Results

- **340 passed, 27 failed** (was 341/26 on 2026-04-30 — 1 new regression)
- No code committed to main since 2026-04-30.

| Failure Cluster | Tests | Root Cause |
|---|---|---|
| `test_scorecard.py` | 10 | Missing `pytz` — DuckDB TIMESTAMPTZ queries fail |
| `test_mapping_policy.py` | 10 | Stale assertions expect removed proxy-discount model |
| `test_recalibration.py` | 4 | Count gate vs calibration-curve data source use inconsistent predicates |
| `test_llm_usage.py` | 1 | Missing `pytz` — TIMESTAMPTZ column query fails |
| `test_ops_events.py` | 1 | Missing `pytz` — TIMESTAMPTZ column query fails |
| `test_google_news.py` | 1 | **NEW** — time-dependent fixture: hardcoded date rotted |

---

## Issues Found

### HIGH (NEW) — `test_google_news.py` Time-Dependent Fixture Has Rotted

`test_fetches_and_deduplicates` asserts that 4 events are returned with `max_age_hours=24*30`. The canned fixture includes `old-article` dated `Mon, 31 Mar 2026 12:00:00 GMT`. As of 2026-05-02 that date is 32 days ago, exceeding the 30-day window. The age filter correctly rejects the article, but the test expects it to be included — so `assert len(events) == 4` becomes `assert 3 == 4`.

- **Fix**: Replace the hardcoded pubDate string in `CANNED_RSS` with a relative datetime computed at import time (e.g., `datetime.now(UTC) - timedelta(days=25)` rendered as RFC 2822), or widen the test's `max_age_hours` argument to a much larger value (e.g., `24 * 365`) that will not expire within the project's foreseeable lifetime.

---

### HIGH (PERSISTENT) — Deprecated Claude Model ID in All Three Prediction Models

`oil_price.py:133`, `ceasefire.py:106`, `hormuz.py:108`, and `ensemble.py` docstring all reference `claude-opus-4-20250514`. Current canonical Anthropic model IDs are `claude-opus-4-7`, `claude-sonnet-4-6`, `claude-haiku-4-5-20251001` — none use a date suffix on Opus or Sonnet. If this model ID is retired, every live `run_brief` call silently fails to produce predictions.

- **Fix**: Replace `"claude-opus-4-20250514"` with `"claude-opus-4-7"` in all three predictor files and update the docstring example in `ensemble.py`. Verify the model ID is still routable in the Anthropic API before the next live run.
- **Open since**: 2026-04-29 (4 days).

---

### HIGH (PERSISTENT) — `pytz` Missing from `pyproject.toml` (12 test failures, 16+ days unfixed)

DuckDB raises `InvalidInputException: Required module 'pytz' failed to import` on any query returning a `TIMESTAMPTZ` value. Affected tables: `runs.started_at/ended_at`, `daily_scorecard.computed_at`, `ops_events.created_at`, `llm_usage.created_at`. `--scorecard` CLI is broken in any environment without `pytz` pre-installed.

- **Fix**: Add `"pytz>=2024.1"` to `[project] dependencies` in `backend/pyproject.toml`.
- **Open since**: ~2026-04-15 (17 days).

---

### HIGH (PERSISTENT) — `test_mapping_policy.py` Stale Assertions (10 failures)

`MappingPolicy.evaluate()` computes `effective_edge = gross_edge - transaction_costs`. Tests were written against the old model where `effective_edge = raw_edge × confidence_discount`. Production code is correct; tests are stale.

- **Fix**: Update assertions in `test_mapping_policy.py` to expect `effective_edge = raw_edge - expected_total_cost` for DIRECT proxy mappings.

---

### MEDIUM (PERSISTENT) — Calibration Curve Predicate Mismatch (4 failures)

`recalibrate_probability()` counts resolved signals using `model_was_correct IS NOT NULL`, but `calibration_curve()` queries the `signal_quality_evaluation` view which also requires `resolution_price IS NOT NULL`. Test fixtures set the former but not the latter.

- **Fix (A)**: Align the count query in `recalibrate_probability()` to also require `resolution_price IS NOT NULL`.
- **Fix (B)**: Update test fixtures to populate `resolution_price`.

---

### MEDIUM (PERSISTENT) — Direct DB Writes Bypass `DbWriter`

The single-writer requirement mandates all mutable writes go through `asyncio.Queue → DbWriter`. These modules write directly via `conn.execute()`:

- `ops/alerts.py:106` — INSERT into `ops_events`
- `scoring/ledger.py:225,256` — INSERT/UPDATE into `signal_ledger`
- `scoring/resolution.py:60,124` — UPDATE `signal_ledger`
- `budget/tracker.py:43` — INSERT into `llm_usage`
- `scoring/scorecard.py:21` — INSERT into `daily_scorecard`
- `cli/brief.py:49,68,350` — INSERT/UPDATE into `runs`, `market_prices`

Risk is low while CLI runs sequentially, but becomes HIGH if any write endpoint is active while the FastAPI server holds an open connection to the same DuckDB file.

- **Recommendation**: Wire `DbWriter` everywhere, or annotate each site with `# SINGLE_PROCESS_ONLY`.

---

### MEDIUM (PERSISTENT) — `backtest/` Module Missing `__init__.py`

`backend/src/parallax/backtest/engine.py` exists but has no `__init__.py`, making the package unimportable as `parallax.backtest`. The module is also undocumented in CLAUDE.md's module map and has no test file.

- **Update from 2026-04-30**: The monkey-patch of `ctx.get_crisis_context` at line 189 IS now protected by try-finally (lines 191-226), so the leak risk reported previously is resolved.
- **Remaining fix**: Add `backend/src/parallax/backtest/__init__.py` and add at minimum a smoke test that the module imports cleanly.

---

### LOW (PERSISTENT) — Multiple `duckdb.connect()` Calls in `brief.py`

`run_brief()` and three helper functions each open separate DuckDB connections (lines 454, 631, 662, 672, 682). Running `brief.py` concurrently with the FastAPI server will deadlock on DuckDB's exclusive writer lock.

- **Recommendation**: Open one connection at the top of each CLI entrypoint and pass it through as a parameter.

---

### LOW (PERSISTENT) — Python Version Requirement Weaker Than Spec

`pyproject.toml` declares `requires-python = ">=3.11"`. Spec and `CLAUDE.md` both state Python 3.12. Runtime is Python 3.11.15.

- **Fix**: Update to `requires-python = ">=3.12"` and ensure the deployment environment pins to 3.12.

---

### LOW (PERSISTENT) — `CLAUDE.md` Tech Stack Contains Stale Entries

`CLAUDE.md` lists `deck.gl`, `MapLibre GL`, `h3-js`, `react-map-gl`, `sentence-transformers`, `searoute`, `shapely`, `google-cloud-bigquery`, and `websockets` as active dependencies. None appear in `pyproject.toml` or `frontend/package.json`. The frontend pivoted to a Recharts polling dashboard.

- **Fix**: Rewrite the tech stack section of `CLAUDE.md` to reflect the actual stack.

---

## Spec / Plan Consistency

The original Phase 1 spec described ~50 LLM agents with H3 spatial visualization. The implementation deliberately pivoted to 3 Claude prediction models + Kalshi/Polymarket + paper-trading signal ledger. The pivot is intentional and documented.

| Spec Item | Status |
|---|---|
| `agents/` — 50-agent country/sub-actor swarm | Out of scope (pivot) |
| `spatial/` — H3 hexagon model, deck.gl | Out of scope (pivot) |
| `api/auth.py` — invite codes, admin password | Not implemented |
| `api/websocket.py` — real-time push | Not implemented; frontend uses polling |
| `simulation/circuit_breaker.py` — escalation limits | Not implemented |
| `ingestion/dedup.py` — semantic deduplication | Not implemented |
| Prediction models (oil_price, ceasefire, hormuz) | Implemented, deprecated model ID blocks live runs |
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
| `truthbrush>=0.2` | Present (installed: 0.3.0) | Yes (`truth_social.py`) | OK |
| `cryptography>=44.0` | Present (installed: 47.0.0) | Yes (Kalshi RSA-PSS auth) | OK |

No CVEs identified in declared dependencies at their minimum declared versions.

---

## Positive Findings

- **340/367 tests pass** — 92.6% pass rate.
- **No secrets in repo** — `.env.example` uses placeholders only.
- **AsyncAnthropic client** used everywhere; no accidental sync client instantiations found.
- **Cascade engine + scenario config** fully implemented and unit-tested.
- **Budget guard and alert dispatcher** wired and tested.
- **Contract registry, divergence detector, portfolio simulator** function correctly per test suite.
- **backtest/engine.py monkey-patch** is now protected by try-finally — previous report's leak concern is resolved.

---

## Recommendations (Priority Order)

1. **Fix `test_google_news.py` time-dependent fixture** — replace hardcoded `pubDate` strings with relative dates so the test doesn't rot. One-line fix.
2. **Verify and update Claude model ID** — confirm whether `claude-opus-4-20250514` still routes to an active endpoint; if not, update to `claude-opus-4-7` in `oil_price.py`, `ceasefire.py`, `hormuz.py`. Silent runtime blocker.
3. **Add `pytz>=2024.1`** to `pyproject.toml` — one line, unblocks 12 failures. Open 17+ days.
4. **Fix `test_mapping_policy.py` assertions** — update to expect cost-aware `effective_edge` semantics.
5. **Fix `recalibrate_probability()` predicate** — align count gate with calibration-curve data source.
6. **Add `backtest/__init__.py`** and a smoke test.
7. **Update `pyproject.toml`** `requires-python` to `>=3.12`.
8. **Wire `DbWriter` or document the assumption** — add `# SINGLE_PROCESS_ONLY` guards where applicable.
9. **Update `CLAUDE.md`** to reflect the actual architecture.
