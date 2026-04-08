# Phase 2: Prediction Persistence + Calibration - Context

**Gathered:** 2026-04-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Persist every prediction the system makes with full context (probability, reasoning, news inputs, cascade state), poll Kalshi/Polymarket for contract resolution outcomes, backfill signal_ledger with resolution data, and provide calibration queries that answer: "Is this system any good?"

NOT in scope: automated trading decisions based on calibration, model prompt changes, UI for calibration data.

</domain>

<decisions>
## Implementation Decisions

### Prediction Storage
- **D-01:** New `prediction_log` table in DuckDB (not extending PredictionOutput model). Each row captures one prediction run with: run_id, model_id, probability, direction, confidence, reasoning, evidence (JSON array), timeframe, news_context (JSON — titles+URLs of articles used), cascade_inputs (JSON — oil price, supply_loss, etc.), created_at. (recommended default — keeps prediction persistence separate from schema used for in-flight processing)
- **D-02:** `run_id` is a UUID generated per `run_brief()` invocation. All 3 predictions in a run share the same run_id for correlation. Signal ledger entries also get the run_id for full traceability.

### Resolution Polling
- **D-03:** Resolution checker is a standalone function `check_resolutions()` callable from CLI (`python -m parallax.cli.brief --check-resolutions`) or as part of the daily run. Not a background daemon. (recommended default — matches CLI-first architecture)
- **D-04:** Poll Kalshi production API for contract settlement status. When a contract resolves: update signal_ledger rows for that ticker with resolution_price, resolved_at, realized_pnl (= resolution_price - market_yes_price at signal time for BUY_YES, inverse for BUY_NO), and model_was_correct (= True if signal direction matched resolution).

### Calibration Queries
- **D-05:** On-demand SQL queries, not materialized views. Data volume is tiny (3 predictions/run, ~3 runs/day = <100 rows/week). Queries live in a `calibration.py` module. (recommended default — no premature optimization)
- **D-06:** Three core calibration queries:
  1. **Hit rate by proxy class** — GROUP BY proxy_class, compute accuracy (model_was_correct = True / total resolved)
  2. **Calibration curve** — Bucket predictions by probability (0-20%, 20-40%, ..., 80-100%), compare predicted probability vs actual resolution rate
  3. **Edge decay** — For resolved signals, compare effective_edge at signal time vs actual outcome, segmented by days-to-resolution
- **D-07:** Calibration CLI command: `python -m parallax.cli.brief --calibration` prints a text report. Requires at least 7 days of data (PERS-04).

### News Context Capture
- **D-08:** Store news references (title + URL + source + fetched_at) as JSON array in prediction_log.news_context, not full article text. Keeps storage light, articles are available via URL if needed. (recommended default)

### Claude's Discretion
- Exact column types and JSON structure for cascade_inputs (whatever the cascade engine currently outputs)
- Whether to add an index on prediction_log.run_id (depends on query patterns, Claude can decide)
- Error handling for Kalshi API polling failures (retry with existing httpx patterns)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 1 outputs (foundation)
- `.planning/phases/01-contract-registry-mapping-policy-evaluation-ledger/01-01-SUMMARY.md` — Registry schema and CRUD patterns
- `.planning/phases/01-contract-registry-mapping-policy-evaluation-ledger/01-03-SUMMARY.md` — Signal ledger schema with resolution columns

### Existing code
- `backend/src/parallax/scoring/ledger.py` — SignalLedger with resolution_price, realized_pnl, model_was_correct columns already defined
- `backend/src/parallax/prediction/schemas.py` — PredictionOutput model (what gets persisted)
- `backend/src/parallax/cli/brief.py` — Pipeline entry point to wire into
- `backend/src/parallax/markets/kalshi.py` — KalshiClient with RSA-PSS auth (used for resolution polling)
- `backend/src/parallax/db/schema.py` — DuckDB table definitions (add prediction_log here)
- `backend/src/parallax/simulation/cascade.py` — CascadeEngine outputs (cascade_inputs source)

### Research
- `.planning/research/contract-mapping/RESEARCH.md` — Contract mapping research (proxy class rationale)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `SignalLedger` already has resolution columns (resolution_price, resolved_at, realized_pnl, model_was_correct, proxy_was_aligned) — just need to populate them
- `KalshiClient` has production API auth — can query contract settlement status
- `create_tables()` in db/schema.py — add prediction_log table alongside existing tables
- DuckDB sync connection pattern from Phase 1 (not async writer)

### Established Patterns
- Pydantic models for all data structures (follow for SignalRecord, PredictionLog)
- In-memory DuckDB for tests with create_tables() fixture
- CLI flags on brief.py (--dry-run, --no-trade) — extend with --check-resolutions, --calibration
- Module-level logger pattern: `logger = logging.getLogger(__name__)`

### Integration Points
- `run_brief()` in brief.py — add run_id generation, prediction persistence after each model call
- Signal ledger — add run_id to record_signal() calls
- New calibration.py module in parallax/scoring/
- New resolution checker in parallax/markets/ or parallax/scoring/

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches based on existing codebase patterns.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 02-prediction-persistence-calibration*
*Context gathered: 2026-04-08*
