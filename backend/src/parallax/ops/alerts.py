"""Alert hooks for critical runtime events."""

from __future__ import annotations

import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol

import duckdb
import httpx

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AlertEvent:
    """Structured alert payload for local logging and optional webhooks."""

    event_type: str
    severity: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )


class AlertSink(Protocol):
    """Minimal sink contract for alert delivery."""

    async def send(self, event: AlertEvent) -> None:
        """Deliver one alert event."""


class LoggerAlertSink:
    """Alert sink backed by standard application logging."""

    _LEVELS = {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warning": logging.WARNING,
        "error": logging.ERROR,
        "critical": logging.CRITICAL,
    }

    async def send(self, event: AlertEvent) -> None:
        logger.log(
            self._LEVELS.get(event.severity.lower(), logging.INFO),
            "ops_alert type=%s message=%s details=%s",
            event.event_type,
            event.message,
            event.details,
        )


@dataclass
class WebhookAlertSink:
    """HTTP webhook sink for external operational alerting."""

    url: str
    timeout_seconds: float = 3.0

    async def send(self, event: AlertEvent) -> None:
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                self.url,
                json={
                    "event_type": event.event_type,
                    "severity": event.severity,
                    "message": event.message,
                    "details": event.details,
                    "timestamp": event.timestamp,
                },
            )
            response.raise_for_status()


@dataclass
class MockWebhookAlertSink:
    """Mock sink that logs webhook-bound alerts without external I/O."""

    target: str

    async def send(self, event: AlertEvent) -> None:
        logger.info(
            "mock_webhook_alert target=%s type=%s severity=%s details=%s",
            self.target,
            event.event_type,
            event.severity,
            event.details,
        )


@dataclass
class DuckDBAlertSink:
    """Persist operational alerts into DuckDB for later inspection."""

    db_conn: duckdb.DuckDBPyConnection
    run_id: str | None = None

    async def send(self, event: AlertEvent) -> None:
        self.db_conn.execute(
            """
            INSERT INTO ops_events (
                event_id,
                run_id,
                event_type,
                severity,
                message,
                details
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                str(uuid.uuid4()),
                self.run_id,
                event.event_type,
                event.severity,
                event.message,
                json.dumps(event.details),
            ],
        )


@dataclass
class AlertDispatcher:
    """Dispatch alerts to one or more sinks, isolating sink failures."""

    sinks: list[AlertSink]

    async def emit(
        self,
        *,
        event_type: str,
        severity: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> AlertEvent:
        event = AlertEvent(
            event_type=event_type,
            severity=severity,
            message=message,
            details=details or {},
        )
        for sink in self.sinks:
            try:
                await sink.send(event)
            except Exception:
                logger.exception(
                    "Alert sink failed for type=%s sink=%s",
                    event.event_type,
                    sink.__class__.__name__,
                )
        return event


def build_alert_dispatcher(
    db_conn: duckdb.DuckDBPyConnection | None = None,
    run_id: str | None = None,
) -> AlertDispatcher:
    """Create the default alert dispatcher for API/CLI entrypoints."""

    sinks: list[AlertSink] = [LoggerAlertSink()]
    if db_conn is not None:
        sinks.append(DuckDBAlertSink(db_conn=db_conn, run_id=run_id))
    webhook_url = os.environ.get("PARALLAX_ALERT_WEBHOOK_URL", "").strip()
    if webhook_url:
        if webhook_url.startswith("mock://"):
            sinks.append(MockWebhookAlertSink(target=webhook_url))
        else:
            sinks.append(WebhookAlertSink(url=webhook_url))
    return AlertDispatcher(sinks=sinks)
