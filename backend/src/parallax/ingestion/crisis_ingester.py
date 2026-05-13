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
        # Batch hash check: one query for all incoming hashes instead of N queries
        incoming_hashes: dict[str, str] = {}
        for event in events:
            incoming_hashes[_headline_hash(event.title)] = event.title

        existing_hashes: set[str] = set()
        if incoming_hashes:
            rows = self._conn.execute(
                "SELECT headline_hash FROM crisis_events WHERE headline_hash IN ({})".format(
                    ",".join("?" for _ in incoming_hashes),
                ),
                list(incoming_hashes.keys()),
            ).fetchall()
            existing_hashes = {row[0] for row in rows}

        # Fuzzy dedup: look back 21 days (was 7) to catch rephrased headlines
        fuzzy_candidate_headlines = self._get_recent_headlines(days=21)

        inserted = 0
        for event in events:
            headline_hash = _headline_hash(event.title)

            if headline_hash in existing_hashes:
                logger.debug("Skipping duplicate headline (hash match): %s", event.title[:50])
                continue

            if any(_headlines_similar(event.title, existing) for existing in fuzzy_candidate_headlines):
                logger.debug("Skipping similar headline: %s", event.title[:50])
                continue

            event_id = str(uuid.uuid4())

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
                fuzzy_candidate_headlines.append(event.title)
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
