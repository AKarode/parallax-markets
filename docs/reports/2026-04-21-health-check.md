# Parallax Health Check — 2026-04-21

**Status: YELLOW**

The system is functional for its actual purpose (prediction market edge-finder) and code quality is solid, but all P0/P1 issues from the April 17 report remain unaddressed — zero code commits since that check. The validation deadline (April 7–21 ceasefire window) ends today; no scorecard results or resolution data have been committed.

---

## Since Last Check (2026-04-17)

**One commit since April 17:** `chore: daily health check 2026-04-17 (YELLOW)` — the health check itself. No code changes.

- All P0/P1 items from April 17 carry forward unchanged.
- One correction to the April 17 report: `google_news.py` **does** set `timeout=15.0` on its `httpx.AsyncClient`; the April 17 finding on missing HTTP timeout for Google News was incorrect.
- New issues found this cycle (ensemble code from prior commits, examined for the first time): see below.

---

## Spec / Plan Consistency

Unchanged from April 17. The original spec describes a 50-agent geopolitical simulator; the actual system is a 3-model prediction market edge-finder. The pivot is deliberate and documented in CLAUDE.md, but the spec/plan files remain stale.

- **[HIGH]** `docs/superpowers/specs/2026-03-30-parallax-phase1-design.md` and `docs/superpowers/plans/2026-03-30-parallax-phase1.md` describe a product that no longer exists. Should be archived with a pointer to CLAUDE.md.
- **[MEDIUM]** All plan checkboxes remain unchecked — plan can no longer serve as progress tracker.

---

## Dependency Audit

### Backend (`pyproject.toml`) — unchanged since April 17

| Issue | Severity |
|-------|----------|
| `requires-python = ">=3.11"` — CLAUDE.md and runtime require Python 3.12 | LOW |
| `h3>=4.1`, `websockets>=14.0` listed in CLAUDE.md "Key Dependencies" but absent from `pyproject.toml` | MEDIUM |
| `truthbrush>=0.2` — niche library, no upper-bound pin, low maintenance activity | LOW |
| `anthropic>=0.52` — no upper bound; SDK breaking changes risk on future major version | LOW |

### Frontend (`package.json`) — no changes

React 18 + Recharts + Vite stack is current. No CVE concerns.

---

## Code Quality Issues

### DuckDB Single-Writer Violations — HIGH (unresolved from April 17)

The `DbWriter` asyncio queue exists but is **not wired into the actual pipeline**. All of the following modules hold a raw `duckdb.DuckDBPyConnection` and write directly, bypassing the queue entirely:

| Module | Violating Operations |
|--------|----------------------|
| `scoring/ledger.py` | `record_signal()` → INSERT; `update_execution()` → UPDATE |
| `scoring/prediction_log.py` | `log_prediction()` → INSERT |
| `scoring/tracker.py` | INSERT to `trade_orders`, `trade_fills`; UPDATE to `trade_positions` |
| `scoring/resolution.py` | UPDATE to `signal_ledger`; UPDATE to `trade_positions` |
| `scoring/scorecard.py` | `_upsert_metric()` → INSERT ... ON CONFLICT |
| `contracts/registry.py` | `upsert_contract()` → INSERT OR REPLACE + DELETE + INSERT; `mark_inactive()` → UPDATE |
| `cli/brief.py` | `_persist_run_start()` → INSERT; `_persist_run_end()` → UPDATE |

Currently safe only because the CLI runs all writes sequentially in a single async task. Will cause `database is locked` errors if the FastAPI server triggers concurrent brief runs or if a background async task races with the CLI.

### New: Missing HTTP Timeouts on Market Clients — MEDIUM

`markets/kalshi.py:154` and `markets/polymarket.py` (5 call sites) all instantiate `httpx.AsyncClient()` without a `timeout=` parameter. A hung Kalshi or Polymarket connection will block the entire brief pipeline indefinitely. Kalshi also has no 429-specific retry/backoff — rate limit responses propagate as `KalshiAPIError` without retry logic.

### New: Ensemble Budget Tracking Bug — MEDIUM

`prediction/ensemble.py:122`:
```python
budget.record(resp.usage.input_tokens, resp.usage.output_tokens, "opus")
```
The model tier is **hardcoded to `"opus"`** regardless of the `model` parameter passed to `ensemble_predict()`. Sonnet calls are being logged and costed as Opus, inflating reported LLM spend and distorting the $20/day budget cap arithmetic.

### New: Ensemble Missing System Prompt / Prompt Caching — MEDIUM

`ensemble_predict()` constructs calls with only a `messages=[{"role": "user", ...}]` parameter — no `system=` argument. This means:
1. Each of the 3 concurrent calls sends the full scenario context in the user turn, which is longer and slower.
2. Anthropic prompt caching (which requires a `system=` param with `cache_control`) cannot be used. The spec's cost model assumes cached system prompts reduce per-call cost by ~90% on the second+ call; without caching, 3-call ensemble costs ~3× the expected amount.

### No Transaction Wrapping in Scorecard — MEDIUM (unresolved)

`compute_daily_scorecard()` calls `_upsert_metric()` in a loop with no transaction boundary. A crash mid-loop leaves partial day metrics in `daily_scorecard`, causing a misleading scorecard display and breaking the `ops_run_success_rate` metric for that date.

### No Idempotency Guard in Signal Ledger — MEDIUM (unresolved)

Running `parallax-brief` twice in the same session appends duplicate rows to `signal_ledger` and `prediction_log` (no `UNIQUE(run_id, model_id)` constraint). The `daily_scorecard` aggregations count these duplicates, double-inflating hit-rate denominators and PnL metrics.

---

## Test Coverage Gaps

No new test files added since April 17. Gaps carry forward:

| Gap | Severity |
|-----|----------|
| No end-to-end integration test (`test_integration.py` planned, never created) | HIGH |
| No test for `ensemble_predict()` budget model tier (hardcoded "opus" bug) | MEDIUM |
| No test for `ensemble_predict()` with missing `system=` prompt | MEDIUM |
| No test for concurrent `DbWriter` writes (single-writer race condition) | MEDIUM |
| No test for scorecard partial-write crash recovery | MEDIUM |
| `budget/tracker.py`, `backtest/engine.py`, `portfolio/allocator.py`, `ops/alerts.py` have no tests | MEDIUM |
| No test for duplicate-run idempotency in `signal_ledger` | MEDIUM |

---

## Architecture Drift

Unchanged from April 17. All pivots (3 models vs 50 agents, REST polling vs WebSocket, no auth, Docker Compose vs cloud) remain deliberate. No new structural drift introduced.

---

## Validation Window Status

Today (April 21) is the **last day of the 2-week ceasefire validation window** (April 7–21) per CLAUDE.md. Observations:

- **No resolution data committed.** The `scoring/resolution.py` backfill logic exists but no resolved signals appear in the report history.
- **No scorecard run results committed.** The `--scorecard` CLI flag and `compute_daily_scorecard()` are implemented, but no scorecard output files appear in the repo.
- **Paper trading on Kalshi Demo** is implemented but Demo sandbox only has sports/crypto markets — geopolitical contracts cannot be traded there. Real trading requires production execution which the runtime guards block by default.

---

## Corrections to April 17 Report

- **Google News timeout (LOW):** April 17 flagged missing `timeout=` in `google_news.py`. This was **incorrect** — `httpx.AsyncClient(timeout=15.0)` is present on line 132. Issue should be closed.

---

## Recommendations

Priority order for the final validation window and beyond:

1. **[P0 — OPEN] Fix DuckDB single-writer violations.** Refactor `SignalLedger`, `PredictionLogger`, `PaperTradeTracker`, `ContractRegistry`, and `scorecard.py` to accept a `DbWriter` and call `enqueue()` instead of `_conn.execute()`. This is the single highest-risk issue for production stability.

2. **[P0 — NEW] Fix ensemble budget model tier.** Change `ensemble.py:122` from hardcoded `"opus"` to pass the actual model tier string. Add a `model_tier` parameter to `ensemble_predict()` (e.g., `"sonnet"` or `"opus"`) and pass it to `budget.record()`.

3. **[P1 — NEW] Add `system=` param to ensemble calls.** Pass the scenario system prompt to `ensemble_predict()` and forward it to each `client.messages.create()` call. This enables prompt caching and aligns with the spec's cost model.

4. **[P1 — OPEN] Add idempotency guard.** Add `UNIQUE (run_id, model_id)` constraint to `prediction_log` and `signal_ledger`, or add a pre-insert existence check, to prevent double-counting on re-runs.

5. **[P1 — OPEN] Wrap scorecard writes in a transaction.** Wrap the `_upsert_metric()` loop in a `BEGIN`/`COMMIT` so partial scorecard writes are atomic.

6. **[P2 — OPEN] Add integration test.** One test that runs `run_brief()` in dry-run mode end-to-end and asserts predictions and signals are written exactly once.

7. **[P2 — OPEN] Archive stale spec/plan docs.** Add a deprecation header to both spec and plan pointing to CLAUDE.md as the authoritative reference.

8. **[P3 — OPEN] Align `pyproject.toml`.** Set `requires-python = ">=3.12"`, add `h3>=4.1` and `websockets>=14.0`.
