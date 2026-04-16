# Phase 10: Prompt Fixes + Dependency Cleanup - Context

**Gathered:** 2026-04-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Models produce independent probability estimates from clean inputs. Fix anchoring to market prices, broken cascade data, noise from tiny sample sizes, and editorial contamination in prompts. Remove dead dependencies.

</domain>

<decisions>
## Implementation Decisions

### Anchoring Removal (PROMPT-01)
- **D-01:** Remove `{market_prices_text}` from all 3 model prompt templates (oil_price.py, ceasefire.py, hormuz.py). Models must never see current market prices before stating their probability estimate.
- **D-02:** Remove the "Prediction Market Contract Context" section's price data from crisis_context.py (e.g., "~48% YES", "~42%", "$200M+ wagered"). Keep contract resolution criteria (what YES/NO means).
- **D-03:** Historical price mentions in the dated timeline (e.g., "Brent surged to $120") stay — these are factual event markers, not current anchors.

### Hormuz Single Probability (PROMPT-03)
- **D-04:** Hormuz model outputs ONE probability: likelihood of partial reopening (>25% of pre-war commercial shipping flow restored) within 14 days.
- **D-05:** Remove the dual "(a) partial / (b) full" specification from the prompt. Full reopening prediction is deferred to Phase 13's political model.
- **D-06:** The existing `invert_probability` mapping in the contract registry continues to handle the inversion from "reopening probability" to "closure contract" pricing.

### Editorial Content Handling (PROMPT-05)
- **D-07:** Remove "What The Market May Be Missing" section entirely from crisis_context.py — models must form their own hypotheses from facts.
- **D-08:** Remove "Key risks" and "Key opportunities" bullets from "Current Market State" section — these are analyst opinions, not facts.
- **D-09:** Keep factual current status lines (Hormuz closed, ceasefire fragile, days remaining) and contract resolution criteria (what contracts resolve on). Models know WHAT they're predicting against without editorial guidance.
- **D-10:** Keep "Current Market State" header with only factual status bullets (no prices, no opinions).

### Claude's Discretion
- Bypass flow fix (PROMPT-02): technical investigation — read cascade engine, determine why bypass_flow is 0 when blockade conditions exist, fix the computation.
- Track record guard (PROMPT-04): straightforward — add n>=10 check in `build_track_record()`, return fallback text below threshold. Requirement specifies the threshold.
- Dead dependency removal (ARCH-04): remove h3, sentence-transformers, searoute, shapely, google-cloud-bigquery, websockets from pyproject.toml.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Prediction Models
- `backend/src/parallax/prediction/oil_price.py` — Oil price prompt template with anchoring + track record injection
- `backend/src/parallax/prediction/ceasefire.py` — Ceasefire prompt template with anchoring + track record injection
- `backend/src/parallax/prediction/hormuz.py` — Hormuz prompt template with dual-probability spec + anchoring
- `backend/src/parallax/prediction/crisis_context.py` — Crisis timeline with editorial sections to strip
- `backend/src/parallax/prediction/schemas.py` — PredictionOutput model (single probability field)

### Track Record
- `backend/src/parallax/scoring/track_record.py` — `build_track_record()` lacks sample size guard

### Cascade Engine
- `backend/src/parallax/simulation/cascade.py` — Cascade engine that should produce non-zero bypass_flow
- `backend/src/parallax/simulation/world_state.py` — WorldState providing blockade conditions

### Pipeline Integration
- `backend/src/parallax/cli/brief.py` — Main pipeline that wires market_prices into predictors (lines ~496-498)
- `backend/src/parallax/contracts/registry.py` — Contract registry with invert_probability for Hormuz

### Dependencies
- `backend/pyproject.toml` — Dead deps: h3, sentence-transformers, searoute, shapely, google-cloud-bigquery, websockets

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `build_track_record()` in `scoring/track_record.py` — already queries signal_ledger, just needs n>=10 guard added
- `CascadeEngine` in `simulation/cascade.py` — bypass flow computation exists, likely needs correct world state initialization
- Contract registry `invert_probability` mapping — already handles reopening→closure inversion for Hormuz

### Established Patterns
- All 3 predictors follow identical pattern: system prompt template → format with context → Claude Sonnet call → parse JSON → return PredictionOutput
- Crisis context injected via `get_crisis_context()` prepended to prompt (hormuz.py:105, similar in others)
- Track record injected via `build_track_record(model_id, db_conn)` with try/except fallback

### Integration Points
- `brief.py` passes `market_prices=market_context` to all 3 predictors — this parameter can be removed or ignored
- `brief.py` lines 496-498 are the async gather calls where market_context flows into predictors
- Each predictor's `predict()` method accepts `market_prices` kwarg — signature change needed

</code_context>

<specifics>
## Specific Ideas

- User wants models to know what contracts resolve on (e.g., "SIGNED DEAL, not just ceasefire") without seeing current prices — resolution criteria are facts, prices are anchors
- Context expansion (filling Aug 2025 – Feb 2026 gap) is Phase 11's scope, not Phase 10
- Full Hormuz reopening prediction deferred to Phase 13's political model — Phase 10 focuses on the near-term partial reopening signal

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 10-prompt-fixes-dependency-cleanup*
*Context gathered: 2026-04-12*
