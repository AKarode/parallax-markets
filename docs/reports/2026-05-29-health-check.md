# Parallax Health Check — 2026-05-29

**Status: 🟡 YELLOW**

## Summary

Test results are unchanged for the seventh consecutive day: **17 failed / 416 passed / 13 skipped (446 total collected)**. All 17 failures cascade from a single missing dependency (`pytz`, Day 44). The invalid Claude model ID (`claude-opus-4-20250514`) in all three prediction files continues to block live LLM inference (Day 31). No code changes have been committed since 2026-05-23; the last 6 commits are all health check reports. Both critical issues remain one-line fixes.

---

## Test Results

```
17 failed | 416 passed | 13 skipped   (run: ~97 s)
```

All 17 failures are in `test_scorecard.py` and cascade from:

```
_duckdb.InvalidInputException: Required module 'pytz' failed to import
ModuleNotFoundError: No module named 'pytz'
```

**Affected test classes:**
- `TestScorecardComputation` — 3 failures
- `TestOpsMetrics` — 3 failures
- `TestDataQualityMetrics` — 2 failures
- `TestScorecardIdempotent` — 1 failure (+ others)

---

## Issues Found

### 🔴 HIGH — Missing `pytz` dependency (Day 44, first reported 2026-04-15)

- **Location**: `backend/pyproject.toml` — `pytz` absent from `dependencies`
- **Impact**: 17 test failures; `scorecard.py`, `crisis_context.py`, `alerts.py`, and `llm_usage` queries use DuckDB `TIMESTAMPTZ` functions requiring `pytz` at the Python level (DuckDB 1.5.3+ behaviour change).
- **Fix**: Add `"pytz>=2024.1"` to `[project] dependencies` in `pyproject.toml`.
- **Status**: Unchanged 44 days.

### 🔴 HIGH — Invalid Claude model ID in all 3 prediction models (Day 31)

- **Locations**:
  - `prediction/ceasefire.py:116` — `model="claude-opus-4-20250514"`
  - `prediction/oil_price.py:143` — `model="claude-opus-4-20250514"`
  - `prediction/hormuz.py:118` — `model="claude-opus-4-20250514"`
- **Impact**: Every live prediction call returns a 400 error from the Anthropic API. Dry-run mode is unaffected (no real API calls), masking the failure in CI.
- **Fix**: Replace with `"claude-opus-4-8"` in all three files (current Opus model as of 2026-05-29). Also update docstring in `ensemble.py:89`.
- **Status**: Unchanged 31 days.

### 🟠 MEDIUM — Direct DuckDB writes outside single-writer queue (architectural drift)

- **Locations** (writes confirmed by grep):
  - `scoring/scorecard.py:21` — `INSERT INTO daily_scorecard` via `conn.execute()`
  - `scoring/prediction_log.py:79` — `INSERT INTO prediction_log` via `self._conn.execute()`
  - `ops/alerts.py:106` — `INSERT INTO ops_events` via `self.db_conn.execute()`
  - `cli/brief.py:130,149,431` — `INSERT`/`UPDATE` via `conn.execute()`
- **Context**: Currently safe in practice (sequential single-process execution), but violates the single-writer invariant from the spec and is a latent hazard under concurrent API load.
- **Recommendation**: Route through `DbWriter.enqueue()` or add explicit documentation that these paths are single-threaded by design.

### 🟠 MEDIUM — `portfolio/` package missing `__init__.py`

- **Location**: `backend/src/parallax/portfolio/` — no `__init__.py` present
- **Impact**: Inconsistent with all other subpackages; breaks IDE auto-discovery and explicit package import guarantees.
- **Fix**: `touch backend/src/parallax/portfolio/__init__.py`

### 🟠 MEDIUM — Oil price predictor: `KeyError` risk on malformed LLM response

- **Location**: `prediction/oil_price.py:160` — `direction=parsed["direction"]`
- **Context**: `ceasefire.py` and `hormuz.py` use `.get()` with defaults for all parsed keys. `oil_price.py` uses direct dict access.
- **Fix**: `direction=parsed.get("direction", "unknown")`

### 🟡 LOW — No test coverage for backtest engine and runner

- **Gaps**: `backtest/engine.py` and `backtest/runner.py` have zero tests; `ops/runtime.py` untested.
- **Impact**: Silent regressions in core backtest execution logic.

### 🟡 LOW — `requires-python = ">=3.11"` inconsistency with CLAUDE.md

- **Location**: `backend/pyproject.toml:5`
- **Context**: CLAUDE.md specifies Python 3.12+ runtime; `pyproject.toml` allows 3.11+.
- **Fix**: Change to `requires-python = ">=3.12"`.

### 🟡 LOW — CLAUDE.md Technology Stack lists stale deps from abandoned simulation spec

- **Stale entries**: `sentence-transformers`, `h3`, `searoute`, `shapely`, `google-cloud-bigquery`, `websockets`
- **Context**: These are from the original H3-spatial geopolitical simulation design that was pivoted away from. The current codebase does not use them.
- **Fix**: Remove from CLAUDE.md Technology Stack section.

---

## Architecture Drift vs. Original Spec

The codebase has **intentionally pivoted** from the original Phase 1 design spec
(`2026-03-30-parallax-phase1-design.md`). That spec described a full geopolitical cascade
simulator with ~50 LLM agents, H3 spatial model, GDELT semantic dedup, WebSocket real-time
dashboard, and deck.gl/MapLibre visualisation. The current system is a focused prediction
market edge-finder (news ingestion → 3 LLM predictors → Kalshi/Polymarket comparison →
divergence signals → paper trading). This pivot is well-documented in CLAUDE.md.

**Spec features not implemented (by design):**
- H3 spatial utilities / hexagonal world model
- 50-agent country→sub-actor swarm
- GDELT semantic deduplication (sentence-transformers)
- WebSocket real-time frontend
- deck.gl / MapLibre GL geospatial visualisation

---

## Dependency Audit

| Dependency | Status | Notes |
|------------|--------|-------|
| `fastapi>=0.115` | ✅ Current | |
| `uvicorn[standard]>=0.34` | ✅ Current | |
| `duckdb>=1.2` | ✅ Current | |
| `anthropic>=0.52` | ✅ Current | |
| `pydantic>=2.10` | ✅ Current | |
| `httpx>=0.28` | ✅ Current | |
| `cryptography>=44.0` | ✅ Current | RSA-PSS for Kalshi auth |
| `truthbrush>=0.2` | ⚠️ Unverified | Scraper lib; verify still maintained |
| `pytz` | ❌ **Missing** | Causes 17 test failures; must be added |
| `pytest>=8.3`, `pytest-asyncio>=0.25`, `pytest-httpx>=0.35` | ✅ Current | Dev deps pinned |

**Frontend** (`package.json`):
| Dependency | Status | Notes |
|------------|--------|-------|
| `react@^18.3.1` | ✅ Current | |
| `recharts@^2.15.0` | ✅ Adequate | |
| `vite@^6.0.0` | ✅ Current | |
| `typescript@~5.6.2` | ✅ Current | |

---

## Positive Signals

- **416 / 446 tests passing** consistently — 93% pass rate stable for 7+ days
- `DbWriter` asyncio queue correctly implemented in `db/writer.py`
- `AsyncAnthropic` used correctly throughout (no sync client in async path)
- `LookAheadGuard` well-tested; prevents look-ahead bias in backtests
- Quarter-Kelly allocator enforces risk caps (max notional, daily loss limit, theme caps)
- No secrets committed (`.env.example` pattern used correctly)
- Schema migration system handles column additions gracefully

---

## Recommendations (Priority Order)

1. **Fix `pytz` immediately** — add `"pytz>=2024.1"` to `[project] dependencies` in `pyproject.toml`. One line, unblocks 17 tests. This is Day 44.

2. **Fix model IDs** — replace `"claude-opus-4-20250514"` → `"claude-opus-4-8"` in `ceasefire.py`, `oil_price.py`, `hormuz.py`. Unblocks live LLM inference. This is Day 31.

3. **Add `portfolio/__init__.py`** — `touch backend/src/parallax/portfolio/__init__.py`

4. **Add `.get()` guard in `oil_price.py:160`** — defensive parse for malformed LLM output.

5. **Add backtest engine/runner tests** — smoke-test `BacktestEngine` with a 3-day window and 2 mock predictions.

6. **Update CLAUDE.md Technology Stack** — remove stale deps from abandoned simulation spec.

7. **Fix `requires-python`** — change `>=3.11` → `>=3.12` in `pyproject.toml`.

---

*Generated by daily health check agent. Run `cd backend && python -m pytest tests/ -q` to reproduce.*
