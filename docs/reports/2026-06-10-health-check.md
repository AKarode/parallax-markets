# Parallax Health Check — 2026-06-10

**Status: YELLOW**

No code changes since the 2026-06-09 health check (only commit is that report itself). All three HIGH-severity issues remain unresolved — now on day 4 of consecutive YELLOW status. One new LOW item identified: prediction models are pinned to a stale Anthropic model ID.

---

## Issues Found

### [HIGH — CARRIED, DAY 4] `trade_id` always overwritten with `position_id` in `ledger.py`

**File:** `backend/src/parallax/scoring/ledger.py:267`

`update_execution()` has no `trade_id` parameter but the SQL updates the `trade_id` column. `position_id` is passed twice in the params list — once for the `trade_id` slot and once for `position_id`:

```python
[execution_status, entry_order_id, position_id, position_id, traded, trade_refused_reason, signal_id]
#                                  ↑ fills trade_id          ↑ fills position_id
```

Every call silently sets `trade_id = position_id`. All downstream P&L attribution and fill reconciliation queries that join on `trade_id` produce wrong results.

**Fix:** Add `trade_id: str | None = None` to the signature and pass it as the third element, or remove `trade_id` from the SQL if it should not be writable via this path.

---

### [HIGH — CARRIED, DAY 4] `ContractRegistry.upsert()` not wrapped in a transaction

**File:** `backend/src/parallax/contracts/registry.py:85–122`

Three sequential `conn.execute()` calls: INSERT the contract, DELETE all proxy mappings, then re-INSERT mappings one by one. A failure in the INSERT loop leaves the contract row with zero proxy mappings — downstream divergence detection and signal generation silently produce nothing for that ticker.

**Fix:** Wrap all three operations in an explicit `BEGIN`/`COMMIT`/`ROLLBACK`.

---

### [HIGH — CARRIED, DAY 4] DuckDB single-writer pattern violated in 8 modules

The `DbWriter` asyncio.Queue topology is correctly implemented in `db/writer.py` but bypassed everywhere else. `DbWriter` is never imported in any production module. Modules performing direct `conn.execute()` writes:

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

### [LOW — NEW] Prediction models pinned to stale Anthropic model ID

**Files:** `prediction/ceasefire.py:116`, `prediction/hormuz.py:118`, `prediction/oil_price.py:143`

All three prediction models are hard-coded to `model="claude-opus-4-20250514"`. The current Anthropic Opus model is `claude-opus-4-8`. The older model ID may stop being served at any time without notice.

Additionally, `budget/tracker.py` records these calls under the key `"opus"` which maps correctly to `_PRICING["opus"]` — but the cost constants (`input: 0.015, output: 0.075` per 1K tokens) should be verified against the actual pricing for `claude-opus-4-20250514` vs `claude-opus-4-8`.

**Fix:** Update model IDs to `claude-opus-4-8` across all three prediction modules.

---

### [LOW — CARRIED] 6 tests permanently skipped in `test_mapping_policy.py`

9 occurrences of `@pytest.mark.skip(reason=_PRE_REFACTOR_REASON)` reduce effective coverage without CI failure. Either complete the refactor these tests guard or delete them.

---

### [LOW — CARRIED] Probability clamping absent in `ensemble.py`

**File:** `backend/src/parallax/prediction/ensemble.py:133`

`probabilities.append(parsed["probability"])` has no bounds check. An LLM response where the extracted probability is slightly above 1.0 propagates unclamped through `compute_ensemble` and into the signal record.

**Fix:** `probabilities.append(max(0.0, min(1.0, float(parsed["probability"]))))`.

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
| 7 | LOW | Update prediction model IDs to `claude-opus-4-8` | `prediction/ceasefire.py`, `hormuz.py`, `oil_price.py` |
| 8 | LOW | Clamp probability to `[0.0, 1.0]` in `ensemble_predict` | `prediction/ensemble.py:133` |
| 9 | LOW | Delete or fix 6 skipped tests in `test_mapping_policy.py` | `backend/tests/` |
