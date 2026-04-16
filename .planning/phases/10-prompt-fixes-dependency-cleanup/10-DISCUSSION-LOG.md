# Phase 10: Prompt Fixes + Dependency Cleanup - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-12
**Phase:** 10-prompt-fixes-dependency-cleanup
**Areas discussed:** Anchoring removal scope, Hormuz probability target, Editorial content handling

---

## Anchoring Removal Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Remove entirely | Strip {market_prices_text} from all prompts AND remove Prediction Market Contract Context from crisis_context.py. Historical timeline prices stay. | ✓ |
| Two-stage prompt | Restructure prompts to get independent estimate first, then reveal market prices for "market awareness" | |
| Remove from templates only | Strip from prompt templates but keep crisis context prices | |

**User's choice:** Remove entirely
**Notes:** Clear preference for full deanchoring. Historical timeline price mentions (e.g., "Brent surged to $120") are factual event markers and stay.

---

## Hormuz Probability Target

| Option | Description | Selected |
|--------|-------------|----------|
| Partial reopening | Predict >25% flow restored within 14 days. Near-term tradeable signal. | ✓ |
| Full reopening within 30d | Higher bar, more dramatic signal, less tradeable near-term | |
| Match contract criterion exactly | Read specific Kalshi resolution criteria. Most precise but requires Phase 12 discovery. | |

**User's choice:** Partial reopening (>25% flow within 14d)
**Notes:** Full reopening deferred to Phase 13 political model. Single probability maps to KXCLOSEHORMUZ sub-contracts via existing inversion.

---

## Editorial Content Handling

| Option | Description | Selected |
|--------|-------------|----------|
| Keep resolution criteria, strip the rest | Keep what contracts resolve on, remove prices + editorial + analyst opinions | ✓ |
| Remove all editorial + contract context | Strip everything after dated timeline | |
| Separate labeled section | Move editorial to labeled "ANALYST HYPOTHESES" section | |

**User's choice:** Keep resolution criteria, strip the rest
**Notes:** User clarified: models should know which markets they're predicting against (contract resolution criteria are facts), but not see current prices or pre-loaded analyst opinions. Context expansion is Phase 11's scope.

---

## Claude's Discretion

- Bypass flow fix (PROMPT-02): technical investigation
- Track record n>=10 guard (PROMPT-04): straightforward threshold check
- Dead dependency removal (ARCH-04): mechanical cleanup

## Deferred Ideas

None — discussion stayed within phase scope
