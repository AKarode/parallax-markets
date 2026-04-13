# Architecture Patterns

**Domain:** Prediction market edge-finder -- v1.4 integration architecture
**Researched:** 2026-04-12
**Confidence:** HIGH (all findings from direct codebase analysis of 10+ source files)

## Current Architecture Overview

```
brief.py (orchestrator, 838 lines)
  |
  +-- _fetch_gdelt_events()  -->  google_news.py, gdelt_doc.py, truth_social.py
  |                                  (3 sources, asyncio.gather, dedup by hash)
  |
  +-- _fetch_oil_prices()    -->  oil_prices.py (EIA API)
  |
  +-- _fetch_kalshi_markets() --> kalshi.py (12 event tickers, production reads)
  +-- _fetch_polymarket_markets() --> polymarket.py (Iran markets)
  |
  +-- 3 HARDCODED MODELS (lines 491-500):
  |     oil_pred = OilPricePredictor(cascade, budget, client)
  |     ceasefire_pred = CeasefirePredictor(budget, client)
  |     hormuz_pred = HormuzReopeningPredictor(cascade, budget, client)
  |     asyncio.gather(oil_pred.predict(...), ceasefire_pred.predict(...), hormuz_pred.predict(...))
  |
  +-- ContractRegistry.seed_initial_contracts()  -->  4 hardcoded ContractRecord objects
  +-- MappingPolicy.evaluate(prediction, market_prices)
  +-- SignalLedger.record_signal(...)
  +-- _deconflict_oil_signals(all_signals)
  +-- PortfolioAllocator.authorize_trade(...)
  +-- PaperTradeTracker.execute_signal(...)
```

### Key Architectural Properties

- **Sequential pipeline**: News -> Predict -> Map -> Signal -> Trade. No parallelism between stages.
- **Hardcoded model list**: 3 models instantiated directly in `run_brief()` at lines 491-493, gathered at lines 494-500.
- **Hardcoded context**: `crisis_context.py` is a single `CRISIS_TIMELINE` string constant (125 lines of Python string).
- **Hardcoded contracts**: `INITIAL_CONTRACTS` is a list of 4 `ContractRecord` objects in `registry.py`.
- **Event tickers**: `IRAN_EVENT_TICKERS` in `kalshi.py` has 12 tickers, but only 4 contracts are registered.
- **No ensemble in live path**: `brief.py` treats each model independently. `simulator.py` has `_aggregate_signals()` with weighted ensemble, but it only runs in backtest/simulation.
- **Each model owns its prompt**: System prompt is a module-level string in each predictor file.
- **Each model calls `get_crisis_context()` independently**: All 3 predictors import and prepend the same context string.
- **Backtest monkey-patches context**: `backtest/engine.py` line 203 replaces `get_crisis_context` at runtime.

---

## Change-by-Change Integration Analysis

### Change 1: Model Registry Pattern in brief.py

**What exists:** Lines 491-500 of `brief.py` hardcode 3 model instantiations and an `asyncio.gather()` call. Adding a 4th model means editing 3+ locations (imports, instantiation, gather call, dry-run mock data at lines 87-129).

**Integration point:** `run_brief()` function, specifically lines 470-500 (live path) and lines 87-129 (dry-run path).

**What changes:**
- **New file:** `prediction/registry.py` -- a `ModelRegistry` class that holds model metadata as data.
- **Modified file:** `brief.py` -- replace lines 491-500 with registry-driven loop.
- **Modified file:** `brief.py` `_make_dry_run_predictions()` -- generate from registry, not hardcoded list.

**Component design:**

```python
# prediction/registry.py

@dataclass
class ModelSpec:
    model_id: str                    # "oil_price", "ceasefire", "hormuz_reopening", "iran_political"
    prediction_type: str             # maps to PredictionOutput.prediction_type
    factory: Callable                # function that creates predictor instance
    requires_cascade: bool           # True for oil_price, hormuz_reopening
    requires_world_state: bool       # True for oil_price, hormuz_reopening
    requires_oil_prices: bool        # True for oil_price only
    enabled: bool = True

class ModelRegistry:
    def __init__(self) -> None:
        self._models: dict[str, ModelSpec] = {}

    def register(self, spec: ModelSpec) -> None: ...
    def get_enabled(self) -> list[ModelSpec]: ...

    async def run_all(
        self,
        events: list[dict],
        oil_prices: list[dict],
        world_state: WorldState,
        market_context: list[dict],
        cascade: CascadeEngine,
        budget: BudgetTracker,
        client: Any,
        db_conn: duckdb.DuckDBPyConnection | None,
    ) -> list[PredictionOutput]:
        """Instantiate and run all enabled models via asyncio.gather."""
        ...
```

**Data flow change:** None. Output is still `list[PredictionOutput]`. Everything downstream (MappingPolicy, SignalLedger, deconfliction, allocator) is unchanged.

**Dependency:** None. Can be built first.

**Risk:** Low. This is a refactor of existing code, not new behavior.

---

### Change 2: File-Based Context System

**What exists:** `prediction/crisis_context.py` has a single `CRISIS_TIMELINE` string constant (125 lines). Every predictor calls `get_crisis_context()` which returns this string. The backtest engine monkey-patches `get_crisis_context` at line 203 to inject date-limited context.

**Integration points:**
- `prediction/crisis_context.py` -- replace string constant with file loader.
- `prediction/oil_price.py` line 117-118, `prediction/ceasefire.py` line 101-102, `prediction/hormuz.py` line 104-105 -- all call `get_crisis_context()`.
- `backtest/engine.py` line 203 -- monkey-patches `get_crisis_context`.

**What changes:**
- **New directory:** `backend/context/` -- markdown files replacing the Python string.
  - `01_pre_crisis.md` -- Aug 2025 to Feb 2026 escalation (currently missing from timeline).
  - `02_crisis_timeline.md` -- Feb 2026 onward (currently the bulk of `CRISIS_TIMELINE`).
  - `03_market_state.md` -- current market snapshot section.
  - `04_prediction_context.md` -- contract-specific context section.
- **Modified file:** `prediction/crisis_context.py` -- `get_crisis_context()` reads and concatenates files from `context/` directory at runtime. Accepts optional `context_dir` parameter.
- **No change to predictors** -- they still call `get_crisis_context()`. Interface is stable.
- **Modified file:** `backtest/engine.py` -- pass `context_dir` parameter instead of monkey-patching.

**Component design:**

```python
# prediction/crisis_context.py (modified)

CONTEXT_DIR = Path(__file__).resolve().parent.parent.parent.parent / "context"

def get_crisis_context(context_dir: Path | None = None) -> str:
    """Read and concatenate all .md files from context directory, sorted by name."""
    base = context_dir or CONTEXT_DIR
    parts = []
    for filename in sorted(base.glob("*.md")):
        parts.append(filename.read_text())
    return "\n\n".join(parts)
```

**Data flow change:** None. Output is still a string. Predictors consume it identically.

**Dependency:** None. Can be built independently.

**Risk:** Low. File I/O is fast (< 1ms for small markdown files). Only risk is missing files at startup -- needs a fallback or clear error message.

---

### Change 3: Rolling Context Pipeline

**What exists:** No rolling context. Each cron run is stateless -- it fetches fresh news and makes predictions with no memory of previous runs. The `prediction_log` table stores historical predictions but they are never read back into prompts. The `_write_scheduled_output()` function in brief.py already writes per-run JSON to `~/parallax-logs/runs/`.

**Integration points:**
- `brief.py` `run_brief()` -- needs to append a context entry after each run.
- `prediction/crisis_context.py` -- needs to compose rolling context into prompt.
- Storage: new `backend/context/rolling/` directory for per-run JSON files.

**What changes:**
- **New file:** `context/rolling.py` -- manages per-run context entries.
- **Modified file:** `brief.py` -- after predictions complete, call `rolling.append_run_context()`.
- **Modified file:** `prediction/crisis_context.py` -- `get_crisis_context()` appends rolling window after static context.

**Component design:**

```python
# context/rolling.py

@dataclass
class RunContext:
    run_id: str
    timestamp: str
    predictions: dict[str, dict]   # model_id -> {probability, direction, confidence}
    news_headlines: list[str]      # top 5 headlines from this run
    market_snapshot: dict[str, float]  # ticker -> yes_price
    self_correction: str | None    # "Previously predicted X, market moved Y"

def append_run_context(run_context: RunContext, context_dir: Path) -> None:
    """Write JSON file for this run. Filename is ISO timestamp for sort order."""
    ...

def compose_rolling_context(context_dir: Path, window_days: int = 5) -> str:
    """Read last N days of run contexts, format as prompt section."""
    ...
```

**Data flow change:**
- New write at end of `run_brief()`: structured JSON per run.
- New read at start of prediction: rolling window injected into prompt.
- Prompt grows by ~200-500 tokens per run entry in window (5 days x 2 runs/day = 10 entries max = ~2K-5K tokens).

**Dependency:** Benefits from Change 2 (file-based context) for clean integration. Could technically work independently but the interface is cleaner if both use the same `context/` directory structure.

**Risk:** Medium. Prompt length management needed. At 10 entries x 200-500 tokens = 2K-5K additional tokens, this is well within Opus context limits but needs a cap mechanism to prevent unbounded growth.

---

### Change 4: New "Iran Political Transition" Model

**What exists:** 3 models with specific signatures:
- `OilPricePredictor.predict(events, prices, world_state, market_prices, db_conn)`
- `CeasefirePredictor.predict(events, [current_negotiations], market_prices, db_conn)`
- `HormuzReopeningPredictor.predict(events, world_state, market_prices, db_conn)`

All return `PredictionOutput`. No shared base class -- just a shared output schema.

**Integration points:**
- **New file:** `prediction/iran_political.py` -- new predictor class.
- **Modified file:** `prediction/registry.py` (from Change 1) -- register new model.
- **Modified file:** `contracts/registry.py` -- add contract records for regime-change tickers.
- **Modified file:** `contracts/mapping_policy.py` -- needs new `ContractFamily` enum value and fair-value estimator.
- **Modified file:** `contracts/schemas.py` -- new `ContractFamily.IRAN_POLITICAL` enum value.

**What changes:**
- New predictor following same pattern as `CeasefirePredictor` (no cascade engine needed).
- New contracts registered from already-known event tickers: `KXIRANDEMOCRACY-27MAR01`, `KXELECTIRAN`, `KXPAHLAVIHEAD-27JAN`, `KXPAHLAVIVISITA`, `KXNEXTIRANLEADER-45JAN01` (all already in `IRAN_EVENT_TICKERS` in `kalshi.py`).
- New proxy mappings: `iran_political` -> these contracts as DIRECT/NEAR_PROXY.
- New `ContractFamily.IRAN_POLITICAL` for regime-change/transition contracts.
- New fair-value estimator in `MappingPolicy._estimate_fair_value()` for political transition contracts.

**Component design:**

```python
# prediction/iran_political.py

class IranPoliticalPredictor:
    """Predicts Iran political transition probabilities."""

    def __init__(self, budget: BudgetTracker, anthropic_client: Any) -> None:
        self._budget = budget
        self._client = anthropic_client

    async def predict(
        self,
        recent_events: list[dict],
        market_prices: list[dict] | None = None,
        db_conn: duckdb.DuckDBPyConnection | None = None,
    ) -> PredictionOutput:
        # model_id = "iran_political"
        # prediction_type = "iran_political_transition"
        # Same LLM call pattern as CeasefirePredictor
        ...
```

**Data flow change:**
- One additional prediction in the `asyncio.gather()` call (4 models instead of 3).
- More contracts in registry -> more MappingResult objects per run -> more signals.
- Budget: ~$0.007 additional per run (one more Opus call). Well within $20/day cap.

**Dependency:** Depends on Change 1 (model registry) for clean addition. Could be added without registry by editing brief.py directly, but that perpetuates the hardcoding problem we are removing.

**Risk:** Low for the model itself. Medium for contract mapping -- needs correct proxy classifications for ~5 new contract families. The `_estimate_fair_value()` method in MappingPolicy needs a new branch for `ContractFamily.IRAN_POLITICAL`.

---

### Change 5: Contract Discovery

**What exists:** `ContractRegistry.seed_initial_contracts()` inserts 4 hardcoded `ContractRecord` objects. `_fetch_kalshi_markets()` in `brief.py` (lines 760-793) iterates `IRAN_EVENT_TICKERS` (12 tickers) to fetch prices, but only 4 of those have registry entries. The other 8 event tickers produce market prices that are fetched but never matched to predictions because the registry has no proxy mappings for them.

**Gap:** The system fetches prices for markets it cannot trade against. 12 event tickers exist in `kalshi.py` but only 4 contracts are in the registry.

**Integration points:**
- **Modified file:** `contracts/registry.py` -- add `discover_from_kalshi()` async method.
- **Modified file:** `brief.py` -- call discovery before or instead of `seed_initial_contracts()`.
- **Uses existing:** `markets/kalshi.py` `_request()` method for API calls.
- **Existing table:** `contract_registry` already has fields for settlement status, resolution_date, metadata.

**What changes:**
- `ContractRegistry` gains `discover_from_kalshi(client)` -- async method that:
  1. Iterates `IRAN_EVENT_TICKERS`.
  2. For each event ticker, calls `GET /markets?event_ticker=X&limit=50`.
  3. For each child market, creates/updates a `ContractRecord` with auto-classified proxy_map.
  4. Sets `is_active` based on market status (open/active = true, settled/finalized = false).
  5. Stores resolution_criteria, resolution_date, volume from API response.
- Hardcoded `INITIAL_CONTRACTS` stays as fallback for when API is unavailable.
- Auto-classification uses ticker patterns (existing `_classify_contract_family()` pattern).

**Component design:**

```python
# contracts/registry.py (extended)

async def discover_from_kalshi(
    self,
    kalshi_client: KalshiClient,
    event_tickers: list[str] | None = None,
) -> int:
    """Discover and register all child contracts from Kalshi event tickers.
    Returns number of contracts discovered.
    """
    tickers = event_tickers or IRAN_EVENT_TICKERS
    count = 0
    for event_ticker in tickers:
        data = await kalshi_client._request(
            "GET", "/markets", params={"event_ticker": event_ticker, "limit": 50}
        )
        for market in data.get("markets", []):
            contract = self._market_to_contract(market, event_ticker)
            self.upsert(contract)
            count += 1
    return count

def _market_to_contract(self, market: dict, event_ticker: str) -> ContractRecord:
    """Convert Kalshi market API response to ContractRecord with auto-classification."""
    # Uses existing _classify_contract_family pattern + new patterns for
    # DEMOCRACY, ELECTIRAN, PAHLAVIHEAD, etc.
    ...
```

**Data flow change:**
- Registry grows from 4 to potentially 30-50 contracts.
- More contracts -> more `MappingPolicy.evaluate()` iterations -> more signals per run.
- Need to handle settled/inactive contracts gracefully (don't generate signals for them).

**Dependency:** Independent, but pairs well with Change 4 (new model needs new contracts registered).

**Risk:** Medium.
- Auto-classification of proxy maps needs careful pattern matching for new ticker families.
- Volume/liquidity filtering needed -- many child contracts may have 0 volume.
- Should NOT run on every pipeline execution. Run as separate CLI command or on a slower cadence (daily).

---

### Change 6: News Source Diversification

**What exists:** `_fetch_gdelt_events()` in `brief.py` (lines 703-743) calls 3 sources in parallel:
- `fetch_google_news(seen_hashes=seen)` -- primary, reliable.
- `fetch_gdelt_docs(timespan="24h", seen_hashes=seen)` -- secondary, gets 429 errors frequently.
- `fetch_truth_social(seen_hashes=seen)` -- POTUS posts.

All return `list[NewsEvent]` (defined in `google_news.py`). Dedup is by `event_hash` (MD5 of URL). The function name `_fetch_gdelt_events` is a legacy name -- it actually fetches from multiple sources already.

**Integration points:**
- **New files:** `ingestion/reuters_rss.py`, `ingestion/ap_rss.py`, `ingestion/oil_feeds.py` -- new source modules.
- **Modified file:** `brief.py` `_fetch_gdelt_events()` -- add new sources to the `asyncio.gather()`.
- **No schema changes** -- all new sources produce `NewsEvent` objects.

**What changes:**
- New RSS feed modules following the exact pattern of `google_news.py`:
  - Accept `seen_hashes` for dedup.
  - Return `list[NewsEvent]`.
  - Filter by age.
  - Source field distinguishes origin ("reuters_rss", "ap_rss", "oil_feed").
- `_fetch_gdelt_events()` gains more `asyncio.gather` entries.
- Consider renaming to `_fetch_news_events()` since GDELT is just one of many sources now.

**Component design:**

```python
# ingestion/reuters_rss.py (new, follows google_news.py pattern exactly)

REUTERS_FEEDS = [
    # Reuters topic-specific RSS URLs
]

async def fetch_reuters_news(
    max_age_hours: int = 24,
    seen_hashes: set[str] | None = None,
) -> list[NewsEvent]:
    ...
```

**Data flow change:**
- More news events per run (currently ~20-50, could grow to 50-150).
- Each model caps its events: oil_price uses `recent_events[:10]`, ceasefire filters for diplomatic keywords first then takes `[:20]`. These caps mean more sources improve diversity but do not bloat prompts.
- Quality of signal may improve with more diverse perspectives.

**Dependency:** None. Completely independent of all other changes.

**Risk:** Low for implementation (the `NewsEvent` interface is stable, new sources just produce more events, existing dedup handles overlap).

**Research flag (MEDIUM confidence):** Reuters and AP RSS feed availability needs verification at implementation time. Reuters has historically restricted free RSS access. May need to fall back to wire service aggregators or alternative feeds.

---

### Change 7: Resolution Backtest

**What exists:** Two separate codepaths for validation:
1. `scoring/resolution.py` `check_resolutions()` -- polls Kalshi API for settled contracts, backfills signal_ledger with resolution_price and P&L.
2. `backtest/engine.py` `run_backtest()` -- replays historical days through models, scores against next-day price movement.

Neither does what "resolution backtest" requires: run the improved models against contracts that have already settled and score model predictions against actual binary settlement outcomes (0 or 1).

**Integration points:**
- **Modified file:** `backtest/engine.py` -- add `run_resolution_backtest()` function.
- **Uses existing:** `scoring/resolution.py` for settlement data retrieval patterns.
- **Uses existing:** signal_ledger table for contracts with `resolution_price IS NOT NULL`.

**What changes:**
- `backtest/engine.py` gains a `run_resolution_backtest()` function:
  1. Load contracts that have settled (from signal_ledger WHERE resolution_price IS NOT NULL, or from `SETTLEMENT_DATA` dict once populated).
  2. For each settled contract, build date-limited context as of the contract's active period.
  3. Run the relevant model(s) with that context.
  4. Compare model probability against settlement outcome (0.0 or 1.0).
  5. Score using Brier score, directional accuracy, and calibration metrics.
- CLI: `python -m parallax.cli.brief --resolution-backtest`

**Component design:**

```python
# backtest/engine.py (extended)

async def run_resolution_backtest(
    settlement_data: dict[str, dict] | None = None,
) -> dict[str, Any]:
    """Run models against settled contracts, score against actual outcomes.

    Unlike run_backtest() which scores against next-day price movement,
    this scores against final binary settlement (0.0 or 1.0).
    """
    settlements = settlement_data or _load_settlements_from_db()
    results = []
    for ticker, data in settlements.items():
        # Build context as of contract's active period
        # Run relevant model(s)
        # Compare prediction vs settlement
        ...
    return _score_resolution_results(results)
```

**Data flow change:**
- This is a new offline analysis tool, not part of the live pipeline.
- Consumes settlement data from DuckDB or hardcoded dict.
- Produces scoring metrics written to results file or stdout.

**Dependency:** Benefits from Change 1 (model registry for selecting which models to run), and Change 2 (file-based context for date-limited injection). Can work without them using the existing monkey-patching pattern in backtest/engine.py.

**Risk:** Medium.
- Need settlement data for enough contracts to be statistically meaningful. Currently `SETTLEMENT_DATA` in backtest/engine.py has 9 tickers all with `"settled": None` -- no actual settlement prices yet.
- Most Iran-related contracts have not settled yet (ceasefire/agreement contracts may not settle for months; oil price max/min contracts settle Dec 31, 2026).
- Scoring methodology: binary settlement (0 or 1) vs. probability estimates requires Brier score or log loss, not just directional accuracy.

---

### Change 8: Unified Ensemble

**What exists:** Two separate aggregation paths:
1. **Live path (brief.py):** Each prediction is independently mapped to contracts via MappingPolicy. No cross-model aggregation. If oil_price and hormuz_reopening both generate signals for KXWTIMAX, they create separate signals with separate edges. Only `_deconflict_oil_signals()` exists (suppresses conflicting oil signals on the same ticker).
2. **Simulator path (simulator.py lines 305-369):** `_aggregate_signals()` implements weighted ensemble -- groups signals by contract ticker, weights by per-model hit rate, combines edges into a single signal per ticker.

The live path records individual model signals. The simulator path aggregates across models. They disagree.

**Integration points:**
- **New file:** `portfolio/ensemble.py` -- shared ensemble logic extracted from simulator.
- **Modified file:** `brief.py` -- add ensemble aggregation after individual signal recording.
- **Modified file:** `portfolio/simulator.py` -- import from shared module instead of own copy.

**What changes:**
- Extract `_aggregate_signals()` from `simulator.py` into `portfolio/ensemble.py`.
- `brief.py` calls `ensemble.aggregate()` after recording individual signals to get combined signals per ticker.
- `simulator.py` imports the same function.
- Both paths use identical weighting, thresholds, and aggregation logic.
- Individual model signals are still recorded in signal_ledger (preserves auditability).
- Ensemble result is used for trade decisions and optionally logged.

**Component design:**

```python
# portfolio/ensemble.py (new, extracted from simulator.py)

@dataclass
class AggregatedSignal:
    ticker: str
    combined_signal: str       # BUY_YES, BUY_NO, HOLD
    combined_edge: float
    entry_side: str | None
    entry_price: float | None
    contributing_models: list[str]
    weights: dict[str, float]

def aggregate_signals(
    signals_by_ticker: dict[str, list],
    hit_rates: dict[tuple[str, str], float],
    edge_threshold: float = 0.05,
    default_hit_rate: float = 0.5,
) -> dict[str, AggregatedSignal]:
    """Weighted ensemble aggregation per contract.

    Used by both brief.py (live) and simulator.py (replay).
    """
    ...
```

**Data flow change:**
- In the live path, trade decisions are currently based on individual model signals.
- With ensemble, trade decisions are based on aggregated cross-model signals per ticker.
- Individual model signals are still recorded in signal_ledger (preserves per-model auditability and hit rate computation).
- The `_deconflict_oil_signals()` function may be subsumed by ensemble logic (ensemble naturally resolves conflicting signals by weighting).

**Dependency:** Benefits from Change 1 (more models = more signals to aggregate) and Change 4 (4th model). Independent technically but more valuable with more models.

**Risk:** Medium.
- Changing how trade decisions are made affects P&L outcomes.
- Need to decide: record ensemble result in signal_ledger as a separate entry, or add ensemble metadata to individual signals.
- Recommendation: Keep individual signals in ledger (preserve auditability), use ensemble result only for allocator/trade decisions. Do not add a new signal_ledger row for ensemble -- that would break the 1:1 mapping between signals and (model, contract) pairs that all scoring queries rely on.

---

## Component Boundaries

### New Components

| Component | File(s) | Responsibility | Depends On |
|-----------|---------|---------------|------------|
| Model Registry | `prediction/registry.py` | Models as data, dynamic instantiation | PredictionOutput schema |
| Context Loader | `prediction/crisis_context.py` (modified) | File-based context reading | `context/` directory |
| Rolling Context | `context/rolling.py` | Per-run context append/compose | Context loader |
| Iran Political Model | `prediction/iran_political.py` | 4th prediction model | PredictionOutput, BudgetTracker |
| Contract Discovery | `contracts/registry.py` (extended) | Auto-register from Kalshi API | KalshiClient, ContractRecord |
| News Sources | `ingestion/reuters_rss.py`, etc. | Additional news feeds | NewsEvent schema |
| Resolution Backtest | `backtest/engine.py` (extended) | Score against settlements | Models, settlement data |
| Shared Ensemble | `portfolio/ensemble.py` | Unified weighted aggregation | Signal data |

### Modified Components

| Component | File | What Changes | Lines Affected |
|-----------|------|-------------|----------------|
| Brief Orchestrator | `cli/brief.py` | Registry-driven models, rolling context write, ensemble | ~30 lines modified in run_brief() |
| Contract Registry | `contracts/registry.py` | Discovery method, more initial contracts | ~100 lines added |
| Mapping Policy | `contracts/mapping_policy.py` | New ContractFamily, new fair-value estimator | ~30 lines added to _estimate_fair_value() |
| Contract Schemas | `contracts/schemas.py` | New ContractFamily enum value | ~2 lines |
| Backtest Engine | `backtest/engine.py` | Resolution backtest mode | ~150 lines added |
| Simulator | `portfolio/simulator.py` | Import shared ensemble | ~5 lines changed |

### Unchanged Components

| Component | Why Unchanged |
|-----------|---------------|
| `markets/kalshi.py` | Already fetches all 12 event tickers. Discovery uses existing `_request()`. |
| `markets/polymarket.py` | Read-only, no changes needed. |
| `scoring/ledger.py` | Signal recording interface unchanged. Individual signals still recorded. |
| `scoring/tracker.py` | Paper trade execution unchanged. |
| `scoring/resolution.py` | Settlement checking unchanged. |
| `portfolio/allocator.py` | Kelly sizing unchanged. Receives signals the same way. |
| `db/schema.py` | No schema changes needed. Existing tables handle all new data. |
| `simulation/cascade.py` | Cascade engine unchanged. |
| `budget/tracker.py` | Budget tracking unchanged. One more model call is trivial. |

---

## Data Flow: Before and After

### Before (Current)

```
News Sources (3)
  |
  v
brief.py::_fetch_gdelt_events()
  |
  v
3 Hardcoded Models (asyncio.gather)
  |
  v
Python string context (crisis_context.py)
  |
  v
4 Hardcoded Contracts (seed_initial_contracts)
  |
  v
MappingPolicy.evaluate() -- per prediction, per contract
  |
  v
Individual signals -> SignalLedger (no cross-model aggregation)
  |
  v
Oil deconfliction only
  |
  v
PortfolioAllocator -> PaperTradeTracker
```

### After (v1.4)

```
News Sources (5+)                              Kalshi API (discovery, separate cadence)
  |                                               |
  v                                               v
brief.py::_fetch_news_events()           ContractRegistry.discover_from_kalshi()
  |                                               |
  v                                               v
File-based context + rolling window       30-50 registered contracts (DuckDB)
  |                                               |
  v                                               |
ModelRegistry.run_all() (4+ models)               |
  |                                               |
  v                                               v
MappingPolicy.evaluate() -- per prediction, per DISCOVERED contract
  |
  v
Individual signals per (model, contract) pair -> SignalLedger
  |
  v
Shared Ensemble aggregation (portfolio/ensemble.py)
  |
  v
Trade decisions based on aggregated signals
  |
  v
PortfolioAllocator -> PaperTradeTracker
  |
  v [after pipeline completes]
Rolling context write (context/rolling/)

  [OFFLINE, separate CLI commands]
  Resolution backtest (score against settlements)
  Contract discovery (enumerate Kalshi child markets)
```

---

## Suggested Build Order

Order based on dependencies, risk, and value. Three phases with internal parallelism.

### Phase 1: Foundation (no dependencies, enable everything else)

These three changes are fully independent and can be built in any order or in parallel.

**1a. Model Registry (Change 1)**
- Refactor brief.py from hardcoded to registry-driven.
- Zero behavior change, pure refactor.
- Enables: Change 4 (new model), Change 7 (resolution backtest model selection).
- Risk: Low.
- LOE: Small (~100-150 lines new, ~30 lines modified in brief.py).

**1b. File-Based Context (Change 2)**
- Move crisis_context.py string to context/ directory with numbered markdown files.
- Zero behavior change, `get_crisis_context()` interface stable.
- Enables: Change 3 (rolling context), cleaner Change 7 (date-limited context via directory override).
- Risk: Low.
- LOE: Small (~50 lines new code, content migration from Python string to markdown files).

**1c. News Diversification (Change 6)**
- Add new RSS/API sources to ingestion/.
- Zero dependency on other changes.
- Each source is independently testable. Pattern is proven (copy google_news.py).
- Risk: Low (known pattern). Reuters feed availability is a research flag for implementation.
- LOE: Small per source (~100 lines each following google_news.py pattern).

### Phase 2: New Capabilities (depend on Phase 1)

**2a. Contract Discovery (Change 5)**
- Extend ContractRegistry with Kalshi API discovery.
- No strict dependency, but benefits from Phase 1a (registry pattern informs auto-classification design).
- Risk: Medium (auto-classification of proxy maps needs testing against real API responses).
- LOE: Medium (~200-300 lines, including proxy classification logic and CLI command).

**2b. Iran Political Model (Change 4)**
- New predictor + new contract registrations + new ContractFamily.
- Depends on: Phase 1a (model registry for clean addition).
- Benefits from: Phase 2a (discovered contracts provide tickers to map to).
- Risk: Low (follows proven CeasefirePredictor pattern).
- LOE: Medium (~200-300 lines predictor, ~50 lines schema/mapping changes).

**2c. Rolling Context (Change 3)**
- Append per-run JSON, compose into prompt.
- Depends on: Phase 1b (file-based context system).
- Risk: Medium (prompt length management needed).
- LOE: Medium (~150-200 lines).

### Phase 3: Integration (depend on Phase 2)

**3a. Unified Ensemble (Change 8)**
- Extract from simulator.py, integrate into brief.py trade decisions.
- More valuable with Phase 2b (4th model gives more signals to aggregate).
- Benefits from Phase 2a (more contracts per model = more signals per ticker to aggregate).
- Risk: Medium (affects trade decisions and downstream P&L, needs careful testing).
- LOE: Medium (~100 lines extraction, ~50 lines brief.py integration).

**3b. Resolution Backtest (Change 7)**
- Score improved models against settled contracts.
- Benefits from Phase 1a (registry for model selection) and Phase 1b (file-based context for date override).
- Benefits from Phase 2b (4th model to include in backtest).
- Risk: Medium (needs actual settlement data -- many contracts have not settled yet).
- LOE: Medium (~200-300 lines extending backtest/engine.py).

### Build Order Rationale

```
Phase 1 (parallel):  1a Registry  |  1b File Context  |  1c News Sources
                         |                |
Phase 2 (parallel):  2a Discovery  |  2b Political Model  |  2c Rolling Context
                         |                |
Phase 3 (parallel):  3a Ensemble   |  3b Resolution Backtest
```

**Why this order:**
- Phase 1 items are pure refactors or additive features with zero risk to existing behavior.
- Phase 2 items build on Phase 1 foundations and introduce new capabilities.
- Phase 3 items integrate across the system and need Phase 2 features to be valuable.
- Within each phase, items can be built in parallel because they touch different files.

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: God Orchestrator
**What:** Putting all new logic directly into brief.py, making it grow from 838 to 1500+ lines.
**Why bad:** brief.py is already the most complex file. Adding registry logic, context loading, ensemble aggregation, and rolling context write directly into `run_brief()` makes it untestable and unreadable.
**Instead:** Each change lives in its own module. brief.py delegates: `registry.run_all()`, `rolling.append()`, `ensemble.aggregate()`. brief.py stays as a thin orchestrator that sequences calls.

### Anti-Pattern 2: Breaking the PredictionOutput Interface
**What:** Adding model-specific fields to PredictionOutput for the political model.
**Why bad:** All downstream code (MappingPolicy, SignalLedger, simulator, scorecard) assumes a uniform PredictionOutput. Model-specific data breaks this contract.
**Instead:** Keep PredictionOutput uniform. Put model-specific metadata in the `evidence` list or use the existing `metadata` field patterns.

### Anti-Pattern 3: Eager Contract Discovery on Every Run
**What:** Running contract discovery on every brief run, hitting Kalshi API with 12 event ticker queries (24+ API calls) every 12 hours.
**Why bad:** Adds 10-30 seconds to pipeline. Wastes Kalshi rate limit budget. Contracts rarely change (new ones appear maybe weekly).
**Instead:** Discovery runs separately as a CLI command (`--discover-contracts`) or on a slower cadence (daily cron). `seed_initial_contracts()` serves as fallback. Registry persists in DuckDB across runs.

### Anti-Pattern 4: Monolithic Context File
**What:** Replacing one giant Python string with one giant markdown file.
**Why bad:** Same problem in different format. Cannot override individual sections for backtest. Cannot update market state without touching timeline.
**Instead:** Multiple smaller numbered files (`01_pre_crisis.md`, `02_crisis_timeline.md`, etc.). Each can be updated, replaced, or overridden independently. Backtest can swap just the timeline file.

### Anti-Pattern 5: Ensemble Replaces Individual Signals
**What:** Only recording the ensemble result in signal_ledger, discarding individual model signals.
**Why bad:** Loses auditability. Cannot debug which model was right/wrong. Cannot compute per-model hit rates needed for ensemble weighting itself. Breaks existing `signal_quality_evaluation` view that filters by model_id.
**Instead:** Record individual model signals (current behavior unchanged). Use ensemble aggregation only for trade authorization decisions. Per-model signals in signal_ledger continue to drive scoring, calibration, and track record.

---

## Scalability Considerations

| Concern | Current (4 contracts, 3 models) | After v1.4 (30-50 contracts, 4 models) | Mitigation |
|---------|--------------------------------|----------------------------------------|------------|
| Signals per run | ~8-12 | ~40-80 | SignalLedger batch writes handle this. DuckDB inserts are fast. |
| LLM calls per run | 3 (Opus) | 4 (Opus) | ~$0.03/run vs $20/day budget. Massive headroom. |
| Kalshi API calls for prices | ~12 per run | ~12 per run (same event tickers) | Discovery is separate from price fetch. |
| Kalshi API calls for discovery | 0 | ~12 per discovery run (not per brief run) | Run discovery daily, not per pipeline. |
| Prompt size | ~3K tokens context | ~5-8K tokens (file context + rolling) | Cap rolling window. Well within Opus limits. |
| DuckDB rows/run | ~20-30 inserts | ~60-100 inserts | Single-writer queue handles this. Sub-second total. |
| Contract registry size | 4 rows | 30-50 rows | Trivial for DuckDB. |

---

## Sources

All findings are HIGH confidence, based on direct source code analysis:

- `cli/brief.py` (838 lines) -- orchestrator, all integration points examined line-by-line
- `prediction/crisis_context.py` (131 lines) -- current context system
- `prediction/oil_price.py` (224 lines) -- model pattern, prompt structure, predict() signature
- `prediction/ceasefire.py` (206 lines) -- model pattern template for new political model
- `prediction/hormuz.py` (220 lines) -- cascade-dependent model pattern
- `prediction/schemas.py` (40 lines) -- PredictionOutput interface contract
- `contracts/registry.py` (285 lines) -- current contract management and INITIAL_CONTRACTS
- `contracts/mapping_policy.py` (589 lines) -- fair-value estimation and ContractFamily routing
- `contracts/schemas.py` (142 lines) -- ProxyClass, ContractFamily, MappingResult schemas
- `portfolio/simulator.py` (534 lines) -- existing ensemble implementation (_aggregate_signals)
- `backtest/engine.py` (384 lines) -- existing backtest infrastructure and SETTLEMENT_DATA
- `markets/kalshi.py` (402 lines) -- API client, IRAN_EVENT_TICKERS (12 tickers)
- `ingestion/google_news.py` (158 lines) -- NewsEvent schema, RSS pattern to copy
- `ingestion/gdelt_doc.py` (142 lines) -- secondary news source pattern
- `ingestion/truth_social.py` (166 lines) -- third news source pattern
- `db/schema.py` (667 lines) -- all DuckDB tables and migrations
- `scoring/resolution.py` (256 lines) -- settlement backfill patterns
- `scoring/track_record.py` (85 lines) -- per-model track record for prompt injection
