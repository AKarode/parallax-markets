# Parallax Health Check — 2026-07-22

**Status: YELLOW**

## Summary

No production code changes since 2026-07-02; the repo has been docs-only for three weeks. A new HIGH issue was found today: `scoring/selective.py:106` uses `np.trapz`, which was removed in NumPy 2.0 — the test `test_selective.py::test_risk_coverage_perfect_ranking` now fails with `AttributeError`. This regression was masked in prior reports because `numpy`/`pandas` were not installed on a clean `pip install -e ".[dev]"`; when they are installed (NumPy 2.4.6 in this environment), the failure is exposed. All other carry-over issues remain unresolved.

---

## Repository State

```
HEAD:         e0e34b1  Tech research report: 2026-07-21
Tests (full): 490 passed | 1 FAILED | 13 skipped | 1 warning
              (clean install: 433 passed | 0 failed | 13 skipped | 4 collection errors)
Project mode: Research concluded — postmortem committed 2026-07-01
```

---

## Delta From Yesterday (2026-07-21)

| Area | Change |
|------|--------|
| Source code commits | 0 |
| Documentation commits | 1 (tech research: batch API + caching, spatial optimization, GDELT alternatives) |
| **New failing test** | `test_selective.py::test_risk_coverage_perfect_ranking` — `np.trapz` removed in NumPy 2.0 |
| Tests passing (full env) | 490 (+57 from newly-installed numpy/pandas) |
| Tests failing | **1 NEW** |
| Tests skipped | 13 (unchanged) |
| Collection errors (clean install) | 4 (unchanged — numpy/pandas absent) |

---

## Issues Found

### NEW

- **[HIGH] `scoring/selective.py:106` — `np.trapz` removed in NumPy 2.0**

  `selective.py` computes area under risk-coverage curve using `np.trapz(risk, coverage)`.
  `np.trapz` was deprecated in NumPy 1.24 and **removed in NumPy 2.0**. The environment
  installs NumPy 2.4.6 (within the `>=1.26` bound in `pyproject.toml`), causing a hard
  `AttributeError` at test time:

  ```
  AttributeError: module 'numpy' has no attribute 'trapz'
  ```

  Test: `backend/tests/test_selective.py::test_risk_coverage_perfect_ranking`

  Fix (one line in `scoring/selective.py:106`):
  ```python
  # Before:
  return float(np.trapz(risk, coverage))
  # After:
  return float(np.trapezoid(risk, coverage))
  ```
  `np.trapezoid` is available since NumPy 1.23 and is the correct replacement. The comment
  on line 101 also references `np.trapz` and should be updated.

---

### CARRY-OVER (HIGH)

- **[HIGH] `portfolio/simulator.py:85` — P&L double-counting bug (flagged 22 days)**

  Line 85: `cash += payout - fees + (pos["quantity"] * pos["entry_price"])`

  Adds the original entry cost back on top of the payout, inflating P&L on every
  closed position. The June 30 commit message claimed this was fixed; the change was
  never applied. Every backtest result, including the postmortem's −$0.35 finding, is
  produced by buggy arithmetic.

  Fix (one line):
  ```python
  cash += payout - fees
  ```

- **[HIGH] DuckDB single-writer pattern violated in 9+ production files**

  `db/writer.py` implements the correct `asyncio.Queue` single-writer pattern and is
  tested, but no production code routes through it. Direct `conn.execute()` writes occur
  in: `cli/brief.py`, `budget/tracker.py`, `scoring/ledger.py`, `scoring/prediction_log.py`,
  `scoring/scorecard.py`, `scoring/resolution.py`, `contracts/registry.py`,
  `ingestion/crisis_ingester.py`, `ops/alerts.py`. Concurrent callers (API + CLI) will
  race on the DuckDB file lock.

- **[HIGH] `cryptography` package missing from `pyproject.toml`**

  `markets/kalshi.py` (lines 19–20) imports `cryptography.hazmat.primitives` for RSA-PSS
  signing on every Kalshi request. `cryptography` does not appear in `pyproject.toml`
  dependencies. Clean install will fail with `ModuleNotFoundError` on first live Kalshi
  call; currently masked by transitive installation.

  Fix: Add `cryptography>=41.0` to base `dependencies`.

- **[HIGH] Core simulation/agent infrastructure never built (intentional pivot)**

  The Phase 1 spec modules (`simulation/engine.py`, `agents/`, `spatial/`, `eval/`) were
  never implemented. The product pivoted to prediction-market edge-finding. The spec and
  plan documents are superseded but not formally marked as such.

---

### CARRY-OVER (MEDIUM)

- **[MEDIUM] `numpy` / `pandas` not in base `[dev]` extras**

  Four test files fail to collect on a clean install because `numpy`/`pandas` are under
  the `[bench]` extras group but test imports are unconditional. Worse, once installed,
  the NumPy 2.0 incompatibility (see HIGH above) causes a hard test failure.

  Fix options:
  1. Add `numpy>=1.26,<2.0`, `pandas>=2.0`, `scikit-learn>=1.3` to base `[dev]` extras
     (add upper bound on numpy to avoid the 2.0 API break until `np.trapz` is replaced).
  2. Or: fix `np.trapz` → `np.trapezoid` first, then add to `[dev]` without upper bound.

- **[MEDIUM] `ops/alerts.py:106` — synchronous DuckDB write inside `async def send()`**

  `DuckDBAlertSink.send()` is declared `async` but executes `self.db_conn.execute(...)`
  synchronously, blocking the asyncio event loop on every alert. Has been flagged for
  multiple reports. Fix: wrap in `asyncio.get_event_loop().run_in_executor(None, ...)`.

- **[MEDIUM] 13 mapping-policy tests permanently skipped, no documented reason**

  All 13 skips in `test_mapping_policy.py` lack a `reason=` argument. Given the project
  is archival, these should be removed or have their skip reason documented.

---

### CARRY-OVER (LOW)

- **[LOW] `requires-python = ">=3.11"` — looser than spec (Python 3.12 required)**
- **[LOW] `pytz>=2024.1` is legacy** — use stdlib `zoneinfo` instead
- **[LOW] No upper bounds on `fastapi`, `duckdb`, `anthropic`, `httpx`, `pydantic`**
- **[LOW] `httpx2` deprecation warning** on every test run (Starlette `TestClient`)
- **[LOW] `truthbrush>=0.2` unlocked minimum pin** — upstream API change could silently break Truth Social ingestion
- **[LOW] `portfolio/__init__.py` and `parallax/config/__init__.py` missing** — implicit namespace packages

---

## Spec/Plan Consistency

No change from 2026-07-02. The codebase correctly reflects the prediction-market pivot; the
Phase 1 simulation spec is superseded. See 2026-07-02 report for the full comparison table.

---

## Recommendations (Priority Order)

1. **(5 min)** Fix `scoring/selective.py:106`: `np.trapz` → `np.trapezoid` (+ update comment on line 101). Unblocks the failing test and prevents silent breakage if `numpy` is added to `[dev]`.

2. **(5 min)** Fix `portfolio/simulator.py:85`: drop `+ (pos["quantity"] * pos["entry_price"])` from the cash update. Corrects the postmortem backtest number.

3. **(5 min)** Add `cryptography>=41.0` to `pyproject.toml` base dependencies. Prevents silent breakage on fresh installs.

4. **(5 min)** Add `numpy>=1.26`, `pandas>=2.0`, `scikit-learn>=1.3` to `[dev]` extras in `pyproject.toml` so `pytest` can collect all 58 bench tests without manual pre-installation.

5. **(Low)** Fix `ops/alerts.py:106` async-blocking write using `run_in_executor`.

6. **(Low)** Document or remove 13 skipped `test_mapping_policy.py` tests.

7. **(Low)** Pin numpy upper bound (`<2.0`) or fix all NumPy 2.0 incompatibilities before removing it.
