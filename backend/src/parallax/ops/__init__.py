"""Operational runtime controls for production-facing entrypoints."""

from parallax.ops.alerts import AlertDispatcher, AlertEvent, build_alert_dispatcher
from parallax.ops.runtime import (
    AppRuntime,
    LocalRuntimeStatus,
    RuntimeAuthorizationError,
    build_kalshi_client_config,
    load_local_runtime_status,
    resolve_api_runtime,
    resolve_cli_runtime,
)

__all__ = [
    "AlertDispatcher",
    "AlertEvent",
    "AppRuntime",
    "LocalRuntimeStatus",
    "RuntimeAuthorizationError",
    "build_alert_dispatcher",
    "build_kalshi_client_config",
    "load_local_runtime_status",
    "resolve_api_runtime",
    "resolve_cli_runtime",
]
