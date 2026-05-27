# Parallax Health Check — 2026-05-27

**Status: 🟡 YELLOW**

## Summary

Test results are unchanged from yesterday: **17 failed / 416 passed / 13 skipped (446 total collected)**. All 17 failures share a single root cause — the `pytz` package is not in `pyproject.toml`, causing DuckDB's internal Python integration to fail whenever any query uses `TIMESTAMPTZ`. This issue has been open **42 days**. The invalid Claude model ID (`claude-opus-4-20250514`) used in all three prediction files blocks live LLM inference and has been open **29 days**. Both are one-line fixes. Architecture is stable and the prediction market edge-finding pivot from the original Phase 1 simulation spec is well-documented and intentional.

---

## Test Results

```
17 failed | 416 passed | 13 skipped   (run: 85.5 s)
```

All 17 failures cascade from a single root cause:

```
_duckdb.InvalidInputException: Required module 'pytz' failed to import
ModuleNotFoundError: No module named 'pytz'
```

**Affected test files (by failure count):**
- `test_scorecard.py` — 8 failures (every scorecard computation test)
- `test_crisis_context_db.py` — 4 failures (DB render, fallback, metadata tests)
- `test_llm_usage.py` — 1 failure
- `test_ops_events.py` — 1 failure
- `test_phase1_critical.py` — 1 failure (staleness predictor falls back to seed context,
  returns age ≈ 1087 h instead of ≈ 2 h because DB query fails)

---

## Issues Found

### 🔴 HIGH — Missing `pytz` dependency (Day 42, first reported 2026-04-15)

- **Location**: `backend/pyproject.toml` — `pytz` absent from `dependencies`
- **Impact**: 17 test failures; `scorecard.py`, `crisis_context.py`, `alerts.py`, `llm_usage`
  queries all use DuckDB `TIMESTAMPTZ` functions that require `pytz` at the Python level.
- **Fix**: One line — add `"pytz>=2024.1"` to `[project] dependencies`.
- **Status**: Unchanged 42 days; reported in every health check since 2026-04-15.

### 🔴 HIGH — Invalid Claude model ID in all 3 prediction models (Day 29)

- **Locations**:
  - `prediction/ceasefire.py:116` — `model="claude-opus-4-20250514"`
  - `prediction/oil_price.py:143` — `model="claude-opus-4-20250514"`
  - `prediction/hormuz.py:118`  — `model="claude-opus-4-20250514"`
- **Impact**: Every live prediction call returns a 400 error from the Anthropic API.
  Dry-run mode is unaffected (no real API calls), masking the failure in CI.
- **Fix**: Replace with `"claude-opus-4-7"` in all three files (3 × one-line change).
  Also update the docstring in `ensemble.py:89` which still references the old ID.
- **Status**: Unchanged 29 days.

### 🟠 MEDIUM — Direct DuckDB writes outside single-writer queue (architectural drift)

- **Locations**:
  - `scoring/scorecard.py:21` — `conn.execute("INSERT INTO daily_scorecard …")`
  - `contracts/registry.py:87,106,116,199` — INSERT/DELETE/UPDATE via direct `conn.execute()`
  - `ingestion/crisis_ingester.py:81` — INSERT via direct `conn.execute()`
- **Context**: All three modules are synchronous (no `async def`), so concurrent racing
  with `DbWriter` is unlikely in current code paths (scorecard via CLI, registry initialised
  synchronously before the event loop starts). However this breaks the architectural invariant
  defined in the spec and creates a latent correctness hazard if any of these paths are ever
  called from an async context (e.g., a future `/api/scorecard/run` endpoint).
- **Recommendation**: Route writes through `DbWriter.enqueue()` or document explicitly why
  each synchronous write is safe (process-exclusive access).

### 🟠 MEDIUM — `portfolio/` package missing `__init__.py`

- **Location**: `backend/src/parallax/portfolio/` — no `__init__.py` present
- **Impact**: Imports like `from parallax.portfolio.simulator import PortfolioSimulator`
  succeed because Python 3 supports namespace packages, but this is inconsistent with every
  other subpackage in the repo, all of which have `__init__.py`. Breaks IDE auto-discovery
  and violates the project's own convention.
- **Fix**: `touch backend/src/parallax/portfolio/__init__.py`

### 🟠 MEDIUM — Oil price predictor: KeyError risk on malformed LLM response

- **Location**: `prediction/oil_price.py:160` — `direction=parsed["direction"]`
- **Context**: `ceasefire.py` and `hormuz.py` use `.get()` with defaults for all parsed keys.
  `oil_price.py` uses direct dict access (`parsed["direction"]`) which raises `KeyError` if
  the LLM response is malformed or partial.
- **Fix**: `direction=parsed.get("direction", "unknown")`

### 🟡 LOW — No test coverage for backtest engine and runner

- **Gaps**:
  - `backtest/engine.py` — zero tests (only `LookAheadGuard` in that directory is tested)
  - `backtest/runner.py` — zero tests
  - `ops/runtime.py` — zero tests
- **Impact**: Core backtest execution logic is untested; the look-ahead guard is tested but
  the engine that wraps it is not. Any regression in `BacktestEngine` would be invisible.

### 🟡 LOW — CLAUDE.md Technology Stack lists deps not in `pyproject.toml`

- **Listed in CLAUDE.md but absent from `pyproject.toml`**:
  `sentence-transformers`, `h3`, `searoute`, `shapely`, `google-cloud-bigquery`, `websockets`
- **Context**: These are from the original Phase 1 geospatial simulation spec which was
  deliberately pivoted away from. The `pyproject.toml` is correct for the current codebase.
  The CLAUDE.md "Technology Stack" section is stale and misleading for onboarding.
- **Fix**: Prune the stale entries from CLAUDE.md's Technology Stack table.

---

## Architecture Drift vs. Original Spec

The codebase has **intentionally pivoted** from the original Phase 1 design spec
(`2026-03-30-parallax-phase1-design.md`). The spec described a full geopolitical cascade
simulator with ~50 LLM agents, H3 spatial model, GDELT semantic dedup, WebSocket real-time
dashboard, and deck.gl/MapLibre visualisation. The current system is a focused prediction
market edge-finder (news ingestion → 3 LLM predictors → Kalshi/Polymarket comparison →
divergence signals → paper trading). This pivot is well-documented in CLAUDE.md and the
`.planning/` directory.

**Spec features NOT implemented (by design):**
- H3 spatial utilities / hexagonal world model
- 50-agent country→sub-actor swarm
- GDELT semantic deduplication (sentence-transformers)
- Circuit breaker (escalation limiter)
- WebSocket real-time frontend
- deck.gl / MapLibre GL geospatial visualisation
- Invite-code auth system

**Frontend**: The current React dashboard uses only `recharts` for charting; `deck.gl`,
`MapLibre GL`, `react-map-gl`, and `h3-js` from the original spec are not installed. This
is correct for the current architecture.

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
| `pytz` | ❌ **Missing** | Causes 17 test failures; add to deps |
| `pytest>=8.3`, `pytest-asyncio>=0.25`, `pytest-httpx>=0.35` | ✅ Current | Dev deps pinned |

**Frontend** (`package.json`):
| Dependency | Status | Notes |
|------------|--------|-------|
| `react@^18.3.1` | ✅ Current | |
| `recharts@^2.15.0` | ✅ Adequate | Charts for dashboard |
| `vite@^6.0.0` | ✅ Current | |
| `typescript@~5.6.2` | ✅ Current | |

---

## Positive Signals

- **416 / 446 tests passing** consistently — 93% pass rate is stable
- **AsyncAnthropic** used correctly throughout (no sync client in async context)
- **LookAheadGuard** is well-tested and prevents look-ahead bias in backtests
- **`DbWriter`** asyncio queue pattern is correctly implemented in `db/writer.py`
- **Budget tracker** enforces $20/day cap and is tested
- **Quarter-Kelly allocator** has risk caps (max notional, daily loss limit, theme caps)
- **No secrets committed** to repo (`.env.example` pattern used correctly)
- **Staleness penalty** wired through ensemble → predictor chain (tested in `test_phase1_critical.py`, currently failing due to pytz cascade)

---

## Recommendations (Priority Order)

1. **Fix pytz immediately** — `pyproject.toml`: add `"pytz>=2024.1"` to `dependencies`.
   Single line, unblocks 17 tests, takes 2 minutes.

2. **Fix model IDs** — Replace `"claude-opus-4-20250514"` → `"claude-opus-4-7"` in
   `ceasefire.py`, `oil_price.py`, `hormuz.py`. Unblocks live LLM inference.

3. **Add `portfolio/__init__.py`** — `touch backend/src/parallax/portfolio/__init__.py`

4. **Add `.get()` guard in `oil_price.py:160`** — defensive parse for malformed LLM output.

5. **Add backtest engine/runner tests** — at minimum, smoke-test `BacktestEngine` with
   a 3-day window and 2 mock predictions to prevent silent regressions.

6. **Update CLAUDE.md Technology Stack** — remove stale deps (`h3`, `searoute`,
   `sentence-transformers`, etc.) that were from the abandoned simulation spec.

---

*Generated by daily health check agent. Run `python -m pytest tests/ -q` to reproduce.*
