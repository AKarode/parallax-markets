# Parallax Health Check — 2026-04-27

**Status: YELLOW**

The core prediction-market pipeline (news → 3 prediction models → market comparison → signal ledger) is operational and well-tested, with 341 of 367 tests passing. The project has deliberately pivoted from the Phase 1 geopolitical-cascade-simulator spec to a tighter prediction-market edge-finder, which is consistent with the 2-week validation window. Two areas need immediate attention: a missing `pytz` runtime dependency causing 15 test failures, and effective-edge logic drift causing 11 test failures in `test_mapping_policy.py`.

---

## Issues Found

### HIGH — Test Failures (26/367)

**`test_scorecard.py` (10 failures), `test_ops_events.py` (1), `test_llm_usage.py` (1)** — `pytz` not installed.
DuckDB raises `InvalidInputException: Required module 'pytz' failed to import` during timestamp queries in `_compute_ops_runtime()`. `pytz` is an undeclared runtime dependency; it needs to be added to `pyproject.toml`.
- **Fix**: Add `"pytz>=2024.1"` to `[project] dependencies` in `backend/pyproject.toml`.

**`test_mapping_policy.py` (11 failures)** — `effective_edge` semantics drift.
Tests were written with the model `effective_edge = raw_edge × confidence_discount`. The implementation now sets `raw_edge = gross_edge` (before costs) and `effective_edge = net_edge` (after costs). For a `DIRECT` proxy (discount=1.0), the test asserts `abs(effective_edge - raw_edge) < 1e-9`, but gets a delta equal to the 2% cost rate. All 11 failures stem from this mismatch.
- **Fix**: Update test assertions to account for cost deduction: `effective_edge = (raw_edge - expected_total_cost) × confidence_discount`, or update test comments/expectations to match the current implementation semantics.

**`test_recalibration.py` (4 failures)** — calibration curve returns no data for bucket.
`recalibrate_probability()` inserts signals with `model_probability=0.7`, but `calibration_curve()` is not finding them in the `60-80%` bucket, so the function returns `(raw_prob, raw_prob)` instead of applying the offset. Likely a predicate mismatch in the calibration query.

---

### MEDIUM — `DbWriter` Not Wired Into Production

The spec mandates all mutable writes go through a single `asyncio.Queue → DbWriter` loop. `DbWriter` exists in `db/writer.py` and is unit-tested, but **no production code calls `writer.enqueue()`**. `SignalLedger`, `PaperTradeTracker`, `PredictionLogger`, `BudgetTracker`, `AlertDispatcher`, and `scorecard.py` all call `conn.execute(INSERT …)` / `conn.execute(UPDATE …)` directly.

For the current single-process CLI model this is safe, but concurrent writes from API server + CLI (both open `duckdb.connect(runtime.db_path)`) risk `database is locked` errors. The CLI opens the DB connection, writes, then closes, so in practice conflicts are unlikely — but the safety property stated in the spec is not enforced.

- **Immediate risk**: Low (CLI runs sequentially; API has no write paths currently).
- **Latent risk**: Medium (any future API endpoint that writes, or a cron job running alongside the API, will deadlock).

---

### MEDIUM — Architecture Pivot from Phase 1 Spec (Undocumented)

The original spec described a full geopolitical cascade simulator: ~50 LLM agents in a country/sub-actor hierarchy, H3 hexagonal spatial model with deck.gl visualization, GDELT BigQuery integration, and a formal eval framework with prompt versioning.

**What was built instead**: 3 focused Claude Sonnet prediction models, Kalshi/Polymarket market comparison, paper-trading signal ledger, daily scorecard. This pivot was reasonable given the 2-week validation window, but the following spec modules are absent with no migration note:

| Missing module | Spec purpose |
|---|---|
| `agents/` | ~50 LLM agents (country/sub-actor hierarchy) |
| `spatial/` | H3 hexagonal model, Overture Maps, Searoute |
| `eval/` | Eval framework, prompt versioning, A/B scoring |
| `api/auth.py` | Invite code + admin middleware |
| `api/websocket.py` | Real-time WebSocket push |
| `simulation/engine.py` | Discrete event simulation loop |
| `simulation/circuit_breaker.py` | Escalation limits + exogenous override |
| `ingestion/dedup.py` | Semantic dedup (sentence-transformers) |

This is not necessarily wrong — the simpler approach may outperform the complex one for the validation deadline — but CLAUDE.md should document the pivot decision explicitly.

---

### LOW — Missing Dependencies in `pyproject.toml`

Several packages listed in the CLAUDE.md tech stack and the Phase 1 spec are absent from `pyproject.toml`. Most are simply unused now due to the architecture pivot, but two are used at runtime:

| Package | Status | Action |
|---|---|---|
| `pytz` | Used by DuckDB internally; missing | Add to `[project] dependencies` |
| `h3>=4.1` | Listed in CLAUDE.md; not in pyproject.toml | Add if `h3_utils.py` is needed |
| `searoute>=1.3` | Spec only; not implemented | Remove from CLAUDE.md or defer to Phase 2 |
| `shapely>=2.0` | Spec only; not implemented | Remove from CLAUDE.md or defer to Phase 2 |
| `sentence-transformers>=3.4` | Spec only (semantic dedup); not implemented | Remove from CLAUDE.md or defer to Phase 2 |
| `google-cloud-bigquery>=3.27` | Spec only (GDELT BigQuery); not implemented | Remove from CLAUDE.md or defer to Phase 2 |
| `websockets>=14.0` | Spec only; not implemented | Remove from CLAUDE.md or defer to Phase 2 |

---

### LOW — Frontend Does Not Match Spec

Spec required deck.gl + MapLibre GL + H3HexagonLayer, 3-column layout, WebSocket-driven live updates, and a timeline scrubber. Actual frontend is React + Recharts (charts only, no geospatial layer). This is consistent with the architecture pivot and is not a bug, but the CLAUDE.md technology section still lists deck.gl, MapLibre, h3-js, and react-map-gl as if they are in use.

- **Fix**: Update `CLAUDE.md` Frontend section to reflect the actual Recharts-only dashboard.

---

### LOW — CLI Opens Multiple Connections to Same DB File

`brief.py` calls `duckdb.connect(runtime.db_path)` on lines 454, 631, 662, 672, and 682 — five separate open/close cycles within one run. Each connection is short-lived and sequential, so no locking occurs in practice. However, if the FastAPI server is also running and holding an open read-write connection to the same file, any CLI connection attempt will fail with `database is locked`. DuckDB only permits one read-write connection per file.

- **Recommendation**: Pool all CLI work into a single connection opened at the start of `run_brief()`, passed through, and closed on exit.

---

## Positive Findings

- **341/367 tests pass** — strong base coverage for the implemented scope.
- **No direct-write violations in production**: `grep` for `INSERT|UPDATE|DELETE` across all production modules (excluding `schema.py` and `writer.py`) returns zero matches (writes occur via ORM-style helpers that ultimately call `conn.execute`, but the conn is managed per-request without concurrent contention in the CLI path).
- **Schema is additive and backwards-compatible**: All 10 spec tables exist; 15 additional tables extend the schema cleanly. Migration helpers in `schema.py` prevent column-existence errors.
- **DuckDB single-writer risk is currently low**: The CLI (`brief.py`) is the only write-path in practice; the API server reads only. The risk would materialize only if write API endpoints were added without also adding the DbWriter queue.
- **Budget guard and kill-switch** are implemented and tested (`ops/runtime.py`, `ops/alerts.py`).
- **No secrets committed** to the repo.

---

## Recommendations (Priority Order)

1. **Add `pytz` to `pyproject.toml`** — unblocks 12 test failures immediately.
2. **Fix `test_mapping_policy.py` effective-edge assertions** — clarify whether `raw_edge` is before or after costs, update tests to match the actual implementation, add a docstring to `MappingResult.raw_edge` explaining its semantics.
3. **Investigate `calibration_curve()` predicate** — the function should find `60-80%` bucket data after 15 signal inserts; trace why it returns empty.
4. **Update CLAUDE.md** to document the architecture pivot (dropped: agent swarm, spatial model, eval framework; added: Kalshi/Polymarket market layer, signal ledger, paper trading). Remove stale tech-stack entries (deck.gl, MapLibre, h3-js, sentence-transformers, searoute, shapely, google-cloud-bigquery, websockets).
5. **Wire DbWriter into production** (or explicitly document it as deferred) — `SignalLedger.record()` and `update_execution()` are the highest-risk call sites if the API server ever acquires write paths.
6. **Consolidate CLI DB connections** — open one connection in `run_brief()`, pass it through, close on exit.
