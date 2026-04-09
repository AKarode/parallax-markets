# Session Log: 2026-04-09 (Evening) — Signal Integrity Fixes from Deep Audit

## Summary

Applied four critical fixes from a deep branch audit of `codex-executable-trading-journal`. The fixes address the most dangerous gaps in the prediction pipeline: circular LLM anchoring on market prices, missing transaction cost model, no quote staleness protection, and flat position sizing. 38 new tests, all TDD. Implementation used parallel subagents for independent fixes.

## What Was Built

### New Modules

| Module | Files | Purpose |
|--------|-------|---------|
| **Cost Model** | `costs/__init__.py`, `costs/fee_model.py` | Frozen dataclass modeling Kalshi taker fees ($0.07) + configurable slippage buffer (1%). Converts to probability space for edge deduction. |

### Modified Modules

| Module | Files Changed | What Changed |
|--------|--------------|-------------|
| **Prediction Models** | `prediction/oil_price.py`, `prediction/ceasefire.py`, `prediction/hormuz.py` | Removed market price injection from all LLM prompts. Removed `market_prices` parameter, `_format_market_prices()` method, and prompt template blocks. |
| **Brief CLI** | `cli/brief.py` | Stopped passing `market_context` to predictors. Fixed pre-existing positional arg swap in `_write_scheduled_output` call. |
| **Divergence Detector** | `divergence/detector.py` | Integrated `CostModel` for net edge calculation. Added `gross_edge`/`net_edge` fields to `Divergence`. Added quote staleness guard (`max_quote_age_seconds`). |
| **Portfolio Allocator** | `portfolio/allocator.py` | Added `kelly_size()` method implementing quarter-Kelly sizing for binary contracts. Modified `authorize_trade()` to use Kelly when edge is provided. |
| **Portfolio Schemas** | `portfolio/schemas.py` | Added optional `edge` field to `ProposedTrade`. |
| **Risk Config** | `config/risk.py` | Added `bankroll` (default $250) and `kelly_multiplier` (default 0.25) fields to `RiskLimits` with validators. |

### New Tests

| Test File | Count | What It Tests |
|-----------|-------|--------------|
| `test_predictor_no_market_prices.py` | 9 | Prompts contain no market prices, signatures have no market_prices param, no _format_market_prices method |
| `test_fee_model.py` | 7 | CostModel math: default/custom fees, net edge positive/negative/zero, zero-cost passthrough |
| `test_detector_costs.py` | 5 | Detector with cost model: filters marginal edge, allows strong edge, backward compatible, gross/net edge fields |
| `test_staleness_guard.py` | 6 | Fresh/stale/boundary quotes, fallback to fetched_at, zero disables guard, default skips check |
| `test_kelly_sizing.py` | 11 | Kelly formula at various edge/price combos, zero/negative edge, min_order_size floor, half-Kelly multiplier, allocator integration, risk cap ceilings |

## Key Design Decisions

### 1. Remove market prices entirely (not two-pass)

Considered a two-pass approach where the LLM first outputs a blind probability, then gets market prices for a commentary pass. Rejected because: (a) the commentary is low-value — LLMs correlate 0.994 with given prices even in "review" mode, (b) doubles LLM cost, (c) adds orchestration complexity for text humans won't read during automated runs. Clean removal is simpler and equally sound for signal independence.

### 2. Cost model uses taker fee only

`CostModel.total_cost_probability_space()` uses taker fee + slippage, not maker fee. Rationale: the system crosses the spread (taker), it doesn't provide liquidity (maker). Maker fee field exists for future use if the system evolves to limit-order strategies.

### 3. Staleness guard defaults to disabled

`max_quote_age_seconds=0.0` means no staleness check by default. This preserves backward compatibility — existing code and tests don't break. Callers that want protection opt in explicitly. The brief pipeline should set this to 120s when wiring up production.

### 4. Kelly sizing falls back to flat sizing

If `ProposedTrade.edge` is None, the allocator uses `default_order_size` (10). This means the entire existing execution path is unchanged unless you explicitly provide edge. No breaking changes.

## Setbacks and Fixes

### 1. Subagent committed P1 and P3 into a single commit

**Problem:** Both parallel subagents were on the same branch. P3 finished after P1 and its commit (`e384022`) included P1's staged files.

**Root cause:** Git staging area is shared. When P3 ran `git add` and committed, P1's already-staged files were included.

**Fix:** Not a real problem — the combined commit contains both fixes correctly. Just means the git history shows 1 commit instead of 2 for these fixes.

**Lesson:** For truly isolated parallel commits, use git worktrees. For same-branch work, accept that commits may merge.

### 2. Pre-existing positional arg bug in brief.py

**Problem:** `_write_scheduled_output(run_id, predictions, signals, runtime, trade_journal, ...)` passed `runtime` where `trade_journal` was expected and vice versa.

**Root cause:** Function signature has `trade_journal` before `runtime` as keyword args, but the call site passed them positionally in wrong order.

**Fix:** Changed to keyword args: `trade_journal=trade_journal, runtime=runtime`.

**Lesson:** Always use keyword args for functions with multiple optional parameters of similar types.

### 3. Pyright "sign possibly unbound" warning

**Problem:** `sign` variable was set inside an `else` branch but referenced in the Divergence constructor using `if candidates` ternary.

**Root cause:** Pyright can't prove `sign` is always bound when `candidates` is truthy, even though logically it is.

**Fix:** Initialize `sign = 1.0` before the branch.

**Lesson:** Initialize variables before branches for static analysis happiness.

## Current State

**What works:**
- All 3 prediction models produce independent probabilities (no market anchoring)
- Divergence detector computes net edge after fees + slippage
- Stale quotes are rejected when staleness guard is enabled
- Kelly sizing produces edge-proportional positions
- 247 tests pass (excluding 16 pre-existing failures in mapping_policy, prediction_log, recalibration)

**What's tested:**
- 38 new tests covering all four fixes
- All TDD: tests written first, confirmed failing, then implementation

**All modules wired into production path** (see wiring section below).

## Wiring into Production Path

After building the modules, wired everything into `brief.py`:

### What was wired

- **Kalshi taker fee** — `MappingCostInputs(expected_fee_rate=0.07)` passed to `MappingPolicy`. Also updated `MappingCostInputs.expected_fee_rate` default from 0.01 to 0.07 in `contracts/schemas.py`.
- **Staleness guard** — already built into `MappingPolicy.evaluate()` (the production path), which checks quote age before computing edge. The `DivergenceDetector` staleness guard is for standalone/direct detection use.
- **Kelly sizing** — `PortfolioAllocator` instantiated with `load_risk_limits()` in `run_brief()`. Trade execution loop now builds `ProposedTrade` with `edge=signal.effective_edge` and passes through allocator for Kelly sizing + risk cap enforcement. Falls back to `default_order_size` when edge/entry_price unavailable.

### Discovery: MappingPolicy already had cost + staleness handling

The `DivergenceDetector` cost model and staleness guard (P1/P2) are useful for standalone detection, but the production brief pipeline uses `MappingPolicy.evaluate()` which already had its own `MappingCostInputs` and staleness checking. The key fix was updating the fee default from 0.01 (placeholder) to 0.07 (real Kalshi taker fee).

### Dry-run mock data adjusted

The higher fee threshold (8.5% total cost = 7% fee + 1.5% half-spread) correctly blocked all mock signals that had marginal edges. Updated mock predictions and market prices to represent realistic divergence scenarios with clear post-cost edge, so the dry-run test still validates the full pipeline.

## Commits

| Hash | Description |
|------|-------------|
| `afd3b43` | fix(prediction): remove market prices from LLM prompts to prevent anchoring |
| `01cda9b` | fix(brief): correct positional arg order in _write_scheduled_output call |
| `e384022` | feat(portfolio): add quarter-Kelly position sizing + feat(costs): fee model + detector integration |
| `cc53de4` | feat(detector): add quote staleness guard to reject stale market snapshots |
| `57862b9` | fix(detector): initialize sign variable to satisfy static analysis |
| `5cf5aae` | docs: session log and README update for signal integrity fixes |
| `2128dfb` | feat(brief): wire cost model, Kelly sizing, and allocator into production path |

## Next Steps

1. **Run 30 days of paper trades** — validate calibration with the `scoring/calibration.py` infrastructure
2. **Raise min_edge_pct** — with cost model in place, the 5% threshold is now post-cost. Consider whether 5% net is still appropriate or should be higher given model uncertainty.
3. **Load portfolio state from DB** — the allocator currently gets an empty `PortfolioState()`. Wire it to load open positions/orders from DuckDB for cumulative risk tracking across runs.
4. **Background fill reconciliation** — `poll_resting_orders()` exists but isn't called on a schedule.
