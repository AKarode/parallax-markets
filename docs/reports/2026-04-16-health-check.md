# Parallax Health Check — 2026-04-16

**Status: YELLOW**

**Summary:** Core simulation modules (cascade engine, DES, world state) and the prediction market pipeline are solid with 233/268 tests passing (87%). However, three active logic bugs are breaking 35 tests: `confidence_discount` is hardcoded to 1.0 regardless of proxy class (killing edge calculation), `pytz` is missing from dependencies (crashing DuckDB TIMESTAMPTZ queries), and the calibration curve queries through a view that requires `resolution_price` while the count-check queries `signal_ledger` directly (inconsistency). The project has also drifted significantly from Phase 1 spec — it evolved from a geopolitical cascade visualizer into a CLI-first prediction market edge-finder, which is a legitimate pivot but leaves the agent swarm, WebSocket dashboard, and eval framework unbuilt.

---

## Issues Found

### 🔴 CRITICAL — Logic Bugs Breaking Tests

- **`confidence_discount` hardcoded to 1.0** [`contracts/mapping_policy.py:290,340`]
  The `_build_mapping_result()` and `_build_non_tradable_result()` methods both hardcode `confidence_discount=1.0`. The proxy-class discount (NEAR_PROXY=0.6, LOOSE_PROXY=0.3) extracted as `_legacy_discount` in `evaluate()` (line 61) is explicitly thrown away. This means 11 `test_mapping_policy.py` tests fail — the discount system that gives higher confidence to direct-proxy signals over loose-proxy signals is completely inoperative. All effective edges are computed as if every contract is a direct match. **Risk: trades on LOOSE_PROXY contracts are being sized/filtered as if they were DIRECT proxy contracts.**

- **`pytz` not in `pyproject.toml`** — causes `_duckdb.InvalidInputException` on TIMESTAMPTZ queries
  DuckDB 1.2+ imports `pytz` internally for TIMESTAMPTZ arithmetic. Affects `test_scorecard.py` (8 failures), `test_llm_usage.py` (1), and `test_ops_events.py` (1). Any production environment without pytz installed will crash on scorecard computation and ops telemetry. Fix: add `"pytz>=2024.1"` to `pyproject.toml` dependencies.

- **`calibration_curve()` queries through `signal_quality_evaluation` VIEW** [`scoring/calibration.py:45-61`]
  The view requires `resolution_price IS NOT NULL` (schema.py:631), but `recalibrate_probability()` in `scoring/recalibration.py` checks signal count directly against `signal_ledger`. Result: the count can show 15 resolved signals, but `calibration_curve()` returns empty because those rows have no `resolution_price`. Tests that insert signals with only `model_was_correct` see empty buckets. Fix: either add `resolution_price` to test fixtures or query `signal_ledger` directly in `calibration_curve()`.

### 🔴 CRITICAL — Test Collection Failures (3 test files blocked)

- **`cryptography` version conflict** — `tests/test_brief.py` and `tests/test_kalshi.py` fail to import
  `pyproject.toml` requires `cryptography>=44.0` but the installed version is 41.0.7. The Rust-backed `cryptography` 41.x panics on import with `pyo3_runtime.PanicException`. Fix: either install `cryptography>=44.0` or add a version ceiling `<42` that is compatible with the current environment.

- **`truthbrush` not installable** — `tests/test_truth_social.py` fails to collect
  `ModuleNotFoundError: No module named 'truthbrush'`. The package is in pyproject.toml but cannot be installed in this environment.

### 🟡 WARNING — Dependency Build Failures

- **`searoute>=1.3` fails to build wheel** — setuptools/hatchling distutils conflict
  `AttributeError: install_layout` prevents wheel build. This blocks installation of the full package in fresh environments. The spatial routing module depends on searoute but it is unused in the current CLI-first pipeline.

- **`sentence-transformers>=3.4` not installed** — GDELT semantic dedup unavailable
  The 4-stage GDELT filter's semantic dedup step (`ingestion/dedup.py`) will fail at runtime if called. Not currently exercised in the main brief pipeline.

- **Python 3.11 in `pyproject.toml`, spec requires 3.12** — `requires-python = ">=3.11"` (pyproject.toml:4)
  Minor version drift from spec. Running on 3.11.15 in this environment with no observed breakage, but 3.12-only features (e.g., improved asyncio) are not available.

### 🟡 WARNING — Single-Writer DuckDB Violations

The spec mandates all writes go through `DbWriter`'s asyncio queue. The following modules write directly via `conn.execute()`:

| File | Operations |
|------|-----------|
| `scoring/ledger.py` | `INSERT INTO signal_ledger`, `UPDATE signal_ledger` |
| `scoring/tracker.py` | `INSERT INTO trade_positions`, `UPDATE trade_orders`, `INSERT INTO trade_fills` |
| `budget/tracker.py` | `INSERT INTO llm_usage` |
| `scoring/scorecard.py` | `INSERT INTO daily_scorecard` (via `_upsert_metric`) |
| `ops/alerts.py` | `INSERT INTO ops_events` |

In the current single-process CLI design these are safe because only one coroutine runs at a time per `brief.py` invocation. However, if `main.py`'s FastAPI server runs these concurrently with other write paths, you will hit `database is locked`. The spec explicitly warns: "Separate processes writing to the same DuckDB file will cause database is locked errors." Worth enforcing before scaling.

### 🟡 WARNING — Test Configuration Split

`pytest.ini` and `pyproject.toml [tool.pytest.ini_options]` both configure pytest. pytest resolves `pytest.ini` with higher priority and prints: `WARNING: ignoring pytest config in pyproject.toml!`. The `pytest.ini` only contains `asyncio_mode = auto` and `testpaths = tests` — it matches pyproject.toml but the split is confusing. Remove one.

### 🟡 WARNING — Dependency Version Constraints

Most production dependencies have no upper bounds (e.g., `fastapi>=0.115`, `duckdb>=1.2`, `anthropic>=0.52`). This allows major-version upgrades to break the build silently. Only dev deps have tight ranges. Consider adding `<N+1` ceilings for major dependencies once they stabilize.

### 🔵 INFO — Architecture Drift from Phase 1 Spec

The project has undergone a significant scope pivot from the original spec (geopolitical cascade visualizer with 50-agent LLM swarm and H3 deck.gl dashboard) to a focused prediction market edge-finder (CLI + Streamlit). This is a legitimate product decision, but the following spec elements are unbuilt:

| Spec Component | Status |
|---------------|---------|
| `agents/registry.py`, `router.py`, `country_agent.py` | Not built — only `runner.py` + `schemas.py` |
| `agents/prompts/*.yaml` (12+ country agents) | Not built |
| `api/routes.py`, `websocket.py`, `auth.py` | Not built — replaced by Streamlit dashboard |
| `eval/` module (predictions, scoring, ground_truth) | Renamed/restructured as `scoring/` |
| `spatial/loader.py` (Overture Maps → H3 cells) | Not built |
| `ingestion/gdelt.py` (BigQuery) | Replaced by `ingestion/gdelt_doc.py` (HTTP API) |
| Frontend (React + deck.gl + MapLibre) | Not built — only nginx.conf stub |
| WebSocket real-time updates | Not implemented |
| Invite-code auth / admin mode | Not implemented |
| Agent swarm (~50 LLM agents) | Not implemented |

The `scoring/` module successfully covers eval scoring, calibration, and resolution tracking described in spec Section 7. The simulation engine, cascade rules, and circuit breaker are cleanly implemented per spec Section 4.

---

## Recommendations

**Immediate (unblock tests):**
1. Add `"pytz>=2024.1"` to `pyproject.toml` dependencies — fixes 10 test failures
2. Fix `confidence_discount` in `mapping_policy.py` — should use a lookup by `proxy_class` (DIRECT=1.0, NEAR_PROXY=0.6, LOOSE_PROXY=0.3) instead of hardcoding 1.0
3. Fix `calibration_curve()` — either add `resolution_price` to test fixtures or query `signal_ledger` directly with a `model_was_correct IS NOT NULL` filter

**Near-term (reliability):**
4. Resolve `cryptography` version — upgrade to >=44.0 or pin compatible version; unblocks brief and Kalshi tests
5. Either route all writes through `DbWriter` queue or document that direct writes are intentional in single-process mode
6. Remove `pytest.ini` and consolidate config in `pyproject.toml`

**Longer-term (spec alignment, if the visual dashboard path is still intended):**
7. Build `agents/registry.py` and first-pass agent prompts for IRGC Navy, CENTCOM, Aramco
8. Implement WebSocket endpoint in `main.py` for real-time cell updates
9. Replace `ingestion/gdelt_doc.py` with BigQuery-backed `ingestion/gdelt.py` for structured actor/event fields

---

## Test Summary

```
Total:    268 collected  (3 files failed to collect: test_brief, test_kalshi, test_truth_social)
Passed:   233 (87%)
Failed:    35 (13%)

Failure breakdown:
  test_mapping_policy.py   11  ← confidence_discount hardcoded to 1.0
  test_scorecard.py         8  ← pytz missing
  test_resolution.py        5  ← pytz missing (TIMESTAMPTZ queries)
  test_recalibration.py     4  ← calibration_curve queries wrong table
  test_report_card.py       3  ← resolution view inconsistency
  test_llm_usage.py         1  ← pytz missing
  test_ops_events.py        1  ← pytz missing
  test_recalibration.py     2  ← calibration_curve empty via view
```
