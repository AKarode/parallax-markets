"""Truth Social ingestion via truthbrush library.

Fetches public posts from key political accounts (e.g., @realDonaldTrump),
filters for Iran/Hormuz relevance, and converts to NewsEvent objects.
No authentication required -- reads public posts only.

Trump's Truth Social posts frequently move prediction markets on Iran/war topics.
Capturing these as first-class news events gives prediction models direct access
to executive signals that may precede news coverage by minutes to hours.
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone, timedelta

from truthbrush.api import Api

from parallax.ingestion.google_news import NewsEvent

logger = logging.getLogger(__name__)

# Default accounts to monitor for Iran-relevant posts
TRUTH_SOCIAL_ACCOUNTS = [
    "realDonaldTrump",
]

# Keywords for filtering Iran/Hormuz-relevant posts
IRAN_KEYWORDS = [
    "iran",
    "hormuz",
    "strait",
    "oil",
    "sanctions",
    "ceasefire",
    "nuclear",
    "war",
    "military",
    "persian gulf",
    "middle east",
    "tehran",
]

# Simple regex to strip HTML tags
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _matches_iran_topic(text: str) -> bool:
    """Check if text contains any Iran/Hormuz-relevant keyword."""
    if not text:
        return False
    lowered = text.lower()
    return any(keyword in lowered for keyword in IRAN_KEYWORDS)


def _strip_html(text: str) -> str:
    """Remove HTML tags from text."""
    return _HTML_TAG_RE.sub("", text)


def _parse_created_at(value: str) -> datetime:
    """Parse ISO format datetime from Truth Social post."""
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError, AttributeError):
        return datetime.now(timezone.utc)


async def fetch_truth_social(
    accounts: list[str] | None = None,
    max_age_hours: int = 24,
    seen_hashes: set[str] | None = None,
) -> list[NewsEvent]:
    """Fetch recent Iran-relevant posts from Truth Social accounts.

    Args:
        accounts: Account handles to fetch (defaults to TRUTH_SOCIAL_ACCOUNTS).
        max_age_hours: Only return posts from the last N hours.
        seen_hashes: Set of already-seen event hashes for dedup.

    Returns:
        List of deduplicated NewsEvent objects, newest first.
    """
    if accounts is None:
        accounts = TRUTH_SOCIAL_ACCOUNTS
    if not accounts:
        return []
    if seen_hashes is None:
        seen_hashes = set()

    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    all_events: list[NewsEvent] = []
    local_hashes: set[str] = set(seen_hashes)

    try:
        api = Api()

        for account in accounts:
            try:
                # truthbrush is synchronous; run in thread to avoid blocking event loop
                statuses = await asyncio.to_thread(
                    lambda acct=account: list(
                        api.pull_statuses(acct, created_after=cutoff)
                    )
                )
            except Exception as exc:
                logger.warning(
                    "Failed to fetch Truth Social posts for @%s: %s", account, exc
                )
                continue

            for status in statuses:
                post_id = status.get("id", "")
                raw_content = status.get("content", "")
                created_at_str = status.get("created_at", "")

                if not post_id or not raw_content:
                    continue

                # Strip HTML tags for clean text
                clean_content = _strip_html(raw_content).strip()

                # Filter for Iran relevance
                if not _matches_iran_topic(clean_content):
                    continue

                # Parse timestamp and filter by age
                published_at = _parse_created_at(created_at_str)
                if published_at < cutoff:
                    continue

                # Build canonical URL and check dedup
                url = f"https://truthsocial.com/@{account}/posts/{post_id}"
                event = NewsEvent(
                    title=clean_content[:120].strip(),
                    url=url,
                    source="truth_social",
                    published_at=published_at,
                    snippet=clean_content[:500],
                    query=account,
                )

                if event.event_hash in local_hashes:
                    continue

                local_hashes.add(event.event_hash)
                all_events.append(event)

    except Exception as exc:
        logger.warning("Truth Social ingestion failed: %s", exc)
        return []

    # Sort newest first
    all_events.sort(key=lambda e: e.published_at, reverse=True)
    logger.info(
        "Truth Social: fetched %d events from %d accounts",
        len(all_events),
        len(accounts),
    )
    return all_events
