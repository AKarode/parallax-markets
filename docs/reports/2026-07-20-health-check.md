# Parallax Repo Health Check — 2026-07-20

**Status: YELLOW**

Zero source-code commits since the 2026-07-19 check (one tech-research doc landed). All issues from yesterday carry forward unchanged. No new issues found today.

---

## Summary

433 tests pass, 13 skip, 4 test files fail to collect due to `numpy`/`pandas` absent from the base `[dev]` extras — identical numbers to 2026-07-19. The standing HIGH issues (missing `cryptography` in `pyproject.toml`, DuckDB single-writer violated across nine files, core simulation/agent infrastructure never built) remain unresolved. No regressions introduced.

---

## Delta From Yesterday (2026-07-19)

| Area | Change |
|------|--------|
| Source code commits | 0 |
| Documentation commits | 1 (tech research: AIS integration, Batch API, binary WebSocket protocol) |
| New issues | 0 |
| Resolved issues | 0 |
| Tests passing | 433 (unchanged) |
| Tests skipped | 13 (unchanged) |
| Test files failing to collect | 4 (unchanged — numpy/pandas) |

---

## Issues Found (All Carry-over)

### [HIGH] `cryptography` Package Missing from `pyproject.toml`

`markets/kalshi.py` lines 19–20 import:
```python
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
```
Required for every RSA-PSS-signed Kalshi API request. `cryptography` appears nowhere in `pyproject.toml`. A clean `pip install -e ".[dev]"` will leave the package absent; the first live run hitting Kalshi will fail with `ModuleNotFoundError`. Currently masked by transitive install from another package.

**Fix:** Add `cryptography>=41.0` to the base `dependencies` list in `pyproject.toml`.

---

### [HIGH] DuckDB Single-Writer Pattern Violated Across the Codebase

The spec declares the `asyncio.Queue` single-writer pattern a **hard constraint**. `db/writer.py` implements `DbWriter` correctly and is tested, but no production code routes through it. At least nine source files write directly to DuckDB via `conn.execute()`:

| File | Tables Written |
|------|----------------|
| `cli/brief.py` | `runs` (INSERT, UPDATE), `market_prices` (INSERT) |
| `budget/tracker.py` | `llm_usage` (INSERT) |
| `scoring/ledger.py` | `signal_ledger` (INSERT, UPDATE) |
| `scoring/prediction_log.py` | `prediction_log` (INSERT) |
| `scoring/scorecard.py` | `daily_scorecard` (INSERT/UPSERT) |
| `scoring/resolution.py` | `signal_ledger` (UPDATE), `trade_positions` (UPDATE) |
| `contracts/registry.py` | `contract_registry`, `contract_proxy_map` (INSERT OR REPLACE, DELETE, INSERT) |
| `ingestion/crisis_ingester.py` | `crisis_events` (INSERT) |
| `ops/alerts.py` | `ops_events` (INSERT) — highest risk: called from `async send()` in FastAPI context |

`cli/brief.py` also opens five separate `duckdb.connect()` calls across sub-commands. Concurrent writes with a running FastAPI server will race on the file lock.

`DbWriter` is effectively dead code in production — no callers outside its own tests.

**Recommendation:** Wire `DbWriter` into the FastAPI lifespan and route async write paths (especially `ops/alerts.py` and ingestion triggered from the API) through it first; CLI path is lower risk but should follow.

---

### [HIGH] Core Simulation/Agent Infrastructure Never Built (Intentional Pivot)

The product has pivoted from geopolitical cascade simulation to prediction-market edge-finding. Phase 1 plan modules that were never implemented:

| Missing Module | Plan Description |
|----------------|------------------|
| `simulation/engine.py` | DES tick loop (heapq priority queue) |
| `simulation/circuit_breaker.py` | Escalation limits and cooldowns |
| `agents/` package | Runner, router, country agent, prompts, 50-agent roster |
| `spatial/` package | H3 utilities, loader, route-to-cell conversion |
| `eval/` package | Predictions, scoring, ground truth, prompt versioning |
| `api/` package | Routes, WebSocket handler, auth middleware |

Frontend has also diverged: no deck.gl H3 hex map, no WebSocket, no `HexMap.tsx`/`AgentFeed.tsx`. Current frontend is a trading dashboard using HTTP polling. `deck.gl`, `MapLibre GL`, `react-map-gl`, and `h3-js` are listed in CLAUDE.md/STACK.md but absent from `package.json`.

**Recommendation:** Mark the Phase 1 design spec (`docs/superpowers/specs/2026-03-30-parallax-phase1-design.md`) and implementation plan as superseded. `CLAUDE.md` already accurately describes the actual architecture.

---

### [MEDIUM] `numpy` / `pandas` Not in Base Dev Dependencies

Four test files fail to collect on a clean `pip install -e ".[dev]"`:

- `tests/test_bench_forecast.py`
- `tests/test_calibration_metrics.py`
- `tests/test_recalibrators.py`
- `tests/test_selective.py`

These modules live under `[bench]` extras but test imports are unconditional. Produces a hard collection error rather than a graceful skip.

**Fix options:**
1. Move `numpy`, `pandas`, `scikit-learn` into the base `[dev]` extras.
2. Guard test imports with `pytest.importorskip("numpy")` to auto-skip gracefully.

---

### [LOW] `requires-python` Drift

`pyproject.toml` specifies `requires-python = ">=3.11"` but CLAUDE.md and the Phase 1 spec both reference Python 3.12. The CI/runtime environment runs 3.11. Minor but creates confusion about the supported baseline.

---

### [LOW] `pytz` Dependency (Deprecated)

`pytz>=2024.1` is a runtime dependency. It is legacy since Python 3.9 introduced `zoneinfo` in the stdlib. New timezone code should use `zoneinfo`; `pytz` can be dropped once all callers are migrated.

---

### [LOW] No Upper Bounds on Critical Runtime Dependencies

`fastapi`, `duckdb`, `anthropic`, `httpx`, and `pydantic` have no upper bounds in `pyproject.toml`. A breaking change (e.g., DuckDB 2.0, FastAPI 1.0) could silently break the project on a fresh install.

---

### [LOW — New Signal] `httpx2` Deprecation Warning in Test Suite

`fastapi`'s `TestClient` emits a `StarletteDeprecationWarning` on every test run:
```
Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
```
Not a failure, but worth tracking; future FastAPI/Starlette versions may make this an error.

**Fix:** Add `httpx2>=0.28` to `[dev]` extras and remove `httpx` from dev deps (keep in runtime deps if needed for the async client).

---

## Recommendations (Priority Order)

1. **(Low effort — overdue)** Add `cryptography>=41.0` to base `dependencies` in `pyproject.toml`. Prevents silent breakage on clean installs when hitting Kalshi.
2. **(Medium effort)** Wire `DbWriter` into async write paths — start with `ops/alerts.py` (async FastAPI context, highest concurrency risk), then `ingestion/crisis_ingester.py`.
3. **(Low effort)** Fix `numpy`/`pandas` test collection errors — add to `[dev]` extras or add `pytest.importorskip`.
4. **(Low effort)** Update `requires-python` to `>=3.12` to match the tested environment.
5. **(Low effort)** Drop `pytz`; migrate any callers to `zoneinfo`.
6. **(Low effort)** Address `httpx2` deprecation warning to get a clean warning-free test run.
7. **(Documentation)** Mark Phase 1 spec and plan as superseded; document the actual prediction-market architecture to prevent future confusion.
