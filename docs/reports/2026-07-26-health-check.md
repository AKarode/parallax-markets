# Parallax Health Check — 2026-07-26

**Status: YELLOW**

## Summary

Test regressions appeared without code changes: 10 tests now fail vs. 0 yesterday, all in
`scoring/resolution.py` and `scoring/report_card.py`. The pattern (time-sensitive resolution
logic + proxy-alignment checks) strongly suggests date-dependent test fixtures have crossed an
expiry boundary as the wall-clock moved past expected resolution dates. Three carry-over HIGH
bugs remain unfixed. The codebase is otherwise stable; 436 tests pass.

---

## Repository State

```
HEAD:         4593310  chore: add uv.lock for reproducible backend dependency resolution
Tests (clean install):  436 passed | 10 failed | 13 skipped | 3 collection errors
Project mode: Research / archival — postmortem committed 2026-07-01
```

---

## Delta From Yesterday (2026-07-25)

| Area | Change |
|------|--------|
| Source code commits | 0 |
| Documentation commits | 1 (tech research 2026-07-25) |
| Infra commits | 1 (`uv.lock` added) |
| New bugs found | 2 (date-dependent test regressions — see below) |
| New issues resolved | 0 |
| Tests passing (clean install) | 436 (+3 vs yesterday — one prior collection error now resolves) |
| Tests failing (clean install) | 10 (**+10 vs yesterday's 0**) |
| Collection errors | 3 (−1 vs yesterday) |

---

## Issues Found

### NEW (HIGH)

- **[HIGH] `scoring/resolution.py` — 6 test failures, likely date-triggered regression**

  All 6 tests in `test_resolution.py` now fail, up from 0 yesterday. No source code changed.
  Failing tests: `test_detect_settled_market`, `test_skip_unsettled_market`,
  `test_backfill_updates_resolution_columns`, `test_backfill_buy_no_pnl`,
  `test_backfill_skips_already_resolved`, `test_check_resolutions_end_to_end`.

  The Iran/Hormuz scenario resolution window (April 7–21 2026) is now well past; test fixtures
  that create markets with hardcoded resolution dates anchored to that window likely now behave
  differently than when they were written (e.g., `resolve_by` dates that were in the future
  are now in the past, flipping branch conditions).

  Action: Read `test_resolution.py` conftest setup and inspect date/timestamp fixtures.
  Replace any hardcoded past dates with `datetime.now(UTC) + timedelta(days=N)` or parametric
  offsets so tests remain time-invariant.

- **[HIGH] `scoring/report_card.py` — 3 test failures, proxy-alignment logic broken**

  `test_buy_yes_resolution_above_half_aligned`, `test_buy_no_resolution_below_half_aligned`,
  `test_buy_yes_resolution_below_half_not_aligned` all fail under `TestProxyWasAlignedInResolution`.
  These test the `TestProxyWasAlignedInResolution` logic, which checks whether a BUY_YES or
  BUY_NO signal was correct given final resolution price. These were passing yesterday; the
  most likely cause is the same date-driven fixture drift as `test_resolution.py` — the
  `check_resolutions()` function these tests depend on may be pulling in stale or time-shifted
  state.

  Action: Investigate shared fixtures with `test_resolution.py`. If the same `resolve_by` date
  hardcoding is the root cause, fixing it in `conftest.py` should unblock both suites.

---

### CARRY-OVER (HIGH)

- **[HIGH] `scoring/selective.py:106` — `np.trapz` removed in NumPy 2.0 (flagged 2026-07-22)**

  `test_selective.py::test_risk_coverage_perfect_ranking` still fails with `AttributeError:
  module 'numpy' has no attribute 'trapz'` (NumPy 2.4.6 installed).

  Fix: `np.trapz(risk, coverage)` → `np.trapezoid(risk, coverage)` on line 106.

- **[HIGH] `portfolio/simulator.py:85` — P&L double-counting (flagged 22+ days)**

  ```python
  cash += payout - fees + (pos["quantity"] * pos["entry_price"])
  ```
  Re-adds entry cost on top of payout, inflating P&L on every closed position.

  Fix: `cash += payout - fees`

- **[HIGH] `cryptography` package missing from `pyproject.toml` (flagged 2026-07-22)**

  `markets/kalshi.py` imports `cryptography.hazmat.primitives` for RSA-PSS signing. Not
  declared in any dependency group; fresh installs will `ModuleNotFoundError` on first Kalshi
  call. Also causes 3 test collection errors (`test_brief.py`, `test_brief_resilience.py`,
  `test_kalshi.py`).

  Fix: Add `cryptography>=41.0` to base `dependencies` in `pyproject.toml`.

- **[HIGH] Core simulation/agent infrastructure never built (intentional pivot, undocumented)**

  `simulation/engine.py`, `simulation/circuit_breaker.py`, `agents/`, `spatial/`, `eval/`,
  and `ingestion/dedup.py` from the Phase 1 spec were never implemented. The `agent_memory`,
  `agent_prompts`, and `decisions` DuckDB tables are dead schema. Spec/plan documents are not
  marked as superseded.

  Fix: Add `## Status (superseded — pivoted to prediction-market edge-finder)` banner to
  `docs/superpowers/specs/2026-03-30-parallax-phase1-design.md` and the companion plan.

---

### CARRY-OVER (MEDIUM)

- **[MEDIUM] DuckDB single-writer pattern never wired**

  `db/writer.py` is implemented and tested but bypassed. Direct `conn.execute()` writes in
  12+ files: `cli/brief.py` (opens 5 separate `duckdb.connect()` connections), `budget/tracker.py`,
  `scoring/ledger.py`, `scoring/prediction_log.py`, `scoring/scorecard.py`, `scoring/tracker.py`,
  `contracts/registry.py`, `ingestion/crisis_ingester.py`, `ops/alerts.py`, `backtest/runner.py`,
  `backtest/look_ahead_guard.py`. Will produce `database is locked` errors under concurrent
  API + CLI use.

- **[MEDIUM] `numpy`/`pandas` not in base `[dev]` extras**

  `test_bench_forecast.py`, `test_calibration_metrics.py`, `test_recalibrators.py`,
  `test_selective.py` fail to collect on `pip install -e ".[dev]"`, silently masking regressions.

  Fix: Add `numpy>=1.26`, `pandas>=2.0`, `scikit-learn>=1.3` to `[dev]` extras (after fixing
  `np.trapz` first).

- **[MEDIUM] `ops/alerts.py:106` — blocking DuckDB write inside `async def send()`**

  `DuckDBAlertSink.send()` calls `self.db_conn.execute(...)` synchronously, blocking the
  event loop on every alert.

  Fix: `await asyncio.get_event_loop().run_in_executor(None, self.db_conn.execute, sql, params)`

- **[MEDIUM] 13 `test_mapping_policy.py` tests permanently skipped without `reason=`**

  No documented rationale. Should be removed or documented given archival status.

---

### CARRY-OVER (LOW)

- **[LOW] `requires-python = ">=3.11"` — looser than the 3.12 runtime in CLAUDE.md**
- **[LOW] `pytz>=2024.1` is legacy** — replace with stdlib `zoneinfo`
- **[LOW] No upper bounds on `fastapi`, `duckdb`, `anthropic`, `httpx`, `pydantic`**
- **[LOW] `httpx2` deprecation warning** on every test run (Starlette `TestClient`)
- **[LOW] `truthbrush>=0.2` unlocked** — upstream change could silently break Truth Social ingestion
- **[LOW] Missing `__init__.py`** in `portfolio/` and `parallax/config/`
- **[LOW] Frontend has no test framework** — `package.json` has no test runner configured

---

## Spec/Plan Consistency

Product is a prediction-market edge-finder (3 Claude models → Kalshi/Polymarket divergence →
paper trades). Phase 1 spec describes a 50-agent LLM swarm with H3 spatial visualization —
this was never built and the spec/plan are not marked as superseded. Frontend uses polling +
Recharts instead of WebSocket + deck.gl HexMap from the spec. Schema has grown from the spec's
10 tables to 26 tables + 2 views; agent/world-state tables exist but are dead.

---

## Recommendations (Priority Order)

1. **(30 min)** Investigate `test_resolution.py` + `test_report_card.py` fixture dates.
   Replace hardcoded past `resolve_by` timestamps with relative offsets to make tests
   time-invariant. This unblocks the 9 new regressions.

2. **(5 min)** `scoring/selective.py:106`: `np.trapz` → `np.trapezoid`. Fixes the 10th failure.

3. **(5 min)** `portfolio/simulator.py:85`: Drop `+ (pos["quantity"] * pos["entry_price"])`.

4. **(5 min)** `pyproject.toml`: Add `cryptography>=41.0` to base deps. Resolves 3 collection errors.

5. **(5 min)** `pyproject.toml`: Add `numpy>=1.26`, `pandas>=2.0`, `scikit-learn>=1.3` to
   `[dev]` extras (after #2 above).

6. **(Low)** `ops/alerts.py:106`: Fix blocking write in async context.

7. **(Low)** Mark Phase 1 spec/plan docs as superseded.
