---
phase: 03-paper-trading-evaluation-continuous-improvement
reviewed: 2026-04-09T18:30:00Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - backend/src/parallax/contracts/mapping_policy.py
  - backend/src/parallax/cli/brief.py
  - backend/tests/test_mapping_policy.py
findings:
  critical: 0
  warning: 3
  info: 2
  total: 5
status: issues_found
---

# Phase 03: Code Review Report

**Reviewed:** 2026-04-09T18:30:00Z
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found

## Summary

Reviewed the contract mapping policy, CLI brief pipeline, and mapping policy tests. The mapping policy itself is well-structured with clean separation of concerns. The main issues are resource management in the brief pipeline (DuckDB connection leak), use of a private API method, and a mutable-object mutation pattern that could cause subtle bugs across prediction models sharing the same pipeline run.

## Warnings

### WR-01: DuckDB connection never closed in run_brief()

**File:** `backend/src/parallax/cli/brief.py:262`
**Issue:** `run_brief()` opens a DuckDB connection at line 262 (`conn = duckdb.connect(db_path)`) but never closes it. Every other function in this file (`_run_check_resolutions` at line 438, `_run_calibration` at line 450, `_run_report_card` at line 462) properly calls `conn.close()`. When `db_path` is a file (not `:memory:`), repeated calls accumulate open connections, and on some platforms DuckDB's single-writer lock can cause subsequent runs to block or fail.
**Fix:**
Wrap the connection in a try/finally block or use it as a context manager. Simplest fix:
```python
async def run_brief(...) -> str:
    budget = BudgetTracker(daily_cap_usd=20.0)
    run_id = str(uuid.uuid4())
    db_path = os.environ.get("DUCKDB_PATH", ":memory:")
    conn = duckdb.connect(db_path)
    try:
        create_tables(conn)
        # ... rest of function body ...
        return brief
    finally:
        conn.close()
```

### WR-02: Mutation of shared PredictionOutput objects during divergence construction

**File:** `backend/src/parallax/cli/brief.py:367`
**Issue:** Line 367 mutates `pred_match.kalshi_ticker = sig.contract_ticker` on the original `PredictionOutput` object from the `predictions` list. When multiple signals map to the same prediction model (e.g., `hormuz_reopening` maps to both `KXCLOSEHORMUZ-27JAN` and `KXWTIMAX-26DEC31`), the second iteration overwrites the `kalshi_ticker` set by the first. This means the `Divergence` objects and any downstream consumer of `predictions` see an inconsistent `kalshi_ticker` value -- whichever signal was processed last wins.
**Fix:**
Either create a shallow copy of the prediction per divergence, or stop mutating the shared object:
```python
from copy import copy

if pred_match and mp_match:
    pred_copy = copy(pred_match)
    pred_copy.kalshi_ticker = sig.contract_ticker
    div = Divergence(
        ...
        prediction=pred_copy,
        ...
    )
```

### WR-03: Direct use of private _request() method on KalshiClient

**File:** `backend/src/parallax/cli/brief.py:643`
**Issue:** `_fetch_kalshi_markets()` calls `client._request("GET", "/markets", ...)` which is a private method (prefixed with `_`). This couples the CLI directly to KalshiClient internals and will break silently if the client's internal API changes. The method is also not part of the documented public interface per the module map in CLAUDE.md.
**Fix:**
Add a public method to `KalshiClient` for fetching markets by event ticker, e.g.:
```python
# In markets/kalshi.py
async def get_event_markets(self, event_ticker: str, limit: int = 10) -> list[dict]:
    data = await self._request("GET", "/markets", params={"event_ticker": event_ticker, "limit": limit})
    return data.get("markets", [])
```
Then in brief.py:
```python
markets = await client.get_event_markets(event_ticker)
```

## Info

### IN-01: Deprecated legacy mapping function still present

**File:** `backend/src/parallax/cli/brief.py:465-539`
**Issue:** `_map_predictions_to_markets_legacy()` (75 lines) is marked DEPRECATED but still present. It is not called anywhere in the codebase. This is dead code that adds maintenance burden and cognitive load.
**Fix:** Remove the function or move it to a `_legacy.py` module if it is needed for reference. The docstring says "Kept for reference" which is a valid reason, but a comment pointing to the git commit where it was replaced would be more durable than keeping the code inline.

### IN-02: Repeated get_active_contracts() call inside nested loop

**File:** `backend/src/parallax/cli/brief.py:347-350`
**Issue:** `registry.get_active_contracts()` is called inside the inner loop (once per mapping per prediction) to look up a contract title. This executes the same SQL query repeatedly when it could be called once before the loop. While not a correctness bug, it is a code quality issue -- the intent is just a title lookup but the implementation re-queries all active contracts each time.
**Fix:**
```python
# Before the loop
active_contracts = {c.ticker: c.title for c in registry.get_active_contracts()}

# Inside the loop
contract_title = active_contracts.get(mapping.contract_ticker)
```

---

_Reviewed: 2026-04-09T18:30:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
