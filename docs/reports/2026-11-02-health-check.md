# Parallax Health Check — 2026-11-02

**Status: YELLOW**

One code commit since last report: `b25b4e4` (Oct 28) fixed HIGH bugs (`np.trapezoid` + added `scikit-learn`/`numpy` to base deps). Since then, only docs commits. All carry-over issues from previous reports remain unresolved — the MEDIUM DuckDB single-writer violations (now Day 8) are the sole actionable risk.

---

## Summary

The prediction-market pipeline is architecturally stable. The 3-model signal system (oil price, ceasefire, Hormuz), Kalshi/Polymarket market reads, divergence detection, and paper-trade lifecycle are coherent and well-tested with 47 test files. The HIGH `np.trapezoid` bug is confirmed fixed. The MEDIUM concurrency bug in direct-write DuckDB paths persists and is the primary risk item — under concurrent FastAPI load, these paths will non-deterministically raise `database is locked`.

---

## Spec / Plan vs. Implementation

The project deliberately pivoted from the Phase 1 spec's 50-agent LLM swarm + H3 spatial visualization to a focused prediction-market edge-finder. This is documented in CLAUDE.md and is coherent. Key deviations from spec:

- **Missing (intentional):** `agents/` module (50-agent swarm), `spatial/` module (H3 loader/h3_utils), `eval/` module (prompt versioning, improvement pipeline), `api/` module (auth, WebSocket handler)
- **Missing from spec, present in code:** `prediction/`, `scoring/`, `contracts/`, `divergence/`, `portfolio/`, `backtest/`, `ingestion/` — all productive additions for the market-edge use case
- **pyproject.toml:** `requires-python = ">=3.11"` but spec calls for Python 3.12. Not a blocking issue.
- **Missing spec deps still absent:** `h3`, `searoute`, `shapely`, `sentence-transformers`, `websockets`, `google-cloud-bigquery` — correctly absent given the pivot.

---

## Issues Found

### MEDIUM Severity — Carry-Over (Day 8)

- **[BUG] DuckDB single-writer violations in live-path modules**
  Six modules write to DuckDB directly via `conn.execute()` / `_conn.execute()` outside the `asyncio.Queue → DbWriter` pattern. Under concurrent FastAPI requests (or when the CLI and API run simultaneously sharing the same `.duckdb` file), these paths can raise `database is locked` non-deterministically.

  Confirmed violators (unchanged since Oct 26):
  - `ops/alerts.py:106` — **highest risk; executes synchronously on every alert dispatch**
  - `scoring/ledger.py:225,256,271,294,305,318`
  - `scoring/prediction_log.py:79`
  - `budget/tracker.py:43`
  - `scoring/tracker.py`, `scoring/resolution.py`

  **Fix:** Route all live-path writes through `DbWriter.enqueue()`. The `DbWriter` class in `db/writer.py` is correctly implemented and available; it just needs wiring into these five live-path modules.

### LOW Severity — Carry-Over (Day 8)

- **[DEP] `streamlit` and `plotly` missing from `pyproject.toml`**
  `dashboard/app.py:16–17` imports both at module level. Neither appears in any dependency group in `pyproject.toml`. A fresh `pip install -e "."` on a clean environment will raise `ModuleNotFoundError` if the dashboard is used. Add both to a `[dashboard]` extras group.

- **[ARCH] `simulation/` module incomplete — missing `engine.py` and `circuit_breaker.py`**
  The spec plan defines `simulation/engine.py` (DES core) and `simulation/circuit_breaker.py`, but only `cascade.py`, `config.py`, and `world_state.py` were implemented. The `cli/brief.py` pipeline does not depend on the DES engine, so this is not a runtime bug — it is an incomplete spec deliverable. Acceptable given the pivot, but worth noting for any future agent-swarm work.

---

## Recommendations

1. **Fix MEDIUM (Day 8 — now actionable):** Wire `DbWriter.enqueue()` into `ops/alerts.py`, `scoring/ledger.py`, `scoring/prediction_log.py`, `budget/tracker.py`. This is mechanical — each site replaces a `conn.execute(sql, params)` with `await db_writer.enqueue(sql, params)`.

2. **Add `streamlit` and `plotly` to `pyproject.toml`** under an optional `[project.optional-dependencies]` group named `dashboard`.

3. **No test regressions detected.** The 47-test suite structure is healthy; the bug-fix commit from Oct 28 resolved prior HIGH issues.
