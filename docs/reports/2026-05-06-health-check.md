# Parallax Health Check — 2026-05-06

**Status: YELLOW**

No code commits since 2026-05-05 (health-check-only commits for 4 days straight). Test results are unchanged at **340 passed, 27 failed**, preserving the same five failure clusters from prior reports. Two HIGH issues remain unactioned (pytz missing, deprecated model ID), and two issues have escalated in severity: the `crisis_context.py` is now 24 days stale past the original validation window, and the `test_google_news.py` fixture will completely collapse in 2 days when the Apr 08 articles age past the 30-day filter.

---

## Test Results

- **340 passed, 27 failed** — identical to 2026-05-02 and 2026-05-05
- Test suite run time: ~60s
- Python: 3.11.15 (system); pytest 8.4.2, pytest-asyncio 0.26.0, pytest-httpx 0.35
- DuckDB: 1.5.2 (installed), pyproject.toml requires >=1.2

| Failure Cluster | Count | Root Cause |
|---|---|---|
| `test_scorecard.py` | 10 | Missing `pytz` — DuckDB TIMESTAMPTZ queries crash |
| `test_mapping_policy.py` | 10 | Stale assertions expect old proxy-discount model, not cost-aware model |
| `test_recalibration.py` | 4 | Count gate (`model_was_correct IS NOT NULL`) diverges from calibration view (`resolution_price IS NOT NULL`) |
| `test_ops_events.py` | 1 | Missing `pytz` — TIMESTAMPTZ column query crashes |
| `test_llm_usage.py` | 1 | Missing `pytz` — TIMESTAMPTZ column query crashes |
| `test_google_news.py` | 1 | Time-dependent fixture: Apr 08 articles will age out in **2 days** (May 8), escalating from `assert 3 == 4` to `assert 0 == 4` |

---

## Issues Found

### HIGH (NEW) — `crisis_context.py` is 24 Days Stale; Validation Window Has Passed

`backend/src/parallax/prediction/crisis_context.py` was last updated **2026-04-12** (line: `"Last updated: 2026-04-12"`). The file's "Current Market State" section states:

> *"Ceasefire: fragile, 10 days remaining."*

Today is 2026-05-06. That 10-day ceasefire window expired ~April 21-22. The CLAUDE.md validation deadline of "April 7-21 2026" has passed. Every live prediction run since April 12 has been injecting a 24-day-stale market snapshot into all three prediction models (oil price, ceasefire, Hormuz reopening). Model output is conditioned on fundamentally incorrect market state.

- **Severity**: HIGH — all live prediction runs produce stale-context outputs; model reasoning about "10 days remaining" in the ceasefire is meaningless
- **Fix**: Update `crisis_context.py` with events from April 12–May 6, revise "Current Market State" section, and update `Last updated` timestamp
- **Open since**: 2026-04-13 (first run after last update)

---

### HIGH (ESCALATING) — `test_google_news.py` Fixture Will Completely Collapse in 2 Days

The test `test_fetches_and_deduplicates` asserts `len(events) == 4` with `max_age_hours=24*30` (30-day filter). Current state:

- `Mon, 31 Mar 2026` article: **already excluded** (36 days old) → test currently fails `assert 3 == 4`
- `Tue, 08 Apr 2026` articles (3 items): will age past the 30-day cutoff on **May 8** (2 days from now)

On May 8, `fetch_google_news` will return 0 events, causing:
1. `assert urls.count("https://example.com/article1") == 1` → fails (count = 0)
2. `assert len(events) == 4` → fails (len = 0)

The test will go from 1 failing assertion to 2, with a completely misleading `assert 0 == 4` error.

- **Severity**: HIGH — test is actively deteriorating; the fixture has no self-healing mechanism; fails permanently after May 8
- **Fix (minimal)**: Replace hardcoded `pubDate` strings with relative dates, e.g. `(datetime.now(UTC) - timedelta(days=N)).strftime(RFC_2822_FORMAT)` with N=5, N=7, N=25; update `max_age_hours` assertion comment
- **Open since**: ~2026-04-30 (failure state); NOW ESCALATING with 2-day deadline

---

### HIGH (PERSISTENT, 21+ days) — `pytz` Missing from `pyproject.toml`

DuckDB 1.5.2 raises `InvalidInputException: Required module 'pytz' failed to import` on any query returning a `TIMESTAMPTZ` column. Affects `runs.started_at/ended_at`, `daily_scorecard.computed_at`, `ops_events.created_at`, `llm_usage.created_at`. The `--scorecard` CLI flag is completely broken in any clean environment.

- **Severity**: HIGH — blocks 12 tests; breaks the `--scorecard` pipeline
- **Fix**: Add `"pytz>=2024.1"` to `[project] dependencies` in `backend/pyproject.toml`
- **Open since**: ~2026-04-15 (21 days)

---

### HIGH (PERSISTENT, 8 days) — Deprecated Claude Model ID Blocks Live Runs

`oil_price.py:132`, `ceasefire.py:106`, and `hormuz.py` call `ensemble_predict()` with `model="claude-opus-4-20250514"`. Valid current IDs are `claude-opus-4-7`, `claude-sonnet-4-6`, `claude-haiku-4-5-20251001`. An invalid model string will cause the Anthropic API to reject every live prediction call.

- **Severity**: HIGH — silent production blocker; no test catches a wrong model ID
- **Fix**: Replace `"claude-opus-4-20250514"` with `"claude-opus-4-7"` in all three prediction files; verify routing before next live run
- **Open since**: 2026-04-29 (8 days)

---

### MEDIUM (PERSISTENT) — `test_mapping_policy.py` Stale Assertions (10 failures)

`MappingPolicy.evaluate()` now computes `effective_edge = gross_edge - expected_total_cost`. Test assertions were written against the old proxy-discount model where `effective_edge = raw_edge × confidence_discount`. Production logic is correct; tests are stale.

- **Severity**: MEDIUM — production code correct; tests mislead
- **Fix**: Update `TestDirectProxyDiscount`, `TestNearProxyDiscount`, `TestLooseProxyDiscount`, `TestProbabilityInversion`, `TestAboveThreshold`, `TestSortedByEffectiveEdge`, `TestDiscountFromHistory` to assert `effective_edge = raw_edge - expected_total_cost`

---

### MEDIUM (PERSISTENT) — Calibration Predicate Mismatch (4 failures)

`recalibrate_probability()` at `scoring/recalibration.py:70` counts qualifying signals with `model_was_correct IS NOT NULL`. The downstream `calibration_curve()` view also requires `resolution_price IS NOT NULL`. Test fixtures populate `model_was_correct` without `resolution_price`, so the count gate passes but calibration curve returns nothing.

- **Severity**: MEDIUM — mechanical recalibration is untestable; behavior under low-data conditions unvalidated
- **Fix (preferred)**: Add `AND resolution_price IS NOT NULL` to the count query in `recalibrate_probability()`

---

### MEDIUM (PERSISTENT) — Direct DB Writes Bypass `DbWriter` Single-Writer Pattern

The spec mandates all writes go through `asyncio.Queue → DbWriter`. The following modules write directly via `conn.execute()`:

| File | Lines | Table |
|---|---|---|
| `ops/alerts.py` | 106 | `ops_events` |
| `scoring/ledger.py` | 225, 256 | `signal_ledger` |
| `scoring/resolution.py` | 60, 124 | `signal_ledger` |
| `budget/tracker.py` | 43 | `llm_usage` |
| `scoring/scorecard.py` | 21 | `daily_scorecard` |
| `cli/brief.py` | 49, 68, 350 | `runs`, `market_prices` |

Risk is LOW while CLI runs sequentially but becomes HIGH if any write endpoint is active concurrently with the FastAPI server.

- **Severity**: MEDIUM (latent HIGH)
- **Fix**: Wire `DbWriter` to all write sites, or annotate each with `# SINGLE_PROCESS_ONLY` and add a guard in `main.py`

---

### LOW (PERSISTENT) — `backtest/` Module Missing `__init__.py`

`backend/src/parallax/backtest/engine.py` has no `__init__.py`, making it unimportable as `parallax.backtest`. Not in the CLAUDE.md module map. No test file.

- **Severity**: LOW — not on critical path; backtest unused in production
- **Fix**: Add `backend/src/parallax/backtest/__init__.py` (empty) + smoke test `test_backtest.py`

---

### LOW (PERSISTENT) — Multiple `duckdb.connect()` Calls in `brief.py`

`run_brief()` and helper functions each open separate DuckDB connections. Concurrent execution with the FastAPI server will deadlock.

- **Severity**: LOW — no current concurrent usage; trap for future development
- **Fix**: Open one connection at CLI entrypoint and thread it through as a parameter

---

### LOW (PERSISTENT) — Python Version Requirement Weaker Than Spec

`pyproject.toml` declares `requires-python = ">=3.11"`. CLAUDE.md and the design spec both state Python 3.12. System runtime is Python 3.11.15.

- **Severity**: LOW — cosmetic mismatch, no current breakage
- **Fix**: Update to `requires-python = ">=3.12"` and upgrade deployment environment

---

### LOW (PERSISTENT) — `CLAUDE.md` Tech Stack Contains Stale Entries

CLAUDE.md lists `deck.gl`, `MapLibre GL`, `h3-js`, `react-map-gl`, `sentence-transformers`, `searoute`, `shapely`, `google-cloud-bigquery`, and `websockets` as active dependencies. None appear in `pyproject.toml` or `frontend/package.json`. The frontend is a Recharts polling dashboard, not a deck.gl hex map.

- **Severity**: LOW — onboarding confusion; no runtime impact
- **Fix**: Rewrite the Technology Stack section of CLAUDE.md to reflect the actual stack

---

## Spec / Plan Consistency

The original Phase 1 spec described ~50 LLM agents with H3 spatial visualization. The implementation deliberately pivoted to 3 Claude prediction models + Kalshi/Polymarket market data + paper-trading signal ledger. Pivot is intentional and documented. The validation deadline of April 7-21 has now passed without updates to crisis context or model IDs.

| Spec Item | Status |
|---|---|
| `agents/` — 50-agent country/sub-actor swarm | Out of scope (deliberate pivot) |
| `spatial/` — H3 hexagon model, deck.gl | Out of scope (deliberate pivot) |
| `api/auth.py` — invite codes, admin password | Not implemented |
| `api/websocket.py` — real-time push | Not implemented; frontend uses polling |
| `simulation/circuit_breaker.py` — escalation limits | Not implemented |
| `ingestion/dedup.py` — semantic deduplication | Not implemented |
| Prediction models (oil_price, ceasefire, hormuz) | Implemented; deprecated model ID blocks live runs |
| `crisis_context.py` — post-cutoff timeline for LLMs | Implemented but **24 days stale** |
| Kalshi + Polymarket clients | Implemented and tested |
| Signal ledger, paper trading, portfolio allocator | Implemented and tested |
| Divergence detector | Implemented and tested |
| Contract registry + mapping policy | Implemented; tests stale (10 failures) |
| Daily scorecard ETL | Implemented; `pytz` bug blocks runtime |

---

## Dependency Audit

| Package | `pyproject.toml` | Installed | Action |
|---|---|---|---|
| `pytz>=2024.1` | **MISSING** | Not installed | **Add immediately** |
| `fastapi>=0.115` | Present | Not installed in test env (install conflict) | OK in full venv |
| `truthbrush>=0.2` | Present | Not installed in test env | OK in full venv |
| `duckdb>=1.2` | Present | 1.5.2 | OK — newer version compatible |
| `cryptography>=44.0` | Present | 41.0.7 (system debian pkg) | Version below minimum; install conflict in this env |
| `anthropic>=0.52` | Present | 0.52+ | OK |
| `h3>=4.1` | Missing | Not installed | Defer to Phase 2 |
| `sentence-transformers>=3.4` | Missing | Not installed | Not used in current pivot |
| `searoute>=1.3` | Missing | Not installed | Not used in current pivot |
| `shapely>=2.0` | Missing | Not installed | Not used in current pivot |
| `google-cloud-bigquery>=3.27` | Missing | Not installed | Not used (GDELT DOC API used instead) |
| `websockets>=14.0` | Missing | Not installed | Not used in current pivot |

No CVEs identified in declared dependencies at their minimum declared versions.

---

## Positive Findings

- **340/367 tests pass** — 92.6% pass rate; no regression since 2026-04-21 (16 days stable)
- **No secrets in repo** — `.env.example` uses placeholders only
- **AsyncAnthropic client** used everywhere; no accidental sync client instantiations
- **Cascade engine + scenario config** fully implemented and unit-tested
- **Budget guard and alert dispatcher** wired and tested
- **Contract registry, divergence detector, portfolio simulator** function correctly per test suite
- **`backtest/engine.py`** monkey-patch protected by `try-finally` (no context leak)
- **`DbWriter`** single-writer implementation correct where used
- **`test_brief.py` (24 tests) and `test_crisis_context.py` (9 tests)** — all pass; signal ledger and dry-run pipeline are solid

---

## Recommendations (Priority Order)

1. **Update `crisis_context.py`** — inject April 12–May 6 events, correct "Current Market State" section; this is the single highest-impact action for live prediction quality. The validation window has passed without this update.
2. **Fix `test_google_news.py` fixture NOW** — replace hardcoded `pubDate` strings with relative dates (e.g. `timedelta(days=5)` from `datetime.now(UTC)`). In 2 days the test cascades from 1 failing assertion to 2 with a completely uninformative error.
3. **Add `pytz>=2024.1` to `pyproject.toml`** — one line, unblocks 12 test failures and fixes `--scorecard` in clean envs. Open 21 days.
4. **Update Claude model ID** — replace `"claude-opus-4-20250514"` with `"claude-opus-4-7"` in `oil_price.py`, `ceasefire.py`, `hormuz.py`. Silent production blocker for live prediction runs.
5. **Fix `test_mapping_policy.py` stale assertions** — update to expect cost-aware `effective_edge = raw_edge - expected_total_cost`.
6. **Align `recalibrate_probability()` predicate** — add `resolution_price IS NOT NULL` to the count query.
7. **Add `backtest/__init__.py`** and a smoke test.
8. **Wire `DbWriter` or annotate direct-write sites** with `# SINGLE_PROCESS_ONLY`.
9. **Update `pyproject.toml`** `requires-python` to `>=3.12`.
10. **Update `CLAUDE.md`** tech stack to reflect the actual implementation.
