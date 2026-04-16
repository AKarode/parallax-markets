# Phase 10: Prompt Fixes + Dependency Cleanup - Research

**Researched:** 2026-04-12
**Domain:** LLM prompt engineering, cascade computation, Python dependency management
**Confidence:** HIGH

## Summary

Phase 10 addresses 5 prompt-quality bugs and 1 dependency cleanup task. All changes are within the existing Python backend -- no new libraries, no new services, no architectural changes. The codebase is well-structured with 3 identical predictor patterns, making prompt template changes systematic.

The highest-impact fix is anchoring removal (PROMPT-01): all 3 model prompts currently receive market prices before generating probability estimates, which biases model outputs toward market consensus. The most technically interesting fix is bypass_flow (PROMPT-02): the cascade engine has a working `activate_bypass()` method that is simply never called in the oil price predictor. The Hormuz dual-probability fix (PROMPT-03) and editorial stripping (PROMPT-05) are straightforward text edits. The track record guard (PROMPT-04) is a 5-line change to an existing function.

**Primary recommendation:** Work through the 6 requirements in dependency order -- anchoring removal first (touches all 3 predictors + brief.py + crisis_context.py), then the three independent fixes (bypass, Hormuz, track record), then editorial cleanup, then dead deps last.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Remove `{market_prices_text}` from all 3 model prompt templates (oil_price.py, ceasefire.py, hormuz.py). Models must never see current market prices before stating their probability estimate.
- **D-02:** Remove the "Prediction Market Contract Context" section's price data from crisis_context.py (e.g., "~48% YES", "~42%", "$200M+ wagered"). Keep contract resolution criteria (what YES/NO means).
- **D-03:** Historical price mentions in the dated timeline (e.g., "Brent surged to $120") stay -- these are factual event markers, not current anchors.
- **D-04:** Hormuz model outputs ONE probability: likelihood of partial reopening (>25% of pre-war commercial shipping flow restored) within 14 days.
- **D-05:** Remove the dual "(a) partial / (b) full" specification from the prompt. Full reopening prediction is deferred to Phase 13's political model.
- **D-06:** The existing `invert_probability` mapping in the contract registry continues to handle the inversion from "reopening probability" to "closure contract" pricing.
- **D-07:** Remove "What The Market May Be Missing" section entirely from crisis_context.py -- models must form their own hypotheses from facts.
- **D-08:** Remove "Key risks" and "Key opportunities" bullets from "Current Market State" section -- these are analyst opinions, not facts.
- **D-09:** Keep factual current status lines (Hormuz closed, ceasefire fragile, days remaining) and contract resolution criteria (what contracts resolve on). Models know WHAT they're predicting against without editorial guidance.
- **D-10:** Keep "Current Market State" header with only factual status bullets (no prices, no opinions).

### Claude's Discretion
- Bypass flow fix (PROMPT-02): technical investigation -- read cascade engine, determine why bypass_flow is 0 when blockade conditions exist, fix the computation.
- Track record guard (PROMPT-04): straightforward -- add n>=10 check in `build_track_record()`, return fallback text below threshold.
- Dead dependency removal (ARCH-04): remove h3, sentence-transformers, searoute, shapely, google-cloud-bigquery, websockets from pyproject.toml.

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PROMPT-01 | All prediction model prompts produce probabilities without seeing current market prices | Anchoring removal pattern documented -- remove `{market_prices_text}` from 3 prompt templates, remove `market_prices` kwarg from 3 predictor `predict()` signatures, remove `market_context` building in brief.py, strip price data from crisis_context.py contract section |
| PROMPT-02 | Oil price model receives computed bypass flow from cascade engine (not hardcoded 0) | Root cause identified -- `activate_bypass()` exists but is never called in oil_price.py. Fix: call it after supply_loss loop. Secondary issue: WorldState constructed empty in brief.py needs initialization |
| PROMPT-03 | Hormuz model outputs a single well-defined probability matching one contract resolution criterion | Prompt template edit -- remove dual "(a) partial / (b) full" spec, define single criterion: >25% flow restored within 14d |
| PROMPT-04 | Track record injection requires minimum sample size (n>=10) before showing hit rate statistics | Guard pattern documented -- add total<10 check after aggregate query in `build_track_record()` |
| PROMPT-05 | Crisis context separates verifiable facts from editorial hypotheses -- models receive facts only | Editorial sections identified -- remove "What The Market May Be Missing" block and "Key risks"/"Key opportunities" bullets from crisis_context.py |
| ARCH-04 | Dead dependencies removed from pyproject.toml | 6 dead deps identified in pyproject.toml: h3, sentence-transformers, searoute, shapely, google-cloud-bigquery, websockets |
</phase_requirements>

## Architecture Patterns

### Predictor Pattern (All 3 Models Follow This)
Each predictor follows an identical pattern that makes systematic changes straightforward: [VERIFIED: codebase inspection]

```
class XxxPredictor:
    async def predict(self, ..., market_prices=None, db_conn=None) -> PredictionOutput:
        # 1. Build track record from db_conn
        track_record = build_track_record(model_id, db_conn)
        # 2. Compute model-specific inputs (cascade for oil/hormuz, filtering for ceasefire)
        # 3. Format prompt: get_crisis_context() + SYSTEM_PROMPT.format(...)
        # 4. Call Claude Sonnet via self._client.messages.create()
        # 5. Parse JSON response
        # 6. Return PredictionOutput
```

### Files Requiring Changes (Complete Inventory)

| File | Changes | Scope |
|------|---------|-------|
| `prediction/oil_price.py` | Remove `{market_prices_text}` from prompt, remove `market_prices` param, remove `_format_market_prices()`, call `activate_bypass()` | PROMPT-01, PROMPT-02 |
| `prediction/ceasefire.py` | Remove `{market_prices_text}` from prompt, remove `market_prices` param, remove `_format_market_prices()` | PROMPT-01 |
| `prediction/hormuz.py` | Remove `{market_prices_text}` from prompt, remove `market_prices` param, remove `_format_market_prices()`, rewrite prompt to single-probability spec | PROMPT-01, PROMPT-03 |
| `prediction/crisis_context.py` | Strip price data from contract context, remove editorial sections | PROMPT-01 (D-02), PROMPT-05 (D-07, D-08, D-09, D-10) |
| `scoring/track_record.py` | Add n>=10 guard after aggregate query | PROMPT-04 |
| `cli/brief.py` | Remove `market_context` dict building and `market_prices=` kwarg from all 3 predict calls | PROMPT-01 |
| `backtest/engine.py` | Remove `market_prices=market_context` from all 3 predict calls (lines 212-214) | PROMPT-01 (consistency) |
| `pyproject.toml` | Remove 6 dead dependencies | ARCH-04 |

### Anti-Patterns to Avoid
- **Partial anchoring removal:** Removing `{market_prices_text}` from prompt templates but leaving the parameter wiring in brief.py. Both must be removed or a future contributor will re-add it to prompts. [VERIFIED: codebase shows `market_context` built at brief.py:481-490]
- **Leaving `_format_market_prices()` as dead code:** Each predictor has a static method that will be unused after PROMPT-01. Remove to prevent confusion.
- **Modifying PredictionOutput schema:** The schema is correct as-is. Single probability field, already used by all 3 models.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Bypass flow computation | Custom formula in oil_price.py | `CascadeEngine.activate_bypass(supply_loss)` | Already exists, parameterized from scenario config, tested |

## Common Pitfalls

### Pitfall 1: bypass_flow Root Cause Is TWO Bugs, Not One
**What goes wrong:** Fixing only the missing `activate_bypass()` call while leaving WorldState empty.
**Why it happens:** `brief.py` line 473 creates `WorldState()` with zero cells. The oil_price predictor's `_iter_cells()` loop finds nothing, so `supply_loss=0`, so even a properly-called `activate_bypass(0)` returns `bypass_flow=0`.
**How to avoid:** Two fixes needed: (1) call `activate_bypass()` in oil_price.py after the supply_loss loop, (2) initialize WorldState with Hormuz blockade cells in brief.py before passing to predictors.
**Warning signs:** After fix, run with `--verbose` and check that `supply_loss > 0` and `bypass_flow > 0` in logs. [VERIFIED: codebase inspection of oil_price.py:91-108 and brief.py:473]

### Pitfall 2: Backtest Engine Also Passes market_prices
**What goes wrong:** Fixing anchoring in brief.py but leaving `backtest/engine.py` lines 212-214 still passing `market_prices=market_context` to predictors.
**Why it happens:** Backtest engine was copied from brief.py and has the same market_prices wiring.
**How to avoid:** Search for all callers of `.predict()` across the codebase. Currently: `brief.py` (lines 496-498) and `backtest/engine.py` (lines 212-214). Both need the same fix.
**Warning signs:** Grep for `market_prices=market_context` -- should return 0 results after fix. [VERIFIED: codebase grep shows both call sites]

### Pitfall 3: Crisis Context Contract Section -- Keep Resolution Criteria
**What goes wrong:** Removing the entire "Prediction Market Contract Context" section when only prices/volumes should be stripped.
**Why it happens:** The section mixes factual resolution criteria ("Resolves YES if...") with current prices ("~48% YES") and volume ("$200M+ wagered").
**How to avoid:** Per D-02 and D-09: keep contract ticker names and resolution criteria. Remove: percentage prices, dollar volumes, editorialized probability descriptions. The rewritten section should look like:
```
### Prediction Market Contracts
- **KXUSAIRANAGREEMENT**: "Will the US and Iran reach a formal agreement?" Resolves YES on SIGNED DEAL.
- **KXCLOSEHORMUZ**: "Will Iran close Strait of Hormuz for 7+ days?" Already settled YES.
- **KXWTIMAX/KXWTIMIN**: Oil price range contracts.
```
[VERIFIED: crisis_context.py lines 106-116 contain the mixed section]

### Pitfall 4: Hormuz Prompt Still Mentions Full Reopening in Scenario Analysis
**What goes wrong:** Removing the dual "(a)/(b)" probability spec but leaving the 25/50/100% scenario analysis in the prompt, which implicitly asks about full reopening.
**Why it happens:** The `recovery_25`, `recovery_50`, `recovery_100` cascade scenarios are computed and injected into the prompt (hormuz.py lines 97-99, 30-32).
**How to avoid:** Keep the scenario analysis for context (it shows sensitivity), but reframe the prompt instruction to be clear: "Using these scenarios as background, estimate ONE probability: the likelihood of partial reopening (>25% of pre-war commercial shipping flow restored) within 14 days." The scenarios provide analytical context; the output spec must request exactly one probability.
[VERIFIED: hormuz.py prompt template lines 23-56]

### Pitfall 5: Test Suite Expects market_prices Parameter
**What goes wrong:** Tests pass after removing market_prices from prompts but break subtly because test fixtures still pass the parameter.
**Why it happens:** `test_prediction.py` calls `predict()` without `market_prices` already (it is optional with default `None`), so tests will not break. But `test_brief.py` may construct market_context.
**How to avoid:** After removing the parameter, run the full test suite. Check `test_brief.py` for `market_context` or `market_prices` usage in predict calls.
[VERIFIED: test_prediction.py does not pass market_prices; needs verification for test_brief.py]

## Code Examples

### PROMPT-01: Anchoring Removal Pattern (oil_price.py)

Before (current):
```python
# oil_price.py prompt template (line 37-38)
Current market prices:
{market_prices_text}
```

After:
```python
# Remove these 2 lines entirely from the prompt template string
# Remove the market_prices_text=... from .format() call
# Remove market_prices parameter from predict() signature
# Remove _format_market_prices() static method
```
[VERIFIED: oil_price.py lines 37-38, 74, 126, 215-223]

### PROMPT-02: Bypass Flow Fix (oil_price.py)

Before (current, broken):
```python
# oil_price.py lines 91-108
supply_loss = 0.0
bypass_flow = 0.0  # <-- Never updated!
price_shock_pct = 0.0

for cell_id, cell_data in self._iter_cells(world_state):
    if cell_data.get("status") in ("blocked", "restricted"):
        result = self._cascade.apply_blockade(world_state, cell_id, 0.5)
        supply_loss += result.get("supply_loss", 0.0)

if supply_loss > 0:
    current_price = self._get_current_brent(current_prices)
    new_price = self._cascade.compute_price_shock(
        current_price, supply_loss, bypass_flow,  # bypass_flow is always 0!
    )
```

After (fixed):
```python
supply_loss = 0.0
price_shock_pct = 0.0

for cell_id, cell_data in self._iter_cells(world_state):
    if cell_data.get("status") in ("blocked", "restricted"):
        result = self._cascade.apply_blockade(world_state, cell_id, 0.5)
        supply_loss += result.get("supply_loss", 0.0)

# Compute bypass flow from cascade engine (was missing -- bug fix)
bypass_result = self._cascade.activate_bypass(supply_loss)
bypass_flow = bypass_result["bypass_flow"]

if supply_loss > 0:
    current_price = self._get_current_brent(current_prices)
    new_price = self._cascade.compute_price_shock(
        current_price, supply_loss, bypass_flow,  # Now uses computed value
    )
```
[VERIFIED: cascade.py `activate_bypass()` method at line 73, returns `{"bypass_flow": float}`]

### PROMPT-02: WorldState Initialization (brief.py)

Before (current, empty world state):
```python
# brief.py line 473
world_state = WorldState()
# ... passed empty to oil_pred.predict() and hormuz_pred.predict()
```

After (initialized with current blockade conditions):
```python
world_state = WorldState()
# Initialize Hormuz cells with current blockade status
# These values represent the current state of the strait
world_state.update_cell(
    cell_id=1,  # Hormuz primary shipping lane
    flow=2_000_000,  # Trickle flow (~10% of pre-war 20M bbl/day)
    status="blocked",
    threat_level=0.9,
)
```
[VERIFIED: WorldState.update_cell() signature at world_state.py lines 37-56]

### PROMPT-04: Track Record Guard

Before (current):
```python
# track_record.py lines 46-48
if row is None or row[0] == 0:
    return _NO_DATA_TEXT

total = int(row[0])
```

After (with n>=10 guard):
```python
if row is None or row[0] == 0:
    return _NO_DATA_TEXT

total = int(row[0])
if total < 10:
    return f"Track record: {total} resolved signal(s) -- too few for reliable statistics (minimum 10 required)."
```
[VERIFIED: track_record.py lines 33-54, requirement specifies n>=10 threshold]

### PROMPT-05: Editorial Stripping from crisis_context.py

Sections to remove entirely:
```python
# Lines 117-125: "### What The Market May Be Missing" (D-07)
### What The Market May Be Missing
- Pakistan talks produced no agreement after 21 hours...
- Hormuz "reopening" is theater...
- ...
```

Lines to remove from "### Current Market State":
```python
# Lines 100-103: Remove "Key risks" and "Key opportunities" bullets (D-08)
- **Key risks:** Ceasefire collapse if no deal by Apr 21...
- **Key opportunities:** If formal agreement reached...
```

Lines to keep in "### Current Market State" (D-09, D-10):
```python
### Current Market State (as of Apr 12, 2026)
- **Strait of Hormuz: effectively closed.** Iran charging tolls, limiting traffic to a trickle.
- **Ceasefire: fragile, 10 days remaining.** No formal agreement. Talks ongoing but stalled.
```

Lines to rewrite in "### Prediction Market Contract Context" (D-02):
```python
# Remove: "Currently ~48% YES", "~42%", "$200M+ wagered", "$3.16M"
# Keep: ticker names, "Resolves YES if..." criteria
### Prediction Market Contracts
- **KXUSAIRANAGREEMENT**: Resolves YES if US and Iran reach a formal agreement (signed deal, not just ceasefire).
- **KXCLOSEHORMUZ**: Resolves YES if Strait of Hormuz closed for 7+ days. Already settled YES.
- **KXWTIMAX/KXWTIMIN**: Oil price range contracts. WTI max/min thresholds.
```
[VERIFIED: crisis_context.py lines 94-125]

### ARCH-04: Dead Dependency Removal

```toml
# pyproject.toml -- remove these 6 lines from dependencies:
"h3>=4.1",                         # Was for H3 hex grid -- now frontend-only
"sentence-transformers>=3.4",      # Was for embeddings -- never used in pipeline
"searoute>=1.3",                   # Was for sea route calc -- replaced by static config
"shapely>=2.0",                    # Was for geometry ops -- no current users
"google-cloud-bigquery>=3.27",     # Was for BigQuery -- replaced by DuckDB
"websockets>=14.0",                # Uvicorn has its own WS support
```
[VERIFIED: pyproject.toml lines 9, 13-16, 18. No imports of h3, sentence_transformers, searoute, shapely, or google.cloud.bigquery found in backend/src/parallax/ code paths]

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.3 + pytest-asyncio 0.25 |
| Config file | `backend/pyproject.toml` [tool.pytest.ini_options] |
| Quick run command | `cd backend && python -m pytest tests/ -x -q` |
| Full suite command | `cd backend && python -m pytest tests/ -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PROMPT-01 | Predict calls produce output without market_prices param | unit | `pytest tests/test_prediction.py -x` | Existing -- tests already call predict() without market_prices |
| PROMPT-01 | brief.py does not pass market_context to predictors | unit | `pytest tests/test_brief.py -x` | Existing -- needs review for market_context usage |
| PROMPT-02 | Oil predictor calls activate_bypass and gets non-zero bypass_flow | unit | `pytest tests/test_prediction.py::TestOilPricePredictor -x` | Needs new test in Wave 0 |
| PROMPT-03 | Hormuz prompt requests single probability, output has one probability field | unit | `pytest tests/test_prediction.py::TestHormuzReopeningPredictor -x` | Existing -- already checks single probability |
| PROMPT-04 | Track record returns fallback when n<10 | unit | `pytest tests/test_track_record.py -x` | Needs new test in Wave 0 |
| PROMPT-05 | Crisis context contains no editorial content | unit | `pytest tests/test_crisis_context.py -x` | Needs new test file in Wave 0 |
| ARCH-04 | Dead deps not in pyproject.toml | unit | `pytest tests/test_dependencies.py -x` | Needs new test in Wave 0 |

### Sampling Rate
- **Per task commit:** `cd backend && python -m pytest tests/ -x -q`
- **Per wave merge:** `cd backend && python -m pytest tests/ -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_prediction.py` -- add test verifying oil_price predictor gets non-zero bypass_flow when world_state has blocked cells (covers PROMPT-02)
- [ ] `tests/test_track_record.py` -- add test verifying n<10 returns informational fallback (covers PROMPT-04)
- [ ] `tests/test_crisis_context.py` -- new file: verify `get_crisis_context()` output has no market prices, no "Key risks", no "What The Market May Be Missing" (covers PROMPT-05 + PROMPT-01/D-02)
- [ ] No framework install needed -- pytest already configured and passing (335 tests collected, 334 passing, 1 pre-existing failure in test_recalibration.py unrelated to this phase)

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | WorldState should be initialized with at least one blocked Hormuz cell reflecting current strait status | Pitfall 1 / Code Examples | If WorldState is intentionally empty (cascade analysis is dead code), the bypass_flow fix is meaningless. Low risk -- the predictor explicitly iterates cells to compute supply_loss, confirming intent. |
| A2 | The 6 listed dependencies (h3, sentence-transformers, searoute, shapely, google-cloud-bigquery, websockets) have no hidden importers in the codebase | ARCH-04 | If any module imports these at runtime, removing them would break the pipeline. Medium risk -- verified via grep but transitive imports possible. |
| A3 | Removing market_prices from predict() signatures will not break any downstream callers beyond brief.py and backtest/engine.py | PROMPT-01 | If there are other callers (e.g., API endpoints), they would get a TypeError. Low risk -- grep found only 2 call sites. |

## Open Questions

1. **WorldState Initialization Values**
   - What we know: WorldState is created empty in brief.py. The cascade engine computes bypass flow from supply loss, which requires non-zero cell flow values.
   - What's unclear: What cell_id values and flow numbers should represent current Hormuz conditions? The scenario config uses `hormuz_daily_flow: 20_000_000` as pre-war capacity. Current flow is ~10% of that (from crisis context: "8 ships in 2 days vs 100+/day pre-war").
   - Recommendation: Initialize with a single Hormuz cell at ~2M bbl/day flow (10% of 20M), status="blocked", threat_level=0.9. This is within Claude's discretion per CONTEXT.md. The values will be approximate but non-zero, which is the key fix.

2. **Brent Price Line in Current Market State**
   - What we know: D-10 says keep factual status lines. D-01/D-02 say remove current market prices.
   - What's unclear: `- **Brent crude: ~$98/barrel futures**` is a factual current data point but also an anchor.
   - Recommendation: Remove the Brent price line from crisis_context.py. The oil price predictor already receives current EIA price data via `current_prices` parameter and `{price_data}` in its prompt. Having Brent price in crisis context is redundant and creates anchoring risk for ceasefire/hormuz models that should not see oil prices.

## Sources

### Primary (HIGH confidence)
- All code references verified by direct file reads of the codebase
- `oil_price.py`, `ceasefire.py`, `hormuz.py` -- full prompt templates and predict() signatures
- `crisis_context.py` -- full CRISIS_TIMELINE string with editorial sections identified
- `cascade.py` -- `activate_bypass()` method confirmed at line 73, returns `{"bypass_flow": float}`
- `track_record.py` -- `build_track_record()` confirmed missing n>=10 guard
- `brief.py` -- `market_context` building at lines 481-490, passed to all 3 predictors at lines 496-498
- `backtest/engine.py` -- `market_prices=market_context` at lines 212-214
- `pyproject.toml` -- all 6 dead dependencies confirmed present
- `scenario_hormuz.yaml` -- bypass capacity config: min=3.5M, max=6.5M bbl/day

### Secondary (MEDIUM confidence)
- Pre-existing test suite: 335 tests, 334 passing (1 unrelated failure in test_recalibration.py)

## Metadata

**Confidence breakdown:**
- Anchoring removal (PROMPT-01): HIGH -- straightforward parameter and template removal across known files
- Bypass flow fix (PROMPT-02): HIGH -- root cause confirmed (missing activate_bypass() call + empty WorldState)
- Hormuz single probability (PROMPT-03): HIGH -- prompt template text edit only
- Track record guard (PROMPT-04): HIGH -- 5-line change to existing function
- Editorial cleanup (PROMPT-05): HIGH -- sections clearly identified in crisis_context.py
- Dead deps (ARCH-04): HIGH -- dependencies confirmed present in pyproject.toml with no runtime importers

**Research date:** 2026-04-12
**Valid until:** 2026-05-12 (stable -- no external library changes involved)
