# Parallax Health Check — 2026-05-30

**Status: 🟡 YELLOW** (regression — 22 failures vs 17 yesterday)

## Summary

Test failures increased from 17 to 22 since yesterday's report. Two root causes drive all failures: the long-standing missing `pytz` dependency (Day 45) and a newly surfaced `DATE()` scalar-function incompatibility in DuckDB 1.2.x. The invalid Claude model ID (`claude-opus-4-20250514`) continues to block all live LLM inference (Day 32). No code has been committed in 7 days; all recent commits are health check reports.

---

## Test Results

```
22 failed | 373 passed | 13 skipped   (run: ~71 s)
2 files failed to collect (fastapi / truthbrush not installed)
```

**Breakdown of failures:**

| File | Failures | Root Cause |
|------|----------|-----------|
| `test_scorecard.py` | 12 | `DATE()` scalar function + `pytz` missing |
| `test_phase1_critical.py` | 4 | `DATE()` in `backtest/runner.py` + `pytz` for `crisis_context` |
| `test_crisis_context_db.py` | 4 | `pytz` missing |
| `test_llm_usage.py` | 1 | `pytz` missing |
| `test_ops_events.py` | 1 | `pytz` missing |

---

## Issues Found

### 🔴 HIGH — `DATE()` as scalar function incompatible with DuckDB 1.2.x (NEW, Day 1)

- **Root cause**: `DATE(column)` is not a valid scalar function in DuckDB 1.2.x; valid syntax is `CAST(col AS DATE)` or `col::DATE`. This worked in DuckDB 1.5.3 (masking the bug), but `pyproject.toml` allows `duckdb>=1.2`, making the code fragile across versions.
- **Affected files**:
  - `scoring/scorecard.py` — 16 `DATE()` occurrences (lines 47, 58, 70, 84, 143, 167, 187, 206, 222, 255, 279, 292, 304, 325, 343, 355)
  - `backtest/runner.py:234` — 1 `DATE()` occurrence
- **Impact**: 16 test failures; scorecard ETL broken on any DuckDB 1.2.x install.
- **Fix**: Replace all `DATE(col)` with `CAST(col AS DATE)` or `col::DATE`.

### 🔴 HIGH — Missing `pytz` dependency (Day 45, first reported 2026-04-15)

- **Location**: `backend/pyproject.toml` — `pytz` absent from `[project] dependencies`
- **Impact**: 6+ test failures across `crisis_context_db`, `llm_usage`, `ops_events`, `scorecard`, `phase1_critical`. DuckDB raises `InvalidInputException: Required module 'pytz'` when comparing Python datetime objects with `TIMESTAMPTZ` columns.
- **Fix**: Add `"pytz>=2024.1"` to `[project] dependencies` in `pyproject.toml`.
- **Status**: Unchanged 45 days.

### 🔴 HIGH — Invalid Claude model ID in all 3 prediction models (Day 32)

- **Locations**:
  - `prediction/ceasefire.py:116` — `model="claude-opus-4-20250514"`
  - `prediction/oil_price.py:143` — `model="claude-opus-4-20250514"`
  - `prediction/hormuz.py:118` — `model="claude-opus-4-20250514"`
  - `prediction/ensemble.py:89` — stale docstring reference
- **Impact**: Every live prediction call returns a 400 error from the Anthropic API. Dry-run mode unaffected (no API calls), masking failure in CI.
- **Fix**: Replace with `"claude-opus-4-8"` in all three files.
- **Status**: Unchanged 32 days.

### 🟠 MEDIUM — Direct DuckDB writes outside single-writer queue (architectural drift)

- **Confirmed write locations** (outside `db/writer.py`):
  - `budget/tracker.py:43` — `INSERT INTO llm_usage` via `self._db_conn.execute()`
  - `ops/alerts.py:106` — `INSERT INTO ops_events` via `self.db_conn.execute()`
  - `scoring/resolution.py:60` — `UPDATE signal_ledger` via `conn.execute()`
  - `backtest/runner.py:290,308,329,356` — multiple inserts via `self._conn.execute()`
  - `cli/brief.py` — multiple `conn.execute()` writes
- **Context**: Safe in current sequential single-process execution, but violates the single-writer invariant from the spec and is a latent hazard under concurrent API load.
- **Status**: Unchanged since first flagged.

### 🟠 MEDIUM — `portfolio/` package missing `__init__.py` (Day 8)

- **Location**: `backend/src/parallax/portfolio/` — no `__init__.py`
- **Impact**: Inconsistent with all other subpackages; breaks IDE auto-discovery and explicit package import guarantees.
- **Also missing**: `backend/src/parallax/config/__init__.py`
- **Fix**: `touch backend/src/parallax/portfolio/__init__.py backend/src/parallax/config/__init__.py`

### 🟠 MEDIUM — Two test files fail to collect (import errors)

- `tests/test_dashboard_endpoints.py` — `ModuleNotFoundError: No module named 'fastapi'` (fastapi is in pyproject.toml but not installed in CI env)
- `tests/test_truth_social.py` — `ModuleNotFoundError: No module named 'truthbrush'` (in pyproject.toml but unavailable via pip install)
- **Impact**: Unknown number of tests in these files are invisible to CI. The `pip install -e ".[dev]"` install path should catch fastapi; truthbrush availability should be verified.

### 🟡 LOW — `requires-python = ">=3.11"` inconsistency with CLAUDE.md

- **Location**: `backend/pyproject.toml:5`
- **Context**: CLAUDE.md specifies Python 3.12+ runtime; `pyproject.toml` allows 3.11+.
- **Fix**: Change to `requires-python = ">=3.12"`.

### 🟡 LOW — No tests for `backtest/engine.py`

- `backtest/engine.py` has zero direct unit tests; only partially exercised by `test_phase1_critical.py` integration tests.
- **Impact**: Silent regressions in the main backtest execution loop.

---

## Architecture Drift vs. Original Spec

The codebase has intentionally pivoted from the original Phase 1 design spec (`2026-03-30-parallax-phase1-design.md`). The original spec described a full geopolitical cascade simulator with ~50 LLM agents, H3 spatial model, GDELT semantic dedup, WebSocket real-time dashboard, and deck.gl/MapLibre visualisation. The current system is a focused prediction market edge-finder (news ingestion → 3 LLM predictors → Kalshi/Polymarket comparison → divergence signals → paper trading). This pivot is well-documented in CLAUDE.md.

**Spec features not implemented (by design):**
- H3 spatial utilities / hexagonal world model
- 50-agent country→sub-actor swarm with GDELT deduplication
- WebSocket real-time frontend
- deck.gl / MapLibre GL geospatial visualisation

---

## Dependency Audit

| Dependency | Status | Notes |
|------------|--------|-------|
| `fastapi>=0.115` | ✅ In pyproject.toml | Not installed in this test env — install step broken |
| `uvicorn[standard]>=0.34` | ✅ Current | |
| `duckdb>=1.2` | ⚠️ Version range too wide | `DATE()` breaks on 1.2.x; pin to `>=1.3` or fix SQL |
| `anthropic>=0.52` | ✅ Current | |
| `pydantic>=2.10` | ✅ Current | |
| `httpx>=0.28` | ✅ Current | |
| `cryptography>=44.0` | ✅ Current | RSA-PSS for Kalshi auth |
| `truthbrush>=0.2` | ⚠️ Not pip-installable | Test file fails to collect; verify package availability |
| `pytz` | ❌ **Missing** | Causes 6+ test failures; must be added |
| `pytest>=8.3`, `pytest-asyncio>=0.25`, `pytest-httpx>=0.35` | ✅ Current | Dev deps pinned |

---

## Positive Signals

- **373 / 408 collected tests passing** (91.4%) — core pipeline still functional
- `DbWriter` asyncio queue correctly implemented in `db/writer.py`
- `AsyncAnthropic` used correctly throughout (no sync client in async path)
- `LookAheadGuard` well-tested; prevents look-ahead bias in backtests
- Quarter-Kelly allocator enforces risk caps (max notional, daily loss limit, theme caps)
- Schema migration system (`_migrate_legacy_tables`) handles column additions gracefully
- No secrets committed (`.env.example` pattern used correctly)
- Signal ledger + paper trade tracker architecture well-structured with good test coverage

---

## Recommendations (Priority Order)

1. **Fix `pytz` immediately** — add `"pytz>=2024.1"` to `[project] dependencies`. One line, unblocks 6+ tests. **This is Day 45.**

2. **Fix `DATE()` SQL** — replace all `DATE(col)` with `col::DATE` in `scorecard.py` (16 locations) and `backtest/runner.py` (1 location). Restores DuckDB cross-version compatibility.

3. **Fix model IDs** — replace `"claude-opus-4-20250514"` → `"claude-opus-4-8"` in `ceasefire.py`, `oil_price.py`, `hormuz.py`. Unblocks live LLM inference. **This is Day 32.**

4. **Tighten DuckDB version floor** — change `duckdb>=1.2` to `duckdb>=1.3` (or fix SQL to be compatible).

5. **Add `portfolio/__init__.py` and `config/__init__.py`** — one-liner each.

6. **Verify `truthbrush` availability** — confirm pip-installable version; add to CI setup.

7. **Add backtest engine unit tests** — smoke test `BacktestEngine` with mock data.

8. **Update `requires-python`** — change `>=3.11` → `>=3.12` to match CLAUDE.md.

---

*Generated by daily health check agent. Run `cd backend && PYTHONPATH=src python -m pytest tests/ -q --ignore=tests/test_dashboard_endpoints.py --ignore=tests/test_truth_social.py` to reproduce.*
