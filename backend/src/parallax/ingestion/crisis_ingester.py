"""Crisis event ingester for structured timeline ingestion.

Ingests crisis events from GDELT/Google News into the crisis_events table,
deduplicating by headline similarity to avoid redundant entries.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher

import duckdb

from parallax.ingestion.google_news import NewsEvent

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.85


def _headline_hash(headline: str) -> str:
    """Generate a hash of the normalized headline for fast dedup."""
    normalized = headline.lower().strip()
    return hashlib.md5(normalized.encode()).hexdigest()


def _headlines_similar(headline1: str, headline2: str) -> bool:
    """Check if two headlines are similar enough to be duplicates."""
    ratio = SequenceMatcher(None, headline1.lower(), headline2.lower()).ratio()
    return ratio >= SIMILARITY_THRESHOLD


class CrisisIngester:
    """Ingests and deduplicates crisis events into DuckDB."""

    def __init__(self, conn: duckdb.DuckDBPyConnection) -> None:
        self._conn = conn

    def ingest_events(
        self,
        events: list[NewsEvent],
        category: str = "general",
    ) -> int:
        """Ingest news events as crisis events, deduplicating by headline.

        Args:
            events: List of NewsEvent objects from Google News or GDELT.
            category: Category tag for the events (e.g., 'ceasefire', 'oil', 'military').

        Returns:
            Number of new events inserted.
        """
        inserted = 0
        existing_headlines = self._get_recent_headlines(days=7)

        for event in events:
            if self._is_duplicate(event.title, existing_headlines):
                logger.debug("Skipping duplicate headline: %s", event.title[:50])
                continue

            event_id = str(uuid.uuid4())
            headline_hash = _headline_hash(event.title)

            try:
                self._conn.execute(
                    """
                    INSERT INTO crisis_events
                    (id, event_time, headline, source, category, url, headline_hash, inserted_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        event_id,
                        event.published_at,
                        event.title,
                        event.source,
                        category,
                        event.url,
                        headline_hash,
                        datetime.now(timezone.utc),
                    ],
                )
                inserted += 1
                existing_headlines.append(event.title)
            except Exception:
                logger.exception("Failed to insert crisis event: %s", event.title[:50])

        logger.info("Ingested %d new crisis events (category=%s)", inserted, category)
        return inserted

    def ingest_from_dict(
        self,
        events: list[dict],
        category: str = "general",
    ) -> int:
        """Ingest events from dictionaries (for seed data).

        Args:
            events: List of dicts with 'headline', 'event_time', 'source', and optional 'url'.
            category: Category tag for the events.

        Returns:
            Number of new events inserted.
        """
        news_events = []
        for event in events:
            event_time = event.get("event_time")
            if isinstance(event_time, str):
                event_time = datetime.fromisoformat(event_time.replace("Z", "+00:00"))
            elif event_time is None:
                event_time = datetime.now(timezone.utc)

            news_events.append(
                NewsEvent(
                    title=event["headline"],
                    url=event.get("url", ""),
                    source=event.get("source", "seed"),
                    published_at=event_time,
                    snippet="",
                    query="",
                )
            )
        return self.ingest_events(news_events, category=category)

    def _get_recent_headlines(self, days: int = 7) -> list[str]:
        """Retrieve recent headlines for deduplication."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        rows = self._conn.execute(
            """
            SELECT headline
            FROM crisis_events
            WHERE event_time >= ?
            """,
            [cutoff],
        ).fetchall()
        return [row[0] for row in rows]

    def _is_duplicate(self, headline: str, existing_headlines: list[str]) -> bool:
        """Check if a headline is a duplicate of any existing headline."""
        headline_hash = _headline_hash(headline)
        row = self._conn.execute(
            "SELECT 1 FROM crisis_events WHERE headline_hash = ? LIMIT 1",
            [headline_hash],
        ).fetchone()
        if row:
            return True

        for existing in existing_headlines:
            if _headlines_similar(headline, existing):
                return True
        return False

    def get_event_count(self) -> int:
        """Return total number of crisis events in the table."""
        row = self._conn.execute("SELECT COUNT(*) FROM crisis_events").fetchone()
        return int(row[0]) if row else 0

    def get_latest_event_time(self) -> datetime | None:
        """Return the most recent event time, or None if table is empty."""
        row = self._conn.execute(
            "SELECT MAX(event_time) FROM crisis_events"
        ).fetchone()
        if row and row[0]:
            return row[0]
        return None
