# Lane D Interface Output

## Owned Runtime Surface

The production-runtime lane adds a new `parallax.ops` package and rewires API startup through it.

### Entry-point runtime resolution

- `parallax.ops.resolve_api_runtime(*, dry_run: bool = False) -> AppRuntime`
- `parallax.ops.resolve_cli_runtime(*, dry_run: bool = False) -> AppRuntime`

Both methods return the same immutable `AppRuntime` shape:

```python
AppRuntime(
    process: str,
    storage: RuntimeConfig,
    requested_execution_environment: str,  # none | demo | live
    execution_environment: str,            # none | demo | live
    kalshi_base_url: str | None,
    live_execution_requested: bool,
    live_execution_authorized: bool,
    kill_switch_enabled: bool,
    authorization_reason: str | None,
    runtime_status: LocalRuntimeStatus,
)
```

Important contract:

- `requested_execution_environment` is what the process asked for.
- `execution_environment` is what the process is actually allowed to initialize.
- `live_execution_authorized` is only `True` when all live gates pass.
- `authorization_reason` explains why a live request was blocked or downgraded.

### Local kill-switch status

- `parallax.ops.load_local_runtime_status(path: str | None = None) -> LocalRuntimeStatus`

Returned shape:

```python
LocalRuntimeStatus(
    path: str,
    exists: bool,
    status: str,
    allow_live_execution: bool,
    kill_switch_enabled: bool,
    reason: str | None,
    updated_at: str | None,
)
```

Default local config path:

- `backend/config/runtime.yaml`
- override with `PARALLAX_RUNTIME_STATUS_PATH`

Accepted local config keys:

- `status`
- `allow_live_execution` or `live_execution_enabled`
- `kill_switch_enabled` or `kill_switch`
- `reason`
- `updated_at`

Safe default:

- missing config file keeps demo execution available in demo mode
- missing config file keeps live execution disabled

### Live authorization gates

Live execution now requires all of the following:

1. `PARALLAX_ENV=live`
2. `PARALLAX_EXECUTION_ENV=live` (or implicit live request via runtime default)
3. local runtime status file exists
4. local runtime status sets live execution enabled
5. local runtime status does not engage the kill switch
6. `PARALLAX_ENABLE_LIVE_EXECUTION=1`
7. `PARALLAX_LIVE_EXECUTION_ACK=I_ACKNOWLEDGE_REAL_MONEY_RISK`

If any gate fails, runtime resolves to `execution_environment="none"` instead of silently falling through to a live-capable client.

### Kill-switch precedence

If the local runtime status engages the kill switch, runtime resolves to `execution_environment="none"` for both `demo` and `live` requests. The process may still start for read-only/status use, but it will not initialize a Kalshi client.

### Market-client initialization hook

- `parallax.ops.build_kalshi_client_config(runtime, *, api_key, private_key_path) -> dict[str, str] | None`

Behavior:

- returns `None` when execution is not authorized for `demo` or `live`
- returns a fully resolved config dict when Kalshi client startup is allowed
- enforces demo/live API base URL separation

### Alerting hook

- `parallax.ops.build_alert_dispatcher() -> AlertDispatcher`
- `await AlertDispatcher.emit(event_type=..., severity=..., message=..., details=...)`

Current sinks:

- structured logger sink
- optional webhook sink via `PARALLAX_ALERT_WEBHOOK_URL`
- `mock://...` webhook targets stay local and log instead of sending network traffic

### API-visible status fields

`/api/health` now exposes:

- `requested_execution_environment`
- `execution_environment`
- `live_execution_authorized`
- `kill_switch_enabled`
- `runtime_status`

## Integrator Notes

- The CLI should be migrated to `resolve_cli_runtime()` before any non-demo execution path is exposed.
- The runtime status file is local-only operational state; no database migration is required for this lane.
