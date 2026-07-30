# Parallax Health Check — 2026-07-30

**Status: YELLOW**

## Summary

No code was committed since yesterday's health check — the two HIGH issues flagged on 2026-07-29 remain open and unaddressed. The test suite is otherwise healthy at 433 pass / 13 skip, but 4 test files cannot be collected on a clean `pip install -e ".[dev]"` install because they depend on the optional `[bench]` extras (`numpy`, `pandas`) that are not included in the dev dependency group. This is an active CI breakage risk.

---

## Issues Found

### [HIGH] `ensemble.py` line 128 — hardcoded `"opus"` in budget recording *(carry-over from 2026-07-29)*

- **File:** `backend/src/parallax/prediction/ensemble.py`, line 128
- `budget.record(resp.usage.input_tokens, resp.usage.output_tokens, "opus")` uses a hardcoded model string. The function already receives a `model` parameter. Opus pricing is 15× Haiku and 3× Sonnet, so the `BudgetTracker` over-counts cost on every call, triggering false `is_over_budget()` responses that degrade the pipeline to rule-based-only mode prematurely.
- **Fix:** `budget.record(resp.usage.input_tokens, resp.usage.output_tokens, model)`

### [HIGH] `DbWriter` is dead code — single-writer invariant unenforced *(carry-over from 2026-07-29)*

- **File:** `backend/src/parallax/db/writer.py`
- `DbWriter` exists and has passing tests but is imported by zero application modules. All 14+ modules (`scoring/ledger.py`, `scoring/tracker.py`, `budget/tracker.py`, `ops/alerts.py`, `cli/brief.py`, `contracts/registry.py`, `backtest/runner.py`, etc.) write to DuckDB via direct synchronous `conn.execute()` calls, bypassing the queue entirely.
- This violates the core DuckDB single-writer architecture in the Phase 1 spec. Under concurrent FastAPI load (e.g., `/api/brief/run` + polling endpoints) this will produce write-write conflicts.
- **Fix:** Either wire `DbWriter` through the `main.py` lifespan and migrate write-producing modules to `writer.enqueue()`, or document that the application runs single-threaded CLI-only and remove the dead `DbWriter` class.

### [MEDIUM] 4 test files fail to collect on `pip install -e ".[dev]"` *(new)*

- **Files:** `tests/test_bench_forecast.py`, `tests/test_calibration_metrics.py`, `tests/test_recalibrators.py`, `tests/test_selective.py`
- All four import `numpy` or `pandas`, which are only in the `[bench]` optional group. Running `pytest tests/` after a clean dev install causes `Interrupted: 4 errors during collection` — no tests run at all unless the four files are explicitly excluded with `--ignore`.
- **Fix (option A):** Move `numpy` and `pandas` into the `[dev]` dependency group (they're lightweight in CI). **Fix (option B):** Add `pytest --ignore=tests/test_bench_forecast.py ...` to the CI command, or wrap the imports in `pytest.importorskip("numpy")`.

### [MEDIUM] API endpoints `/api/predictions`, `/api/markets`, `/api/divergences` always return `[]` in production *(carry-over from 2026-07-29)*

- **File:** `backend/src/parallax/main.py`, lines 43–45
- `app.state.last_predictions/markets/divergences` are only populated when `POST /api/brief/run` is called over HTTP. The production workflow (`python -m parallax.cli.brief`) calls `run_brief()` directly and never touches `app.state`, so the dashboard endpoints always serve empty lists when the server is running alongside CLI execution.
- **Fix:** Have these endpoints query the DB (`signal_ledger`, `market_prices`, `prediction_log`) directly instead of relying on in-memory state.

### [MEDIUM] Blocking synchronous DB writes inside `async` functions *(carry-over from 2026-07-29)*

- **Files:** `ops/alerts.py` line 106 (`DuckDBAlertSink.send` is `async` but calls `conn.execute()` synchronously), `budget/tracker.py` line 43 (called from async brief paths)
- Blocks the FastAPI event loop on every alert or budget write. Low risk under CLI-only usage but becomes a latency issue if the server handles concurrent requests.
- **Fix:** Wrap with `asyncio.to_thread()` or route through `DbWriter` once it is wired in.

### [LOW] `portfolio/` and `config/` directories missing `__init__.py` *(carry-over from 2026-07-29)*

- Both directories are importable via hatchling's auto-discovery but are not proper Python packages, which can break tooling (mypy, pyright, editable installs with `--no-build-isolation`).
- **Fix:** `touch backend/src/parallax/portfolio/__init__.py backend/src/parallax/config/__init__.py`

### [LOW] Stale `BudgetTracker` pricing constants

- **File:** `backend/src/parallax/budget/tracker.py`, lines 10–13
- Pricing comment says "Updated per validation: Haiku ~$0.005/call, Sonnet ~$0.031/call" but the hardcoded per-1K-token rates do not match current Anthropic API pricing (e.g., Haiku 4.5 input is $0.0008/1K, not $0.001/1K). Over-counting inputs less severely than the `"opus"` bug, but the table should be refreshed to avoid confusing budget reports.

### [INFO] Architecture drift vs Phase 1 spec (acknowledged, no action needed)

- `agents/` swarm → replaced by 3 focused prediction models in `prediction/`
- `spatial/` H3 hex indexing → deleted; deck.gl dashboard replaced by polling React SPA
- `eval/` framework → split across `scoring/`, `backtest/`, `bench/`
- `api/` sub-package → consolidated into `main.py`
- These are intentional architectural pivots documented across prior health checks. The current implementation is coherent and the spec is simply stale.

---

## Test Health

| Outcome | Count |
|---------|-------|
| Passed  | 433   |
| Skipped | 13    |
| Collection errors | 4 (bench deps not installed) |

The 4 collection errors prevent `pytest tests/` from running at all without `--ignore` flags. Fix the `[dev]` dep group or add CI `--ignore` flags.

---

## Recommendations (Priority Order)

1. **`ensemble.py` line 128** — one-line fix, eliminates false budget exhaustion. Change `"opus"` → `model`.
2. **4 test collection errors** — add `numpy` and `pandas` to `[dev]` deps so `pytest` doesn't abort on collection.
3. **Decide on `DbWriter`** — wire it in or delete it; the current state is misleading.
4. **API endpoints read from DB** — `last_predictions` / `last_markets` / `last_divergences` should query live DB tables.
5. **Add `__init__.py`** to `portfolio/` and `config/`.
6. **Refresh `BudgetTracker` pricing** to current Anthropic API rates.
