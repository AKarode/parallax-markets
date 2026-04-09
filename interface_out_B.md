# Lane B Interface Output

## Public tracker methods

```python
async def poll_resting_orders(
    self,
    *,
    limit: int | None = None,
) -> list[OrderAttempt]
```

```python
async def cancel_order(
    self,
    order_id: str,
    *,
    reason: str | None = None,
) -> OrderAttempt
```

```python
async def cancel_stale_orders(
    self,
    *,
    max_age_seconds: float,
    limit: int | None = None,
    reason: str | None = None,
) -> list[OrderAttempt]
```

## Venue client surface

```python
async def get_order(self, order_id: str) -> dict
```

```python
async def cancel_order(self, order_id: str) -> dict
```

## Database impact

- No schema or column changes are required.
- `trade_orders.status` now intentionally carries richer order-lifecycle states:
  - `resting`
  - `partially_filled`
  - existing terminal states remain `filled`, `cancelled`, and `rejected`
- `signal_ledger.execution_status` is still constrained to the existing coarse states already used by the app:
  - `accepted`
  - `filled`
  - `cancelled`
  - `rejected`

## Behavioral notes for integration

- `poll_resting_orders()` is idempotent against already-recorded fills by reconciling from persisted `trade_orders.filled_quantity`.
- Partial fills update the existing `trade_positions` row for the signal and append delta fill records into `trade_fills`.
- Cancelling an order after a partial fill leaves `signal_ledger.execution_status = 'filled'` because a live position exists, while `trade_orders.status` becomes `cancelled`.
