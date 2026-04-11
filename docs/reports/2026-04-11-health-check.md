# Parallax Phase 1 — Daily Health Check
**Date:** 2026-04-11
**Status:** YELLOW

---

## Summary

The backend prediction-market pipeline came to life between April 8–11: 70+ source files, 34 test files, a 23-table DuckDB schema, 3 LLM prediction models (oil price, ceasefire, Hormuz), Kalshi/Polymarket market clients, and a full scoring/paper-trading stack are all committed and tested. However, 14 direct `conn.execute()` write calls across 5 modules bypass the async `DbWriter` queue — the project's core architectural constraint — creating a latent race-condition risk. The agent swarm (50 agents / 12 countries) from the Phase 1 spec has been deliberately replaced by 3 focused LLM predictors; the React/deck.gl frontend remains a Docker stub.

---

## Changes Since 2026-04-07

**Massive implementation sprint — all backend tasks completed in 4 days:**

- `backend/pyproject.toml` — project manifest with all 14 runtime deps + 3 dev deps ✓
- `backend/src/parallax/db/{schema.py,writer.py,runtime.py,queries.py}` — 23-table DuckDB schema, async single-writer queue, runtime config ✓
- `backend/src/parallax/simulation/{cascade.py,engine.py,world_state.py,circuit_breaker.py,config.py}` — 6-rule cascade engine, DES event scheduler, in-memory world state ✓
- `backend/src/parallax/ingestion/{google_news.py,gdelt_doc.py,gdelt.py,oil_prices.py,entities.py,dedup.py,truth_social.py}` — all data source ingestion modules ✓
- `backend/src/parallax/markets/{kalshi.py,polymarket.py,schemas.py}` — RSA-PSS Kalshi client, Polymarket CLOB client ✓
- `backend/src/parallax/prediction/{oil_price.py,ceasefire.py,hormuz.py,schemas.py}` — 3 LLM prediction models with cascade reasoning ✓
- `backend/src/parallax/scoring/{ledger.py,tracker.py,calibration.py,scorecard.py,resolution.py,recalibration.py,report_card.py,prediction_log.py,track_record.py}` — full scoring stack with 25+ daily metrics ✓
- `backend/src/parallax/contracts/{registry.py,mapping_policy.py,schemas.py}` — contract registry with proxy classification ✓
- `backend/src/parallax/cli/brief.py` — daily intelligence brief CLI ✓
- `backend/src/parallax/budget/tracker.py` — $20/day LLM budget enforcement ✓
- `backend/src/parallax/portfolio/allocator.py` — Quarter-Kelly position sizing ✓
- `backend/src/parallax/ops/{alerts.py,runtime.py}` — alert dispatcher, runtime config ✓
- `backend/tests/` — 34 test files covering all major modules ✓

---

## Issues Found

### Critical

- **[CRITICAL] Single-writer violations — 14 locations across 5 modules.** The `DbWriter` async queue (`db/writer.py`) is the project's declared single-writer pattern, preventing DuckDB WAL contention. The following modules bypass it entirely with direct `conn.execute()` write calls:

  | File | Operations |
  |------|-----------|
  | `budget/tracker.py` | `INSERT INTO llm_usage` |
  | `scoring/ledger.py` | `INSERT INTO signal_ledger`, `UPDATE signal_ledger` |
  | `scoring/tracker.py` | `INSERT/UPDATE trade_orders`, `INSERT/UPDATE trade_positions`, `INSERT INTO trade_fills` |
  | `contracts/registry.py` | `INSERT OR REPLACE INTO contract_registry`, `DELETE/INSERT INTO contract_proxy_map`, `UPDATE contract_registry` |
  | `scoring/resolution.py` | `UPDATE signal_ledger`, `UPDATE trade_positions` |

  Under the current CLI-only usage pattern these writes are sequential and safe, but any move toward concurrent async execution (FastAPI + WebSocket + scheduled brief) will hit WAL conflicts. The `db/writer.py` queue should be the only write path.

### High

- **[HIGH] Agent swarm from spec not implemented — deliberate pivot.** The Phase 1 design spec (Section 4) calls for 50 LLM agents across 12 countries with a 3-layer memory system, agent registry (`agents/registry.py`), and keyword router (`agents/router.py`). Only `agents/runner.py` and `agents/schemas.py` exist; no registry or router. CLAUDE.md confirms the product has pivoted to 3 focused prediction models (oil price, ceasefire, Hormuz) with cascade reasoning. This is a sound trade-off for the 2-week Hormuz validation window, but the pivot is not formally documented in the spec — the design doc still describes the swarm architecture. **Recommendation: add a one-paragraph Architecture Decision Record to the spec noting the pivot, or update the spec, to avoid confusion.**

- **[HIGH] React/deck.gl frontend is a stub.** Tasks 17–20 of the plan (React + TypeScript scaffold, H3 hex map, agent feed, live indicators, prediction cards) are unimplemented. The `frontend/` directory contains only `Dockerfile`, `nginx.conf`, and `.dockerignore`. The spec positions the dashboard as a "visually compelling demo-ready" deliverable. With 10 days left in the April 21 evaluation window, the CLI-first approach is pragmatic, but demo readiness requires at minimum a read-only data display layer.

### Medium

- **[MEDIUM] GDELT source deviates from spec — BigQuery replaced by DOC API.** The spec and plan (Tasks 9–10) specify GDELT ingestion via BigQuery with 15-minute cadence and structured event data. The implementation uses the GDELT DOC 2.0 HTTP API (free, unkeyed), which returns article-level metadata, not GDELT event records. The `google-cloud-bigquery>=3.27` dependency is listed in `pyproject.toml` but unused in the ingestion pipeline. This is a pragmatic choice (no GCP credentials needed, lower latency for news headlines) but the heavyweight BigQuery SDK is an unused dependency that adds ~25MB to the install footprint.

- **[MEDIUM] End-to-end integration test absent.** Task 21 of the plan calls for a full-tick integration test covering: event ingestion → cascade → agent decision → prediction → market fetch → divergence → signal → paper trade → resolution → scorecard. No such test exists. The 34 unit tests are thorough at the module level but a pipeline smoke test is needed before trusting the full brief cycle in production.

- **[MEDIUM] Prompt versioning module absent.** The spec (Section 6) calls for semver-versioned prompts with A/B tracking and automated regression detection. The `predictions` table has a `prompt_version` column and `signal_ledger` has `experiment_id`/`variant`, but there is no dedicated versioning module — prompt strings are inline in each predictor. Without versioning infrastructure, calibration drift from prompt changes is undetectable.

- **[MEDIUM] `duckdb` version floor at `>=1.2` — should be `>=1.3`.** The April 3–6 research reports validated that DuckDB v1.3.0+ provides the `SPATIAL_JOIN` operator with ~58x speedup for H3 proximity queries. The current floor allows installing v1.2.x which lacks this. Set to `>=1.3` in `pyproject.toml`.

### Low

- **[LOW] `google-cloud-bigquery>=3.27` is an unused heavyweight dependency.** BigQuery GDELT was replaced by the DOC API. The SDK pulls in `google-auth`, `google-api-core`, `proto-plus`, and other Google infra packages (~30MB transitive install). Remove it unless BigQuery integration is actively planned.

- **[LOW] R-tree spatial index absent from schema.** Previous research recommended `CREATE INDEX cell_rtree ON world_state_delta (cell_id) USING RTREE` for H3 proximity query performance. The 23-table schema in `db/schema.py` has no spatial indexes. Low impact at current data volumes; worth adding before the scorecard query load grows.

- **[LOW] `pytest-httpx` version pinned to `>=0.35,<0.36`.** The narrow upper bound (`<0.36`) will block upgrades and may conflict with future `httpx` releases. Loosen to `>=0.35` unless a specific breaking change is known.

- **[LOW] GitHub Actions workflows permissions not updated.** The April 3–7 health checks flagged that `.github/workflows/claude.yml` and `claude-code-review.yml` need `pull-requests: write` and `issues: write`. Unresolved carry-forward.

---

## Spec / Plan Consistency

| Plan Task | Status | Notes |
|-----------|--------|
-------|
| Task 1 — Project scaffold + DuckDB schema | ✓ Complete | 23 tables vs 10 in spec; extended for trading pipeline |
| Task 2 — Single-writer DB layer | ⚠ Partial | `DbWriter` exists but 14 callers bypass it |
| Task 3 — Scenario config loader (YAML) | ✓ Complete | `simulation/config.py` |
| Task 4 — H3 spatial utilities | ✓ Complete | `spatial/h3_utils.py` |
| Task 5 — In-memory world state | ✓ Complete | `simulation/world_state.py` |
| Task 6 — Cascade rules engine | ✓ Complete | `simulation/cascade.py` — 6 rules |
| Task 7 — Circuit breaker | ✓ Complete | `simulation/circuit_breaker.py` |
| Task 8 — DES engine | ✓ Complete | `simulation/engine.py` |
| Task 9 — GDELT ingestion | ⚠ Deviated | Uses DOC API not BigQuery; functional but different data shape |
| Task 10 — Semantic deduplication | ✓ Complete | `ingestion/dedup.py` with sentence-transformers |
| Task 11 — Agent schemas/validation | ⚠ Partial | `agents/schemas.py` exists; Pydantic models present |
| Task 12 — Agent registry + router | ✗ Not built | No `agents/registry.py` or `agents/router.py` — deliberate pivot |
| Task 13 — Agent runner | ⚠ Partial | `agents/runner.py` exists; not wired to registry/router |
| Task 14 — Eval framework | ✓ Complete | `scoring/` — 25+ metrics, calibration, scorecard |
| Task 15 — Prompt versioning | ✗ Not built | Column exists in DB; no versioning module |
| Task 16 — FastAPI backend | ✓ Complete | `main.py` — 6 endpoints + dashboard |
| Tasks 17–20 — React frontend | ✗ Not built | Nginx stub only |
| Task 21 — Integration test | ✗ Not built | No end-to-end pipeline test |
| Task 22 — .gitignore + env vars | ✓ Complete | `.gitignore` committed |

---

## Dependency Audit

| Package | Current Floor | Concern |
|---------|--------------|--------|
| `duckdb` | >=1.2 | Should be >=1.3 for SPATIAL_JOIN performance |
| `google-cloud-bigquery` | >=3.27 | Unused — BigQuery replaced by GDELT DOC API |
| `pytest-httpx` | >=0.35,<0.36 | Overly narrow upper bound |
| `anthropic` | >=0.52 | OK — Structured Outputs + Batch API both GA |
| `h3` | >=4.1 | OK — 4.4.x stable |
| `cryptography` | >=44.0 | OK — required for RSA-PSS Kalshi auth |
| `truthbrush` | >=0.2 | Low-traffic dependency; verify it tracks Truth Social API changes |

No known CVEs identified in current dependency set.

---

## Test Coverage

**34 test files — excellent unit coverage across all major modules.**

Present: schema, writer, cascade, engine, world_state, circuit_breaker, config, brief, gdelt_doc, google_news, kalshi, polymarket, prediction, scorecard, calibration, ledger, tracker, resolution, recalibration, report_card, divergence, registry, mapping_policy, dashboard, budget, ops_events, h3_utils, runs, truth_social, contracts_schemas, experiment_tags, edge_decay, prediction_log, track_record.

**Missing:**
- End-to-end pipeline integration test (Task 21) — full brief cycle smoke test
- `agents/runner.py` LLM integration test (currently only schema-level agent tests exist)
- Concurrent write stress test for `DbWriter` to validate queue ordering under load

---

## Architecture Drift

Module layout matches CLAUDE.md module map with one structural deviation: the spec's `agents/` subdirectory was planned for 50-agent swarm but contains only 2 files (`runner.py`, `schemas.py`). The prediction models in `prediction/` effectively replace the agent swarm for the Hormuz crisis use case. The `spatial/h3_utils.py` module exists but the spec planned H3 utilities under `simulation/` — minor, no functional impact.

The `dashboard/` module (`data.py`, `app.py`) is an addition not in the original plan; it provides reusable query functions for the FastAPI layer, which is a clean separation.

---

## Recommendations

1. **Fix single-writer violations (CRITICAL).** Route all write paths through `DbWriter.enqueue()`. The 5 violating modules need their `conn.execute()` write calls replaced with `await db_writer.enqueue(sql, params)`. Add a `grep` CI check to catch future violations: `grep -rn "conn\.execute" --include="*.py" | grep -v "db/writer.py" | grep -E "INSERT|UPDATE|DELETE"`.

2. **Document the agent-swarm pivot (HIGH).** Add a one-paragraph ADR to `docs/` (or update the spec) noting that 3 focused LLM predictors replace the 50-agent swarm for Phase 1. Prevents future contributors from re-implementing the swarm without understanding the trade-off.

3. **Write the end-to-end integration test (MEDIUM).** A single test that runs `--dry-run` brief end-to-end and asserts: predictions generated → signals logged → trades recorded → scorecard computable. This is the critical regression guard before going live.

4. **Remove `google-cloud-bigquery` from `pyproject.toml` (MEDIUM).** It's a ~30MB transitive install for zero benefit. If BigQuery GDELT is revived, add it back then.

5. **Bump `duckdb` floor to `>=1.3` (LOW).** One-line change in `pyproject.toml`.

6. **Loosen `pytest-httpx` pin to `>=0.35` (LOW).** Remove the `<0.36` upper bound.

7. **Fix GitHub Actions permissions (LOW).** Add `pull-requests: write` + `issues: write` to both workflow files. Eight-day carry-forward.

---

*Next check: 2026-04-12. Priority watch: single-writer fix, integration test, April 21 evaluation deadline.*
