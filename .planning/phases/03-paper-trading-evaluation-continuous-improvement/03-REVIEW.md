---
phase: 03-paper-trading-evaluation-continuous-improvement
reviewed: 2026-04-09T12:00:00Z
depth: standard
files_reviewed: 18
files_reviewed_list:
  - backend/src/parallax/cli/brief.py
  - backend/src/parallax/contracts/mapping_policy.py
  - backend/src/parallax/dashboard/__init__.py
  - backend/src/parallax/dashboard/app.py
  - backend/src/parallax/dashboard/data.py
  - backend/src/parallax/db/schema.py
  - backend/src/parallax/scoring/calibration.py
  - backend/src/parallax/scoring/ledger.py
  - backend/src/parallax/scoring/recalibration.py
  - backend/src/parallax/scoring/report_card.py
  - backend/src/parallax/scoring/resolution.py
  - backend/tests/test_brief.py
  - backend/tests/test_dashboard_data.py
  - backend/tests/test_recalibration.py
  - backend/tests/test_report_card.py
  - scripts/cron-health-check.sh
  - scripts/install-cron.sh
  - scripts/parallax-cron.sh
findings:
  critical: 1
  warning: 5
  info: 3
  total: 9
status: issues_found
---

# Phase 03: Code Review Report

**Reviewed:** 2026-04-09T12:00:00Z
**Depth:** standard
**Files Reviewed:** 18
**Status:** issues_found

## Summary

Reviewed the Phase 03 paper trading, evaluation, and continuous improvement pipeline including the CLI brief, contract mapping, scoring/calibration system, dashboard, resolution checker, report card, and cron automation scripts. The codebase is well-structured with good separation of concerns and thorough test coverage. Key concerns: a shell script command injection risk in the cron error marker, an unreliable row count method in the resolution backfill, silent data isolation when using in-memory DuckDB defaults, and an unused function parameter in the dashboard data layer.

## Critical Issues

### CR-01: Command injection in cron error marker JSON

**File:** `scripts/parallax-cron.sh:41`
**Issue:** `$CMD` is interpolated directly into a JSON string without escaping. If command arguments contain double quotes, backslashes, or other special characters, the resulting JSON is malformed. More importantly, if this JSON is later parsed by a tool that evaluates embedded content, it creates an injection vector.
**Fix:**
```bash
# Replace line 41 with proper JSON escaping
ESCAPED_CMD=$(echo "$CMD" | sed 's/\\/\\\\/g; s/"/\\"/g')
echo "{\"timestamp\": \"$TIMESTAMP\", \"command\": \"$ESCAPED_CMD\", \"exit_code\": $EXIT_CODE}" > "$ERROR_DIR/$TIMESTAMP.json"
```

## Warnings

### WR-01: Unreliable row count after UPDATE in _backfill_signal

**File:** `backend/src/parallax/scoring/resolution.py:139-150`
**Issue:** The follow-up SELECT counts ALL rows matching `contract_ticker` and `resolved_at`, not just those updated by this specific call. If `_backfill_signal` is called multiple times for the same ticker (e.g., retries, or multiple settlement timestamps), the count will be incorrect -- it includes rows resolved by prior calls with the same timestamp.
**Fix:**
```python
# Option A: Use DuckDB's rowcount from the execute result
result = conn.execute(...)
# DuckDB >=0.9 supports result.fetchone() returning affected row count
# for UPDATE statements. Alternatively, count before and after:

count_before = conn.execute(
    "SELECT COUNT(*) FROM signal_ledger WHERE contract_ticker = ? AND resolution_price IS NOT NULL",
    [ticker],
).fetchone()[0]

# ... execute UPDATE ...

count_after = conn.execute(
    "SELECT COUNT(*) FROM signal_ledger WHERE contract_ticker = ? AND resolution_price IS NOT NULL",
    [ticker],
).fetchone()[0]

return count_after - count_before
```

### WR-02: In-memory DuckDB creates isolated databases across CLI subcommands

**File:** `backend/src/parallax/cli/brief.py:261,415,447,457`
**Issue:** When `DUCKDB_PATH` is not set, it defaults to `":memory:"`. Each `duckdb.connect(":memory:")` call creates a separate, isolated database. This means `run_brief` writes predictions to one in-memory DB, but `_run_check_resolutions`, `_run_calibration`, and `_run_report_card` each create their own empty in-memory DBs. Data is never shared. This silently produces empty results for `--calibration` and `--report-card` unless `DUCKDB_PATH` is explicitly set to a file.
**Fix:**
```python
# In the functions that create standalone connections, warn if using :memory:
db_path = os.environ.get("DUCKDB_PATH", ":memory:")
if db_path == ":memory:":
    logger.warning(
        "DUCKDB_PATH not set -- using in-memory DB. "
        "Data from prior runs will not be available."
    )
```

### WR-03: Unused `limit` parameter in get_latest_brief

**File:** `backend/src/parallax/dashboard/data.py:24-25`
**Issue:** The `limit` parameter is accepted but never used in the SQL query. The query always fetches only the latest single `run_id` regardless of what `limit` is set to.
**Fix:**
```python
def get_latest_brief(
    conn: duckdb.DuckDBPyConnection, limit: int = 1,
) -> list[dict]:
    rows = conn.execute(
        """
        SELECT model_id, probability, direction, confidence, reasoning, created_at
        FROM prediction_log
        WHERE run_id IN (
            SELECT DISTINCT run_id FROM prediction_log
            ORDER BY created_at DESC
            LIMIT ?
        )
        ORDER BY run_id DESC, model_id
        """,
        [limit],
    ).fetchall()
    # ... rest unchanged
```

### WR-04: Unquoted variable expansion in cron script

**File:** `scripts/parallax-cron.sh:29,36`
**Issue:** `$CMD` is used unquoted on lines 29 and 36. This causes word splitting and glob expansion if arguments contain spaces or wildcard characters. While current usage passes simple flags like `--scheduled --no-trade`, this is fragile.
**Fix:**
```bash
# Line 29
CMD="$*"  # or keep CMD="$@" but always quote usage

# Line 36
if python -m parallax.cli.brief "$@" >> "$RUN_LOG" 2>&1; then
```

### WR-05: proxy_was_aligned uses identical logic to model_was_correct

**File:** `backend/src/parallax/scoring/resolution.py:121-128`
**Issue:** Both `model_was_correct` and `proxy_was_aligned` use the exact same CASE WHEN logic. The schema and column naming suggest `proxy_was_aligned` should measure whether the proxy contract moved in the direction predicted by the model (i.e., was the proxy a good stand-in for the underlying prediction), which is a different question than whether the model's directional bet was correct. Currently they are always identical, making the field redundant.
**Fix:** Either remove `proxy_was_aligned` if it is intentionally identical, or implement distinct logic. For example, `proxy_was_aligned` could compare the model's raw prediction direction against the contract outcome, while `model_was_correct` evaluates the trade P&L.

## Info

### IN-01: DuckDB connection never closed in dashboard app

**File:** `backend/src/parallax/dashboard/app.py:37-39`
**Issue:** The `conn` opened via `duckdb.connect()` is never explicitly closed. Streamlit reruns `main()` on every user interaction, creating a new connection each time. While Python GC eventually cleans these up, explicit cleanup is better practice.
**Fix:**
```python
try:
    conn = duckdb.connect(db_path, read_only=True)
except Exception as e:
    st.error(f"Cannot connect to DuckDB: {e}")
    return

try:
    # ... all dashboard rendering ...
finally:
    conn.close()
```

### IN-02: Incorrect find command for today's scheduled run count

**File:** `scripts/cron-health-check.sh:23`
**Issue:** The `find` command uses `-newer "$HOME/parallax-logs/runs" -mtime 0` which does not reliably count today's files. The `-newer` flag compares against the directory's last modification time (which changes on every file write), and `-mtime 0` means "modified in the last 24 hours", not "modified today". These combined produce unpredictable results.
**Fix:**
```bash
RUNS=$(find "$HOME/parallax-logs/runs" -name "*.json" -newermt "$TODAY" 2>/dev/null | wc -l | tr -d ' ')
```

### IN-03: dashboard/__init__.py is empty

**File:** `backend/src/parallax/dashboard/__init__.py`
**Issue:** The file exists but is empty (0 content lines). This is fine for a namespace package marker but the module has no public API exports. This is consistent with the project convention of minimal `__init__.py` files, so no action needed -- noted for completeness.

---

_Reviewed: 2026-04-09T12:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
