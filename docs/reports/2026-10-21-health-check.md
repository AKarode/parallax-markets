# Parallax Health Check — 2026-10-21

**Status: YELLOW**

The codebase is functional and well-tested for its current purpose, but it has fully pivoted away from the Phase 1 spec. The project shipped as a prediction market edge-finder (Kalshi/Polymarket divergence + paper trading) rather than the geopolitical cascade simulator with 50 LLM agents and H3 hex visualization described in the spec. Nine tests are failing, some dependencies are missing from `pyproject.toml`, and several modules write directly to DuckDB bypassing the single-writer queue.

---

## Summary

| Category | Status |
|----------|--------|
| Spec/Plan consistency | ⚠️ Architecture diverged (intentional pivot) |
| Dependency audit | ⚠️ `cryptography` undeclared; `numpy`/`pandas` in wrong extras group |
| Code quality | ⚠️ DuckDB single-writer violations in 4 modules |
| Test coverage | ⚠️ 9 failures, 7 collection errors from missing deps |
| Architecture/file layout | ✅ Consistent with CLAUDE.md (post-pivot truth) |

---

## Issues Found

### [HIGH] Architecture pivot not reflected in spec/plan docs

- `docs/superpowers/specs/2026-03-30-parallax-phase1-design.md` describes a geopolitical cascade simulator with ~50 LLM country agents, H3 hex map visualization, WebSocket dashboard, GDELT BigQuery ingestion, and semantic dedup.
- The actual codebase is a **prediction market edge-finder**: 3 Claude prediction models → Kalshi/Polymarket market price comparison → divergence signals → paper trades.
- Entire spec modules are absent: `agents/`, `eval/`, `api/`, `spatial/`. `simulation/` is partial (only `cascade.py`, `config.py`, `world_state.py`; missing `engine.py`, `circuit_breaker.py`).
- **This appears intentional** — CLAUDE.md documents the current architecture correctly. The spec/plan docs are stale artifacts from the original design. Recommend either archiving them or adding a note that they represent the original design pre-pivot.

### [MEDIUM] 9 failing tests

Running `pytest` (excluding missing-dep test files) produces 9 failures:

- `tests/test_resolution.py` — 5 failures: `TestCheckMarketResolution` (detect_settled_market, skip_unsettled_market), `TestBackfillSignal` (backfill_updates_resolution_columns, backfill_buy_no_pnl, backfill_skips_already_resolved), `TestCheckResolutionsEndToEnd`
- `tests/test_report_card.py` — 3 failures: `TestProxyWasAlignedInResolution` (buy_yes_resolution_above_half_aligned, buy_no_resolution_below_half_aligned, buy_yes_resolution_below_half_not_aligned)

These touch the resolution/settlement and P&L report card logic — core scoring pipeline components.

### [MEDIUM] Missing `cryptography` dependency in `pyproject.toml`

- `markets/kalshi.py` uses RSA-PSS signing which requires the `cryptography` package.
- `cryptography` is **not declared** in `pyproject.toml` dependencies.
- This causes `ModuleNotFoundError: No module named 'cryptography'` when collecting `test_kalshi.py` and `test_brief.py`.
- **Fix**: Add `cryptography>=42.0` to `[project.dependencies]`.

### [MEDIUM] DuckDB single-writer violations — 4 modules bypass `asyncio.Queue`

The spec mandates all writes go through `db/writer.py`'s `asyncio.Queue`. The following modules write directly to DuckDB:

- `ops/alerts.py:106` — `INSERT INTO ops_events` via `self.db_conn.execute()`
- `budget/tracker.py:43` — `INSERT INTO llm_usage` via `self._db_conn.execute()`
- `cli/brief.py:130,149,431` — `INSERT INTO runs`, `UPDATE runs`, `INSERT INTO market_prices` via bare `conn.execute()`
- `backtest/runner.py:290,308,329,356` — multiple INSERTs via `self._conn.execute()`

Under concurrent async load these can trigger DuckDB `database is locked` errors. The `backtest/` module operates on a separate connection by design (offline replay), so it may be acceptable there. The ops, budget, and CLI write paths are the real risk.

### [MEDIUM] `numpy` / `pandas` in wrong optional group — causes test collection errors

- `numpy`, `pandas`, `scikit-learn`, `matplotlib` are in `[bench]` optional extras.
- `scoring/calibration_metrics.py`, `scoring/recalibrators.py`, and `scoring/selective.py` import `numpy` at module level — these are not bench-only modules; they're part of the core scoring pipeline.
- `test_calibration_metrics.py`, `test_recalibrators.py`, `test_selective.py` fail to collect with `ModuleNotFoundError: No module named 'numpy'`.
- **Fix**: Move `numpy` (and `pandas` if needed by scoring) into `[project.dependencies]`, not `[bench]`.

### [LOW] `requires-python` mismatch

- `pyproject.toml` specifies `requires-python = ">=3.11"` but spec says Python 3.12.
- The runtime is Python 3.11.17. No functional impact but creates drift from documented requirements.

### [LOW] FastAPI / httpx deprecation warning

- `starlette.testclient` emits `StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated; install httpx2 instead`.
- Affects all tests that use `TestClient`. No failures, but will become an error when `starlette` drops the compatibility shim.
- **Fix**: Add `httpx2>=0.28` to dev deps when upgrading.

### [LOW] Spec dependencies never installed

The following packages appear in the Phase 1 spec/plan but are absent from `pyproject.toml`:
`h3>=4.1`, `sentence-transformers>=3.4`, `searoute>=1.3`, `shapely>=2.0`, `websockets>=14.0`, `google-cloud-bigquery>=3.27`. This is expected given the pivot away from the spatial/agent architecture — noting for completeness.

---

## Recommendations

1. **Fix the 9 test failures** — `test_resolution.py` and `test_report_card.py` are in the core scoring path. Investigate the resolution/backfill and proxy-alignment logic.

2. **Add `cryptography` to `pyproject.toml`** — Kalshi auth depends on it; the package silently works when it happens to be installed but will break in a fresh environment.

3. **Move `numpy` to core deps** — `scoring/recalibrators.py` and `scoring/calibration_metrics.py` are not bench-only; they need numpy at runtime.

4. **Audit DuckDB write paths** — Wrap `ops/alerts.py` and `budget/tracker.py` writes through `DbWriter.enqueue()` to prevent lock contention in the async server path. The `cli/brief.py` writes are synchronous CLI only, acceptable as-is if brief.py is never called from within the async server context.

5. **Archive or annotate stale spec docs** — Add a header note to `docs/superpowers/specs/2026-03-30-parallax-phase1-design.md` marking it as the original design pre-pivot to avoid future confusion.
