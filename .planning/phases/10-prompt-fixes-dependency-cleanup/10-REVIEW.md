---
phase: 10-prompt-fixes-dependency-cleanup
reviewed: 2026-04-12T22:30:00Z
depth: standard
files_reviewed: 11
files_reviewed_list:
  - backend/src/parallax/prediction/crisis_context.py
  - backend/src/parallax/prediction/oil_price.py
  - backend/src/parallax/prediction/ceasefire.py
  - backend/src/parallax/prediction/hormuz.py
  - backend/src/parallax/scoring/track_record.py
  - backend/src/parallax/cli/brief.py
  - backend/src/parallax/backtest/engine.py
  - backend/tests/test_crisis_context.py
  - backend/tests/test_track_record.py
  - backend/tests/test_prediction.py
  - backend/pyproject.toml
findings:
  critical: 0
  warning: 6
  info: 4
  total: 10
status: issues_found
---

# Phase 10: Code Review Report

**Reviewed:** 2026-04-12T22:30:00Z
**Depth:** standard
**Files Reviewed:** 11
**Status:** issues_found

## Summary

Reviewed prediction model prompts, track record injection, CLI pipeline, backtest engine, tests, and project configuration. No critical security vulnerabilities found. The codebase is well-structured with parameterized SQL queries, proper error handling on JSON parsing, and good test coverage for the new track_record module.

Key concerns are: (1) the DuckDB connection in `run_brief()` is not protected by try/finally, risking leaked connections on exceptions; (2) all three prediction models access `response.content[0]` without guarding against empty content arrays; (3) LLM-returned probabilities from parsed JSON are not validated/clamped before being passed to `PredictionOutput`, relying entirely on Pydantic to raise -- which surfaces as an unhandled `ValueError` at the caller; (4) budget cap is never checked before making LLM calls; (5) model identifier mismatch between code (`opus`) and docstrings/comments (`Sonnet`).

## Warnings

### WR-01: DuckDB connection leak on exception in run_brief()

**File:** `backend/src/parallax/cli/brief.py:454-623`
**Issue:** `run_brief()` opens a DuckDB connection at line 454 and closes it at line 623, but there is no try/finally block protecting the ~170 lines between them. If any exception is thrown (e.g., by `asyncio.gather` on prediction models, `_persist_market_prices`, `ContractRegistry`, `SignalLedger`, or the paper trade execution block), `conn.close()` is never called. DuckDB file connections that are not closed can leave lock files and corrupt state, especially given the "single-writer" constraint noted in CLAUDE.md.
**Fix:** Wrap the connection lifecycle in try/finally:
```python
conn = duckdb.connect(runtime.db_path)
try:
    create_tables(conn)
    _persist_run_start(conn, run_id, runtime)
    # ... all existing logic ...
    _persist_run_end(conn, run_id, ...)
finally:
    conn.close()
```
Alternatively, record the error in the `runs` table inside an except block before re-raising. The existing `_persist_run_end` with `status="completed"` already has an `error` parameter that is never used.

### WR-02: Unchecked index access on LLM response content array

**File:** `backend/src/parallax/prediction/oil_price.py:139`, `ceasefire.py:114`, `hormuz.py:116`
**Issue:** All three predictors access `response.content[0].text` without checking that `response.content` is non-empty. While the Anthropic API typically returns at least one content block, an API error, timeout, or unexpected response shape could produce an empty `content` list, resulting in an `IndexError` with no useful error message.
**Fix:** Add a guard before indexing:
```python
if not response.content:
    raise ValueError("LLM returned empty content for oil_price prediction")
raw_text = response.content[0].text
```

### WR-03: Budget cap never checked before LLM calls

**File:** `backend/src/parallax/cli/brief.py:494-500`, `backend/src/parallax/prediction/oil_price.py:128`, `ceasefire.py:104`, `hormuz.py:106`
**Issue:** The `BudgetTracker` has an `is_over_budget()` method (tracker.py:61) but it is never called before making LLM API calls. All three prediction models call `self._budget.record()` after the API call completes, but never check the budget beforehand. If the budget is exhausted (e.g., during backtest with many days), API calls continue unbounded. The CLAUDE.md states a "$20/day cap" constraint and the tracker's docstring says "Auto-degrades to rule-based when budget is exceeded" -- but no degradation logic exists.
**Fix:** Check budget before each LLM call in the predict methods, or in `run_brief()` before launching the `asyncio.gather` of predictions:
```python
if budget.is_over_budget():
    logger.warning("Budget exceeded, using fallback predictions")
    predictions = _make_dry_run_predictions()
else:
    predictions = list(await asyncio.gather(...))
```

### WR-04: KeyError on malformed LLM JSON response (oil_price only)

**File:** `backend/src/parallax/prediction/oil_price.py:157-159`
**Issue:** The oil_price predictor accesses `parsed["probability"]`, `parsed["direction"]`, and `parsed["magnitude_range"]` with direct dict indexing (not `.get()`). If the LLM returns valid JSON but omits one of these required keys, it throws a `KeyError` with no context about which field was missing. The ceasefire and hormuz predictors partially mitigate this with `.get()` for some fields (e.g., `direction`, `magnitude_range`) but not for `probability` or `reasoning`. All three models would benefit from uniform handling.
**Fix:** Use `.get()` with sensible defaults, or wrap in a try/except KeyError that produces a clear error message:
```python
try:
    probability = parsed["probability"]
    direction = parsed["direction"]
    reasoning = parsed["reasoning"]
except KeyError as exc:
    raise ValueError(
        f"oil_price LLM response missing required field {exc}: {list(parsed.keys())}"
    ) from exc
```

### WR-05: Backtest engine monkey-patches module-level function without thread safety

**File:** `backend/src/parallax/backtest/engine.py:187-226`
**Issue:** The backtest engine temporarily replaces `ctx.get_crisis_context` with a lambda (line 189) and restores it in a finally block (line 226). This monkey-patching is not thread-safe -- if any concurrent code (another async task, a test runner, etc.) calls `get_crisis_context()` during the backtest loop, it would get the date-limited context instead of the full timeline. Additionally, the lambda captures `context_text` by closure, which is reassigned each loop iteration -- but this is safe because the replacement happens inside the loop.
**Fix:** Instead of monkey-patching, pass the context string as a parameter to the predictor's `predict()` method (e.g., `context_override: str | None = None`). This eliminates global state mutation:
```python
# In each predictor's predict() method:
from parallax.prediction.crisis_context import get_crisis_context
context = context_override or get_crisis_context()
prompt = context + "\n\n" + SYSTEM_PROMPT.format(...)
```

### WR-06: Model name / cost mismatch between code and budget tracker

**File:** `backend/src/parallax/prediction/oil_price.py:129,136`, `ceasefire.py:105,111`, `hormuz.py:107,113`, `backend/src/parallax/budget/tracker.py:8-14`
**Issue:** All three predictors call `model="claude-opus-4-20250514"` (Opus) for the API call, and correctly record budget with `"opus"` pricing. However, every docstring and comment still references "Claude Sonnet" (oil_price.py:4,76; ceasefire.py:4,79; hormuz.py:4,75). This is misleading for anyone reading the code. More importantly, the budget tracker comment (tracker.py:9) says "Sonnet ~$0.031/call" suggesting the expected cost model was Sonnet, not Opus. Opus costs 5x more per token ($0.015/$0.075 vs $0.003/$0.015 input/output per 1K tokens). The CLAUDE.md budget analysis ("3 Sonnet calls ~$0.02/run, massive headroom") is now incorrect -- 3 Opus calls cost ~$0.10+/run.
**Fix:** Update all docstrings and comments to reference "Claude Opus" instead of "Claude Sonnet". Update the CLAUDE.md budget estimate to reflect Opus pricing. If Sonnet was intended for cost reasons, switch the model parameter back to a Sonnet model string.

## Info

### IN-01: Duplicated JSON response parsing across all three predictors

**File:** `backend/src/parallax/prediction/oil_price.py:140-152`, `ceasefire.py:114-127`, `hormuz.py:116-129`
**Issue:** All three prediction models contain identical markdown-fence stripping and JSON parsing logic (strip, check for ```json prefix, strip trailing ```, json.loads, catch JSONDecodeError). This ~12-line block is copy-pasted three times.
**Fix:** Extract to a shared utility:
```python
# In prediction/utils.py
def parse_llm_json(raw_text: str, model_id: str) -> dict:
    text = raw_text.strip()
    if text.startswith("```json") or text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:]).strip()
    if text.endswith("```"):
        text = text[:-3].rstrip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse %s raw response: %s", model_id, raw_text)
        raise ValueError(f"Failed to parse {model_id} LLM response: {text[:200]}") from exc
```

### IN-02: Duplicated _format_events across all three predictors

**File:** `backend/src/parallax/prediction/oil_price.py:184-199`, `ceasefire.py:173-189`, `hormuz.py:184-199`
**Issue:** The `_format_events` static method is nearly identical across all three predictor classes. Each supports both "new news format" (with title) and "legacy GDELT BigQuery format" with minor differences in the legacy output fields.
**Fix:** Extract to a shared utility in `prediction/utils.py` and import in each predictor.

### IN-03: Backtest accesses private attribute _spend_today on BudgetTracker

**File:** `backend/src/parallax/backtest/engine.py:256`
**Issue:** The backtest engine accesses `budget._spend_today` directly (a private attribute by Python naming convention) instead of using the public `budget.total_spend_today()` method or `budget.stats()["spend_today_usd"]`.
**Fix:**
```python
summary["budget_used"] = f"${budget.total_spend_today():.2f}"
```

### IN-04: Prediction models access private _cells attribute on WorldState

**File:** `backend/src/parallax/prediction/oil_price.py:172`, `backend/src/parallax/prediction/hormuz.py:154,178`
**Issue:** Both `OilPricePredictor._iter_cells()` and `HormuzReopeningPredictor._get_hormuz_status()` / `_estimate_recovery()` access `ws._cells` directly. WorldState already has a public `snapshot()` method and `get_cell()` accessor. Accessing private attributes couples these modules to WorldState's internal representation.
**Fix:** Add a public `cell_ids()` property to WorldState, or iterate over `ws.snapshot()`:
```python
# In WorldState:
@property
def cell_ids(self) -> list[int]:
    return list(self._cells.keys())
```

---

_Reviewed: 2026-04-12T22:30:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
