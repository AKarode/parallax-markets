# Parallax Health Check — 2026-08-21

**Status: YELLOW**

## Summary

No code changes since `31244dd` (2026-08-20 tech research report). Tests hold at 433 passed / 0 failed / 13 skipped with 4 unchanged collection errors (`numpy`/`pandas`/`sklearn` missing from `[dev]` extras). All issues are carry-forwards; no regressions, no new findings.

---

## Repository State

```
HEAD:         31244dd  Add daily tech research scout report for 2026-08-20
Tests:        433 passed | 0 failed | 13 skipped | 4 collection errors
              (unchanged from 2026-08-20)
Project mode: Archival — postmortem committed 2026-07-01, no new production code expected
```

---

## Changes Since Last Report (2026-08-20)

No new commits to production code. No issues resolved. All findings below are unchanged carry-forwards.

---

## Issues Found

### HIGH

- **[HIGH] DuckDB single-writer pattern not enforced (carry-forward, day 5+)**

  `db/writer.py` implements `DbWriter` (asyncio.Queue → DuckDB) per spec, but every production module bypasses it with direct `conn.execute()` writes. Confirmed files:
  `scoring/scorecard.py`, `scoring/tracker.py`, `scoring/ledger.py`, `scoring/resolution.py`, `scoring/prediction_log.py`, `cli/brief.py`, `main.py`, `ops/alerts.py`, `contracts/registry.py`, `ingestion/crisis_ingester.py`, `backtest/runner.py`, `budget/tracker.py`.

  `cli/brief.py` opens 5 separate `duckdb.connect()` calls across async functions; concurrent runs risk `database is locked` errors.

  Risk is low in archival/single-process mode but is the most significant structural debt if the project is reactivated.

- **[HIGH] `portfolio/simulator.py:84-85` — P&L double-counting bug (persistent)**

  Lines 82–85:
  ```python
  fees = pos["quantity"] * entry_price * FEE_RATE
  pnl = payout - fees                                         # omits cost basis
  cash += payout - fees + (pos["quantity"] * pos["entry_price"])  # restores only entry_price, not effective cost
  ```
  Both `pnl` and `cash` are wrong: cost basis is excluded from `pnl`, and only `quantity × entry_price` (not full cost-including-fees) is returned to `cash`. Postmortem −$0.35 figure computed with this engine is directionally correct (no edge) but numerically unreliable. Two-line fix documented in 2026-07-04 report.

- **[HIGH] Phase 1 spec/plan are stale; v2 architecture is undocumented**

  `docs/superpowers/specs/2026-03-30-parallax-phase1-design.md` and `docs/superpowers/plans/2026-03-30-parallax-phase1.md` describe a 50-agent swarm + H3 hex map + WebSocket DES — architecture never built. The actual v2 system is documented only in `CLAUDE.md`. No v2 spec file exists.

### MEDIUM

- **[MEDIUM] Missing `__init__.py` in `portfolio/` and `config/` packages (carry-forward)**

  `backend/src/parallax/portfolio/` and `backend/src/parallax/config/` both lack `__init__.py`. Imports work in tests because pytest adds the `src/` path, but a clean `pip install` in strict environments may fail. Trivial two-file fix.

- **[MEDIUM] 4 test files uncollectable — missing bench extras**

  `test_bench_forecast.py`, `test_calibration_metrics.py`, `test_recalibrators.py`, `test_selective.py` fail collection with `ModuleNotFoundError` for `pandas`, `numpy`, `sklearn`. These live in the `[bench]` extras group only. Broken collection silently hides any future failures in those files.

  Fix: add `pytest.importorskip("pandas")` guards, or add bench deps to `[dev]` extras.

- **[MEDIUM] `ingestion/dedup.py` never implemented**

  Plan Task 10 specified semantic dedup via `sentence-transformers`. No dedup layer exists between GDELT DOC fetch and signal generation; duplicate signals from the same event can inflate confidence scores.

### LOW

- **[LOW] CLAUDE.md lists v1-only stack dependencies not in `pyproject.toml`**

  `h3>=4.1`, `searoute>=1.3`, `shapely>=2.0`, `sentence-transformers>=3.4`, `websockets>=14.0`, `google-cloud-bigquery>=3.27` appear under "Key Dependencies" but are absent from `pyproject.toml` and not installed.

- **[LOW] `pyproject.toml` python floor mismatch**

  Spec and CLAUDE.md require `>=3.12`; `pyproject.toml` declares `>=3.11`; runtime environment is Python 3.11. Not currently a breakage, but the declared floor diverges from the stated requirement.

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
- 433 tests passing with strong coverage of v2 modules.

---

## Recommendations (priority order)

1. **[Immediate]** Add `pytest.importorskip("pandas")` / `pytest.importorskip("numpy")` guards to 4 bench test files, or add bench deps to `[dev]`. Broken collection hides failures silently.
2. **[Short-term]** Add `__init__.py` to `parallax/portfolio/` and `parallax/config/` — two-file fix.
3. **[Short-term]** Fix `portfolio/simulator.py:84-85` P&L double-counting — two-line correction for archival accuracy.
4. **[Medium-term]** Write a v2 design doc under `docs/superpowers/specs/` and mark the Phase 1 spec as archived.
5. **[Low-priority]** Decide on DbWriter enforcement or document single-process assumption explicitly in CLAUDE.md.
6. **[Low-priority]** Clean up CLAUDE.md stack section to remove v1-only dependencies.
