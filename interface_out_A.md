# Lane A Interface Output

## Updated Entry Point

`MappingPolicy.evaluate` now accepts cost and freshness controls while remaining callable as `evaluate(prediction, market_prices)`:

```python
def evaluate(
    prediction: PredictionOutput,
    market_prices: list[MarketPrice],
    *,
    cost_inputs: MappingCostInputs | None = None,
    staleness_policy: MarketStalenessPolicy | None = None,
    evaluated_at: datetime | None = None,
) -> list[MappingResult]
```

## Behavior Changes

- Legacy proxy-edge discounting (`1.0 / 0.6 / 0.3`) is no longer used in trade gating.
- Only explicit contract-native estimators are allowed:
  - `ceasefire -> iran_agreement`
  - `hormuz_reopening -> hormuz_closure`
  - `oil_price -> oil_price_max`
  - `oil_price -> oil_price_min`
  - generic direct binary contracts still map directly
- Unsupported proxy relationships now return `tradeability_status="non_tradable"`.
- Quotes older than the configured threshold now return `tradeability_status="non_tradable"`.
- A contract is only tradable when:
  - `gross_edge > expected_total_cost`
  - `net_edge >= min_effective_edge`

## New Schema Types

- `ContractFamily`
- `MappingCostInputs`
- `MarketStalenessPolicy`
- `FairValueEstimate`

## New `MappingResult` Fields

- `contract_family`
- `estimator_name`
- `fair_value_yes`
- `fair_value_no`
- `quote_timestamp`
- `quote_age_seconds`
- `staleness_threshold_seconds`
- `quote_is_stale`
- `gross_edge`
- `expected_fee_rate`
- `expected_slippage_rate`
- `expected_total_cost`
- `net_edge`

## Database Fields Needed By Integrator

Recommended additions to `signal_ledger`:

- `contract_family VARCHAR`
- `pricing_estimator VARCHAR`
- `fair_value_yes DOUBLE`
- `fair_value_no DOUBLE`
- `gross_edge DOUBLE`
- `expected_fee_rate DOUBLE`
- `expected_slippage_rate DOUBLE`
- `expected_total_cost DOUBLE`
- `net_edge DOUBLE`
- `quote_age_seconds DOUBLE`
- `staleness_threshold_seconds DOUBLE`
- `quote_is_stale BOOLEAN DEFAULT false`

Recommended additions to contract metadata storage or first-class columns:

- `contract_family VARCHAR`
- `expected_fee_rate DOUBLE`
- `expected_slippage_rate DOUBLE`
- `staleness_threshold_seconds DOUBLE`
- `allow_fetched_at_fallback BOOLEAN`
- `oil_move_scale_usd DOUBLE`

## Notes For Lane E

- Existing callers do not need an immediate signature change because the new parameters are keyword-only and optional.
- To get real venue behavior, Lane E should source `MappingCostInputs` from config or DB instead of relying on constructor defaults.
