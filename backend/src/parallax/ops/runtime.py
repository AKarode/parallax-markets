"""Runtime safety controls for API and CLI initialization."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from parallax.db.runtime import RuntimeConfig, resolve_runtime_config

logger = logging.getLogger(__name__)

KALSHI_DEMO_API_BASE_URL = "https://demo-api.kalshi.co/trade-api/v2"
KALSHI_LIVE_API_BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"
LIVE_EXECUTION_ACK = "I_ACKNOWLEDGE_REAL_MONEY_RISK"
_ENABLED_STATUSES = {"enabled", "ready", "armed", "active"}
_BLOCKED_STATUSES = {"disabled", "paused", "halted", "stopped"}


class RuntimeAuthorizationError(RuntimeError):
    """Raised when runtime configuration violates execution safety rules."""


@dataclass(frozen=True)
class LocalRuntimeStatus:
    """Local control-plane status loaded from a config file."""

    path: str
    exists: bool
    status: str
    allow_live_execution: bool
    kill_switch_enabled: bool
    reason: str | None = None
    updated_at: str | None = None

    @property
    def live_execution_enabled(self) -> bool:
        """Return whether the local status file explicitly authorizes live execution."""

        return (
            self.exists
            and self.allow_live_execution
            and not self.kill_switch_enabled
            and self.status in _ENABLED_STATUSES
        )


@dataclass(frozen=True)
class AppRuntime:
    """Resolved runtime state for one entrypoint process."""

    process: str
    storage: RuntimeConfig
    requested_execution_environment: str
    execution_environment: str
    kalshi_base_url: str | None
    live_execution_requested: bool
    live_execution_authorized: bool
    kill_switch_enabled: bool
    authorization_reason: str | None
    runtime_status: LocalRuntimeStatus

    @property
    def data_environment(self) -> str:
        return self.storage.data_environment

    @property
    def db_path(self) -> str:
        return self.storage.db_path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _default_runtime_status_path() -> Path:
    return _repo_root() / "backend" / "config" / "runtime.yaml"


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).strip().lower() in {"1", "true", "yes", "on", "enabled"}


def _load_structured_file(path: Path) -> dict[str, Any]:
    raw_text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        loaded = json.loads(raw_text)
    else:
        loaded = yaml.safe_load(raw_text)
    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        raise RuntimeAuthorizationError(
            f"Runtime status file must be a mapping: {path}",
        )
    return loaded


def load_local_runtime_status(path: str | None = None) -> LocalRuntimeStatus:
    """Load kill-switch and live authorization state from local config."""

    configured_path = Path(
        path
        or os.environ.get("PARALLAX_RUNTIME_STATUS_PATH", "")
        or _default_runtime_status_path(),
    )
    if not configured_path.exists():
        return LocalRuntimeStatus(
            path=str(configured_path),
            exists=False,
            status="missing",
            allow_live_execution=False,
            kill_switch_enabled=False,
            reason="Runtime status file missing; live execution stays disabled.",
        )

    payload = _load_structured_file(configured_path)
    allow_live_execution = _coerce_bool(
        payload.get(
            "allow_live_execution",
            payload.get("live_execution_enabled"),
        ),
    )
    status = str(payload.get("status", "")).strip().lower()
    if not status:
        status = "enabled" if allow_live_execution else "disabled"
    kill_switch_enabled = _coerce_bool(
        payload.get("kill_switch_enabled", payload.get("kill_switch")),
    )
    if status in _BLOCKED_STATUSES:
        kill_switch_enabled = True

    return LocalRuntimeStatus(
        path=str(configured_path),
        exists=True,
        status=status,
        allow_live_execution=allow_live_execution,
        kill_switch_enabled=kill_switch_enabled,
        reason=str(payload.get("reason")).strip() if payload.get("reason") else None,
        updated_at=str(payload.get("updated_at")).strip()
        if payload.get("updated_at")
        else None,
    )


def _normalize_execution_environment(value: str | None, *, default: str) -> str:
    normalized = (value or default or "none").strip().lower()
    if normalized not in {"none", "demo", "live"}:
        logger.warning(
            "Unknown execution environment %s, defaulting to %s",
            value,
            default,
        )
        return default
    return normalized


def _resolve_kalshi_base_url(
    execution_environment: str,
    override: str | None,
) -> str | None:
    if execution_environment == "none":
        return None

    default_url = (
        KALSHI_LIVE_API_BASE_URL
        if execution_environment == "live"
        else KALSHI_DEMO_API_BASE_URL
    )
    candidate = (override or default_url).strip().rstrip("/")
    if execution_environment == "demo" and "demo" not in candidate:
        raise RuntimeAuthorizationError(
            "Demo execution requires a Kalshi demo API base URL.",
        )
    if execution_environment == "live" and "demo" in candidate:
        raise RuntimeAuthorizationError(
            "Live execution cannot use a Kalshi demo API base URL.",
        )
    return candidate


def _resolve_live_authorization_reason(
    *,
    storage: RuntimeConfig,
    runtime_status: LocalRuntimeStatus,
    live_opt_in: bool,
    ack_value: str,
) -> str | None:
    reasons: list[str] = []
    if storage.data_environment != "live":
        reasons.append(
            f"data_environment={storage.data_environment} cannot authorize live execution",
        )
    if not runtime_status.exists:
        reasons.append(f"runtime status file missing at {runtime_status.path}")
    if runtime_status.kill_switch_enabled:
        reasons.append("kill switch engaged")
    if runtime_status.reason:
        reasons.append(runtime_status.reason)
    if runtime_status.exists and not runtime_status.allow_live_execution:
        reasons.append("local runtime status disallows live execution")
    if runtime_status.exists and runtime_status.status not in _ENABLED_STATUSES:
        reasons.append(f"runtime status={runtime_status.status}")
    if not live_opt_in:
        reasons.append("PARALLAX_ENABLE_LIVE_EXECUTION=1 not set")
    if ack_value != LIVE_EXECUTION_ACK:
        reasons.append(
            "PARALLAX_LIVE_EXECUTION_ACK missing required confirmation phrase",
        )
    if not reasons:
        return None
    return "; ".join(dict.fromkeys(reasons))


def _resolve_process_runtime(*, process: str, dry_run: bool = False) -> AppRuntime:
    storage = resolve_runtime_config(dry_run=dry_run)
    runtime_status = load_local_runtime_status()
    requested_execution_environment = _normalize_execution_environment(
        os.environ.get("PARALLAX_EXECUTION_ENV"),
        default=storage.execution_environment,
    )

    if dry_run or storage.data_environment in {"dry_run", "test"}:
        return AppRuntime(
            process=process,
            storage=storage,
            requested_execution_environment="none",
            execution_environment="none",
            kalshi_base_url=None,
            live_execution_requested=False,
            live_execution_authorized=False,
            kill_switch_enabled=runtime_status.kill_switch_enabled,
            authorization_reason=None,
            runtime_status=runtime_status,
        )

    live_requested = requested_execution_environment == "live"
    live_opt_in = _coerce_bool(os.environ.get("PARALLAX_ENABLE_LIVE_EXECUTION"))
    live_ack = os.environ.get("PARALLAX_LIVE_EXECUTION_ACK", "").strip()

    execution_environment = requested_execution_environment
    authorization_reason: str | None = None

    if storage.data_environment == "demo":
        if live_requested:
            execution_environment = "demo"
            authorization_reason = (
                "Demo data environment cannot initialize live execution."
            )
    elif storage.data_environment == "live":
        if requested_execution_environment == "demo":
            execution_environment = "none"
            authorization_reason = (
                "Live data environment cannot fall back to demo execution."
            )
        elif live_requested:
            authorization_reason = _resolve_live_authorization_reason(
                storage=storage,
                runtime_status=runtime_status,
                live_opt_in=live_opt_in,
                ack_value=live_ack,
            )
            if authorization_reason:
                execution_environment = "none"
    else:
        execution_environment = "none"

    if runtime_status.kill_switch_enabled and execution_environment != "none":
        execution_environment = "none"
        authorization_reason = "; ".join(
            part
            for part in [
                authorization_reason,
                "Kill switch engaged by local runtime status.",
            ]
            if part
        )

    kalshi_base_url = _resolve_kalshi_base_url(
        execution_environment,
        os.environ.get("KALSHI_BASE_URL"),
    )

    return AppRuntime(
        process=process,
        storage=storage,
        requested_execution_environment=requested_execution_environment,
        execution_environment=execution_environment,
        kalshi_base_url=kalshi_base_url,
        live_execution_requested=live_requested,
        live_execution_authorized=execution_environment == "live",
        kill_switch_enabled=runtime_status.kill_switch_enabled,
        authorization_reason=authorization_reason,
        runtime_status=runtime_status,
    )


def resolve_api_runtime(*, dry_run: bool = False) -> AppRuntime:
    """Resolve the guarded runtime used by FastAPI startup."""

    return _resolve_process_runtime(process="api", dry_run=dry_run)


def resolve_cli_runtime(*, dry_run: bool = False) -> AppRuntime:
    """Resolve the guarded runtime intended for CLI startup paths."""

    return _resolve_process_runtime(process="cli", dry_run=dry_run)


def build_kalshi_client_config(
    runtime: AppRuntime,
    *,
    api_key: str,
    private_key_path: str,
) -> dict[str, str] | None:
    """Return Kalshi client configuration only when runtime policy allows it."""

    if runtime.execution_environment not in {"demo", "live"}:
        return None
    if not api_key or not private_key_path:
        return None
    return {
        "api_key": api_key,
        "private_key_path": private_key_path,
        "base_url": runtime.kalshi_base_url or KALSHI_DEMO_API_BASE_URL,
    }
