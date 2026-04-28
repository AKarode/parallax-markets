# Parallax Health Check — 2026-04-28

**Status: YELLOW**

The core prediction-market pipeline remains operational with 341 of 367 tests passing, identical to the 2026-04-27 snapshot. No new code was committed since the last health check — the only change is the addition of that report itself. Three chronic test-failure clusters persist unchanged: a missing `pytz` runtime dependency (12 failures), `effective_edge` semantics drift in mapping-policy tests (11 failures), and a calibration-curve predicate mismatch (4 failures). The April 7–21 validation window has closed; the system is in maintenance/analysis mode.

---

## Issues Found

### HIGH — `pytz` Missing from `pyproject.toml` (12 test failures, 12+ days unfixed)

DuckDB raises `InvalidInputException: Required module 'pytz' failed to import` during any query that returns a `TIMESTAMPTZ` column value back to Python. Four tables use `TIMESTAMPTZ`: `runs.started_at/ended_at`, `daily_scorecard.computed_at`, `ops_events.created_at`, and `llm_usage.created_at`. All aggregation queries over these tables fail in-process.

Affected tests: `test_scorecard.py` (9 failures), `test_ops_events.py` (1), `test_llm_usage.py` (1), `test_scorecard.py::TestScorecardIdempotent` (1).

This bug has been flagged in every health report since 2026-04-16 (12 days) with no fix applied. Scorecard computation (`--scorecard` CLI flag) is broken in any environment where `pytz` is not pre-installed.

- **Fix**: Add `"pytz>=2024.1"` to `[project] dependencies` in `backend/pyproject.toml`. One line, unblocks 12 tests immediately.

---

### HIGH — `effective_edge` Semantics Mismatch in Mapping Policy Tests (11 failures, persistent)

`MappingPolicy.evaluate()` sets `raw_edge = gross_edge` (before transaction costs) and `effective_edge = net_edge` (after costs). Tests were written under an older model where `effective_edge = raw_edge × confidence_discount`, making them expect `effective_edge ≈ raw_edge` for a `DIRECT` proxy. The delta is exactly the 2% cost rate, causing `abs(0.14 − 0.16) = 0.02 > 1e-9` assertion failures.

Affected tests: `TestDirectProxyDiscount`, `TestNearProxyDiscount`, `TestLooseProxyDiscount`, `TestProbabilityInversion`, `TestAboveThreshold`, `TestSortedByEffectiveEdge`, `TestDiscountFromHistory` (7 + 4 subtests).

The production code is correct; the tests are stale. The `reason` string in `MappingResult` documents the semantics accurately (`"gross edge 16.0%, costs 2.0%, net edge 14.0%"`).

- **Fix**: Update test assertions to use `net_edge` semantics: for `DIRECT` proxy, assert `abs(effective_edge - (raw_edge - expected_total_cost)) < 1e-9`. Add a docstring to `MappingResult.raw_edge` and `MappingResult.effective_edge` explaining the cost-deduction model.

---

### MEDIUM — Calibration Curve Returns Empty for Expected Bucket (4 failures, persistent)

`recalibrate_probability()` inserts `signal_ledger` rows with `model_probability=0.7`, but `calibration_curve()` finds no rows in the 60–80% bucket, so the function returns `(raw_prob, raw_prob)` unchanged. The test then asserts `abs(calibrated − 0.55) < 0.02` and fails with a delta of 0.15 (the full raw probability).

Root cause likely: a predicate in `calibration_curve()` filters on `model_was_correct IS NOT NULL` or `resolution_price IS NOT NULL`, and the test data does not set these fields. The calibration logic requires resolved signals, but test fixtures don't resolve them.

Affected tests: `test_recalibration.py` (4 failures).

- **Fix**: Check whether `calibration_curve()` requires `model_was_correct IS NOT NULL` or similar resolved-signal gating. Update test fixtures to include resolved outcomes, or add a bypass for unit-test contexts.

---

### MEDIUM — `DbWriter` Not Wired Into Production (unchanged from previous reports)

The spec mandates all mutable writes go through the `asyncio.Queue → DbWriter` loop. `DbWriter` exists in `db/writer.py` and is tested, but **no production module calls `writer.enqueue()`**. `SignalLedger`, `PaperTradeTracker`, `PredictionLogger`, `BudgetTracker`, `AlertDispatcher`, `scorecard.py`, and `resolution.py` all call `conn.execute(INSERT …)` / `conn.execute(UPDATE …)` directly.

Current risk is low because the CLI runs sequentially and the API has no write endpoints. Risk escalates to high if any write API endpoint is added (e.g., `/api/brief/run` currently runs with `dry_run=True` but if ever switched to live writes while the API server holds an open connection, deadlocks will occur).

- **Recommendation**: Either wire `DbWriter` (medium effort) or explicitly mark this as a Phase 2 item with a comment in `brief.py` and `ledger.py`.

---

### LOW — Python Version Requirement Weaker Than Spec

`pyproject.toml` declares `requires-python = ">=3.11"`. The spec and `CLAUDE.md` both state Python 3.12 is the target runtime. The actual test environment is Python 3.11.15. No 3.12-specific syntax is used in production code, so this is not a current bug, but it should be aligned with the spec to avoid environment drift.

- **Fix**: Update to `requires-python = ">=3.12"` and test against Python 3.12.

---

### LOW — Multiple `duckdb.connect()` Calls in `brief.py` (unchanged)

`run_brief()` opens a connection at line 454, and three helper functions (`_run_calibration`, `_run_report_card`, `_run_scorecard`) each open additional connections at lines 662, 672, and 682. While these are sequential and short-lived in the CLI path, any attempt to run `brief.py` while the FastAPI server holds an open read-write connection to the same file will fail with `database is locked`.

- **Recommendation**: Open a single connection at the top of each entrypoint function, pass it through as a parameter, close on exit.

---

### LOW — `CLAUDE.md` Tech Stack Lists Unused Packages (unchanged)

`CLAUDE.md` still lists `deck.gl`, `MapLibre GL`, `h3-js`, `react-map-gl`, `sentence-transformers`, `searoute`, `shapely`, `google-cloud-bigquery`, and `websockets` as active dependencies. None of these are in `pyproject.toml` or `package.json`. The frontend is React + Recharts only.

- **Fix**: Update `CLAUDE.md` tech stack and frontend sections to reflect the actual pivot (Recharts dashboard, no geospatial layer).

---

## Spec / Plan Consistency

The original Phase 1 spec called for ~50 LLM agents in a country/sub-actor hierarchy, H3 spatial model, GDELT BigQuery integration, deck.gl visualization, and a formal eval/prompt-versioning framework. The implementation deliberately pivoted to 3 focused Claude Sonnet prediction models + Kalshi/Polymarket market comparison + paper-trading signal ledger. This pivot is consistent with the 2-week validation timeline but is not documented in `CLAUDE.md`.

| Missing from spec | Impact |
|---|---|
| `agents/` (50-agent swarm) | Out of scope — pivot decision |
| `spatial/` (H3 hexagon model) | Out of scope — pivot decision |
| `eval/` (prompt versioning, A/B scoring) | Partially replaced by `scoring/scorecard.py` |
| `api/auth.py` (invite codes, admin middleware) | Not implemented |
| `api/websocket.py` (real-time push) | Not implemented |
| `simulation/engine.py` (DES loop) | Present as stub; cascade engine is implemented |
| `simulation/circuit_breaker.py` | Not implemented |
| `ingestion/dedup.py` (semantic dedup) | Not implemented |

None of these absences are regressions — they are documented pivot decisions. The `scoring/` layer, `contracts/`, `divergence/`, and `portfolio/` modules are all net-additions beyond the original spec that support the prediction-market focus.

---

## Dependency Audit

| Package | `pyproject.toml` | Used | Notes |
|---|---|---|---|
| `pytz>=2024.1` | **MISSING** | Yes (DuckDB TIMESTAMPTZ) | Add immediately |
| `h3>=4.1` | Missing | No | Defer to Phase 2 |
| `sentence-transformers>=3.4` | Missing | No | Defer to Phase 2 |
| `searoute>=1.3` | Missing | No | Defer to Phase 2 |
| `shapely>=2.0` | Missing | No | Defer to Phase 2 |
| `google-cloud-bigquery>=3.27` | Missing | No | Defer to Phase 2 |
| `websockets>=14.0` | Missing | No | Not used |
| `truthbrush>=0.2` | Present | Yes (truth_social.py) | OK |
| `cryptography>=44.0` | Present | Yes (Kalshi RSA-PSS auth) | OK |

No known CVEs identified in declared dependencies at their current minimum versions.

---

## Positive Findings

- **341/367 tests pass** — strong coverage for implemented scope; all 26 failures are known and pre-existing.
- **No new regressions** since 2026-04-27.
- **No secrets in repo** — `.env.example` uses placeholder values; no live keys or credentials.
- **Schema is additive and backward-compatible** — migration helpers in `schema.py` prevent column-existence errors on existing databases.
- **Budget guard and kill-switch** implemented and tested (`ops/runtime.py`, `ops/alerts.py`).
- **Cascade engine** (`simulation/cascade.py`) and scenario config (`config/scenario_hormuz.yaml`) are correct and tested.
- **Frontend builds cleanly** with React + Recharts; no TypeScript errors in the component tree.

---

## Recommendations (Priority Order)

1. **Add `pytz>=2024.1` to `pyproject.toml`** — 30-second fix, unblocks 12 test failures immediately. This has been open 12+ days.
2. **Fix `test_mapping_policy.py` assertions** — update expected `effective_edge` to `raw_edge - expected_total_cost` for cost-aware semantics; add docstrings to `MappingResult` fields.
3. **Debug `calibration_curve()` predicate** — determine whether it requires resolved outcomes and update test fixtures accordingly.
4. **Update `pyproject.toml` Python requirement** to `>=3.12` to match spec and avoid environment drift.
5. **Update `CLAUDE.md`** — document the architecture pivot; remove stale tech-stack entries (deck.gl, MapLibre, h3-js, sentence-transformers, searoute, shapely, google-cloud-bigquery, websockets).
6. **Wire `DbWriter` or explicitly defer** — add a comment to `SignalLedger.record_signal()` and `brief.py` noting the single-connection assumption, to prevent future concurrent-write bugs.
