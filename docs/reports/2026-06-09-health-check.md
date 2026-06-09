# Parallax Health Check — 2026-06-09

**Status: YELLOW**

No code changes since the 2026-06-08 health check (only commit is that report itself). All three HIGH-severity issues from yesterday remain unresolved and are now 2+ days old. One LOW item from yesterday (`ensemble.py` empty-input crash) is confirmed as a false alarm — the guard already exists in `compute_ensemble`; only the missing probability-clamp remains valid.

---

## Issues Found

### [HIGH — CARRIED, DAY 3] `trade_id` always overwritten with `position_id` in `ledger.py`

**File:** `backend/src/parallax/scoring/ledger.py:267`

`update_execution()` has no `trade_id` parameter but the SQL updates the `trade_id` column. `position_id` is passed twice in the params list — once for the `trade_id` slot and once for `position_id`:

```python
[execution_status, entry_order_id, position_id, position_id, traded, trade_refused_reason, signal_id]
#                                  ↑ fills trade_id          ↑ fills position_id
```

Every call silently sets `trade_id = position_id`. All downstream P&L attribution and fill reconciliation queries that join on `trade_id` produce wrong results.

**Fix:** Add `trade_id: str | None = None` to the signature and use it as the third element, or remove `trade_id` from the SQL if it should not be writable via this path.

---

### [HIGH — CARRIED, DAY 3] `ContractRegistry.upsert()` not wrapped in a transaction

**File:** `backend/src/parallax/contracts/registry.py:85–122`

Three sequential `conn.execute()` calls: INSERT the contract, DELETE all proxy mappings, then re-INSERT mappings one by one. A failure in the INSERT loop leaves the contract row with zero proxy mappings — downstream divergence detection and signal generation silently produce nothing for that ticker.

**Fix:** Wrap all three operations in an explicit `BEGIN`/`COMMIT`/`ROLLBACK`.

---

### [HIGH — CARRIED, DAY 3] DuckDB single-writer pattern violated in 8 modules

The `DbWriter` asyncio.Queue topology is correctly implemented in `db/writer.py` but bypassed everywhere else. Modules performing direct `conn.execute()` writes:

| Module | Write targets |
|--------|--------------|
| `cli/brief.py` | `runs`, `market_prices` |
| `scoring/ledger.py` | `signal_ledger` (INSERT + UPDATE) |
| `scoring/prediction_log.py` | `prediction_log` |
| `scoring/resolution.py` | `signal_ledger`, `trade_positions` |
| `scoring/tracker.py` | `trade_orders`, `trade_fills`, `trade_positions` |
| `ops/alerts.py` | `ops_events` |
| `ingestion/crisis_ingester.py` | `crisis_events` |
| `budget/tracker.py` | `llm_usage` |

Under any concurrent execution (FastAPI background tasks, future scheduler integration), these will contend and may produce non-deterministic `database is locked` errors.

---

### [MEDIUM — CARRIED] Missing error handling at external API boundaries

**`ingestion/oil_prices.py`:** `resp.raise_for_status()` guards against non-2xx, but a 200 response with a non-JSON body (e.g., EIA returning an HTML maintenance page) will raise an unhandled `JSONDecodeError` and abort the full brief run. Wrap `resp.json()` in a `try/except (ValueError, json.JSONDecodeError)`.

**`markets/kalshi.py`:** Non-2xx errors are raised with status code only — the response body is not logged. Auth failures (401/403) are opaque in logs. Add `logger.warning("Kalshi %s %s: %s", method, path, response.text[:500])` before raising.

---

### [MEDIUM — CARRIED] Architecture drift — plan doc not updated after pivot

`docs/superpowers/plans/2026-03-30-parallax-phase1.md` still describes the 50-agent swarm / H3 hex-map architecture. `CLAUDE.md` correctly reflects the current prediction-market system. The plan doc is actively misleading for anyone using it as implementation guidance.

**Recommendation:** Add a `> [PIVOTED 2026-04-XX — See CLAUDE.md for current architecture]` block at the top of the plan doc.

---

### [MEDIUM — CARRIED] `h3>=4.1` absent from `pyproject.toml`

`simulation/world_state.py` and `simulation/cascade.py` use H3 cell IDs (as `BIGINT`) in the schema, and the original design relies on the `h3` Python library. It is not listed as a dependency. Any future import of `import h3` fails on a clean install.

**Recommendation:** Add `h3>=4.1` to `pyproject.toml` or explicitly document it is intentionally dropped.

---

### [LOW — CARRIED] 6 tests permanently skipped in `test_mapping_policy.py`

9 occurrences of `@pytest.mark.skip` / `"skip"` reduce effective coverage without CI failure. Either complete the refactor these tests guard or delete them.

---

### [LOW — CARRIED] Probability clamping absent in `ensemble.py`

**File:** `backend/src/parallax/prediction/ensemble.py:133`

`probabilities.append(parsed["probability"])` has no bounds check. An LLM response where the extracted probability is slightly above 1.0 (e.g., due to a rounding artifact or a model returning `1.05`) propagates unclamped through `compute_ensemble` and into the signal record.

**Fix:** `probabilities.append(max(0.0, min(1.0, float(parsed["probability"]))))`.

---

### [LOW — CORRECTION from 2026-06-08] `trimmed_mean` empty-input concern was a false alarm

Yesterday's report flagged `trimmed_mean([])` as a crash risk. Confirmed not a real risk: `ensemble_predict` raises before reaching `compute_ensemble` if `all_parsed` is empty (line 139–140), and `compute_ensemble` itself guards `len < 2` (lines 61–67) before calling `trimmed_mean`. The crash path does not exist.

---

## What's Working Well

- **`DbWriter` pattern is correctly implemented** — architecture is right; violations are in consumers, not the design.
- **43 test files** — thorough coverage for prediction, scoring, market, and portfolio modules.
- **`scenario_hormuz.yaml`** parameters match spec defaults.
- **Kalshi RSA-PSS auth** is correctly implemented and tested.
- **`BudgetTracker` + kill-switch** wired up and tested.
- **`scorecard.py` ETL** computes 15+ metrics; idempotency tests pass.
- **`ContractRegistry` proxy classification** (DIRECT / NEAR_PROXY / LOOSE_PROXY) is solid and well-tested.
- **Ensemble temperature sampling** with staleness penalty is a well-designed improvement over single-call prediction.

---

## Recommendations (Priority Order)

| # | Priority | Action | File |
|---|----------|--------|------|
| 1 | HIGH | Fix `trade_id` param bug: add `trade_id` to `update_execution()` signature | `scoring/ledger.py:267` |
| 2 | HIGH | Wrap `ContractRegistry.upsert()` in `BEGIN`/`COMMIT`/`ROLLBACK` | `contracts/registry.py:85–122` |
| 3 | HIGH | Route direct writes through `DbWriter` queue | 8 modules (see table above) |
| 4 | MEDIUM | Catch `JSONDecodeError` in `oil_prices.py`; log response body on non-2xx in `kalshi.py` | ingestion, markets |
| 5 | MEDIUM | Add pivot notice to Phase 1 plan doc | `docs/superpowers/plans/2026-03-30-parallax-phase1.md` |
| 6 | MEDIUM | Add `h3>=4.1` to `pyproject.toml` | `pyproject.toml` |
| 7 | LOW | Clamp probability to `[0.0, 1.0]` in `ensemble_predict` | `prediction/ensemble.py:133` |
| 8 | LOW | Delete or fix 6 skipped tests in `test_mapping_policy.py` | `backend/tests/` |
