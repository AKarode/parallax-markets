"""GDELT ingestion: BigQuery fetch + 4-stage noise filter.

Stages:
1. Volume gate — filter low-signal events unless entity-override matches
2. Structural dedup — collapse actor+action+target within 1-hour windows
3. Relevance scoring — weight events by Goldstein scale & source diversity
4. Semantic dedup — handled separately in dedup.py
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from parallax.ingestion.entities import matches_critical_entity

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Stage 1: Volume gate
# ---------------------------------------------------------------------------

def volume_gate(
    event: dict[str, Any],
    min_mentions: int = 3,
    min_sources: int = 2,
    check_entity_override: bool = False,
) -> bool:
    """Return True if *event* passes the volume threshold or entity override."""
    mentions = event.get("NumMentions", 0)
    sources = event.get("NumSources", 0)

    if mentions > min_mentions and sources > min_sources:
        return True

    if check_entity_override:
        searchable = " ".join(
            str(event.get(k, ""))
            for k in ("Actor1Name", "Actor2Name", "summary", "ActionGeo_FullName")
        )
        if matches_critical_entity(searchable):
            return True

    return False


# ---------------------------------------------------------------------------
# Stage 2: Structural dedup — actor+action+target in 1-hour window
# ---------------------------------------------------------------------------

def _structural_key(event: dict[str, Any]) -> str:
    """Deterministic key from actor pair + action code."""
    parts = [
        str(event.get("Actor1Code", "")),
        str(event.get("EventCode", "")),
        str(event.get("Actor2Code", "")),
    ]
    return hashlib.md5("|".join(parts).encode()).hexdigest()


def structural_dedup(
    events: list[dict[str, Any]],
    window_hours: int = 1,
) -> list[dict[str, Any]]:
    """Collapse events with the same actor+action+target within *window_hours*.

    Within each window, the event with the most mentions is kept.
    """
    if len(events) <= 1:
        return list(events)

    def _event_time(ev: dict[str, Any]) -> datetime:
        raw = ev.get("DateAdded") or ev.get("DATEADDED") or ""
        if isinstance(raw, datetime):
            return raw
        raw_str = str(raw).strip()
        if not raw_str:
            return datetime.min.replace(tzinfo=timezone.utc)
        try:
            if len(raw_str) == 14:  # YYYYMMDDHHMMSS
                return datetime.strptime(raw_str, "%Y%m%d%H%M%S").replace(
                    tzinfo=timezone.utc
                )
            return datetime.fromisoformat(raw_str).replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            return datetime.min.replace(tzinfo=timezone.utc)

    # Sort by time for windowing
    sorted_events = sorted(events, key=_event_time)

    seen: dict[str, tuple[datetime, dict[str, Any]]] = {}
    kept: list[dict[str, Any]] = []
    window = timedelta(hours=window_hours)

    for ev in sorted_events:
        key = _structural_key(ev)
        ev_time = _event_time(ev)

        if key in seen:
            prev_time, prev_ev = seen[key]
            if ev_time - prev_time <= window:
                # Keep the one with more mentions
                if ev.get("NumMentions", 0) > prev_ev.get("NumMentions", 0):
                    # Replace previous with this one
                    kept = [e for e in kept if e is not prev_ev]
                    kept.append(ev)
                    seen[key] = (ev_time, ev)
                continue  # Skip this duplicate

        seen[key] = (ev_time, ev)
        kept.append(ev)

    return kept


# ---------------------------------------------------------------------------
# Stage 3: Relevance scoring
# ---------------------------------------------------------------------------

def relevance_score(event: dict[str, Any]) -> float:
    """Score 0..1 combining Goldstein scale, source diversity, and entity match.

    Components (each 0..1, weighted):
    - goldstein:  abs(GoldsteinScale) / 10, capped  (weight 0.3)
    - sources:    min(NumSources / 15, 1.0)          (weight 0.3)
    - entity:     1.0 if critical entity else 0.0     (weight 0.4)
    """
    goldstein = min(abs(event.get("GoldsteinScale", 0)) / 10.0, 1.0)
    sources = min(event.get("NumSources", 0) / 15.0, 1.0)

    searchable = " ".join(
        str(event.get(k, ""))
        for k in ("Actor1Name", "Actor2Name", "summary", "ActionGeo_FullName")
    )
    entity = 1.0 if matches_critical_entity(searchable) else 0.0

    return round(0.3 * goldstein + 0.3 * sources + 0.4 * entity, 4)


# ---------------------------------------------------------------------------
# Full pipeline (for use by the scheduler)
# ---------------------------------------------------------------------------

async def fetch_gdelt_events(
    bq_client: Any,
    query: str,
    *,
    min_mentions: int = 3,
    min_sources: int = 2,
) -> list[dict[str, Any]]:
    """Fetch from BigQuery, apply volume gate + structural dedup + scoring.

    Semantic dedup (stage 4) is handled separately.
    """
    import asyncio

    rows = await asyncio.to_thread(
        lambda: [dict(row) for row in bq_client.query(query).result()]
    )
    logger.info("GDELT: fetched %d raw rows", len(rows))

    # Stage 1 — volume gate with entity override
    gated = [
        ev for ev in rows
        if volume_gate(ev, min_mentions, min_sources, check_entity_override=True)
    ]
    logger.info("GDELT: %d after volume gate", len(gated))

    # Stage 2 — structural dedup
    deduped = structural_dedup(gated)
    logger.info("GDELT: %d after structural dedup", len(deduped))

    # Stage 3 — relevance scoring
    for ev in deduped:
        ev["relevance_score"] = relevance_score(ev)

    return deduped
