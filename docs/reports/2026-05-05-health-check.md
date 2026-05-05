# Parallax Health Check — 2026-05-05

**Status: YELLOW**

No code has been committed since 2026-05-02 (3 days of health-check-only commits). Test results are identical to the previous report: 340 passed, 27 failed across the same five failure clusters. All HIGH issues persist, with the `pytz` bug now open 20+ days and the deprecated Claude model ID open 7 days. The `test_google_news.py` time-dependent fixture is now 35 days past its embedded publish date.

---

## Test Results

- **340 passed, 27 failed** — identical to 2026-05-02; no new regressions, no new fixes
- Test suite run time: 60.98s
- Python: 3.11 (system); pytest 8.3, pytest-asyncio 0.26, pytest-httpx 0.35

| Failure Cluster | Count | Root Cause |
|---|---|---|
| `test_scorecard.py` | 10 | Missing `pytz` — DuckDB TIMESTAMPTZ queries crash |
| `test_mapping_policy.py` | 10 | Stale assertions expect old proxy-discount model, not cost-aware model |
| `test_recalibration.py` | 4 | Count gate (`model_was_correct IS NOT NULL`) diverges from calibration view (`resolution_price IS NOT NULL`) |
| `test_ops_events.py` | 1 | Missing `pytz` — TIMESTAMPTZ column query crashes |
| `test_llm_usage.py` | 1 | Missing `pytz` — TIMESTAMPTZ column query crashes |
| `test_google_news.py` | 1 | Time-dependent fixture: hardcoded pubDate is now 35 days old, exceeds 30-day age window |

---

## Issues Found

### HIGH (PERSISTENT, 20+ days) — `pytz` Missing from `pyproject.toml`

DuckDB raises `InvalidInputException: Required module 'pytz' failed to import` on any query returning a `TIMESTAMPTZ` column. Affects: `runs.started_at/ended_at`, `daily_scorecard.computed_at`, `ops_events.created_at`, `llm_usage.created_at`. The `--scorecard` CLI flag is completely broken in any environment where `pytz` is not incidentally pre-installed.

- **Severity**: HIGH — blocks 12 tests; breaks the `--scorecard` pipeline in clean environments
- **Fix**: Add `"pytz>=2024.1"` to `[project] dependencies` in `backend/pyproject.toml`
- **Open since**: ~2026-04-15 (20 days)

---

### HIGH (PERSISTENT, 7 days) — Deprecated Claude Model ID Blocks Live Runs

`oil_price.py:133`, `ceasefire.py`, and `hormuz.py` call `ensemble_predict()` with `model="claude-opus-4-20250514"`. This is not a valid current Anthropic model ID (current IDs: `claude-opus-4-7`, `claude-sonnet-4-6`, `claude-haiku-4-5-20251001`). If the model string is rejected by the API, every `run_brief` live call silently fails to produce predictions.

- **Severity**: HIGH — silent production blocker; no test catches a wrong model ID
- **Fix**: Replace `"claude-opus-4-20250514"` with `"claude-opus-4-7"` in `oil_price.py`, `ceasefire.py`, and `hormuz.py`; verify the ID routes correctly before the next live run
- **Open since**: 2026-04-29 (7 days)

---

### HIGH (PERSISTENT) — `test_google_news.py` Time-Dependent Fixture Rotted

`test_fetches_and_deduplicates` expects 4 events with `max_age_hours=24*30=720`. The fixture includes an article with `pubDate: Mon, 31 Mar 2026 12:00:00 GMT`, which is now 35 days old — beyond the 30-day window. The age filter correctly excludes it; the test assertion (`assert len(events) == 4`) fails with `assert 3 == 4`. This will never self-heal.

- **Severity**: HIGH — test will never pass without a fix; misleading CI failure
- **Fix (minimal)**: Widen `max_age_hours` to `24 * 365` for the test's old-article fixture case, or replace the hardcoded `pubDate` with `(datetime.now(UTC) - timedelta(days=25)).strftime(RFC_2822_FORMAT)`
- **Open since**: ~2026-04-30 (5 days in failure state; fixture was technically planted earlier)

---

### MEDIUM (PERSISTENT) — `test_mapping_policy.py` Stale Assertions (10 failures)

`MappingPolicy.evaluate()` now computes `effective_edge = gross_edge - expected_total_cost` (cost-aware model). Test assertions were written against the old model where `effective_edge = raw_edge × confidence_discount`. Example from `test_direct_proxy_full_edge`: test expects `effective_edge ≈ raw_edge` (no cost deduction); actual is `raw_edge - 0.02 = net_edge`. Production code is correct; tests are stale.

- **Severity**: MEDIUM — production logic is correct; tests are misleading
- **Fix**: Update `TestDirectProxyDiscount`, `TestNearProxyDiscount`, `TestLooseProxyDiscount`, `TestProbabilityInversion`, `TestAboveThreshold`, `TestSortedByEffectiveEdge`, and `TestDiscountFromHistory` to assert `effective_edge = raw_edge - expected_total_cost`

---

### MEDIUM (PERSISTENT) — Calibration Predicate Mismatch (4 failures)

`recalibrate_probability()` at `scoring/recalibration.py:70` counts qualifying signals with `model_was_correct IS NOT NULL`. The downstream `calibration_curve()` query goes via the `signal_quality_evaluation` view, which also requires `resolution_price IS NOT NULL`. Test fixtures populate `model_was_correct` without `resolution_price`, so count gate passes but calibration curve returns nothing. `TestCalibrationCurveModelFilter` tests fail with `assert 0 == 1` / `assert 0 == 2`.

- **Severity**: MEDIUM — mechanical recalibration feature is untestable; behavior under low-data conditions is unvalidated
- **Fix (A — preferred)**: Align `recalibrate_probability()`'s count query to also require `resolution_price IS NOT NULL`
- **Fix (B)**: Populate `resolution_price` in the test fixtures

---

### MEDIUM (PERSISTENT) — Direct DB Writes Bypass `DbWriter` Single-Writer Pattern

The spec mandates all writes go through `asyncio.Queue → DbWriter`. The following modules bypass this and write directly via `conn.execute()`:

| File | Lines | Table |
|---|---|---|
| `ops/alerts.py` | 106 | `ops_events` |
| `scoring/ledger.py` | 225, 256 | `signal_ledger` |
| `scoring/resolution.py` | 60, 124 | `signal_ledger` |
| `budget/tracker.py` | 43 | `llm_usage` |
| `scoring/scorecard.py` | 21 | `daily_scorecard` |
| `cli/brief.py` | 49, 68, 350 | `runs`, `market_prices` |

Risk is LOW while CLI runs sequentially as a single process, but becomes HIGH if any write endpoint is active while the FastAPI server holds an open DuckDB connection.

- **Severity**: MEDIUM (latent HIGH)
- **Fix**: Wire `DbWriter` to all write sites, or annotate each with `# SINGLE_PROCESS_ONLY` and add an assertion/guard in `main.py`

---

### LOW (PERSISTENT) — `backtest/` Module Missing `__init__.py`

`backend/src/parallax/backtest/engine.py` has no `__init__.py`, making it unimportable as `parallax.backtest`. It is undocumented in the CLAUDE.md module map and has no test file.

- **Severity**: LOW — not on the critical path; backtest is unused in production
- **Fix**: Add `backend/src/parallax/backtest/__init__.py` (empty) and a smoke test `test_backtest.py`

---

### LOW (PERSISTENT) — Multiple `duckdb.connect()` Calls in `brief.py`

`run_brief()` and three helper functions each open separate DuckDB connections. Running `brief.py` concurrently with the FastAPI server will deadlock on DuckDB's exclusive writer lock.

- **Severity**: LOW — no current concurrent usage, but a trap for future development
- **Fix**: Open one connection at the top of each CLI entrypoint and thread it through as a parameter

---

### LOW (PERSISTENT) — Python Version Requirement Weaker Than Spec

`pyproject.toml` declares `requires-python = ">=3.11"`. CLAUDE.md and the design spec both state Python 3.12. The system runtime is Python 3.11.

- **Severity**: LOW — cosmetic mismatch, no current breakage
- **Fix**: Update to `requires-python = ">=3.12"`; upgrade the deployment environment to Python 3.12

---

### LOW (PERSISTENT) — `CLAUDE.md` Tech Stack Contains Stale Entries

CLAUDE.md's "Technology Stack" section lists `deck.gl`, `MapLibre GL`, `h3-js`, `react-map-gl`, `sentence-transformers`, `searoute`, `shapely`, `google-cloud-bigquery`, and `websockets` as active dependencies. None appear in `pyproject.toml` or `frontend/package.json`. The frontend is a Recharts polling dashboard, not a deck.gl hex map.

- **Severity**: LOW — onboarding confusion; no runtime impact
- **Fix**: Rewrite the Technology Stack section of CLAUDE.md to reflect the actual stack

---

## Spec / Plan Consistency

The original Phase 1 spec described ~50 LLM agents with H3 spatial visualization (deck.gl, MapLibre). The implementation deliberately pivoted to 3 Claude prediction models + Kalshi/Polymarket market data + paper-trading signal ledger. The pivot is intentional and documented.

| Spec Item | Status |
|---|---|
| `agents/` — 50-agent country/sub-actor swarm | Out of scope (deliberate pivot) |
| `spatial/` — H3 hexagon model, deck.gl | Out of scope (deliberate pivot) |
| `api/auth.py` — invite codes, admin password | Not implemented |
| `api/websocket.py` — real-time push | Not implemented; frontend uses polling |
| `simulation/circuit_breaker.py` — escalation limits | Not implemented |
| `ingestion/dedup.py` — semantic deduplication | Not implemented |
| Prediction models (oil_price, ceasefire, hormuz) | Implemented; deprecated model ID is a live blocker |
| Kalshi + Polymarket clients | Implemented and tested |
| Signal ledger, paper trading, portfolio allocator | Implemented and tested |
| Divergence detector | Implemented and tested |
| Contract registry + mapping policy | Implemented; tests are stale (10 failures) |
| Daily scorecard ETL | Implemented; `pytz` bug blocks runtime |

---

## Dependency Audit

| Package | `pyproject.toml` | Actually Used | Action |
|---|---|---|---|
| `pytz>=2024.1` | **MISSING** | Yes (DuckDB TIMESTAMPTZ) | **Add immediately** |
| `h3>=4.1` | Missing | No | Defer to Phase 2 if needed |
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

- **340/367 tests pass** — 92.6% pass rate; no regression in 3 days
- **No secrets in repo** — `.env.example` uses placeholders only
- **AsyncAnthropic client** used everywhere; no accidental sync client instantiations
- **Cascade engine + scenario config** fully implemented and unit-tested
- **Budget guard and alert dispatcher** wired and tested
- **Contract registry, divergence detector, portfolio simulator** function correctly per test suite
- **`backtest/engine.py` monkey-patch** is protected by `try-finally` (no context leak)
- **DuckDB `DbWriter`** single-writer implementation is correct where it is used

---

## Recommendations (Priority Order)

1. **Add `pytz>=2024.1` to `pyproject.toml`** — one line, unblocks 12 test failures; fixes `--scorecard` in clean envs. Open 20+ days.
2. **Update Claude model ID** — replace `"claude-opus-4-20250514"` with `"claude-opus-4-7"` in `oil_price.py`, `ceasefire.py`, `hormuz.py`. Silent production blocker.
3. **Fix `test_google_news.py` time-dependent fixture** — widen `max_age_hours` or use a relative date. One-line fix; test will never self-heal.
4. **Fix `test_mapping_policy.py` stale assertions** — update to expect cost-aware `effective_edge = raw_edge - expected_total_cost`.
5. **Align `recalibrate_probability()` predicate** — add `resolution_price IS NOT NULL` to the count query, matching the calibration view.
6. **Add `backtest/__init__.py`** and a smoke test.
7. **Wire `DbWriter` or annotate direct-write sites** — add `# SINGLE_PROCESS_ONLY` where applicable.
8. **Update `pyproject.toml`** `requires-python` to `>=3.12`.
9. **Update `CLAUDE.md`** tech stack to reflect the actual implementation.
