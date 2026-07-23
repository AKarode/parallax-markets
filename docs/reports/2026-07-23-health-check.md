# Parallax Health Check — 2026-07-23

**Status: YELLOW**

## Summary

No production code changes since 2026-07-02; the repo remains in archival/research mode. All
carry-over issues from yesterday are unresolved. The three HIGH bugs — `np.trapz` NumPy 2.0
incompatibility, P&L double-counting in `portfolio/simulator.py`, and undeclared `cryptography`
dependency — remain unfixed. Test baseline is stable: 433 passed / 13 skipped / 0 failed on a
clean `[dev]` install; 4 collection errors persist for the numpy-dependent bench test files.

---

## Repository State

```
HEAD:         ed8d00c  Add tech research report: 2026-07-22 findings
Tests (clean install):  433 passed | 0 failed | 13 skipped | 4 collection errors
Tests (full env w/ numpy):  490 passed | 1 FAILED | 13 skipped
Project mode: Research / archival — postmortem committed 2026-07-01
```

---

## Delta From Yesterday (2026-07-22)

| Area | Change |
|------|--------|
| Source code commits | 0 |
| Documentation commits | 1 (tech research: Sonnet 5, GDELT Cloud, Batch API, DuckDB upgrades) |
| New bugs found | 0 |
| New issues resolved | 0 |
| Tests passing (clean install) | 433 (unchanged) |
| Tests failing (clean install) | 0 (unchanged) |
| Collection errors | 4 (unchanged — numpy/pandas absent from `[dev]` extras) |

---

## Issues Found

### CARRY-OVER (HIGH)

- **[HIGH] `scoring/selective.py:106` — `np.trapz` removed in NumPy 2.0 (flagged 2026-07-22)**

  `selective.py` computes area under the risk-coverage curve with `np.trapz(risk, coverage)`.
  `np.trapz` was removed in NumPy 2.0; with NumPy 2.4.6 installed the test
  `test_selective.py::test_risk_coverage_perfect_ranking` fails with `AttributeError`.

  Fix (two lines in `scoring/selective.py`):
  ```python
  # Line 101 comment: update reference from np.trapz → np.trapezoid
  # Line 106:
  return float(np.trapezoid(risk, coverage))  # was np.trapz
  ```

- **[HIGH] `portfolio/simulator.py:85` — P&L double-counting (flagged 22+ days)**

  ```python
  cash += payout - fees + (pos["quantity"] * pos["entry_price"])
  ```
  Re-adds the entry cost on top of the payout, inflating P&L on every closed position.
  Every backtest result produced by this codebase (including the postmortem's −$0.35 figure)
  uses buggy arithmetic.

  Fix:
  ```python
  cash += payout - fees
  ```

- **[HIGH] `cryptography` package missing from `pyproject.toml` (flagged 2026-07-22)**

  `markets/kalshi.py` lines 19–20 import `cryptography.hazmat.primitives` for RSA-PSS signing
  on every Kalshi API request. `cryptography` is absent from `pyproject.toml`; fresh installs
  will fail with `ModuleNotFoundError` on the first live Kalshi call.

  Fix: Add `cryptography>=41.0` to base `dependencies` in `pyproject.toml`.

- **[HIGH] Core simulation/agent infrastructure never built (intentional pivot, unflagged in docs)**

  `simulation/engine.py`, `simulation/circuit_breaker.py`, `agents/`, `spatial/`, and `eval/`
  modules from the Phase 1 spec were never implemented. The product pivoted to
  prediction-market edge-finding. The spec and plan documents are not marked as superseded.
  The `agent_memory`, `agent_prompts`, and `decisions` tables in `db/schema.py` are dead
  schema — no code writes to them.

  Fix: Add a `## Status` section to the spec and plan docs noting the pivot date and current
  product direction.

---

### CARRY-OVER (MEDIUM)

- **[MEDIUM] DuckDB single-writer pattern implemented but never wired (flagged 22+ days)**

  `db/writer.py` provides the correct `asyncio.Queue` single-writer and is tested, but zero
  production code routes through it. Direct `conn.execute()` writes in 9+ files (`cli/brief.py`,
  `budget/tracker.py`, `scoring/ledger.py`, `scoring/prediction_log.py`, `scoring/scorecard.py`,
  `scoring/resolution.py`, `contracts/registry.py`, `ingestion/crisis_ingester.py`,
  `ops/alerts.py`) will race on the DuckDB file lock under concurrent API + CLI use.

- **[MEDIUM] `numpy`/`pandas` not in base `[dev]` extras**

  Four test files (`test_bench_forecast.py`, `test_calibration_metrics.py`,
  `test_recalibrators.py`, `test_selective.py`) fail to collect on `pip install -e ".[dev]"`.
  They are silently skipped during standard CI, masking the `np.trapz` regression.

  Fix: Add `numpy>=1.26`, `pandas>=2.0`, `scikit-learn>=1.3` to `[dev]` extras. Fix `np.trapz`
  first to avoid the test failure being immediately exposed.

- **[MEDIUM] `ops/alerts.py:106` — synchronous DuckDB write inside `async def send()`**

  `DuckDBAlertSink.send()` is declared `async` but calls `self.db_conn.execute(...)` blocking
  the event loop on every alert dispatch.

  Fix: `await asyncio.get_event_loop().run_in_executor(None, self.db_conn.execute, sql, params)`

- **[MEDIUM] 13 `test_mapping_policy.py` tests permanently skipped without `reason=`**

  All 13 skips have no documented rationale. Given archival status these should be removed or
  documented.

---

### CARRY-OVER (LOW)

- **[LOW] `requires-python = ">=3.11"` — looser than the 3.12 runtime spec requires**
- **[LOW] `pytz>=2024.1` is legacy** — replace with stdlib `zoneinfo`
- **[LOW] No upper bounds on `fastapi`, `duckdb`, `anthropic`, `httpx`, `pydantic`** — silent
  break risk on major version bumps
- **[LOW] `httpx2` deprecation warning** on every test run (Starlette `TestClient`)
- **[LOW] `truthbrush>=0.2` unlocked** — upstream API change could silently break Truth Social
  ingestion
- **[LOW] Missing `__init__.py`** in `portfolio/` and `parallax/config/` — implicit namespace
  packages

---

## Spec/Plan Consistency

No change since 2026-07-02. The codebase correctly reflects the prediction-market pivot.
Phase 1 simulation spec is superseded but not formally marked as such. Schema has grown from
10 spec-defined tables to 26 tables + 2 views. The `agents/`, `spatial/`, and `eval/` module
trees from the plan were never built.

---

## Recommendations (Priority Order)

1. **(5 min)** `scoring/selective.py:106`: `np.trapz` → `np.trapezoid`, update comment on
   line 101. Unblocks the failing test and is a prerequisite for adding numpy to `[dev]`.

2. **(5 min)** `portfolio/simulator.py:85`: Drop `+ (pos["quantity"] * pos["entry_price"])`
   from cash update. Corrects postmortem P&L arithmetic.

3. **(5 min)** `pyproject.toml`: Add `cryptography>=41.0` to base dependencies.

4. **(5 min)** `pyproject.toml`: Add `numpy>=1.26`, `pandas>=2.0`, `scikit-learn>=1.3` to
   `[dev]` extras (after fixing #1 above).

5. **(Low)** `ops/alerts.py:106`: Fix blocking write in async context via `run_in_executor`.

6. **(Low)** Document or remove the 13 skipped `test_mapping_policy.py` tests.

7. **(Low)** Add a `## Status (superseded)` banner to the Phase 1 spec and plan docs.
