# Parallax Repo Health Check — 2026-07-19

**Status: YELLOW**

One source-code-adjacent commit landed since the 2026-07-18 check (a tech-research doc). Zero source code changes. All YELLOW issues from yesterday persist unchanged, plus one new HIGH issue identified today: `cryptography` is imported by `markets/kalshi.py` for RSA-PSS signing but is not listed anywhere in `pyproject.toml`, meaning a fresh clean install will fail at the Kalshi API call.

---

## Summary

Zero source-code commits between the 2026-07-18 health check and today. 433 tests pass, 13 skip, 4 test files fail to collect due to missing `numpy`/`pandas` in the base `[dev]` extras — same numbers as yesterday. The newly surfaced `cryptography` dependency gap is the only net-new finding; everything else is carried from the standing YELLOW list.

---

## Delta From Yesterday (2026-07-18)

| Area | Change |
|------|--------|
| Source code commits | 0 |
| Documentation commits | 1 (tech-research: Batch API, AIS, GDELT alternatives) |
| New issues | 1 — `cryptography` missing from `pyproject.toml` |
| Resolved issues | 0 |
| Tests passing | 433 (unchanged) |
| Tests skipped | 13 (unchanged) |
| Test files failing to collect | 4 (unchanged — numpy/pandas) |

---

## Issues Found

### [HIGH — NEW] `cryptography` Package Missing from `pyproject.toml`

`markets/kalshi.py` imports at lines 19–20:
```python
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
```
These are required for every RSA-PSS-signed Kalshi API request. `cryptography` appears nowhere in `pyproject.toml` (not in base deps, not in `[dev]`, not in `[bench]`). A clean `pip install -e ".[dev]"` will leave the package absent; the first live run that hits Kalshi will fail with `ModuleNotFoundError`. The package happens to be present in this environment as a transitive dependency of something else, which masks the gap.

**Fix:** Add `cryptography>=41.0` to the base `dependencies` list in `pyproject.toml`.

---

### [HIGH — Carry-over] DuckDB Single-Writer Pattern Violated Across the Codebase

The spec declares the asyncio.Queue single-writer pattern a **hard constraint**. `db/writer.py` implements `DbWriter` correctly and is tested, but **no production code routes through it**. At least nine source files write directly to DuckDB via `conn.execute()`:

| File | Tables Written |
|------|---------------|
| `cli/brief.py` | `runs` (INSERT, UPDATE), `market_prices` (INSERT) |
| `budget/tracker.py` | `llm_usage` (INSERT) |
| `scoring/ledger.py` | `signal_ledger` (INSERT, UPDATE) |
| `scoring/prediction_log.py` | `prediction_log` (INSERT) |
| `scoring/scorecard.py` | `daily_scorecard` (INSERT/UPSERT) |
| `scoring/resolution.py` | `signal_ledger` (UPDATE), `trade_positions` (UPDATE) |
| `contracts/registry.py` | `contract_registry` (INSERT OR REPLACE, UPDATE), `contract_proxy_map` (DELETE, INSERT) |
| `ingestion/crisis_ingester.py` | `crisis_events` (INSERT) |
| `ops/alerts.py` | `ops_events` (INSERT) — highest risk: called from an `async send()` method |

Additionally, `cli/brief.py` opens **five separate `duckdb.connect()` calls** across different sub-commands, each creating an independent file connection. If the FastAPI server is running simultaneously, concurrent write connections to the same DuckDB file will race.

`DbWriter` is effectively dead code in production — it has no callers outside its own tests.

**Recommendation:** Wire `DbWriter` into the FastAPI lifespan and route the async write paths (especially `ops/alerts.py` and any ingestion called from the API) through it. The CLI sequential path is lower risk but should also be migrated for consistency.

---

### [HIGH — Carry-over] Core Simulation Infrastructure Not Built (Intentional Pivot)

These modules from the Phase 1 plan are absent. The product has pivoted from geopolitical cascade simulation to prediction-market edge-finding:

| Missing Module | Plan Description |
|---------------|-----------------|
| `simulation/engine.py` | DES tick loop (heapq priority queue) |
| `simulation/circuit_breaker.py` | Escalation limits and cooldowns |
| `agents/` package | Runner, router, country agent, prompts, 50-agent roster |
| `spatial/` package | H3 utilities, loader, route-to-cell conversion |
| `eval/` package | Predictions, scoring, ground truth, prompt versioning |
| `api/` package | Dedicated routes, websocket handler, auth middleware |

Frontend has also diverged: no deck.gl H3 hex map, no WebSocket connection, no `useHexData.ts` / `HexMap.tsx` / `AgentFeed.tsx`. Current frontend is a trading dashboard using HTTP polling.

**Recommendation:** Mark the Phase 1 design spec (`docs/superpowers/specs/2026-03-30-parallax-phase1-design.md`) as superseded. The current `CLAUDE.md` already describes the actual architecture accurately.

---

### [MEDIUM — Carry-over] `numpy` / `pandas` Not in Base Dev Dependencies

Four test files fail to collect because `numpy` is not installed by `pip install -e ".[dev]"`:

- `tests/test_bench_forecast.py`
- `tests/test_calibration_metrics.py`
- `tests/test_recalibrators.py`
- `tests/test_selective.py`

These modules are under `[bench]` extras but tests import them unconditionally.

**Fix options:**
1. Move `numpy`, `pandas`, `scikit-learn` to the base `[dev]` extras
2. Guard test imports with `pytest.importorskip("numpy")` to auto-skip gracefully

---

### [MEDIUM — Carry-over] Architecture Drift vs. Phase 1 Plan File Layout

| Plan Path | Actual Path | Status |
|-----------|-------------|--------|
| `ingestion/gdelt.py` | `ingestion/gdelt_doc.py` | Renamed, different API (DOC not BigQuery) |
| `ingestion/dedup.py` | (absent) | Spec's semantic dedup not implemented |
| `agents/` | (absent) | Replaced by `prediction/` |
| `eval/` | (absent) | Replaced by `scoring/` |
| `api/routes.py`, `api/websocket.py`, `api/auth.py` | (absent) | Folded into `main.py` |
| `simulation/engine.py`, `simulation/circuit_breaker.py` | (absent) | DES not built |
| (not in plan) | `backtest/`, `bench/`, `contracts/`, `divergence/`, `portfolio/`, `markets/` | Added post-pivot |

---

### [LOW — Carry-over] `requires-python` Drift

`pyproject.toml` specifies `requires-python = ">=3.11"` but the Phase 1 spec and `CLAUDE.md` both reference Python 3.12. The CI environment runs 3.11. The gap is minor but creates confusion.

---

### [LOW — Carry-over] `pytz` Dependency (Deprecated)

`pytz>=2024.1` is listed as a runtime dependency. It is legacy since Python 3.9 introduced `zoneinfo` in the stdlib. Any new timezone code should use `zoneinfo`; `pytz` can be dropped once all callers are migrated.

---

### [LOW — Carry-over] No Upper Bounds on Critical Runtime Dependencies

`fastapi`, `duckdb`, `anthropic`, `httpx`, and `pydantic` have no upper bounds in `pyproject.toml`. A breaking change (e.g., DuckDB 2.0, FastAPI 1.0) could silently break the project on fresh install.

---

## Recommendations (Priority Order)

1. **(Low effort — new)** Add `cryptography>=41.0` to base `dependencies` in `pyproject.toml`. Prevents silent breakage on clean installs.
2. **(Medium effort)** Wire `DbWriter` into the async write paths — primarily `ops/alerts.py` (called from async FastAPI context) and ingestion paths triggered from the API server.
3. **(Low effort)** Fix the `numpy`/`pandas` test collection errors — add to `[dev]` extras or add `pytest.importorskip`.
4. **(Low effort)** Update `requires-python` to `>=3.12` to match the tested environment.
5. **(Low effort)** Drop `pytz`, migrate any callers to `zoneinfo`.
6. **(Documentation)** Mark the Phase 1 design spec and plan as superseded; document the actual prediction-market architecture.
