# Parallax Health Check — 2026-05-12

**Status: YELLOW**

No code changes since the 2026-05-11 health check commit — all four HIGH issues are now one day older. The streak of consecutive YELLOW days is **11**. Test baseline remains **27 failed, 302 passed** (per 2026-05-11 full-venv run; local environment cannot run tests due to `cryptography 41.0.7` Debian system package conflict blocking `pip install -e .`).

---

## Changes Since Last Report

**None.** The only commit since `2026-05-11-health-check.md` was the commit that wrote that report. No production code, tests, dependencies, or configuration were modified.

---

## Test Results

- **Baseline: 27 failed, 302 passed** (from 2026-05-11 full-venv run — unchanged)
- Local test runner blocked: `pip install -e .` fails with `Cannot uninstall cryptography 41.0.7, RECORD file not found` (Debian system package); tests cannot be collected in this env
- Failure set is identical to 2026-04-21 through 2026-05-11 (11 consecutive days)

| Failure Cluster | Count | Root Cause |
|---|---|---|
| `test_scorecard.py` | 9 | Missing `pytz` — DuckDB `TIMESTAMPTZ` queries crash |
| `test_mapping_policy.py` | 11 | Stale assertions expect old proxy-discount model |
| `test_recalibration.py` | 4 | Calibration predicate mismatch (`model_was_correct` vs `resolution_price`) |
| `test_ops_events.py` | 1 | Missing `pytz` |
| `test_llm_usage.py` | 1 | Missing `pytz` |
| `test_google_news.py` | 1 | Hardcoded April 8 pubDates now 34 days old; 30-day filter returns `[]` |

---

## Issues Found

### HIGH (ESCALATING — 30 days) — `crisis_context.py` Stale; Validation Window Expired

`backend/src/parallax/prediction/crisis_context.py` header reads `Last updated: 2026-04-12`. Today is 2026-05-12 — **30 days stale**. All three live prediction models (`oil_price`, `ceasefire`, `hormuz_reopening`) inject this stale context block into every Claude API call. The "Current Market State" section describes a ceasefire with "10 days remaining" that expired April 21. Every live prediction run reasons about fundamentally incorrect market conditions.

- **Severity**: HIGH — all live prediction outputs conditioned on 30-day-stale context
- **Fix**: Update with events from April 12–May 12; revise "Current Market State" section; update `Last updated: 2026-05-12`
- **Open since**: 2026-04-13 (30 days unactioned)

---

### HIGH (ESCALATING — 14 days) — Deprecated Claude Model ID Blocks Live Prediction Runs

`oil_price.py:133`, `ceasefire.py:106`, and `hormuz.py:108` all call `ensemble_predict()` with `model="claude-opus-4-20250514"`. This is not a valid Anthropic model ID. Valid current IDs: `claude-opus-4-7`, `claude-sonnet-4-6`, `claude-haiku-4-5-20251001`. Every live prediction call is rejected by the Anthropic API.

- **Severity**: HIGH — silent production blocker; no test validates the model ID string
- **Fix**: Replace `"claude-opus-4-20250514"` with `"claude-opus-4-7"` in three files (5-minute fix)
- **Open since**: 2026-04-28 (14 days unactioned)

---

### HIGH (ESCALATING — 27+ days) — `pytz` Missing from `pyproject.toml`

DuckDB 1.5.2 raises `InvalidInputException: Required module 'pytz' failed to import` on any query returning a `TIMESTAMPTZ` column. Affects `runs.started_at/ended_at`, `daily_scorecard.computed_at`, `ops_events.created_at`, `llm_usage.created_at`. The `--scorecard` CLI path is completely broken in clean-install environments; 11 tests fail as a direct result.

- **Severity**: HIGH — blocks 11 tests; breaks `--scorecard` pipeline in clean installs
- **Fix**: Add `"pytz>=2024.1"` to `[project] dependencies` in `backend/pyproject.toml` (1-minute fix)
- **Open since**: ~2026-04-15 (27+ days unactioned)

---

### HIGH (ESCALATING — 4 days) — `test_google_news.py` Fixture Permanently Broken

`test_fetches_and_deduplicates` uses hardcoded `pubDate` strings referencing April 8, 2026 articles with `max_age_hours=24*30`. As of today (May 12), all articles are 34 days old; `fetch_google_news` returns `[]`, causing `AssertionError: assert 0 == 1`. This failure is permanent and gets worse with each passing day.

- **Severity**: HIGH — test permanently broken; detonated May 8 (4 days ago)
- **Fix**: Replace hardcoded `pubDate` strings (`test_google_news.py:29,35,41,54,60`) with relative dates computed at test runtime; reduce `max_age_hours` to `24 * 10`
- **Open since**: 2026-05-08 (4 days)

---

### MEDIUM (PERSISTENT) — `test_mapping_policy.py` Stale Assertions (11 failures)

`MappingPolicy.evaluate()` was refactored to a cost-aware fair-value model (`effective_edge = gross_edge - expected_total_cost`). Test assertions still target the old proxy-discount architecture. `confidence_discount` is now hardcoded to `1.0`. All 11 failures have been consistently present for 21+ days.

- **Severity**: MEDIUM — production code is correct; stale tests mask future regressions
- **Fix**: Rewrite affected assertions; replace `confidence_discount` assertions with `assert result.confidence_discount == 1.0`

---

### MEDIUM (PERSISTENT) — Calibration Predicate Mismatch (4 failures)

`recalibrate_probability()` (`scoring/recalibration.py:71`) counts qualifying signals with `WHERE model_id = ? AND model_was_correct IS NOT NULL`. The downstream `calibration_curve()` queries from `signal_quality_evaluation` view, which additionally requires `resolution_price IS NOT NULL`. Test fixtures populate `model_was_correct` without `resolution_price`, so count gate passes but calibration silently does nothing.

- **Severity**: MEDIUM — mechanical recalibration untestable
- **Fix**: Add `AND resolution_price IS NOT NULL` to count query in `recalibrate_probability()` at `scoring/recalibration.py:71`

---

### MEDIUM (PERSISTENT) — Direct DB Writes Bypass `DbWriter` Single-Writer Pattern

The spec mandates all writes go through `asyncio.Queue → DbWriter`. The following modules still write directly via `conn.execute()`:

| File | Write Location | Table(s) |
|---|---|---|
| `ops/alerts.py` | Line 106 | `ops_events` |
| `scoring/ledger.py` | Lines 225, 256 | `signal_ledger` |
| `scoring/prediction_log.py` | Line 85 | `prediction_log` |
| `scoring/resolution.py` | Lines 60, 124 | `signal_ledger` |
| `scoring/scorecard.py` | Line 21 | `daily_scorecard` |
| `budget/tracker.py` | Line 43 | `llm_usage` |
| `cli/brief.py` | Lines 49, 68, 350 | `runs`, `market_prices` |

Risk is LOW while CLI runs sequentially but becomes HIGH if any write path runs concurrently with the FastAPI server.

- **Severity**: MEDIUM (latent HIGH)
- **Fix**: Wire `DbWriter` to all write sites, or annotate each with `# SINGLE_PROCESS_ONLY` and add a startup guard

---

### LOW (PERSISTENT) — `backtest/` Module Missing `__init__.py`

`backend/src/parallax/backtest/engine.py` exists but has no `__init__.py` sibling, making `from parallax.backtest.engine import ...` fail at import. The module is absent from the CLAUDE.md module map and has no test.

- **Severity**: LOW — not on critical path
- **Fix**: Add `backend/src/parallax/backtest/__init__.py` (empty) and a smoke test

---

### LOW (PERSISTENT) — Python Version Requirement Weaker Than Spec

`pyproject.toml` declares `requires-python = ">=3.11"`. CLAUDE.md and the Phase 1 design spec state Python 3.12. System runtime is Python 3.11.15. No current breakage; cosmetic drift.

- **Severity**: LOW
- **Fix**: Update to `requires-python = ">=3.12"`

---

### LOW (PERSISTENT) — `CLAUDE.md` Tech Stack Lists Uninstalled Dependencies

CLAUDE.md lists `deck.gl`, `MapLibre GL`, `h3-js`, `react-map-gl`, `sentence-transformers`, `searoute`, `shapely`, `google-cloud-bigquery`, and `websockets` as active dependencies. None appear in `pyproject.toml` or `frontend/package.json`. The frontend is a Recharts REST-polling dashboard; the spec's H3 hex-map pivot never happened.

- **Severity**: LOW — onboarding confusion; no runtime impact
- **Fix**: Rewrite CLAUDE.md Technology Stack section to reflect the actual stack

---

## Spec / Plan Consistency

The Phase 1 spec described ~50 LLM agents with H3 spatial visualization. The implementation deliberately pivoted to 3 Claude prediction models + prediction-market arbitrage. That pivot is intentional and well-documented. No regression from prior reports on these items.

| Spec Item | Status |
|---|---|
| `agents/` — 50-agent country/sub-actor swarm | Out of scope (deliberate pivot) |
| `spatial/` — H3 hexagon model, deck.gl | Out of scope (deliberate pivot) |
| `api/auth.py` — invite codes, admin password | Not implemented |
| `api/websocket.py` — real-time push | Not implemented; frontend uses polling |
| `simulation/circuit_breaker.py` — escalation limits | Not implemented |
| `ingestion/dedup.py` — semantic deduplication | Not implemented |
| Prediction models (oil_price, ceasefire, hormuz) | Implemented; **deprecated model ID blocks live runs** |
| `crisis_context.py` — post-cutoff context injection | Implemented but **30 days stale** |
| Kalshi + Polymarket clients | Implemented and tested |
| Signal ledger, paper trading, portfolio allocator | Implemented and tested |
| Divergence detector | Implemented and tested |
| Contract registry + mapping policy | Implemented; tests stale (11 failures) |
| Daily scorecard ETL | Implemented; `pytz` bug blocks runtime in clean envs |

---

## Dependency Audit

| Package | `pyproject.toml` | Status | Action |
|---|---|---|---|
| `pytz>=2024.1` | **MISSING** | Not installed | **Add immediately — 27+ days unactioned** |
| `fastapi>=0.115` | Present | OK in full venv | No action |
| `truthbrush>=0.2` | Present | OK in full venv | No action |
| `duckdb>=1.2` | Present | 1.5.2 installed | OK |
| `cryptography>=44.0` | Present | 41.0.7 (Debian) | Version below declared minimum; blocks test install in this env |
| `anthropic>=0.52` | Present | OK | OK |

Frontend (`react ^18.3.1`, `recharts ^2.15.0`, `vite ^6.0.0`, `typescript ~5.6.2`): current, no CVEs flagged.

---

## Positive Findings

- **302/329 tests pass** — no regressions from 2026-04-21 baseline; consistent for 21+ days
- **No secrets in repo** — `.env.example` uses placeholders only
- **`AsyncAnthropic` client** used everywhere; no sync client instantiations
- **Cascade engine + scenario YAML config** fully implemented and unit-tested
- **Budget guard and alert dispatcher** wired and tested
- **`DbWriter` single-writer implementation** is correct where used
- **test_brief.py (24 tests) and test_crisis_context.py (9 tests)** — all pass in full venv; dry-run pipeline solid
- **Runtime safety controls** (kill switch, live-execution ACK) — correctly implemented and tested
- **RSA-PSS Kalshi auth** — correct implementation with cryptography library

---

## Recommendations (Priority Order)

1. **[5 min] Fix model ID** — replace `"claude-opus-4-20250514"` with `"claude-opus-4-7"` in `oil_price.py:133`, `ceasefire.py:106`, `hormuz.py:108`. Silent production blocker for 14 days.
2. **[1 min] Add `pytz`** — append `"pytz>=2024.1"` to `[project] dependencies` in `pyproject.toml`. Unblocks 11 test failures and `--scorecard` pipeline. 27+ days unactioned.
3. **[1 hr] Fix `test_google_news.py`** — replace hardcoded April 8 `pubDate` strings with relative dates; change `max_age_hours` to `24 * 10`. Permanently broken as of May 8.
4. **[2 hrs] Update `crisis_context.py`** — inject April 12–May 12 events; revise "Current Market State"; update `Last updated: 2026-05-12`. Required before any live prediction run is meaningful.
5. **[1 hr] Fix `test_mapping_policy.py`** — update assertions to expect cost-aware `effective_edge = gross_edge - expected_total_cost`.
6. **[30 min] Align `recalibrate_probability()` predicate** — add `AND resolution_price IS NOT NULL` to count query at `scoring/recalibration.py:71`.
7. **[30 min] Add `backtest/__init__.py`** and a smoke test.
8. **[2 hrs] Wire `DbWriter` or annotate direct-write sites** — prevents future locking bugs if concurrent writes ever occur.
9. **[5 min] Update `pyproject.toml`** `requires-python` to `>=3.12`.
10. **[30 min] Update `CLAUDE.md`** tech stack section to reflect the actual Recharts polling implementation.
