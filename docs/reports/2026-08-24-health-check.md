# Parallax Health Check — 2026-08-24

**Status: RED**

Third consecutive day at RED with no source code progress. The two critical issues — `DbWriter` never instantiated (single-writer contract unenforced) and `cryptography` missing from `pyproject.toml` (Kalshi auth breaks on clean install) — remain open. Since the last report, only one commit landed (a tech research report); no `backend/src` or `frontend/src` files have been touched.

---

## Delta Since 2026-08-23

- **Zero source changes.** `git log --since="2026-08-23"` shows one commit: `1671b2d` — the daily tech research scout report. No implementation, dependency, or configuration changes.
- All CRITICAL and HIGH issues from the 2026-08-23 report carry over verbatim.
- Streak: 3 consecutive RED reports (08-22, 08-23, 08-24) with the same root causes.

---

## Issues Found

### CRITICAL

- **[ARCH] DbWriter never started — single-writer DuckDB contract unenforced** (unchanged from 08-22)
  `db/writer.py` implements the correct asyncio.Queue pattern, but no module instantiates it. `backend/src/parallax/main.py:35` opens `duckdb.connect(db_path)` directly into `app.state.db`, and every write in the system uses that raw connection. Confirmed with `grep -r "DbWriter("` across `backend/src/parallax` — one match, in `writer.py` itself. Under any concurrent write load (FastAPI request writing + background CLI cron writing to the same DB file), this will produce `database is locked` errors. The spec at Section 9 explicitly commits to the single-writer topology; the code silently violates it.
  _Callers with direct writes bypassing the queue:_ `scoring/ledger.py`, `scoring/resolution.py`, `scoring/scorecard.py`, `scoring/prediction_log.py`, `scoring/tracker.py`, `scoring/recalibration.py`, `scoring/calibration.py`, `scoring/report_card.py`, `scoring/track_record.py`, `ops/alerts.py`, `budget/tracker.py`, `cli/brief.py`, `dashboard/data.py`, `dashboard/app.py`, `portfolio/simulator.py`, `ingestion/crisis_ingester.py`, `prediction/crisis_context.py`, `contracts/mapping_policy.py`, `contracts/registry.py`, `backtest/runner.py`, `backtest/report.py`, `backtest/look_ahead_guard.py`, plus `db/schema.py`.

- **[DEP] `cryptography` missing from `pyproject.toml`** (unchanged from 08-22)
  `markets/kalshi.py` imports `cryptography.hazmat` for RSA-PSS request signing (verified). No `cryptography` entry in `backend/pyproject.toml` dependencies. A clean `pip install -e .` succeeds; Kalshi auth fails at runtime with `ModuleNotFoundError`. One-line fix, third day unfixed.

### HIGH

- **[SPEC] Three planned packages entirely absent from the codebase**
  `backend/src/parallax/agents/`, `backend/src/parallax/eval/`, and `backend/src/parallax/spatial/` do not exist on disk. This represents the deliberate pivot away from the Phase 1 spec (50-agent LLM swarm on H3 hex map with prompt versioning + A/B eval) toward the CLAUDE.md architecture (3 focused prediction models against Kalshi/Polymarket prices). The pivot is real and successful — 433 tests pass — but the spec at `docs/superpowers/specs/2026-03-30-parallax-phase1-design.md` and the plan at `docs/superpowers/plans/2026-03-30-parallax-phase1.md` still describe the old architecture. This makes health-check spec-drift alarms noisy every day.

- **[SPEC] `simulation/engine.py` and `simulation/circuit_breaker.py` missing**
  `simulation/cascade.py`, `simulation/config.py`, and `simulation/world_state.py` are present (verified) and align with the plan. The DES event queue (`engine.py`) and the escalation circuit breaker (`circuit_breaker.py`) that would drive them are absent. Cascade code is dead-ended: it can be called from `cli/brief.py` but there is no tick loop. In the current prediction-market product this is fine; keeping the vestigial `simulation/` modules is technical debt.

### MEDIUM

- **[DEP] Spec-required packages absent from `pyproject.toml`**
  `h3`, `searoute`, `shapely`, `sentence-transformers`, `google-cloud-bigquery`, `websockets` all appear in the Phase 1 spec (Section 2 spatial model, Section 6 GDELT semantic dedup, Section 5 WebSocket push) but none are declared. Consistent with the pivot; not blocking today, but the plan-vs-actual gap is unlabeled anywhere in the repo.

- **[DEP] `requires-python = ">=3.11"` conflicts with CLAUDE.md (Python 3.12)**
  `backend/pyproject.toml:4` allows 3.11; `CLAUDE.md` and infra docs specify 3.12. A `pip install -e .` on 3.11 will succeed and then fail at import time on any `Union[X, Y]`-style syntax that assumed 3.12+.

- **[SPEC] `db/queries.py` missing; read queries scattered**
  The plan (Task 2) specifies read helpers `get_current_tick`, `get_latest_snapshot_tick`, `get_world_state_at_tick`, `get_recent_decisions`. None exist. Read queries live in `dashboard/data.py` and inline throughout `main.py` — reasonable given the pivot but worth noting.

- **[SPEC] `api/` package not split out from `main.py`**
  `main.py` is a single file holding 14 route handlers (confirmed via grep for `@app.`). The plan specifies `api/routes.py`, `api/websocket.py`, `api/auth.py`. Not urgent, but `main.py` will grow harder to maintain as more endpoints land.

- **[SPEC] `ingestion/dedup.py` missing**
  GDELT semantic-dedup stage (sentence-transformers cosine similarity) is not implemented. In the current product the GDELT DOC API path (`ingestion/gdelt_doc.py`) does not run through dedup at all. If GDELT starts returning near-duplicate stories, predictors will overweight them.

- **[TEST] Plan-specified tests missing**
  `test_h3_utils.py`, `test_gdelt_filter.py` (only `test_gdelt_doc.py` exists), `test_dedup.py`, `test_circuit_breaker.py`, `test_agent_schemas.py`, `test_agent_router.py`, `test_agent_runner.py`, `test_auth.py`, `test_integration.py`. Most correspond to unimplemented modules — no code, no tests.

- **[TEST] Four test files require `bench` extras and fail to collect otherwise**
  `test_bench_forecast.py`, `test_calibration_metrics.py`, `test_selective.py`, `test_recalibrators.py` import `numpy`/`pandas`, which live in the `bench` optional-dependency group. Default `pip install -e ".[dev]"` leaves them uncollectable. Either move to `[dev]` or document `[dev,bench]` as the developer install.

- **[ARCH] Frontend has drifted from spec**
  Spec calls for `HexMap.tsx`, `AgentFeed.tsx`, `LiveIndicators.tsx`, `Timeline.tsx`, `PredictionCards.tsx`, `HexPopover.tsx`. Actual frontend (verified): `ContractDetail.tsx`, `KpiBar.tsx`, `MarketsTable.tsx`, `ModelCards.tsx`, `ModelHealth.tsx`, `OpsFooter.tsx`, `PortfolioPanel.tsx`, `PriceChart.tsx`, `Sparkline.tsx`. Deliberate product pivot — flagging only because the design spec is now stale.

---

## Test Coverage Summary

| Category | Status |
|---|---|
| Core tests (433 passing per 08-23 report) | GREEN — no reason to believe this has changed given zero source diffs |
| Bench-extras tests (4 uncollectable without `[bench]`) | YELLOW — same as yesterday |
| Plan-specified tests missing | 9 files (see MEDIUM finding above) |

---

## Recommendations

1. **[Urgent — 3rd day]** Wire up `DbWriter` in `main.py` lifespan. Start it as a background task, expose it on `app.state.db_writer`, refactor the ~22 direct-write callers to route through `enqueue()`. This is the single highest-risk open issue and it has been the top recommendation for three days running.

2. **[Urgent — 3rd day]** Add `cryptography` to `pyproject.toml` dependencies. One-line change. Kalshi auth is silently broken on clean installs.

3. **[Backlog]** Retire or archive `docs/superpowers/specs/2026-03-30-parallax-phase1-design.md` and `docs/superpowers/plans/2026-03-30-parallax-phase1.md`. Replace with a new spec that describes the prediction-market architecture. Every daily health check will keep flagging the same spec drift until this happens.

4. **[Backlog]** Decide whether to keep the vestigial `simulation/cascade.py`, `simulation/world_state.py`, `simulation/config.py` (used by `cli/brief.py`) or extract them into `prediction/` where they belong given the pivot.

5. **[Backlog]** Bump `requires-python` to `>=3.12` to match CLAUDE.md, or update CLAUDE.md to allow 3.11.

6. **[Backlog]** Add a `[dev,bench]` install step to CI so the four bench-extras tests actually run.
