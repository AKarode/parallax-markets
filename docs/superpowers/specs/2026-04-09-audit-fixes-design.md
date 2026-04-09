# Audit Fixes: Signal Independence, Cost Model, Staleness Guard, Kelly Sizing

**Date:** 2026-04-09
**Status:** Approved
**Branch:** `audit-fixes-signal-integrity`

## Summary

Four fixes addressing the most critical findings from the deep branch audit. These fixes transform the prediction pipeline from "circular signal with no cost awareness" to "independent signal with economic honesty."

Priority order:
1. **P0** — Remove market prices from LLM prompts (signal independence)
2. **P1** — Add fee + slippage model to edge calculation (cost awareness)
3. **P2** — Quote staleness guard (execution safety)
4. **P3** — Quarter-Kelly sizing (edge-proportional position sizing)

## Fix 1: Remove Market Prices from LLM Prompts (P0)

### Problem

All three prediction models inject current market prices into the Claude prompt. ForecastBench research shows LLMs correlate at 0.994 with market prices when given them. This makes the divergence detection loop nearly circular — the LLM outputs ~market price, system compares to market price, finds tiny divergence, calls it a "signal."

### Changes

**`prediction/oil_price.py`:**
- Remove `Current market prices:\n{market_prices_text}` block from `OIL_PRICE_SYSTEM_PROMPT`
- Remove `"Consider what the market may already be pricing in..."` line
- Remove `market_prices` parameter from `predict()` signature
- Remove `_format_market_prices()` static method
- Remove `market_prices_text=...` from prompt `.format()` call

**`prediction/ceasefire.py`:**
- Same pattern: remove market prices block, parameter, format method, format call

**`prediction/hormuz.py`:**
- Same pattern: remove market prices block, parameter, format method, format call

**`cli/brief.py`:**
- Remove `market_context` dict construction (lines 376-385)
- Remove `market_prices=market_context` from all three `predict()` calls (lines 391-393)

**What stays:** Track record injection (`{track_record}`) remains — that's mechanical calibration feedback from resolved signals, not market anchoring.

### Test Criteria

- All three predictors accept calls without `market_prices` parameter
- Prompts contain no market price data
- `brief.py` pipeline runs end-to-end without passing market context to predictors
- Dry-run brief still produces output

## Fix 2: Fee + Slippage Model in Edge Calculation (P1)

### Problem

The 5% `min_edge_pct` threshold compares raw model-vs-ask edge with no deduction for fees or slippage. Kalshi taker fees are $0.07/contract. In thin markets, a 5% apparent edge may be zero or negative after costs.

### New File: `costs/fee_model.py`

```python
@dataclass(frozen=True)
class CostModel:
    taker_fee_per_contract: float = 0.07  # $0.07 Kalshi taker fee
    maker_fee_per_contract: float = 0.00  # currently zero
    slippage_buffer: float = 0.01         # 1% for thin geopolitical markets

    def total_cost_probability_space(self) -> float:
        """Total cost as a fraction of the $1 contract payout."""
        return self.taker_fee_per_contract + self.slippage_buffer

    def net_edge(self, raw_edge: float) -> float:
        """Subtract costs from raw edge. Negative = no real edge."""
        return raw_edge - self.total_cost_probability_space()
```

Also create `costs/__init__.py`.

### Integration: `divergence/detector.py`

- `DivergenceDetector.__init__()` accepts optional `cost_model: CostModel | None`
- If provided, `detect()` computes `net_edge = cost_model.net_edge(raw_edge)` and uses that for threshold comparison
- `Divergence` model gains two new fields: `gross_edge: float`, `net_edge: float`
- The existing `edge` field becomes the net edge; `gross_edge` preserves the raw value

### Test Criteria

- `CostModel` with default fees returns `total_cost = 0.08` (7¢ fee + 1¢ slippage)
- A raw edge of 0.06 with default costs → net edge of -0.02 → HOLD (not a signal)
- A raw edge of 0.15 with default costs → net edge of 0.07 → still a signal if > min_edge
- Detector with no cost model behaves identically to current behavior (backward compatible)

## Fix 3: Quote Staleness Guard (P2)

### Problem

The divergence detector uses `best_yes_ask` / `best_no_ask` snapshots from a polling cycle. In thin event markets, quotes can move significantly in 30-60 seconds. No staleness check exists.

### Changes: `divergence/detector.py`

- `DivergenceDetector.__init__()` accepts `max_quote_age_seconds: float = 120.0`
- Before computing divergence for a market, check:
  ```python
  quote_time = market.quote_timestamp or market.fetched_at
  staleness = (now - quote_time).total_seconds()
  if staleness > self._max_quote_age:
      # mark as stale, skip
  ```
- Stale quotes produce a `Divergence` with `signal="STALE_QUOTE"` and `tradeability_status="non_tradable"`

### Test Criteria

- Quote 10 seconds old → normal processing
- Quote 200 seconds old → STALE_QUOTE signal, non_tradable
- Quote with no timestamp → uses `fetched_at` as fallback
- `max_quote_age_seconds=0` disables the guard (all quotes pass)

## Fix 4: Quarter-Kelly Sizing (P3)

### Problem

The allocator uses flat `default_order_size` (10 contracts) regardless of edge magnitude. A 6% edge and a 25% edge get identical sizing.

### Changes: `config/risk.py`

Add two fields to `RiskLimits`:
```python
bankroll: float = 250.0          # total capital for sizing (same as max_notional default)
kelly_multiplier: float = 0.25   # quarter-Kelly
```

### Changes: `portfolio/allocator.py`

Add a method:
```python
def kelly_size(self, edge: float, entry_price: float) -> int:
    """Compute quarter-Kelly position size for a binary contract.

    For binary contracts bought at price p with model probability p+edge:
    kelly_fraction = edge / (1 - entry_price)
    size = floor(fraction * multiplier * bankroll / entry_price)
    """
    if edge <= 0 or entry_price <= 0 or entry_price >= 1.0:
        return 0
    kelly_fraction = edge / (1.0 - entry_price)
    raw_size = kelly_fraction * self._risk_limits.kelly_multiplier * self._risk_limits.bankroll / entry_price
    return max(self._risk_limits.min_order_size, math.floor(raw_size))
```

Modify `authorize_trade()`:
- If `ProposedTrade` has an `edge` field (new optional field on `ProposedTrade`), compute Kelly size as the starting `requested_size` instead of `default_order_size`
- All existing risk caps (notional, theme, daily loss) still apply as ceilings
- If `edge` is not provided, fall back to `default_order_size`

### Changes: `portfolio/schemas.py`

Add optional field to `ProposedTrade`:
```python
edge: float | None = None  # net edge (post-cost) for Kelly sizing
```

### Test Criteria

- Edge=0.10 at price=0.30: Kelly fraction = 0.10/0.70 = 0.143, quarter-Kelly = 0.0357, size = floor(0.0357 * 250 / 0.30) = floor(29.7) = 29 contracts (then capped by risk limits)
- Edge=0.05 at price=0.50: Kelly fraction = 0.10, quarter = 0.025, size = floor(0.025 * 250 / 0.50) = floor(12.5) = 12 contracts
- Edge=0 → size=0 (no trade)
- Edge negative → size=0
- No edge provided → falls back to default_order_size=10
- Kelly size exceeding max_notional → capped by existing risk limits
- Kelly size below min_order_size → uses min_order_size

## File Summary

| File | Action | Fix |
|---|---|---|
| `prediction/oil_price.py` | Edit | P0: Remove market prices |
| `prediction/ceasefire.py` | Edit | P0: Remove market prices |
| `prediction/hormuz.py` | Edit | P0: Remove market prices |
| `cli/brief.py` | Edit | P0: Remove market context passing |
| `costs/__init__.py` | New | P1: Package init |
| `costs/fee_model.py` | New | P1: Fee + slippage model |
| `divergence/detector.py` | Edit | P1+P2: Cost model + staleness guard |
| `markets/schemas.py` | No change | Already has quote_timestamp |
| `portfolio/allocator.py` | Edit | P3: Kelly sizing |
| `portfolio/schemas.py` | Edit | P3: Add edge field |
| `config/risk.py` | Edit | P3: Add bankroll + kelly_multiplier |

## Test Files

| File | Tests |
|---|---|
| `tests/test_oil_price_no_market.py` | New: P0 prompt independence |
| `tests/test_ceasefire_no_market.py` | New: P0 prompt independence |
| `tests/test_hormuz_no_market.py` | New: P0 prompt independence |
| `tests/test_fee_model.py` | New: P1 cost calculations |
| `tests/test_detector_costs.py` | New: P1+P2 detector with costs + staleness |
| `tests/test_kelly_sizing.py` | New: P3 Kelly math + allocator integration |

## Implementation Order

1. P0 first — removes code, no new dependencies
2. P1 second — new module, integrates into detector
3. P2 third — builds on detector changes from P1
4. P3 last — independent from P0-P2, touches different files

Each fix is independently committable and testable.
