# Parallax Health Check — 2026-05-10

**Status: YELLOW**

Test results unchanged at **340 passed, 27 failed** (92.6% pass rate) — zero fixes and zero regressions since the 2026-05-09 report; no commits to main since the May 9 health-check commit. All four HIGH issues from yesterday have aged one more day without action: `pytz` missing (25+ days), deprecated model ID (12 days), stale crisis context (28 days), and broken `test_google_news.py` fixture (2 days since detonation).

---

## Test Results

- **340 passed, 27 failed** — identical to 2026-05-02 through 2026-05-09 (9 consecutive days)
- Test suite run time: ~79s
- Python: 3.11.15 (system); pytest 8.4.2, pytest-asyncio 0.26.0, pytest-httpx 0.35.0
- DuckDB: 1.5.2 installed; `pyproject.toml` requires `>=1.2`

| Failure Cluster | Count | Root Cause |
|---|---|---|
| `test_scorecard.py` | 10 | Missing `pytz` — DuckDB `TIMESTAMPTZ` queries crash |
| `test_mapping_policy.py` | 12 | Stale assertions expect old proxy-discount model, not cost-aware fair-value model |
| `test_recalibration.py` | 4 | Count gate (`model_was_correct IS NOT NULL`) diverges from calibration view (`resolution_price IS NOT NULL`) |
| `test_ops_events.py` | 1 | Missing `pytz` — `TIMESTAMPTZ` column query crashes |
| `test_llm_usage.py` | 1 | Missing `pytz` — `TIMESTAMPTZ` column query crashes |
| `test_google_news.py` | 1 | **BROKEN** — Apr 08 articles aged past 30-day filter; `fetch_google_news` returns `[]` |

---

## Issues Found

### HIGH (ESCALATING, 28 days) — `crisis_context.py` Stale; Validation Window Expired

`backend/src/parallax/prediction/crisis_context.py` header reads `Last updated: 2026-04-12`. Today is 2026-05-10 — **28 days stale**. The "Current Market State" section describes a ceasefire with "10 days remaining" that expired April 21–22. The CLAUDE.md validation deadline of "April 7–21 2026" has passed.

Every live prediction run injects this stale context into all three models (oil_price, ceasefire, hormuz_reopening). All model reasoning about the ceasefire, Hormuz status, and current Brent pricing is conditioned on fundamentally incorrect market state.

- **Severity**: HIGH — all live prediction outputs are conditioned on 28-day-stale context
- **Fix**: Update with events from April 12–May 10; revise "Current Market State" section; update `Last updated: 2026-05-10`
- **Open since**: 2026-04-13 (28 days unactioned)

---

### HIGH (12 days) — Deprecated Claude Model ID Blocks Live Prediction Runs

`oil_price.py:133`, `ceasefire.py:106`, and `hormuz.py:108` all call `ensemble_predict()` with `model="claude-opus-4-20250514"`. This is not a valid Anthropic model ID — valid current IDs are `claude-opus-4-7`, `claude-sonnet-4-6`, `claude-haiku-4-5-20251001`. Every live prediction call will be rejected by the Anthropic API.

- **Severity**: HIGH — silent production blocker; no test validates the model ID string
- **Fix**: Replace `"claude-opus-4-20250514"` with `"claude-opus-4-7"` in all three prediction files
- **Open since**: 2026-04-28 (12 days unactioned)

---

### HIGH (25+ days) — `pytz` Missing from `pyproject.toml`

DuckDB 1.5.2 raises `InvalidInputException: Required module 'pytz' failed to import` on any query returning a `TIMESTAMPTZ` column. Affects `runs.started_at/ended_at`, `daily_scorecard.computed_at`, `ops_events.created_at`, `llm_usage.created_at`. The `--scorecard` CLI flag is completely broken in any clean-install environment.

- **Severity**: HIGH — blocks 12 tests; breaks `--scorecard` pipeline in clean envs
- **Fix**: Add `"pytz>=2024.1"` to `[project] dependencies` in `backend/pyproject.toml`
- **Open since**: ~2026-04-15 (25+ days unactioned)

---

### HIGH (2 days) — `test_google_news.py` Fixture Returns Empty List

`test_fetches_and_deduplicates` uses hardcoded `pubDate` strings referencing April 8, 2026 articles with `max_age_hours=24*30` (30-day window). As of May 8, all articles are older than 30 days; `fetch_google_news` returns `[]`, causing:

```
AssertionError: assert 0 == 1
  where 0 = [].count("https://example.com/article1")
```

This failure is permanent until the fixture is fixed. The test has no self-healing mechanism.

- **Severity**: HIGH — test permanently broken; fixture has no self-healing mechanism
- **Fix**: Replace hardcoded `pubDate` strings with relative dates computed at test runtime:
  ```python
  from datetime import datetime, timedelta, timezone
  RFC_2822 = "%a, %d %b %Y %H:%M:%S GMT"
  date_5d_ago = (datetime.now(timezone.utc) - timedelta(days=5)).strftime(RFC_2822)
  ```
  Update all 4 `pubDate` entries in `CANNED_RSS` and `DUPLICATE_RSS`; set `max_age_hours` to 10 days.
- **Open since**: 2026-05-08 (detonated)

---

### MEDIUM (PERSISTENT) — `test_mapping_policy.py` Stale Assertions (12 failures)

`MappingPolicy.evaluate()` was refactored from a proxy-discount model (`effective_edge = raw_edge × confidence_discount`) to a cost-aware fair-value model (`effective_edge = net_edge = gross_edge - expected_total_cost`). The `confidence_discount` field is now hardcoded to `1.0`. Test assertions were written against the old architecture and have never been updated.

Confirmed failure examples today:
- `test_direct_proxy_full_edge`: expects `effective_edge == raw_edge` (no cost deduction); actual `effective_edge = raw_edge - costs`
- `test_near_proxy_discounted_edge`: expects `confidence_discount == 0.6`; actual `== 1.0`
- `test_inverted_probability`: expects `raw_edge == -0.2`; actual `== 0.16`
- `test_above_threshold_trades`: expects `should_trade is True`; `cost_blocked` because cost > gross edge

- **Severity**: MEDIUM — production code is correct; tests mislead and mask future regressions
- **Fix**: Rewrite affected assertions to expect `effective_edge = gross_edge - expected_total_cost`; remove `confidence_discount` assertions or replace with `assert result.confidence_discount == 1.0`

---

### MEDIUM (PERSISTENT) — Calibration Predicate Mismatch (4 failures)

`recalibrate_probability()` (`scoring/recalibration.py:70`) counts qualifying signals with:
```sql
WHERE model_id = ? AND model_was_correct IS NOT NULL
```
The downstream `calibration_curve()` queries from the `signal_quality_evaluation` view, which additionally requires `resolution_price IS NOT NULL`. Test fixtures populate `model_was_correct` without `resolution_price`, so the count gate passes (≥10 signals found) but `calibration_curve()` returns empty, and recalibration silently does nothing.

- **Severity**: MEDIUM — mechanical recalibration is untestable; behavior under sufficient-data conditions unvalidated
- **Fix**: Add `AND resolution_price IS NOT NULL` to the count query in `recalibrate_probability()` to align the gate with the curve query

---

### MEDIUM (PERSISTENT) — Direct DB Writes Bypass `DbWriter` Single-Writer Pattern

The spec mandates all writes go through `asyncio.Queue → DbWriter`. The following modules still write directly via `conn.execute()`:

| File | Lines | Table(s) |
|---|---|---|
| `ops/alerts.py` | 106 | `ops_events` |
| `scoring/ledger.py` | 225, 256 | `signal_ledger` |
| `scoring/resolution.py` | 60, 124 | `signal_ledger` |
| `budget/tracker.py` | 43 | `llm_usage` |
| `scoring/scorecard.py` | ~21 | `daily_scorecard` |
| `cli/brief.py` | 49, 68, 350 | `runs`, `market_prices` |

Risk is LOW while the CLI runs sequentially but becomes HIGH if any write endpoint runs concurrently with the FastAPI server.

- **Severity**: MEDIUM (latent HIGH)
- **Fix**: Wire `DbWriter` to all write sites, or annotate each with `# SINGLE_PROCESS_ONLY` and add a startup guard in `main.py`

---

### LOW (PERSISTENT) — `backtest/` Module Missing `__init__.py`

`backend/src/parallax/backtest/engine.py` exists with no `__init__.py` sibling, making it unimportable as `parallax.backtest`. The module is absent from the CLAUDE.md module map and has no test file.

- **Severity**: LOW — not on critical path; backtest unused in production
- **Fix**: Add `backend/src/parallax/backtest/__init__.py` (empty) + smoke test `test_backtest.py`

---

### LOW (PERSISTENT) — Python Version Requirement Weaker Than Spec

`pyproject.toml` declares `requires-python = ">=3.11"`. CLAUDE.md and the design spec both state Python 3.12. System runtime is Python 3.11.15.

- **Severity**: LOW — cosmetic mismatch, no current breakage
- **Fix**: Update to `requires-python = ">=3.12"` and upgrade the deployment environment

---

### LOW (PERSISTENT) — `CLAUDE.md` Tech Stack Lists Uninstalled Dependencies

CLAUDE.md lists `deck.gl`, `MapLibre GL`, `h3-js`, `react-map-gl`, `sentence-transformers`, `searoute`, `shapely`, `google-cloud-bigquery`, and `websockets` as active dependencies. None appear in `pyproject.toml` or `frontend/package.json`. The frontend is a Recharts polling dashboard, not a deck.gl hex map.

- **Severity**: LOW — onboarding confusion; no runtime impact
- **Fix**: Rewrite the Technology Stack section of CLAUDE.md to reflect the actual stack (FastAPI + DuckDB + React + Recharts + polling)

---

## Spec / Plan Consistency

The original Phase 1 spec described ~50 LLM agents with H3 spatial visualization. The implementation deliberately pivoted to 3 Claude prediction models + Kalshi/Polymarket market data + paper-trading signal ledger. The pivot is intentional and well-understood. The most pressing spec-consistency gap remains the stale prediction infrastructure.

| Spec Item | Status |
|---|---|
| `agents/` — 50-agent country/sub-actor swarm | Out of scope (deliberate pivot) |
| `spatial/` — H3 hexagon model, deck.gl | Out of scope (deliberate pivot) |
| `api/auth.py` — invite codes, admin password | Not implemented |
| `api/websocket.py` — real-time push | Not implemented; frontend uses polling |
| `simulation/circuit_breaker.py` — escalation limits | Not implemented |
| `ingestion/dedup.py` — semantic deduplication | Not implemented |
| Prediction models (oil_price, ceasefire, hormuz) | Implemented; **deprecated model ID blocks live runs** |
| `crisis_context.py` — post-cutoff timeline for LLMs | Implemented but **28 days stale** |
| Kalshi + Polymarket clients | Implemented and tested |
| Signal ledger, paper trading, portfolio allocator | Implemented and tested |
| Divergence detector | Implemented and tested |
| Contract registry + mapping policy | Implemented; tests stale (12 failures) |
| Daily scorecard ETL | Implemented; `pytz` bug blocks runtime |

---

## Dependency Audit

| Package | `pyproject.toml` | Installed | Action |
|---|---|---|---|
| `pytz>=2024.1` | **MISSING** | Not installed | **Add immediately — 25+ days unactioned** |
| `fastapi>=0.115` | Present | Not installed in test env | OK in full venv |
| `truthbrush>=0.2` | Present | Not installed in test env | OK in full venv |
| `duckdb>=1.2` | Present | 1.5.2 | OK |
| `cryptography>=44.0` | Present | 41.0.7 (Debian system pkg) | Version below minimum; install conflict in this env |
| `anthropic>=0.52` | Present | 0.52+ | OK |
| `h3>=4.1` | Missing | Not installed | Not needed in current architecture |
| `sentence-transformers>=3.4` | Missing | Not installed | Not needed in current architecture |
| `searoute>=1.3` | Missing | Not installed | Not needed in current architecture |
| `shapely>=2.0` | Missing | Not installed | Not needed in current architecture |
| `google-cloud-bigquery>=3.27` | Missing | Not installed | Not needed (GDELT DOC API used instead) |
| `websockets>=14.0` | Missing | Not installed | Not needed in current architecture |

No CVEs identified in declared dependencies at their minimum declared versions.

Frontend dependencies (`react ^18.3.1`, `recharts ^2.15.0`, `vite ^6.0.0`, `typescript ~5.6.2`) are current and not flagged for CVEs.

---

## Positive Findings

- **340/367 tests pass** — 92.6% pass rate stable since 2026-04-21 (19 consecutive days, no regressions)
- **No secrets in repo** — `.env.example` uses placeholders only
- **`AsyncAnthropic` client** used everywhere; no accidental sync client instantiations
- **Cascade engine + scenario config** fully implemented and unit-tested
- **Budget guard and alert dispatcher** wired and tested
- **Contract registry, divergence detector, portfolio simulator** function correctly per test suite
- **`DbWriter`** single-writer implementation is correct where used
- **`test_brief.py` (24 tests) and `test_crisis_context.py` (9 tests)** — all pass; dry-run pipeline and signal ledger are solid

---

## Recommendations (Priority Order)

1. **Fix `test_google_news.py` fixture** — replace hardcoded `pubDate` strings with relative dates (e.g., `datetime.now(UTC) - timedelta(days=5)`). Test is permanently broken as of May 8.
2. **Update Claude model ID** — replace `"claude-opus-4-20250514"` with `"claude-opus-4-7"` in `oil_price.py`, `ceasefire.py`, `hormuz.py`. Silent production blocker. 12 days unactioned.
3. **Update `crisis_context.py`** — inject April 12–May 10 events, revise "Current Market State," update timestamp. 28 days stale.
4. **Add `pytz>=2024.1` to `pyproject.toml`** — one-line fix, unblocks 12 test failures and fixes `--scorecard` in clean environments. 25+ days unactioned.
5. **Fix `test_mapping_policy.py` stale assertions** — update to expect cost-aware `effective_edge = gross_edge - expected_total_cost`.
6. **Align `recalibrate_probability()` predicate** — add `AND resolution_price IS NOT NULL` to the count query.
7. **Add `backtest/__init__.py`** and a smoke test.
8. **Wire `DbWriter` or annotate direct-write sites** with `# SINGLE_PROCESS_ONLY`.
9. **Update `pyproject.toml`** `requires-python` to `>=3.12`.
10. **Update `CLAUDE.md`** tech stack section to reflect the actual implementation.
