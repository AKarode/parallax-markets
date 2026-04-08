# Contract Registry, Mapping Policy & Evaluation Ledger - Research

**Researched:** 2026-04-08
**Domain:** Prediction market contract alignment, proposition mapping, P&L tracking
**Confidence:** HIGH (domain is well-understood, codebase fully examined)

## Summary

The current Parallax pipeline has a critical structural weakness: the mapping between model predictions and tradeable contracts is a heuristic function (`_map_predictions_to_markets()` in `cli/brief.py`) with no formal proposition alignment, no proxy quality tracking, and no confidence discounting. This means the system can be "right" about geopolitics but lose money because the model's claim and the contract's resolution criteria are semantically different.

Three components need to be built: (1) a **Contract Registry** in DuckDB that stores each contract's exact resolution criteria and proxy classification relative to each model type, (2) a **Mapping Policy** module that replaces the heuristic mapping with explicit proposition alignment and confidence discounting, and (3) an **Evaluation Ledger** that persists every signal with full provenance for calibration analysis.

**Primary recommendation:** Build all three as pure Python + Pydantic + DuckDB -- no external libraries needed beyond what's already in the stack. The contract registry is the foundation; mapping policy and evaluation ledger depend on it.

## Project Constraints (from CLAUDE.md)

- **Tech stack locked:** Python 3.12, FastAPI, DuckDB, Pydantic 2.10+, httpx, anthropic SDK [VERIFIED: codebase]
- **Budget:** $20/day LLM calls -- these components involve zero LLM calls (pure logic) [VERIFIED: CLAUDE.md]
- **Naming:** snake_case functions, PascalCase classes, frozen dataclasses for immutable types [VERIFIED: CLAUDE.md]
- **Module design:** Absolute imports from `parallax.*`, private utilities prefixed with `_` [VERIFIED: CLAUDE.md]
- **Error handling:** Defensive checks return defaults rather than raising [VERIFIED: CLAUDE.md]
- **DB pattern:** Async single-writer queue via `DbWriter`, read-only queries in `db/queries.py` [VERIFIED: codebase]
- **GSD workflow:** Must use GSD commands for file changes [VERIFIED: CLAUDE.md]

## Standard Stack

### Core (already in project -- no new dependencies)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| DuckDB | 1.2+ | Contract registry & evaluation ledger storage | Already the project DB, OLAP-optimized for analytics queries [VERIFIED: pyproject.toml] |
| Pydantic | 2.10+ | Data models for contracts, mappings, ledger entries | Already used for all schemas in the project [VERIFIED: codebase] |
| Python enum | stdlib | ProxyClass, MappingDecision enums | Type-safe categorical values, no deps [VERIFIED: stdlib] |

### Supporting (already available)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| uuid | stdlib | Unique IDs for ledger entries | Every signal record |
| datetime | stdlib | Timestamps for all records | Every record |
| logging | stdlib | Audit trail for mapping decisions | Every mapping decision |

### No New Dependencies Needed

This is a data modeling and business logic problem. The existing stack (DuckDB + Pydantic + Python stdlib) handles it completely. Adding libraries would be overengineering.

## Architecture Patterns

### Recommended Module Structure

```
backend/src/parallax/
├── contracts/
│   ├── __init__.py
│   ├── registry.py         # ContractRegistry class + DuckDB CRUD
│   ├── schemas.py          # Contract, ProxyClass, ContractMapping models
│   └── mapping_policy.py   # MappingPolicy class -- replaces _map_predictions_to_markets
├── scoring/
│   ├── tracker.py          # (existing) PaperTradeTracker
│   └── ledger.py           # EvaluationLedger class -- persistent signal tracking
```

### Pattern 1: Contract Registry as a Typed Catalog

**What:** Each contract in the registry has its exact resolution criteria stored as structured data, not just a ticker string. The registry knows which model types can map to which contracts and at what proxy quality.

**When to use:** Every time the pipeline needs to match a prediction to a tradeable contract.

**Data model:**

```python
# Source: Designed from codebase analysis of existing schemas
from enum import Enum
from datetime import datetime
from pydantic import BaseModel


class ProxyClass(str, Enum):
    """How closely a contract maps to a model's prediction.
    
    DIRECT: Contract resolves on exactly what the model predicts.
      Example: model predicts "ceasefire holds 14d" -> contract "Will Iran ceasefire hold?"
    
    NEAR_PROXY: Contract resolves on a closely correlated but different proposition.
      Example: model predicts "ceasefire holds" -> contract "US-Iran agreement by May"
      (ceasefire holding is necessary but not sufficient for full agreement)
    
    LOOSE_PROXY: Contract resolves on a loosely correlated proposition.
      Example: model predicts "Hormuz reopens" -> contract "US-Iran agreement by May"
      (Hormuz reopening is one possible outcome of many in an agreement)
    
    NONE: No meaningful mapping exists. Do not trade.
    """
    DIRECT = "direct"
    NEAR_PROXY = "near_proxy"
    LOOSE_PROXY = "loose_proxy"
    NONE = "none"


class ContractRecord(BaseModel):
    """A prediction market contract with resolution criteria."""
    
    ticker: str                    # e.g., "KXUSAIRANAGREEMENT-27-26MAY"
    source: str                    # "kalshi" or "polymarket"
    event_ticker: str              # e.g., "KXUSAIRANAGREEMENT-27" (Kalshi event grouping)
    title: str                     # Natural language: "Will US and Iran reach agreement by May 2026?"
    resolution_criteria: str       # Exact: "Resolves YES if official agreement announced by May 31, 2026 23:59 ET"
    resolution_date: datetime | None  # When contract resolves
    
    # Proxy classification per model type
    proxy_map: dict[str, ProxyClass]  # {"ceasefire": "near_proxy", "hormuz_reopening": "loose_proxy", "oil_price": "none"}
    
    # Confidence discount factors per proxy class
    # Applied multiplicatively: effective_edge = raw_edge * discount
    discount_map: dict[str, float]    # {"direct": 1.0, "near_proxy": 0.6, "loose_proxy": 0.3}
    
    # Market metadata
    is_active: bool = True
    last_checked: datetime | None = None


class MappingResult(BaseModel):
    """Result of mapping a prediction to a contract."""
    
    prediction_model_id: str       # "ceasefire", "oil_price", "hormuz_reopening"
    contract_ticker: str
    proxy_class: ProxyClass
    raw_edge: float                # model_prob - market_prob before discount
    confidence_discount: float     # multiplier from proxy class
    effective_edge: float          # raw_edge * confidence_discount
    should_trade: bool             # False if proxy_class == NONE or effective_edge < threshold
    reason: str                    # Human-readable explanation of mapping decision
```

### Pattern 2: Mapping Policy as Explicit Decision Logic

**What:** Replaces the heuristic `_map_predictions_to_markets()` with a structured policy that:
1. Looks up all active contracts from the registry
2. For each prediction, finds contracts with proxy_class != NONE
3. Applies confidence discount based on proxy class
4. Refuses trades when effective_edge falls below threshold
5. Logs every decision (including refusals) for audit

**Why this matters:** The current code maps ceasefire -> KXUSAIRANAGREEMENT without acknowledging these are different propositions. A ceasefire holding != a formal US-Iran agreement. The model could be 100% right about ceasefire but lose money because the agreement contract resolves on different criteria.

**Decision logic:**

```python
# Source: Designed from analysis of existing _map_predictions_to_markets() weaknesses

class MappingPolicy:
    """Decides whether and how to map a prediction to a contract."""
    
    # Default discount factors -- conservative
    DEFAULT_DISCOUNTS = {
        ProxyClass.DIRECT: 1.0,       # Full confidence
        ProxyClass.NEAR_PROXY: 0.6,   # 40% haircut
        ProxyClass.LOOSE_PROXY: 0.3,  # 70% haircut
        ProxyClass.NONE: 0.0,         # Never trade
    }
    
    def __init__(
        self,
        registry: "ContractRegistry",
        min_effective_edge_pct: float = 5.0,  # Minimum edge after discount
        max_loose_proxy_trades: int = 1,       # Limit loose proxy exposure
    ) -> None:
        self._registry = registry
        self._min_edge = min_effective_edge_pct / 100.0
        self._max_loose = max_loose_proxy_trades
    
    def evaluate(
        self,
        prediction: "PredictionOutput",
        market_prices: list["MarketPrice"],
    ) -> list[MappingResult]:
        """Evaluate all possible contract mappings for a prediction.
        
        Returns ALL evaluated mappings (including rejected ones) for audit.
        Only mappings with should_trade=True are actionable.
        """
        results = []
        # ... for each contract in registry matching this model type ...
        # ... compute raw_edge, apply discount, decide should_trade ...
        return results
```

### Pattern 3: Evaluation Ledger as Append-Only Signal Log

**What:** Every signal the system generates gets a permanent record with full provenance: what the model claimed, which contract it mapped to, what proxy class, what the market price was at entry, and eventually what happened (resolution + realized P&L).

**Why:** This is the foundation for calibration analysis ("are we actually good at this?"), hit-rate computation, and proxy quality assessment ("do near-proxy trades actually make money?").

```python
# Source: Extension of existing TradeRecord + Divergence models

class SignalRecord(BaseModel):
    """Immutable record of a signal event -- the evaluation ledger entry."""
    
    signal_id: str                    # UUID
    created_at: datetime
    
    # Model claim (what the model said)
    model_id: str                     # "ceasefire", "oil_price", "hormuz_reopening"
    model_claim: str                  # Natural language: "Ceasefire holds with 62% probability over 14d"
    model_probability: float          # 0.62
    model_timeframe: str              # "14d"
    model_reasoning: str              # Full reasoning chain
    
    # Contract mapping (what we traded)
    contract_ticker: str              # "KXUSAIRANAGREEMENT-27-26MAY"
    contract_title: str               # "Will US and Iran reach agreement by May 2026?"
    proxy_class: str                  # "near_proxy"
    confidence_discount: float        # 0.6
    
    # Market state at signal time
    market_yes_price: float           # 0.48
    market_no_price: float            # 0.52
    market_volume: float              # 8500
    raw_edge: float                   # 0.14 (model 0.62 - market 0.48)
    effective_edge: float             # 0.084 (0.14 * 0.6 discount)
    signal: str                       # "BUY_YES" / "BUY_NO" / "HOLD"
    
    # Trade execution (filled after trade)
    trade_id: str | None = None       # Links to paper_trades table
    traded: bool = False              # Whether we actually traded
    trade_refused_reason: str | None = None  # Why we didn't trade
    
    # Resolution (filled when contract resolves)
    resolution_price: float | None = None     # 1.0 (YES) or 0.0 (NO)
    resolved_at: datetime | None = None
    realized_pnl: float | None = None
    model_was_correct: bool | None = None     # Did the model's claim match reality?
    proxy_was_aligned: bool | None = None     # Did the proxy contract track the model's claim?
```

### Anti-Patterns to Avoid

- **Probability-as-identity mapping:** The current code treats `pred.probability` as directly comparable to `market.yes_price` even when they answer different questions. A model probability of "62% ceasefire holds" is NOT the same as a market price of "48% US-Iran agreement" even though both are floats between 0 and 1. The proxy class and discount exist to handle this. [VERIFIED: brief.py lines 311-317 show direct probability substitution]

- **Mutating prediction objects:** The current `_map_predictions_to_markets()` mutates `pred.kalshi_ticker` and `pred.probability` in place. This destroys the model's original claim. The new pattern should produce MappingResult objects without mutating PredictionOutput. [VERIFIED: brief.py lines 259-317]

- **Hardcoded ticker prefixes:** The current code splits on "-" and matches by prefix (e.g., "KXUSAIRANAGREEMENT"). This breaks when Kalshi changes ticker naming conventions. The registry should store full tickers with event grouping metadata. [VERIFIED: brief.py lines 252-256]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| UUID generation | Custom ID scheme | `uuid.uuid4()` | Already used in TradeRecord [VERIFIED: scoring/tracker.py] |
| Time handling | String timestamps | `datetime` with UTC timezone | Already used everywhere in codebase [VERIFIED: all schemas] |
| Data validation | Manual checks | Pydantic validators | Already the pattern for all models [VERIFIED: schemas.py] |
| DB writes | Direct DuckDB calls | `DbWriter.enqueue()` | Existing async single-writer queue [VERIFIED: db/writer.py] |
| Probability clamping | Manual bounds checking | Existing `clamp_probability` validator | Already on PredictionOutput and MarketPrice [VERIFIED: prediction/schemas.py] |

**Key insight:** Everything needed for these three components already exists in the stack. The problem is structural (missing data model + missing decision logic), not a missing library.

## Common Pitfalls

### Pitfall 1: Proposition Mismatch Blindness

**What goes wrong:** Model predicts "ceasefire holds with P=0.62" and trades on "US-Iran agreement by May" at P=0.48. The ceasefire holds but no formal agreement materializes. Model was "right" but loses money.

**Why it happens:** No formal representation of the semantic gap between model claims and contract resolution criteria.

**How to avoid:** The ProxyClass enum + confidence discount is the minimum viable solution. Every contract in the registry must have explicit proxy classifications per model type. The mapping policy must refuse to trade when proxy_class is NONE and must discount edge for non-DIRECT mappings.

**Warning signs:** Win rate on NEAR_PROXY trades is lower than on DIRECT trades. If much lower, the discount factor is too generous.

### Pitfall 2: Oil Price Direction-to-Threshold Translation

**What goes wrong:** The current code (brief.py lines 311-317) translates oil price direction predictions into threshold probabilities with a naive formula: `P(WTI hits $120) = confidence` for increase, `1 - confidence` for decrease. This ignores magnitude -- a model predicting $3-8 increase from $92 baseline gives a VERY different probability of hitting $120 vs $100.

**Why it happens:** Oil price predictions are fundamentally different from binary event predictions. They have direction AND magnitude, but Kalshi contracts are binary thresholds.

**How to avoid:** The contract registry should store the threshold value (e.g., $120) as structured metadata. The mapping policy should translate magnitude_range into threshold probability explicitly: if model predicts $92 + [$3, $8] increase, P(reaching $120) is much lower than P(reaching $100). This is a probability distribution question, not a simple confidence flip.

**Warning signs:** Oil price trades consistently lose despite correct direction predictions.

### Pitfall 3: Stale Contract Data

**What goes wrong:** Contracts expire, new ones appear, resolution dates pass. If the registry isn't refreshed, the system maps to expired contracts.

**Why it happens:** Prediction markets are dynamic -- contracts open and close frequently.

**How to avoid:** The registry should be refreshed at the start of each pipeline run (already fetching from Kalshi/Polymarket APIs). Add an `is_active` flag and `last_checked` timestamp. The mapping policy should only consider active contracts.

**Warning signs:** API errors when trying to trade on expired tickers.

### Pitfall 4: Evaluation Without Resolution Ground Truth

**What goes wrong:** Building a beautiful evaluation ledger but never populating the resolution fields because nobody checks contract outcomes.

**Why it happens:** Resolution checking requires periodic polling of Kalshi API after contract closes.

**How to avoid:** Add a `check_resolutions()` method that polls the API for settled contracts and backfills ledger entries. The existing `PaperTradeTracker.check_resolutions()` pattern can be extended.

**Warning signs:** Ledger has many open entries and no resolved ones after weeks of running.

### Pitfall 5: Conflating Proxy Quality with Model Quality

**What goes wrong:** Blaming the model when a LOOSE_PROXY trade loses, or crediting the model when a LOOSE_PROXY trade wins by luck.

**Why it happens:** Not segmenting evaluation metrics by proxy class.

**How to avoid:** The evaluation ledger includes `proxy_class` on every record. All calibration analysis MUST be segmented: "model hit rate on DIRECT trades" vs "model hit rate on NEAR_PROXY trades" vs overall. The `model_was_correct` and `proxy_was_aligned` fields capture this distinction.

## Code Examples

### DuckDB Schema for Contract Registry

```sql
-- Source: Designed to complement existing schema.py tables
-- [VERIFIED: DuckDB 1.2+ supports these types per existing schema.py]

CREATE TABLE IF NOT EXISTS contract_registry (
    ticker VARCHAR PRIMARY KEY,
    source VARCHAR NOT NULL,           -- "kalshi" or "polymarket"
    event_ticker VARCHAR NOT NULL,     -- Kalshi event grouping
    title VARCHAR NOT NULL,            -- Natural language title
    resolution_criteria TEXT NOT NULL,  -- Exact resolution language
    resolution_date TIMESTAMP,
    is_active BOOLEAN DEFAULT true,
    last_checked TIMESTAMP,
    metadata JSON                      -- Flexible: threshold values, etc.
);

CREATE TABLE IF NOT EXISTS contract_proxy_map (
    ticker VARCHAR NOT NULL,
    model_type VARCHAR NOT NULL,        -- "ceasefire", "oil_price", "hormuz_reopening"
    proxy_class VARCHAR NOT NULL,       -- "direct", "near_proxy", "loose_proxy", "none"
    confidence_discount DOUBLE NOT NULL DEFAULT 1.0,
    notes TEXT,                         -- Why this classification
    PRIMARY KEY (ticker, model_type),
    FOREIGN KEY (ticker) REFERENCES contract_registry(ticker)
);

CREATE TABLE IF NOT EXISTS signal_ledger (
    signal_id VARCHAR PRIMARY KEY,
    created_at TIMESTAMP NOT NULL,
    
    -- Model claim
    model_id VARCHAR NOT NULL,
    model_claim TEXT NOT NULL,
    model_probability DOUBLE NOT NULL,
    model_timeframe VARCHAR NOT NULL,
    model_reasoning TEXT,
    
    -- Contract mapping
    contract_ticker VARCHAR NOT NULL,
    contract_title VARCHAR,
    proxy_class VARCHAR NOT NULL,
    confidence_discount DOUBLE NOT NULL,
    
    -- Market state at signal time
    market_yes_price DOUBLE NOT NULL,
    market_no_price DOUBLE NOT NULL,
    market_volume DOUBLE,
    raw_edge DOUBLE NOT NULL,
    effective_edge DOUBLE NOT NULL,
    signal VARCHAR NOT NULL,           -- BUY_YES / BUY_NO / HOLD / REFUSED
    
    -- Trade execution
    trade_id VARCHAR,                  -- FK to paper_trades
    traded BOOLEAN DEFAULT false,
    trade_refused_reason TEXT,
    
    -- Resolution
    resolution_price DOUBLE,
    resolved_at TIMESTAMP,
    realized_pnl DOUBLE,
    model_was_correct BOOLEAN,
    proxy_was_aligned BOOLEAN
);
```

### Seed Data: Initial Contract Registry

```python
# Source: Derived from IRAN_EVENT_TICKERS in kalshi.py [VERIFIED: kalshi.py lines 24-37]
# These are the known Kalshi event tickers the system already tracks

INITIAL_CONTRACTS = [
    {
        "event_ticker": "KXUSAIRANAGREEMENT-27",
        "source": "kalshi",
        "title": "US-Iran Agreement",
        "proxy_map": {
            "ceasefire": ProxyClass.NEAR_PROXY,        # Ceasefire is necessary but not sufficient
            "hormuz_reopening": ProxyClass.LOOSE_PROXY, # Agreement might include Hormuz but not guaranteed
            "oil_price": ProxyClass.NONE,               # Agreement doesn't directly resolve oil price
        },
    },
    {
        "event_ticker": "KXCLOSEHORMUZ-27JAN",
        "source": "kalshi",
        "title": "Strait of Hormuz Closure",
        "proxy_map": {
            "hormuz_reopening": ProxyClass.DIRECT,      # Directly answers the question (inverted)
            "oil_price": ProxyClass.NEAR_PROXY,          # Hormuz status strongly affects oil prices
            "ceasefire": ProxyClass.LOOSE_PROXY,         # Ceasefire might lead to Hormuz changes
        },
    },
    {
        "event_ticker": "KXWTIMAX-26DEC31",
        "source": "kalshi",
        "title": "WTI Oil Price Maximum by Year End",
        "proxy_map": {
            "oil_price": ProxyClass.NEAR_PROXY,          # Direction maps to threshold, not DIRECT
            "hormuz_reopening": ProxyClass.LOOSE_PROXY,  # Hormuz reopening affects oil prices
            "ceasefire": ProxyClass.NONE,                # Ceasefire has weak direct oil link
        },
    },
    {
        "event_ticker": "KXWTIMIN-26DEC31",
        "source": "kalshi",
        "title": "WTI Oil Price Minimum by Year End",
        "proxy_map": {
            "oil_price": ProxyClass.NEAR_PROXY,
            "hormuz_reopening": ProxyClass.LOOSE_PROXY,
            "ceasefire": ProxyClass.NONE,
        },
    },
]
```

### Calibration Query Examples

```sql
-- Source: Standard calibration analysis pattern [ASSUMED]

-- Hit rate by proxy class
SELECT 
    proxy_class,
    COUNT(*) as total_signals,
    COUNT(CASE WHEN traded THEN 1 END) as traded_count,
    COUNT(CASE WHEN realized_pnl > 0 THEN 1 END) as wins,
    COUNT(CASE WHEN realized_pnl < 0 THEN 1 END) as losses,
    AVG(realized_pnl) as avg_pnl,
    SUM(realized_pnl) as total_pnl,
    AVG(CASE WHEN model_was_correct THEN 1.0 ELSE 0.0 END) as model_accuracy,
    AVG(CASE WHEN proxy_was_aligned THEN 1.0 ELSE 0.0 END) as proxy_alignment
FROM signal_ledger
WHERE resolved_at IS NOT NULL
GROUP BY proxy_class;

-- Model calibration curve (are 70% predictions right 70% of the time?)
SELECT 
    ROUND(model_probability * 10) / 10 as prob_bucket,
    COUNT(*) as n,
    AVG(CASE WHEN model_was_correct THEN 1.0 ELSE 0.0 END) as actual_rate,
    AVG(model_probability) as predicted_rate
FROM signal_ledger
WHERE resolved_at IS NOT NULL AND proxy_class = 'direct'
GROUP BY prob_bucket
ORDER BY prob_bucket;

-- Edge decay: does entry edge predict P&L?
SELECT
    CASE 
        WHEN effective_edge > 0.15 THEN 'strong'
        WHEN effective_edge > 0.10 THEN 'moderate'
        WHEN effective_edge > 0.05 THEN 'weak'
    END as edge_bucket,
    AVG(realized_pnl) as avg_pnl,
    COUNT(*) as n
FROM signal_ledger
WHERE traded AND resolved_at IS NOT NULL
GROUP BY edge_bucket;
```

### Integration Point: Replacing _map_predictions_to_markets()

```python
# Source: Designed to replace brief.py lines 239-319 [VERIFIED: codebase analysis]

# BEFORE (current -- heuristic, mutates predictions):
predictions = _map_predictions_to_markets(predictions, market_prices)
detector = DivergenceDetector(min_edge_pct=5.0)
divergences = detector.detect(predictions, market_prices)

# AFTER (proposed -- structured, non-mutating):
policy = MappingPolicy(registry=contract_registry, min_effective_edge_pct=5.0)
signals: list[SignalRecord] = []

for pred in predictions:
    mappings = policy.evaluate(pred, market_prices)
    for mapping in mappings:
        signal = ledger.record_signal(pred, mapping)
        signals.append(signal)

# Only trade signals that passed the policy
actionable = [s for s in signals if s.traded == False and s.signal in ("BUY_YES", "BUY_NO")]
```

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Default discount factors (DIRECT=1.0, NEAR_PROXY=0.6, LOOSE_PROXY=0.3) are reasonable starting points | Architecture Patterns | Could over/under-trade on proxy contracts. Calibrate with data after first runs. |
| A2 | Calibration query patterns are standard SQL analytics | Code Examples | Low risk -- DuckDB SQL is well-documented |
| A3 | KXUSAIRANAGREEMENT is NEAR_PROXY for ceasefire (not DIRECT) | Seed Data | If Kalshi's resolution criteria actually match ceasefire holding, this should be DIRECT. Must verify exact resolution language from Kalshi. |
| A4 | Oil price model's magnitude_range can be translated to threshold probability | Pitfall 2 | If the model doesn't output a distribution, this translation is still heuristic. But it's better than the current `1 - confidence` approach. |
| A5 | Separating contract_proxy_map into its own table (vs JSON in contract_registry) is better for query performance | DuckDB Schema | DuckDB handles JSON well, but normalized tables are easier to update per-model-type. Either works. |

## Open Questions (RESOLVED)

1. **Exact Kalshi resolution criteria** — RESOLVED: Store `resolution_criteria` verbatim from Kalshi API `/markets/{ticker}` response. Seed data uses placeholder strings; fetched on first live run.
   - What we know: Event tickers from `kalshi.py` (KXUSAIRANAGREEMENT, KXCLOSEHORMUZ, etc.)
   - Decision: Fetch from Kalshi API at registry initialization time. The `/markets/{ticker}` endpoint returns a `rules` field with resolution criteria. Store verbatim.

2. **How to handle inverted contracts** — RESOLVED: `invert_probability: bool` field added to `contract_proxy_map` table and `ContractRecord` model. MappingPolicy applies `1 - model_probability` when True.
   - What we know: KXCLOSEHORMUZ resolves YES if Hormuz IS closed. The model predicts reopening probability.
   - Decision: Add an `invert_probability: bool` field to the proxy_map. When True, the effective model probability is `1 - model_probability` before comparison.

3. **Polymarket integration specificity** — RESOLVED: Deferred to Phase 5. Phase 1 covers Kalshi only. Discovered Polymarket markets default to LOOSE_PROXY with `needs_classification: bool` flag.
   - What we know: Polymarket client searches by keyword ("Iran", "Hormuz") and returns condition_id/slug-based tickers.
   - Decision: For v1, manually classify known Polymarket Iran markets. For discovered markets, default to LOOSE_PROXY.

4. **When to refresh the registry** — RESOLVED: Seed with INITIAL_CONTRACTS on first run. Each pipeline run merges with live API data: new tickers get `needs_classification=true`, missing tickers marked inactive.
   - What we know: Each pipeline run already fetches live market data.
   - Decision: Seed with INITIAL_CONTRACTS on first run. On each pipeline run, merge with live API data.

## Sources

### Primary (HIGH confidence)
- `backend/src/parallax/cli/brief.py` -- Current mapping logic analyzed line by line
- `backend/src/parallax/markets/kalshi.py` -- IRAN_EVENT_TICKERS, KalshiClient API
- `backend/src/parallax/markets/schemas.py` -- MarketPrice, PaperTrade models
- `backend/src/parallax/prediction/schemas.py` -- PredictionOutput model
- `backend/src/parallax/divergence/detector.py` -- DivergenceDetector logic
- `backend/src/parallax/scoring/tracker.py` -- TradeRecord, PaperTradeTracker
- `backend/src/parallax/db/schema.py` -- Existing DuckDB tables (12 tables)
- `backend/src/parallax/prediction/oil_price.py` -- Oil price model output structure
- `backend/src/parallax/prediction/ceasefire.py` -- Ceasefire model output structure
- `backend/src/parallax/prediction/hormuz.py` -- Hormuz model output structure

### Secondary (MEDIUM confidence)
- DuckDB documentation for SQL syntax and JSON handling [ASSUMED: based on existing schema patterns]

### Tertiary (LOW confidence)
- None -- all findings derived from codebase analysis

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new dependencies, fully understood existing stack
- Architecture (data models): HIGH -- derived directly from existing Pydantic models and gaps
- Architecture (discount factors): MEDIUM -- starting values are heuristic, need calibration data
- Pitfalls: HIGH -- each pitfall identified from specific code patterns in the codebase
- Proxy classifications: MEDIUM -- need to verify Kalshi exact resolution criteria

**Research date:** 2026-04-08
**Valid until:** 2026-05-08 (stable domain, unlikely to change)
