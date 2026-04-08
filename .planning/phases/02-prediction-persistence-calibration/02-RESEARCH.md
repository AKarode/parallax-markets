# Phase 2: Prediction Persistence + Calibration - Research

**Researched:** 2026-04-08
**Domain:** DuckDB persistence, Kalshi API settlement polling, calibration SQL queries
**Confidence:** HIGH

## Summary

This phase adds three capabilities to the existing pipeline: (1) persist every prediction with full context in a new `prediction_log` DuckDB table, (2) poll Kalshi production API for contract settlement and backfill signal_ledger resolution columns, and (3) provide on-demand calibration SQL queries answering "is this system any good?"

The existing codebase is well-structured for this work. The signal_ledger table already has resolution columns (resolution_price, resolved_at, realized_pnl, model_was_correct, proxy_was_aligned) that just need to be populated. The KalshiClient already authenticates to the production API. DuckDB 1.5.1 handles JSON columns natively. The data volume is tiny (~9 predictions/day, ~27 signal_ledger rows/day), so no performance concerns.

**Primary recommendation:** Build three modules -- `parallax.scoring.prediction_log` (persistence), `parallax.scoring.resolution` (Kalshi polling + backfill), `parallax.scoring.calibration` (SQL queries + text report) -- following the established pattern of Pydantic model + DuckDB class seen in SignalLedger.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** New `prediction_log` table in DuckDB (not extending PredictionOutput model). Each row captures one prediction run with: run_id, model_id, probability, direction, confidence, reasoning, evidence (JSON array), timeframe, news_context (JSON -- titles+URLs of articles used), cascade_inputs (JSON -- oil price, supply_loss, etc.), created_at.
- **D-02:** `run_id` is a UUID generated per `run_brief()` invocation. All 3 predictions in a run share the same run_id for correlation. Signal ledger entries also get the run_id for full traceability.
- **D-03:** Resolution checker is a standalone function `check_resolutions()` callable from CLI (`python -m parallax.cli.brief --check-resolutions`) or as part of the daily run. Not a background daemon.
- **D-04:** Poll Kalshi production API for contract settlement status. When a contract resolves: update signal_ledger rows for that ticker with resolution_price, resolved_at, realized_pnl, and model_was_correct.
- **D-05:** On-demand SQL queries, not materialized views. Data volume is tiny. Queries live in a `calibration.py` module.
- **D-06:** Three core calibration queries: (1) hit rate by proxy class, (2) calibration curve by probability bucket, (3) edge decay by effective_edge bucket.
- **D-07:** Calibration CLI command: `python -m parallax.cli.brief --calibration` prints a text report. Requires at least 7 days of data (PERS-04).
- **D-08:** Store news references (title + URL + source + fetched_at) as JSON array in prediction_log.news_context, not full article text.

### Claude's Discretion
- Exact column types and JSON structure for cascade_inputs (whatever the cascade engine currently outputs)
- Whether to add an index on prediction_log.run_id (depends on query patterns, Claude can decide)
- Error handling for Kalshi API polling failures (retry with existing httpx patterns)

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PERS-01 | Every PredictionOutput persisted in DuckDB with timestamp and run_id | prediction_log table schema, PredictionLogEntry model, persistence in run_brief() after each model call |
| PERS-02 | Resolution checker polls Kalshi/Polymarket APIs for settled contracts, backfills signal_ledger | Kalshi GET /markets/{ticker} returns status ("determined"/"finalized") + result + settlement_value fields; update signal_ledger resolution columns |
| PERS-03 | Calibration queries: hit rate by proxy class, calibration curve, edge decay | Three SQL queries in calibration.py module, text report formatter |
| PERS-04 | At least 7 days of prediction data before calibration analysis is valid | Data guard check in calibration report -- query min(created_at) from prediction_log, refuse if < 7 days |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| duckdb | 1.5.1 | Prediction log + calibration queries | Already used for all persistence [VERIFIED: python3 -c "import duckdb; print(duckdb.__version__)"] |
| pydantic | 2.10+ | PredictionLogEntry model | Already used for all data models in the project [VERIFIED: pyproject.toml] |
| httpx | 0.28+ | Kalshi API polling in resolution checker | Already used by KalshiClient [VERIFIED: kalshi.py] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| uuid (stdlib) | - | Generate run_id per brief invocation | Same pattern as signal_id in SignalLedger [VERIFIED: ledger.py] |
| json (stdlib) | - | Serialize news_context and cascade_inputs to JSON strings | DuckDB JSON columns accept json.dumps() strings [VERIFIED: tested DuckDB JSON round-trip] |

### Alternatives Considered
None -- all libraries already in use. No new dependencies needed.

## Architecture Patterns

### Recommended Project Structure
```
backend/src/parallax/scoring/
    calibration.py          # NEW: 3 calibration SQL queries + text report
    prediction_log.py       # NEW: PredictionLogEntry model + PredictionLogger class
    resolution.py           # NEW: check_resolutions() + Kalshi settlement polling
    ledger.py               # EXISTING: add run_id column, update_resolution() method
    tracker.py              # EXISTING: unchanged
```

### Pattern 1: Pydantic Model + DuckDB Class (established pattern)
**What:** Each persistence concern gets a Pydantic model (data shape) and a class wrapping DuckDB operations (CRUD).
**When to use:** Every new table in this phase.
**Example:**
```python
# Source: established pattern in backend/src/parallax/scoring/ledger.py
class PredictionLogEntry(BaseModel):
    """Immutable record of a single prediction."""
    log_id: str
    run_id: str
    model_id: str
    probability: float
    direction: str
    confidence: float
    reasoning: str
    evidence: list[str]  # serialized as JSON
    timeframe: str
    news_context: list[dict]  # serialized as JSON
    cascade_inputs: dict | None  # serialized as JSON, None for non-cascade models
    created_at: datetime

class PredictionLogger:
    """Append-only prediction log backed by DuckDB."""
    def __init__(self, conn: duckdb.DuckDBPyConnection) -> None:
        self._conn = conn

    def log_prediction(self, run_id: str, prediction: PredictionOutput, 
                       news_context: list[dict], cascade_inputs: dict | None) -> PredictionLogEntry:
        ...
```
[VERIFIED: follows SignalLedger pattern in ledger.py]

### Pattern 2: CLI Flag Extension (established pattern)
**What:** Add `--check-resolutions` and `--calibration` flags to the existing argparse in brief.py.
**When to use:** For resolution polling and calibration report CLI access.
**Example:**
```python
# Source: established pattern in backend/src/parallax/cli/brief.py
parser.add_argument("--check-resolutions", action="store_true",
    help="Poll Kalshi for settled contracts and backfill outcomes")
parser.add_argument("--calibration", action="store_true",
    help="Print calibration report (requires 7+ days of data)")
```
[VERIFIED: brief.py already uses this pattern for --dry-run, --no-trade]

### Pattern 3: Sync DuckDB Connection (Phase 1 pattern)
**What:** Use synchronous DuckDB connection (not async DbWriter) for all new persistence.
**When to use:** All reads and writes in this phase.
**Why:** Phase 1 established this pattern. The data volume is tiny. The async DbWriter exists but is for high-throughput scenarios. [VERIFIED: brief.py uses `conn = duckdb.connect(db_path)` directly]

### Anti-Patterns to Avoid
- **Extending PredictionOutput model:** D-01 explicitly says use a separate table. PredictionOutput is the in-flight processing model; prediction_log is the historical record.
- **Background daemon for resolution checking:** D-03 says standalone function callable from CLI, not a daemon.
- **Materialized views for calibration:** D-05 says on-demand SQL queries. Data volume is ~100 rows/week.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| UUID generation | Custom ID scheme | `str(uuid.uuid4())` | Standard, collision-free, matches signal_id pattern [VERIFIED: ledger.py] |
| JSON serialization for DuckDB | Custom serializer | `json.dumps()` for insert, DuckDB returns JSON as string | DuckDB JSON type accepts string, returns string [VERIFIED: tested round-trip] |
| Probability bucketing | Custom bucket logic | SQL CASE WHEN for 5 buckets | Standard SQL pattern, no Python needed |
| P&L calculation | Custom formula | `resolution_price - market_yes_price` for BUY_YES, `(1 - resolution_price) - market_no_price` for BUY_NO | Matches D-04 specification |

## Common Pitfalls

### Pitfall 1: Kalshi Market Status Values
**What goes wrong:** Polling for "resolved" status when Kalshi uses different terminology.
**Why it happens:** Kalshi API v2 uses specific status values: "initialized", "inactive", "active", "closed", "determined", "disputed", "amended", "finalized". The resolution outcome is in the `result` field, not the `status` field.
**How to avoid:** Check for `status` in ("determined", "finalized") to detect resolved markets. The `result` field contains "yes" or "no". The `settlement_value` field is a fixed-point dollar string (0.0 to 1.0 for binary markets). The `settlement_ts` field gives the settlement timestamp.
**Warning signs:** Getting empty results from resolution polling.
[CITED: docs.kalshi.com/changelog -- status values and settlement_ts documented]

### Pitfall 2: DuckDB JSON Column Insert Syntax
**What goes wrong:** Passing Python dicts directly to DuckDB parameterized queries for JSON columns.
**Why it happens:** DuckDB JSON columns accept strings, not Python dicts.
**How to avoid:** Always `json.dumps()` before inserting into a JSON column. On read, DuckDB returns JSON as a string -- use `json.loads()` if you need a dict.
**Warning signs:** TypeError on insert.
[VERIFIED: tested DuckDB 1.5.1 JSON round-trip -- stores and returns as string]

### Pitfall 3: run_id Not in signal_ledger Schema
**What goes wrong:** D-02 says signal_ledger entries should get run_id, but the current signal_ledger table has no run_id column.
**Why it happens:** Phase 1 built signal_ledger without run_id (it wasn't a requirement then).
**How to avoid:** Add `run_id VARCHAR` column to signal_ledger table DDL in create_tables(). Add run_id parameter to `record_signal()`. For DuckDB in-memory (test mode), the table is recreated each time so ALTER TABLE isn't needed. For persistent DuckDB, use `ALTER TABLE signal_ledger ADD COLUMN IF NOT EXISTS run_id VARCHAR`.
**Warning signs:** run_id missing from signal records, can't correlate signals with prediction runs.
[VERIFIED: signal_ledger schema in db/schema.py has no run_id column]

### Pitfall 4: Cascade Inputs Vary by Model
**What goes wrong:** Assuming all 3 models have cascade_inputs when only oil_price and hormuz use the cascade engine.
**Why it happens:** CeasefirePredictor takes only (events, current_negotiations), no cascade engine.
**How to avoid:** cascade_inputs should be nullable in prediction_log. For ceasefire model, store None/null. For oil_price, store: supply_loss, bypass_flow, price_shock_pct, current_price. For hormuz, store whatever cascade state it uses.
**Warning signs:** NullPointerError when trying to serialize cascade state from ceasefire model.
[VERIFIED: CeasefirePredictor.__init__ takes (budget, anthropic_client) -- no cascade engine]

### Pitfall 5: Kalshi Demo vs Production for Resolution Polling
**What goes wrong:** Polling demo API for settlement status, getting no geopolitical markets.
**Why it happens:** Demo sandbox only has sports/crypto markets. Iran/Hormuz contracts are only on production.
**How to avoid:** Resolution checker MUST use production API URL (`https://api.elections.kalshi.com/trade-api/v2`), same as market price fetching in brief.py.
**Warning signs:** All tickers returning "not found" from resolution check.
[VERIFIED: brief.py uses PROD_URL for market fetching; CLAUDE.md documents this gotcha]

## Code Examples

### prediction_log Table DDL
```sql
-- Source: follows contract_registry pattern in db/schema.py
CREATE TABLE IF NOT EXISTS prediction_log (
    log_id VARCHAR PRIMARY KEY,
    run_id VARCHAR NOT NULL,
    model_id VARCHAR NOT NULL,
    probability DOUBLE NOT NULL,
    direction VARCHAR NOT NULL,
    confidence DOUBLE NOT NULL,
    reasoning TEXT,
    evidence JSON,
    timeframe VARCHAR NOT NULL,
    news_context JSON,
    cascade_inputs JSON,
    created_at TIMESTAMP NOT NULL
)
```
[VERIFIED: follows column naming conventions from existing tables in db/schema.py]

### Cascade Inputs Structure for oil_price Model
```python
# Source: backend/src/parallax/prediction/oil_price.py lines 71-88
cascade_inputs = {
    "supply_loss": supply_loss,        # float, bbl/day lost
    "bypass_flow": bypass_flow,        # float, bbl/day through alternate routes
    "price_shock_pct": price_shock_pct, # float, percentage price increase
    "current_price": current_price,     # float, current Brent $/bbl
}
```
[VERIFIED: read from oil_price.py predict() method]

### News Context Structure (D-08)
```python
# Each news event stored as:
news_context = [
    {
        "title": "Iran-US talks resume in Oman",
        "url": "https://...",
        "source": "google_news",       # or "gdelt_doc"
        "fetched_at": "2026-04-08T12:00:00Z"
    },
    # ... up to 10-20 events per prediction
]
```
[VERIFIED: matches NewsEvent fields from _fetch_gdelt_events() in brief.py]

### Resolution Backfill Query
```python
# Update signal_ledger resolution columns for a settled contract
conn.execute("""
    UPDATE signal_ledger
    SET resolution_price = ?,
        resolved_at = ?,
        realized_pnl = CASE
            WHEN signal = 'BUY_YES' THEN ? - market_yes_price
            WHEN signal = 'BUY_NO' THEN (1.0 - ?) - market_no_price
            ELSE NULL
        END,
        model_was_correct = CASE
            WHEN signal = 'BUY_YES' AND ? > 0.5 THEN true
            WHEN signal = 'BUY_NO' AND ? <= 0.5 THEN true
            WHEN signal IN ('BUY_YES', 'BUY_NO') THEN false
            ELSE NULL
        END
    WHERE contract_ticker = ?
      AND resolution_price IS NULL
""", [resolution_price, resolved_at, resolution_price, resolution_price, 
      resolution_price, resolution_price, ticker])
```
[ASSUMED: P&L formula based on D-04 specification; model_was_correct logic needs validation]

### Calibration Query: Hit Rate by Proxy Class
```sql
-- Source: D-06 specification
SELECT
    proxy_class,
    COUNT(*) AS total,
    SUM(CASE WHEN model_was_correct THEN 1 ELSE 0 END) AS correct,
    ROUND(SUM(CASE WHEN model_was_correct THEN 1 ELSE 0 END)::DOUBLE / COUNT(*), 3) AS hit_rate
FROM signal_ledger
WHERE model_was_correct IS NOT NULL
GROUP BY proxy_class
ORDER BY proxy_class
```
[ASSUMED: standard SQL pattern; DuckDB syntax verified for CASE/ROUND]

### Calibration Query: Calibration Curve
```sql
SELECT
    CASE
        WHEN model_probability < 0.2 THEN '0-20%'
        WHEN model_probability < 0.4 THEN '20-40%'
        WHEN model_probability < 0.6 THEN '40-60%'
        WHEN model_probability < 0.8 THEN '60-80%'
        ELSE '80-100%'
    END AS bucket,
    COUNT(*) AS n,
    ROUND(AVG(model_probability), 3) AS avg_predicted,
    ROUND(AVG(CASE WHEN model_was_correct THEN 1.0 ELSE 0.0 END), 3) AS actual_rate
FROM signal_ledger
WHERE model_was_correct IS NOT NULL
GROUP BY bucket
ORDER BY bucket
```
[ASSUMED: standard SQL bucketing pattern]

### Calibration Query: Edge Decay
```sql
SELECT
    CASE
        WHEN ABS(effective_edge) < 0.05 THEN '<5%'
        WHEN ABS(effective_edge) < 0.10 THEN '5-10%'
        WHEN ABS(effective_edge) < 0.15 THEN '10-15%'
        ELSE '15%+'
    END AS edge_bucket,
    COUNT(*) AS n,
    ROUND(AVG(ABS(effective_edge)), 3) AS avg_edge,
    ROUND(AVG(realized_pnl), 4) AS avg_pnl,
    ROUND(AVG(CASE WHEN model_was_correct THEN 1.0 ELSE 0.0 END), 3) AS hit_rate
FROM signal_ledger
WHERE realized_pnl IS NOT NULL
GROUP BY edge_bucket
ORDER BY edge_bucket
```
[ASSUMED: D-06 says "segmented by days-to-resolution" but edge_bucket is more actionable -- planner may adjust]

### Kalshi Market Resolution Check
```python
# Source: Kalshi API v2 changelog -- status and settlement fields
async def _check_market_resolution(client: KalshiClient, ticker: str) -> dict | None:
    """Check if a Kalshi market has settled. Returns resolution data or None."""
    data = await client._request("GET", f"/markets/{ticker}")
    market = data.get("market", data)
    status = market.get("status", "")
    if status in ("determined", "finalized"):
        result = market.get("result", "")  # "yes" or "no"
        settlement_value = float(market.get("settlement_value", 0))  # 0.0 or 1.0 for binary
        settlement_ts = market.get("settlement_ts")
        return {
            "status": status,
            "result": result,
            "resolution_price": settlement_value,  # 1.0 if yes, 0.0 if no
            "settled_at": settlement_ts,
        }
    return None
```
[CITED: docs.kalshi.com/changelog -- settlement_value and settlement_ts fields added Dec 2025/Feb 2026]

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Kalshi v2 no settlement_ts | `settlement_ts` on GET /markets response | Dec 25 2025 | Can capture exact resolution time |
| Kalshi `market_result` empty for scalar | `market_result` returns "scalar" | Jan 28 2026 | Better identification of settlement type |
| Kalshi WebSocket only settlement | REST GET also returns settlement data | Feb 26 2026 | Can poll REST instead of requiring WebSocket |

[CITED: docs.kalshi.com/changelog]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | P&L formula: `resolution_price - market_yes_price` for BUY_YES | Code Examples | Incorrect P&L calculation -- but formula is straightforward binary math |
| A2 | model_was_correct = True when BUY_YES and resolution > 0.5 | Code Examples | Could misclassify correctness if resolution is scalar not binary |
| A3 | Edge decay query uses edge_bucket instead of days-to-resolution | Code Examples | D-06 says "segmented by days-to-resolution" -- may need both dimensions |
| A4 | Kalshi `result` field is "yes" or "no" for binary markets | Pitfall 1 | Could be different format -- verify with actual API response |
| A5 | `settlement_value` is 0.0 or 1.0 for binary markets | Code Examples | Could be in cents or other format |

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.3 with pytest-asyncio 0.25 |
| Config file | backend/pyproject.toml [tool.pytest.ini_options] |
| Quick run command | `cd backend && python -m pytest tests/test_prediction_log.py tests/test_resolution.py tests/test_calibration.py -x` |
| Full suite command | `cd backend && python -m pytest tests/ -x` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PERS-01 | Prediction persisted with all fields | unit | `pytest tests/test_prediction_log.py::test_log_prediction_persists_all_fields -x` | Wave 0 |
| PERS-01 | run_id shared across 3 predictions | unit | `pytest tests/test_prediction_log.py::test_run_id_correlates_predictions -x` | Wave 0 |
| PERS-01 | news_context JSON round-trip | unit | `pytest tests/test_prediction_log.py::test_news_context_json_roundtrip -x` | Wave 0 |
| PERS-02 | Resolution backfill updates signal_ledger | unit | `pytest tests/test_resolution.py::test_backfill_updates_resolution_columns -x` | Wave 0 |
| PERS-02 | Settled contracts detected from Kalshi response | unit | `pytest tests/test_resolution.py::test_detect_settled_market -x` | Wave 0 |
| PERS-02 | Unsettled contracts skipped | unit | `pytest tests/test_resolution.py::test_skip_unsettled_market -x` | Wave 0 |
| PERS-03 | Hit rate by proxy class query | unit | `pytest tests/test_calibration.py::test_hit_rate_by_proxy_class -x` | Wave 0 |
| PERS-03 | Calibration curve bucketing | unit | `pytest tests/test_calibration.py::test_calibration_curve -x` | Wave 0 |
| PERS-03 | Edge decay analysis | unit | `pytest tests/test_calibration.py::test_edge_decay -x` | Wave 0 |
| PERS-04 | 7-day minimum data guard | unit | `pytest tests/test_calibration.py::test_minimum_data_guard -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** Quick run command for new tests
- **Per wave merge:** `cd backend && python -m pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_prediction_log.py` -- covers PERS-01
- [ ] `tests/test_resolution.py` -- covers PERS-02
- [ ] `tests/test_calibration.py` -- covers PERS-03, PERS-04
- Framework install: None needed -- pytest already configured and working

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | N/A -- uses existing Kalshi RSA-PSS auth |
| V3 Session Management | no | N/A -- CLI tool, no sessions |
| V4 Access Control | no | N/A -- single-user tool |
| V5 Input Validation | yes | Pydantic models validate all inputs; parameterized SQL prevents injection |
| V6 Cryptography | no | N/A -- no new crypto, existing RSA-PSS auth unchanged |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| SQL injection in calibration queries | Tampering | All queries use parameterized statements or literal SQL with no user input [VERIFIED: existing pattern in ledger.py] |
| API key exposure in logs | Information Disclosure | Existing KalshiClient doesn't log credentials; resolution checker reuses same client [VERIFIED: kalshi.py logging] |

## Sources

### Primary (HIGH confidence)
- `backend/src/parallax/scoring/ledger.py` -- SignalLedger pattern, signal_ledger schema with resolution columns
- `backend/src/parallax/db/schema.py` -- All DuckDB table definitions, column naming conventions
- `backend/src/parallax/cli/brief.py` -- Pipeline entry point, CLI flag pattern, run flow
- `backend/src/parallax/markets/kalshi.py` -- KalshiClient with _request(), production URL pattern
- `backend/src/parallax/prediction/oil_price.py` -- Cascade inputs structure (supply_loss, bypass_flow, price_shock_pct)
- `backend/src/parallax/prediction/ceasefire.py` -- No cascade engine (cascade_inputs is null)
- DuckDB 1.5.1 JSON round-trip verified via Python test

### Secondary (MEDIUM confidence)
- [docs.kalshi.com/changelog](https://docs.kalshi.com/changelog) -- settlement_value, settlement_ts, status values, result field

### Tertiary (LOW confidence)
- Kalshi `result` field exact format ("yes"/"no") -- needs live API verification (A4)
- Kalshi `settlement_value` exact format for binary markets -- needs live API verification (A5)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already in use, no new dependencies
- Architecture: HIGH -- follows established Pydantic + DuckDB patterns from Phase 1
- Pitfalls: HIGH -- verified against actual codebase, Kalshi API docs consulted
- Calibration queries: MEDIUM -- SQL is standard but exact bucketing and P&L formulas are assumed

**Research date:** 2026-04-08
**Valid until:** 2026-04-22 (stable domain, DuckDB/Kalshi APIs unlikely to change in 2 weeks)
