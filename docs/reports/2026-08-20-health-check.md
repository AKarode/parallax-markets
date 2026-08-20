# Parallax Health Check — 2026-08-20

**Status: YELLOW**

No code changes since 2026-08-19. All core tests pass (433 passed, 13 skipped); 4 test files fail to collect due to missing bench extras (`numpy`, `pandas`, `sklearn`). The three standing architectural concerns from prior runs remain open: DuckDB single-writer violations throughout the codebase, stale Phase 1 spec/plan documentation, and missing `__init__.py` in `portfolio/` and `config/` packages.

---

## Issues Found

### [HIGH] DuckDB single-writer pattern not enforced (unchanged from prior runs)

- `db/writer.py` implements `DbWriter` (asyncio.Queue → DuckDB) per spec, but every non-db module bypasses it with direct `conn.execute()` writes.
- Violations confirmed in: `scoring/scorecard.py`, `scoring/tracker.py`, `scoring/ledger.py`, `scoring/resolution.py`, `scoring/prediction_log.py`, `cli/brief.py`, `main.py`, `ops/alerts.py`, `contracts/registry.py`, `ingestion/crisis_ingester.py`, `backtest/runner.py`, `budget/tracker.py`.
- `cli/brief.py` opens 5 separate `duckdb.connect(runtime.db_path)` calls in different async functions — if any two run concurrently (e.g., resolution check while a brief runs), a `database is locked` error is possible.
- No changes made since this was first flagged on 2026-08-17.

### [HIGH] Phase 1 spec/plan are stale; v2 architecture is undocumented

- `docs/superpowers/specs/2026-03-30-parallax-phase1-design.md` and `docs/superpowers/plans/2026-03-30-parallax-phase1.md` describe a 50-agent LLM swarm, H3 hex map, WebSocket streaming, and DES simulation. This architecture was never built.
- The actual v2 system (3-model prediction pipeline + Kalshi paper trading) is documented only in `CLAUDE.md`, not in any spec/plan file.
- No action taken since flagged.

### [MEDIUM] Missing `__init__.py` in `portfolio/` and `config/` packages

- `backend/src/parallax/portfolio/` — no `__init__.py`. Contains `allocator.py`, `schemas.py`, `simulator.py`.
- `backend/src/parallax/config/` — no `__init__.py`. Contains `risk.py`.
- Imports work in tests because pytest adds the src path, but this is fragile. A clean `pip install` in a strict environment may fail.
- First flagged 2026-08-19; not fixed.

### [MEDIUM] 4 test files uncollectable — missing bench extras

- `tests/test_bench_forecast.py`, `tests/test_calibration_metrics.py`, `tests/test_recalibrators.py`, `tests/test_selective.py` all fail to collect with `ModuleNotFoundError: No module named 'pandas'` (and `numpy`, `sklearn`).
- Root cause: these tests require `[bench]` extras (`pip install -e ".[bench]"`), but CI and the dev install only do `pip install -e ".[dev]"`.
- Fix: either add bench deps to `[dev]`, or gate these tests with `pytest.importorskip("pandas")`.

### [MEDIUM] `ingestion/dedup.py` never implemented

- Plan Task 10 specified semantic dedup using `sentence-transformers`. Never built.
- Currently no dedup layer between GDELT DOC fetch and signal generation; duplicate signals from the same event can inflate confidence scores.

### [LOW] CLAUDE.md lists v1-only stack dependencies

- `h3>=4.1`, `searoute>=1.3`, `shapely>=2.0`, `sentence-transformers>=3.4`, `websockets>=14.0`, `google-cloud-bigquery>=3.27` are listed under "Key Dependencies" but are not in `pyproject.toml` and are not installed.
- Misleads developers about what the system actually uses.

### [LOW] `pyproject.toml` python version mismatch

- Spec says `>=3.12`. `pyproject.toml` says `>=3.11`. Runtime environment has Python 3.11.
- Currently not a problem, but spec claims 3.12 features may be used (union type `|` syntax is fine since 3.10).

---

## Test Suite Status

| Scope | Result |
|-------|--------|
| Core suite (433 tests, 13 skipped) | ✅ PASS |
| `test_bench_forecast.py` | ❌ Collection error (no pandas) |
| `test_calibration_metrics.py` | ❌ Collection error (no numpy) |
| `test_recalibrators.py` | ❌ Collection error (no sklearn) |
| `test_selective.py` | ❌ Collection error (no pandas) |

---

## What's Healthy

- Full prediction pipeline operational: Google News + GDELT DOC → Claude Sonnet × 3 models → Kalshi/Polymarket divergence → paper trade.
- Scoring/calibration system mature: 13 modules including recalibration, track record, selective filtering, daily scorecard ETL.
- Budget guard: $20/day cap enforced with per-model cost logging.
- Backtest system with look-ahead guard preventing future data leakage.
- 47 test files with strong coverage of v2 modules.
- Daily automated health checks operational (160+ reports in `docs/reports/`).

---

## Recommendations (priority order)

1. **[Immediate]** Fix the 4 uncollectable test files: add `pytest.importorskip("pandas")` / `pytest.importorskip("numpy")` guards, or add bench deps to `[dev]`. Broken test collection hides failures.
2. **[Short-term]** Add `__init__.py` to `parallax/portfolio/` and `parallax/config/` — two-line fix.
3. **[Short-term]** Decide on DbWriter enforcement: either route all writes through it or document (in CLAUDE.md) that v2 relies on sequential CLI runs and single-process FastAPI, making GIL-level serialization sufficient.
4. **[Medium-term]** Write a v2 design doc under `docs/superpowers/specs/` and archive the Phase 1 spec with a redirect note.
5. **[Low-priority]** Clean up CLAUDE.md stack section to remove v1-only dependencies.
