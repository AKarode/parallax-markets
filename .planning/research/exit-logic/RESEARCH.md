# Exit/Sell Logic Feasibility Research

**Researched:** 2026-04-09
**Domain:** Kalshi position management, transaction cost analysis
**Confidence:** HIGH (code verified, fee formula from multiple sources)

## Summary

Active exit trading (take-profit/stop-loss/edge-decay sells) on Kalshi faces a steep
transaction cost hurdle. Kalshi's taker fee formula `0.07 * P * (1-P)` is charged on
**both buy and sell legs**, meaning a round-trip trade pays the fee twice. At mid-range
prices (40-60 cents), the round-trip fee alone is 2.8-3.5 cents per contract, requiring
a 3-4 cent price movement just to break even -- before accounting for bid-ask spread
slippage on each leg.

The existing codebase has strong position tracking infrastructure but zero sell/exit
capability. The Kalshi API `place_order` method currently hardcodes `"action": "buy"`.
Selling requires changing this to `"action": "sell"`, which is a trivial API change.
The harder problem is building the decision logic for when to exit.

**Primary recommendation:** Do NOT build active exit trading for v1. The fee structure
makes it unprofitable for most realistic scenarios. Instead, focus on improving entry
signal quality and hold to settlement. Revisit exit logic only after collecting data
showing systematic edge decay patterns across multiple runs.

## Fee Math (Exact Breakeven Calculation)

### Kalshi Taker Fee Formula

```
fee_per_contract = 0.07 * P * (1 - P)
```

Where P is the contract price in dollars (0 to 1). [CITED: whirligigbear.substack.com/p/makertaker-math-on-kalshi]

Maximum fee: $0.0175/contract at P = $0.50. [VERIFIED: multiple sources agree]

Maker fees: 0% on most markets, 0.25% on high-profile events. [CITED: Kalshi help center]

### Round-Trip Cost Analysis

A round-trip (buy + sell) pays taker fees twice, plus spread slippage on each leg.

**Scenario: Buy YES at $0.50, sell later at higher price**

| Component | Entry (buy at $0.50) | Exit (sell at $0.55) | Total |
|-----------|---------------------|---------------------|-------|
| Taker fee | 0.07*0.50*0.50 = $0.0175 | 0.07*0.55*0.45 = $0.0173 | $0.0348 |
| Half-spread slippage (est. 2c spread) | $0.01 | $0.01 | $0.02 |
| **Total cost** | | | **$0.0548** |

**Breakeven price movement needed:** ~5.5 cents at mid-range prices.

### Fee Table by Entry Price

| Entry Price | Fee (entry) | Fee (exit, +5c move) | Round-trip fee | + Spread (2c) | Min Move to Break Even |
|-------------|-------------|---------------------|----------------|----------------|----------------------|
| $0.20 | $0.0112 | $0.0117 | $0.0229 | $0.0429 | ~4.3 cents |
| $0.35 | $0.0159 | $0.0168 | $0.0327 | $0.0527 | ~5.3 cents |
| $0.50 | $0.0175 | $0.0173 | $0.0348 | $0.0548 | ~5.5 cents |
| $0.65 | $0.0159 | $0.0147 | $0.0306 | $0.0506 | ~5.1 cents |
| $0.80 | $0.0112 | $0.0098 | $0.0210 | $0.0410 | ~4.1 cents |

### Comparison to Current Model (Hold to Settlement)

Holding to settlement pays fees **once** (entry only). Settlement itself is free --
the contract resolves to $0 or $1 with no exit fee.

| Strategy | Fee cost | Spread cost | Total cost | Edge needed |
|----------|----------|-------------|------------|-------------|
| Hold to settlement | $0.0175 max | $0.01 (entry only) | ~$0.028 | ~3 cents |
| Active exit (round-trip) | $0.035 max | $0.02 (both legs) | ~$0.055 | ~5.5 cents |

**Active exit costs ~2x what hold-to-settlement costs.** This means the edge decay
must be severe enough that exiting early saves more than the extra 2.7 cents/contract
of transaction costs.

### System's Current Cost Model

The codebase models costs via `MappingCostInputs` in `contracts/schemas.py`:

```python
class MappingCostInputs(BaseModel):
    expected_fee_rate: float = 0.01        # 1% flat estimate
    expected_slippage_rate: float = 0.01   # 1% flat estimate
    use_half_spread_as_slippage_floor: bool = True
```

The default `expected_fee_rate = 0.01` (1 cent per dollar) is a reasonable average
but understates the actual fee at mid-range prices ($0.0175 at 50c = 1.75%).
For exit analysis, this model would need to account for DOUBLE the fee rate.

## Infrastructure: What Exists vs What's Missing

### EXISTS: Position Tracking (Complete)

`PaperTradeTracker` in `scoring/tracker.py` has:
- `get_open_positions()` -- queries `trade_positions WHERE status = 'open'`
- `PositionRecord` with `entry_price`, `open_quantity`, `unrealized_pnl`, `exit_price`
- Full order lifecycle: `OrderAttempt` -> `FillRecord` -> `PositionRecord`
- Order cancellation support (`cancel_order`, `cancel_stale_orders`)
- Schema has `exit_price`, `closed_at`, `realized_pnl` columns ready

### EXISTS: Market Price Fetching (Complete)

`KalshiClient.get_market_price(ticker)` fetches live prices per run.
`market_prices` table stores historical snapshots with bid/ask/spread data.
Each run already fetches fresh prices for all tracked contracts.

### EXISTS: Edge Calculation (Complete)

`MappingPolicy.evaluate()` computes `buy_yes_edge` and `buy_no_edge` each run.
`SignalLedger` stores `effective_edge` per signal with full market state.

### EXISTS: Edge Decay Analytics (Partial)

`calibration.py` has `edge_decay()` function that buckets signals by edge size
and computes hit rate and counterfactual PnL. But this analyzes edge at signal
creation time, NOT edge change over time for the same contract across runs.

### EXISTS: Resolution/Close Logic (Settlement Only)

`resolution.py` closes positions at settlement: `_close_positions()` sets
`status='closed'`, `exit_price`, `realized_pnl` based on settlement price.
This is settlement-only -- no concept of early exit.

### MISSING: Sell Order Capability

`KalshiClient.place_order()` hardcodes `"action": "buy"`. To sell:

```python
# Current (line 360 of kalshi.py):
payload = {
    "ticker": ticker,
    "action": "buy",        # <-- hardcoded
    "side": side,
    "count": quantity,
    "type": "limit",
    "yes_price" if side == "yes" else "no_price": price,
}

# Needed for sell:
payload["action"] = "sell"
```

This is a 1-line change to the API layer. The Kalshi API supports `"action": "sell"`
to close existing positions. [ASSUMED -- based on standard exchange API patterns;
Kalshi API docs should be verified]

### MISSING: Position-Aware Signal Logic

The system is completely stateless regarding existing positions:
- `MappingPolicy.evaluate()` does not check if a position already exists
- If the model flips from BUY_YES to suggesting BUY_NO on the same contract,
  it would try to open a new opposing position rather than close the existing one
- No "SELL" or "CLOSE" signal type exists -- only BUY_YES, BUY_NO, HOLD, REFUSED

### MISSING: Exit Decision Engine

No component evaluates whether to close an open position based on:
- Current edge vs entry edge (edge decay)
- Take-profit threshold reached
- Stop-loss threshold breached
- Model signal reversal

### MISSING: Cross-Run Edge Tracking

`signal_ledger` records edge at signal creation time. To detect edge decay,
you'd need to compare the SAME contract's edge across multiple runs. Currently
each run creates independent signal records with no linkage to prior signals
for the same contract.

## Signal Re-Evaluation Analysis

When the model runs again and produces a different probability for a contract
where a position is open:

1. `MappingPolicy.evaluate()` computes new edges based on fresh market prices
2. A new `SignalRecord` is created in `signal_ledger` (append-only)
3. The new signal has NO awareness of the existing open position
4. If the new signal is BUY_YES and we already hold YES, it would try to buy more
5. If the new signal is HOLD, nothing happens -- but this IS implicit edge decay info

The data to detect edge flips EXISTS in the ledger (compare consecutive signals
for the same contract_ticker), but no code reads it that way.

## Feasibility Assessment

### Profitable? Almost certainly NOT for v1.

**The math is brutal:**

1. Round-trip costs are ~5.5 cents at mid-range prices
2. Geopolitical prediction markets are LOW LIQUIDITY (wide spreads make it worse)
3. The system runs 1-3x/day -- price moves between runs are unlikely to exceed
   the round-trip cost threshold regularly
4. Binary contracts approach 0 or 1 as resolution nears -- the biggest gains come
   from holding through resolution, not trading around positions

**When exit trading COULD be profitable:**

- Contract price moved 10+ cents in your favor (take-profit on a 2x cost basis)
- Model confidence dropped dramatically AND market hasn't moved (true edge decay)
- New contradictory information makes the position clearly wrong (stop-loss)
- You're trading at extreme prices (5c or 95c) where fees are minimal

### Risk of Building It Prematurely

- Complexity: adds position-aware state to every signal evaluation
- Overtrade risk: fee drag from unnecessary round-trips destroys edge
- Optimization theater: building exit logic before proving entry logic works

## Recommended Approach

### Phase 1 (Now): Collect Edge Decay Data

Add a lightweight query that tracks edge change per contract across runs:

```python
# In calibration.py or a new module:
def edge_history_by_contract(conn):
    """Track how edge evolves for the same contract across runs."""
    return conn.execute("""
        SELECT
            contract_ticker,
            run_id,
            created_at,
            effective_edge,
            entry_price,
            market_yes_price,
            signal
        FROM signal_ledger
        WHERE signal IN ('BUY_YES', 'BUY_NO', 'HOLD')
        ORDER BY contract_ticker, created_at
    """).fetchall()
```

This requires zero infrastructure changes and produces the data needed to decide
if exit trading is worth building.

### Phase 2 (If Data Shows Opportunity): Position-Aware Evaluation

Only build if Phase 1 data shows:
- Systematic edge decay > 5 cents within the holding period
- At least 20% of positions would benefit from early exit
- Net savings after double fees still positive

### Phase 3 (If Proven): Full Exit Engine

- Add `"action": "sell"` support to `KalshiClient.place_order()`
- Add SELL_YES / SELL_NO signal types to the ledger
- Build `ExitPolicy` that checks open positions against current model output
- Wire into `brief.py` run loop: evaluate exits BEFORE evaluating new entries

## Open Questions

1. **Kalshi sell API**: Does the demo sandbox support sell orders? Need to verify
   since demo only has sports/crypto markets.
2. **Maker fee on exits**: If exit orders rest on the book (maker), fees drop to
   0% on most markets. This would halve the exit-leg cost but requires limit
   orders that may not fill.
3. **Partial exits**: Can you sell 5 of 10 contracts? Kalshi API likely supports
   this but needs verification.
4. **Position netting**: Does Kalshi net long YES against new short YES automatically,
   or do you need explicit sell orders?

## Sources

- [Maker/Taker Math on Kalshi](https://whirligigbear.substack.com/p/makertaker-math-on-kalshi) - fee formula
- [Kalshi Fee Schedule](https://kalshi.com/fee-schedule) - official fee page
- [Kalshi Fees Help Center](https://help.kalshi.com/trading/fees) - maker vs taker explanation
- Code: `backend/src/parallax/markets/kalshi.py` (lines 352-367) - place_order hardcodes "buy"
- Code: `backend/src/parallax/contracts/schemas.py` (lines 45-67) - MappingCostInputs
- Code: `backend/src/parallax/scoring/tracker.py` (lines 162-174) - get_open_positions
- Code: `backend/src/parallax/scoring/calibration.py` (lines 74-101) - edge_decay analysis
- Code: `backend/src/parallax/scoring/ledger.py` - append-only signal records
- Code: `backend/src/parallax/scoring/resolution.py` (lines 117-172) - settlement-only close
