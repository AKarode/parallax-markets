# Lane C Interface Output

## Delivered Modules

- `backend/src/parallax/portfolio/allocator.py`
- `backend/src/parallax/portfolio/schemas.py`
- `backend/src/parallax/config/risk.py`

## Primary Contract

`PortfolioAllocator.authorize_trade(proposed_trade, current_positions)` returns:

```python
TradeAuthorization(
    authorized: bool,
    allowed_size: int,
    block_reason: str,
)
```

## Accepted Input Shapes

`proposed_trade` can be:

- `ProposedTrade`
- a mapping / dict with `ticker`, `side`, `price` and optional `requested_size`, `theme`
- tracker-like payloads using aliases such as `quantity`, `entry_price`, or `intended_price`

`current_positions` can be:

- `PortfolioState`
- a mapping / dict with:
  - `positions`
  - optional `open_orders`
  - optional `daily_realized_pnl`
- a plain sequence of open positions, which is treated as `PortfolioState(positions=...)`

## Risk Semantics

- Notional is modeled as binary-contract max loss: `size * price`
- Gross notional includes open positions plus active open orders
- Theme exposure includes open positions plus active open orders sharing the same normalized theme
- Daily loss checks are driven by `daily_realized_pnl`
- Open-position cap only blocks a trade if it would open a new `ticker + side` position

## Config Surface

`RiskLimits` supports:

- `max_notional`
- `max_open_orders`
- `max_open_positions`
- `daily_loss_limit`
- `default_order_size`
- `min_order_size`
- `theme_limits: dict[str, float]`

Risk config can be loaded from:

- defaults via `DEFAULT_RISK_LIMITS`
- YAML via `RiskLimits.from_yaml(path)`
- env-selected YAML via `load_risk_limits()` and `PARALLAX_RISK_CONFIG`

## DB Impact

Lane C introduces no schema changes and does not require updates to `backend/src/parallax/db/schema.py`.
