# Parallax Health Check — 2026-05-11

**Status: YELLOW**

Test results unchanged at **27 failed, 302 passed** (302/329 = 91.8% in this env; prior full-venv baseline was 340/367 = 92.6%) — zero code changes since the 2026-05-10 health-check commit. All four HIGH issues have aged one more day: `pytz` missing (26+ days), deprecated model ID (13 days), stale crisis context (29 days), broken `test_google_news.py` fixture (3 days). The streak of consecutive YELLOW days is now **10** days.

---

## Test Results

- **27 failed, 302 passed** — identical failure set to 2026-05-02 through 2026-05-10 (10 consecutive days)
- Env note: `fastapi` and `truthbrush` not installed in test runner → `test_dashboard_endpoints.py` and `test_truth_social.py` excluded from collection (both pass in full venv; excluded here only due to missing deps)
- Python: 3.11.15 (system); pytest 8.4.2, pytest-asyncio 0.26.0, pytest-httpx 0.35.0
- DuckDB: 1.5.2 installed; `pyproject.toml` requires `>=1.2`

| Failure Cluster | Count | Root Cause |
|---|---|---|
| `test_scorecard.py` | 9 | Missing `pytz` — DuckDB `TIMESTAMPTZ` queries crash |
| `test_mapping_policy.py` | 11 | Stale assertions expect old proxy-discount model, not cost-aware fair-value model |
| `test_recalibration.py` | 4 | Count gate (`model_was_correct IS NOT NULL`) diverges from calibration view (`resolution_price IS NOT NULL`) |
| `test_ops_events.py` | 1 | Missing `pytz` — `TIMESTAMPTZ` column query crashes |
| `test_llm_usage.py` | 1 | Missing `pytz` — `TIMESTAMPTZ` column query crashes |
| `test_google_news.py` | 1 | Hardcoded April 8 pubDates now 33 days old; 30-day filter returns `[]` |

### Complete Failing Test List

```
tests/test_google_news.py::TestFetchGoogleNews::test_fetches_and_deduplicates
tests/test_llm_usage.py::test_record_persists_llm_usage_row_with_run_id
tests/test_mapping_policy.py::TestAboveThreshold::test_above_threshold_trades
tests/test_mapping_policy.py::TestDirectProxyDiscount::test_direct_proxy_full_edge
tests/test_mapping_policy.py::TestDiscountFromHistory::test_evaluate_uses_updated_discounts
tests/test_mapping_policy.py::TestDiscountFromHistory::test_high_hit_rate_raises_discount
tests/test_mapping_policy.py::TestDiscountFromHistory::test_loose_proxy_ceiling
tests/test_mapping_policy.py::TestDiscountFromHistory::test_low_hit_rate_lowers_discount
tests/test_mapping_policy.py::TestLooseProxyDiscount::test_loose_proxy_discounted_edge
tests/test_mapping_policy.py::TestNearProxyDiscount::test_near_proxy_discounted_edge
tests/test_mapping_policy.py::TestProbabilityInversion::test_inverted_probability
tests/test_mapping_policy.py::TestSortedByEffectiveEdge::test_sorted_descending
tests/test_ops_events.py::test_duckdb_alert_sink_persists_alert_event
tests/test_recalibration.py::TestCalibrationCurveModelFilter::test_model_id_filter
tests/test_recalibration.py::TestCalibrationCurveModelFilter::test_no_model_id_returns_global
tests/test_recalibration.py::TestRecalibrateProbability::test_above_min_signals_adjusts_probability
tests/test_recalibration.py::TestRecalibrateProbability::test_offset_capped_at_max
tests/test_scorecard.py::TestDataQualityMetrics::test_executable_coverage
tests/test_scorecard.py::TestDataQualityMetrics::test_quote_staleness
tests/test_scorecard.py::TestOpsMetrics::test_llm_cost
tests/test_scorecard.py::TestOpsMetrics::test_run_count
tests/test_scorecard.py::TestOpsMetrics::test_run_success_rate
tests/test_scorecard.py::TestScorecardComputation::test_brier_score_computed
tests/test_scorecard.py::TestScorecardComputation::test_scorecard_writes_to_table
tests/test_scorecard.py::TestScorecardComputation::test_signal_quality_metrics
tests/test_scorecard.py::TestScorecardComputation::test_tradeability_funnel
tests/test_scorecard.py::TestScorecardIdempotent::test_rerun_overwrites
```

---

## Issues Found

### HIGH (ESCALATING, 29 days) — `crisis_context.py` Stale; Validation Window Expired

`backend/src/parallax/prediction/crisis_context.py` header reads `Last updated: 2026-04-12`. Today is 2026-05-11 — **29 days stale**. The "Current Market State" section describes a ceasefire with "10 days remaining" that expired April 21–22. Every live prediction run injects this stale context into all three models (`oil_price`, `ceasefire`, `hormuz_reopening`). All model reasoning about the ceasefire status, Hormuz conditions, and current Brent pricing is conditioned on fundamentally incorrect market state.

- **Severity**: HIGH — all live prediction outputs conditioned on 29-day-stale context
- **Fix**: Update with events from April 12–May 11; revise "Current Market State" section; update `Last updated: 2026-05-11`
- **Open since**: 2026-04-13 (29 days unactioned)

---

### HIGH (13 days) — Deprecated Claude Model ID Blocks Live Prediction Runs

`oil_price.py:133`, `ceasefire.py:106`, and `hormuz.py:108` all call `ensemble_predict()` with `model="claude-opus-4-20250514"`. This is not a valid Anthropic model ID — valid current IDs are `claude-opus-4-7`, `claude-sonnet-4-6`, `claude-haiku-4-5-20251001`. Every live prediction call is rejected by the Anthropic API with a 404/invalid model error.

- **Severity**: HIGH — silent production blocker; no test validates the model ID string
- **Fix**: Replace `"claude-opus-4-20250514"` with `"claude-opus-4-7"` in `oil_price.py:133`, `ceasefire.py:106`, `hormuz.py:108`
- **Open since**: 2026-04-28 (13 days unactioned)

---

### HIGH (26+ days) — `pytz` Missing from `pyproject.toml`

DuckDB 1.5.2 raises `InvalidInputException: Required module 'pytz' failed to import` on any query returning a `TIMESTAMPTZ` column. Affects `runs.started_at/ended_at`, `daily_scorecard.computed_at`, `ops_events.created_at`, `llm_usage.created_at`. The `--scorecard` CLI flag is completely broken in any clean-install environment; 11 tests fail as a direct result.

- **Severity**: HIGH — blocks 11 tests; breaks `--scorecard` pipeline in clean envs
- **Fix**: Add `"pytz>=2024.1"` to `[project] dependencies` in `backend/pyproject.toml`
- **Open since**: ~2026-04-15 (26+ days unactioned)

---

### HIGH (3 days) — `test_google_news.py` Fixture Returns Empty List

`test_fetches_and_deduplicates` uses hardcoded `pubDate` strings referencing April 8, 2026 articles with `max_age_hours=24*30` (30-day window). As of today (May 11), all articles are 33 days old; `fetch_google_news` returns `[]`, causing `AssertionError: assert 0 == 1`. This failure is permanent until fixed.

- **Severity**: HIGH — test permanently broken; detonated May 8
- **Fix**: Replace hardcoded `pubDate` strings with relative dates computed at test runtime:
  ```python
  from datetime import datetime, timedelta, timezone
  RFC_2822 = "%a, %d %b %Y %H:%M:%S GMT"
  date_5d_ago = (datetime.now(timezone.utc) - timedelta(days=5)).strftime(RFC_2822)
  ```
  Update all 4 `pubDate` entries in `CANNED_RSS` and `DUPLICATE_RSS`; change `max_age_hours` to `24 * 10`.
- **Open since**: 2026-05-08 (3 days)

---

### MEDIUM (PERSISTENT) — `test_mapping_policy.py` Stale Assertions (11 failures)

`MappingPolicy.evaluate()` was refactored from a proxy-discount model to a cost-aware fair-value model (`effective_edge = gross_edge - expected_total_cost`). `confidence_discount` is now hardcoded to `1.0`. Test assertions were written against the old architecture and have never been updated. Confirmed failures: `test_direct_proxy_full_edge`, `test_near_proxy_discounted_edge`, `test_inverted_probability`, `test_above_threshold_trades`, `test_sorted_descending`, plus all 4 `TestDiscountFromHistory` tests.

- **Severity**: MEDIUM — production code is correct; tests mislead and mask future regressions
- **Fix**: Rewrite affected assertions to expect `effective_edge = gross_edge - expected_total_cost`; replace `confidence_discount` assertions with `assert result.confidence_discount == 1.0`

---

### MEDIUM (PERSISTENT) — Calibration Predicate Mismatch (4 failures)

`recalibrate_probability()` (`scoring/recalibration.py:70`) counts qualifying signals with `WHERE model_id = ? AND model_was_correct IS NOT NULL`. The downstream `calibration_curve()` queries from `signal_quality_evaluation` view, which additionally requires `resolution_price IS NOT NULL`. Test fixtures populate `model_was_correct` without `resolution_price`, so the count gate passes but `calibration_curve()` returns empty, and recalibration silently does nothing.

- **Severity**: MEDIUM — mechanical recalibration untestable; behavior under sufficient-data conditions unvalidated
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

- **Severity**: LOW — not on critical path
- **Fix**: Add `backend/src/parallax/backtest/__init__.py` (empty) + smoke test

---

### LOW (PERSISTENT) — Python Version Requirement Weaker Than Spec

`pyproject.toml` declares `requires-python = ">=3.11"`. CLAUDE.md and the design spec both state Python 3.12. System runtime is Python 3.11.15.

- **Severity**: LOW — cosmetic mismatch, no current breakage
- **Fix**: Update to `requires-python = ">=3.12"` and upgrade deployment environment

---

### LOW (PERSISTENT) — `CLAUDE.md` Tech Stack Lists Uninstalled Dependencies

CLAUDE.md lists `deck.gl`, `MapLibre GL`, `h3-js`, `react-map-gl`, `sentence-transformers`, `searoute`, `shapely`, `google-cloud-bigquery`, and `websockets` as active dependencies. None appear in `pyproject.toml` or `frontend/package.json`. The frontend is a Recharts polling dashboard, not a deck.gl hex map.

- **Severity**: LOW — onboarding confusion; no runtime impact
- **Fix**: Rewrite the Technology Stack section of CLAUDE.md to reflect the actual stack (FastAPI + DuckDB + React + Recharts + polling)

---

## Spec / Plan Consistency

The original Phase 1 spec described ~50 LLM agents with H3 spatial visualization. The implementation deliberately pivoted to 3 Claude prediction models + Kalshi/Polymarket market data + paper-trading signal ledger. The pivot is intentional and well-understood.

| Spec Item | Status |
|---|---|
| `agents/` — 50-agent country/sub-actor swarm | Out of scope (deliberate pivot) |
| `spatial/` — H3 hexagon model, deck.gl | Out of scope (deliberate pivot) |
| `api/auth.py` — invite codes, admin password | Not implemented |
| `api/websocket.py` — real-time push | Not implemented; frontend uses polling |
| `simulation/circuit_breaker.py` — escalation limits | Not implemented |
| `ingestion/dedup.py` — semantic deduplication | Not implemented |
| Prediction models (oil_price, ceasefire, hormuz) | Implemented; **deprecated model ID blocks live runs** |
| `crisis_context.py` — post-cutoff timeline for LLMs | Implemented but **29 days stale** |
| Kalshi + Polymarket clients | Implemented and tested |
| Signal ledger, paper trading, portfolio allocator | Implemented and tested |
| Divergence detector | Implemented and tested |
| Contract registry + mapping policy | Implemented; tests stale (11 failures) |
| Daily scorecard ETL | Implemented; `pytz` bug blocks runtime |

---

## Dependency Audit

| Package | `pyproject.toml` | Installed | Action |
|---|---|---|---|
| `pytz>=2024.1` | **MISSING** | Not installed | **Add immediately — 26+ days unactioned** |
| `fastapi>=0.115` | Present | Not in test env | OK in full venv |
| `truthbrush>=0.2` | Present | Not in test env | OK in full venv |
| `duckdb>=1.2` | Present | 1.5.2 | OK |
| `cryptography>=44.0` | Present | 41.0.7 (Debian system pkg) | Version below minimum declared; install conflict in this env |
| `anthropic>=0.52` | Present | 0.52+ | OK |

Frontend dependencies (`react ^18.3.1`, `recharts ^2.15.0`, `vite ^6.0.0`, `typescript ~5.6.2`) are current and not flagged for CVEs. No new CVEs identified in declared dependencies.

---

## Positive Findings

- **302/329 tests pass** (91.8%) — no regressions from prior report; consistent since 2026-04-21
- **No secrets in repo** — `.env.example` uses placeholders only
- **`AsyncAnthropic` client** used everywhere; no sync client instantiations
- **Cascade engine + scenario config** fully implemented and unit-tested
- **Budget guard and alert dispatcher** wired and tested
- **Contract registry, divergence detector, portfolio simulator** function correctly per test suite
- **`DbWriter`** single-writer implementation is correct where used
- **`test_brief.py` (24 tests) and `test_crisis_context.py` (9 tests)** — all pass; dry-run pipeline solid

---

## Recommendations (Priority Order)

1. **Fix `test_google_news.py` fixture** — replace hardcoded `pubDate` strings with relative dates (`datetime.now(UTC) - timedelta(days=5)`); change `max_age_hours` to `24 * 10`. Permanently broken as of May 8. One-hour fix.
2. **Update Claude model ID** — replace `"claude-opus-4-20250514"` with `"claude-opus-4-7"` in `oil_price.py:133`, `ceasefire.py:106`, `hormuz.py:108`. Silent production blocker. 13 days unactioned. Five-minute fix.
3. **Add `pytz>=2024.1` to `pyproject.toml`** — one-line fix, unblocks 11 test failures and fixes `--scorecard` in clean environments. 26+ days unactioned. One-minute fix.
4. **Update `crisis_context.py`** — inject April 12–May 11 events, revise "Current Market State," update timestamp. 29 days stale. Required before any live prediction run is meaningful.
5. **Fix `test_mapping_policy.py` stale assertions** — update to expect cost-aware `effective_edge = gross_edge - expected_total_cost`.
6. **Align `recalibrate_probability()` predicate** — add `AND resolution_price IS NOT NULL` to count query in `scoring/recalibration.py:70`.
7. **Add `backtest/__init__.py`** and a smoke test.
8. **Wire `DbWriter` or annotate direct-write sites** with `# SINGLE_PROCESS_ONLY`.
9. **Update `pyproject.toml`** `requires-python` to `>=3.12`.
10. **Update `CLAUDE.md`** tech stack section to reflect the actual implementation.
