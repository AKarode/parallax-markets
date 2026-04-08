---
phase: 01-contract-registry-mapping-policy-evaluation-ledger
reviewed: 2026-04-08T12:00:00Z
depth: standard
files_reviewed: 13
files_reviewed_list:
  - backend/src/parallax/cli/brief.py
  - backend/src/parallax/contracts/__init__.py
  - backend/src/parallax/contracts/mapping_policy.py
  - backend/src/parallax/contracts/registry.py
  - backend/src/parallax/contracts/schemas.py
  - backend/src/parallax/db/schema.py
  - backend/src/parallax/scoring/ledger.py
  - backend/tests/test_brief.py
  - backend/tests/test_contracts_schemas.py
  - backend/tests/test_ledger.py
  - backend/tests/test_mapping_policy.py
  - backend/tests/test_registry.py
  - backend/tests/test_schema.py
findings:
  critical: 1
  warning: 4
  info: 2
  total: 7
status: issues_found
---

# Phase 01: Code Review Report

**Reviewed:** 2026-04-08T12:00:00Z
**Depth:** standard
**Files Reviewed:** 13
**Status:** issues_found

## Summary

This phase introduces the Contract Registry, Mapping Policy, and Signal Ledger -- the core infrastructure for mapping prediction model outputs to tradeable contracts with proxy-aware confidence discounting. The code is well-structured, follows project conventions, and has comprehensive test coverage. However, there are several issues: a fragile positional column mapping in the ledger that will break silently if the schema changes, an N+1 query pattern in the registry, a DuckDB connection leak in the brief pipeline, and a mutable default argument on a Pydantic model.

## Critical Issues

### CR-01: Fragile positional column mapping in SignalLedger._row_to_record()

**File:** `backend/src/parallax/scoring/ledger.py:215-243`
**Issue:** `_row_to_record()` maps `SELECT *` results to `SignalRecord` fields by positional index (row[0], row[1], ..., row[24]). If the `signal_ledger` table schema is ever reordered, or a column is added in the middle, all downstream fields silently receive wrong values. This is especially dangerous because DuckDB's `SELECT *` column order is not guaranteed to match insertion order across schema migrations. A wrong `signal` or `effective_edge` value could trigger incorrect trades.
**Fix:** Use named column access. Either query explicit column names instead of `SELECT *`, or use DuckDB's `.df()` / `.fetchdf()` to get named columns:
```python
def _row_to_record(self, row: tuple) -> SignalRecord:
    # Replace SELECT * with explicit column list in get_signals() and get_actionable_signals()
    # e.g.: SELECT signal_id, created_at, model_id, ... FROM signal_ledger
    ...
```
Or define the column list as a module constant and use it in both queries and the mapping function to keep them in sync.

## Warnings

### WR-01: DuckDB connection opened but never closed in run_brief()

**File:** `backend/src/parallax/cli/brief.py:231-232`
**Issue:** `conn = duckdb.connect(db_path)` opens a DuckDB connection that is never closed. When `db_path` is a file path (not `:memory:`), this holds a file lock for the process lifetime and can cause errors if another process (e.g., FastAPI server) tries to access the same DB. In-memory mode is unaffected but the code path supports file-based DB via `DUCKDB_PATH` env var.
**Fix:** Use a context manager or explicit close:
```python
conn = duckdb.connect(db_path)
try:
    create_tables(conn)
    # ... rest of pipeline
finally:
    conn.close()
```

### WR-02: N+1 query pattern in ContractRegistry.get_contracts_for_model()

**File:** `backend/src/parallax/contracts/registry.py:164-197`
**Issue:** For each row returned from the `contract_proxy_map` join query, `_load_contract(ticker)` executes two additional queries (one for the contract row, one for its proxy map). With 4 initial contracts and 3 model types, this is manageable now, but if the registry grows, this becomes an N+1 query anti-pattern that could cause logic bugs if the DB state changes between queries in a concurrent environment.
**Fix:** Load the full contract data in the initial query with a JOIN, or batch-load all needed tickers in a single query:
```python
# Option: batch load
tickers = [row[0] for row in rows]
contracts_by_ticker = {c.ticker: c for c in self._batch_load_contracts(tickers)}
```

### WR-03: Mutable default dict shared across ContractRecord instances

**File:** `backend/src/parallax/contracts/schemas.py:45`
**Issue:** `discount_map: dict[str, float] = DEFAULT_DISCOUNT_MAP` uses a module-level mutable dict as a default value. In Pydantic v2, this is safe because Pydantic copies defaults during validation. However, if anyone mutates `record.discount_map` in-place (e.g., `record.discount_map["direct"] = 0.5`), it could affect the module-level `DEFAULT_DISCOUNT_MAP` in Pydantic v1 or if the model config changes. This is a latent bug.
**Fix:** Use `default_factory` pattern:
```python
from pydantic import Field

discount_map: dict[str, float] = Field(default_factory=lambda: {
    "direct": 1.0, "near_proxy": 0.6, "loose_proxy": 0.3, "none": 0.0,
})
```

### WR-04: Redundant contract lookup in run_brief() inner loop

**File:** `backend/src/parallax/cli/brief.py:249-254`
**Issue:** Inside the `for mapping in mappings` loop, `registry.get_active_contracts()` is called on every iteration to find the contract title. This queries the DB repeatedly for the same data. With 3 predictions times ~3-4 mappings each, this is ~12 redundant DB round-trips.
**Fix:** Hoist the lookup outside both loops:
```python
active_contracts = {c.ticker: c for c in registry.get_active_contracts()}
for pred in predictions:
    mappings = policy.evaluate(pred, market_prices)
    for mapping in mappings:
        contract_title = active_contracts.get(mapping.contract_ticker, None)
        title = contract_title.title if contract_title else None
        ...
```

## Info

### IN-01: Async test methods missing pytest.mark.asyncio decorator

**File:** `backend/tests/test_brief.py:154-178`
**Issue:** The `TestRunBriefDryRun` class has `async def` test methods but no `@pytest.mark.asyncio` decorator or class-level marker. These tests rely on pytest-asyncio's `auto` mode being configured (via `pyproject.toml` or `pytest.ini`). If `auto` mode is not set, these tests will silently be collected but not properly awaited.
**Fix:** Add explicit markers for clarity:
```python
@pytest.mark.asyncio
async def test_dry_run_produces_output(self, capsys):
    ...
```

### IN-02: Deprecated legacy mapping function retained

**File:** `backend/src/parallax/cli/brief.py:299-373`
**Issue:** `_map_predictions_to_markets_legacy()` is marked as DEPRECATED and retained "for reference." This is 74 lines of dead code. While the docstring explains the intent, dead code increases maintenance burden and can confuse new contributors.
**Fix:** Consider moving to a `docs/` or `archive/` location, or remove it entirely since git history preserves it.

---

_Reviewed: 2026-04-08T12:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
