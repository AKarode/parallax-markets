"""Google News RSS poller for real-time geopolitical events.

Polls RSS feeds every N minutes, deduplicates, returns structured events.
No API key required. ~5-15 min latency from event to article.
"""

from __future__ import annotations

import hashlib
import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

import httpx

logger = logging.getLogger(__name__)

# RSS feed URLs for Iran/Hormuz/oil topics
FEED_QUERIES = [
    "iran ceasefire",
    "iran hormuz strait",
    "iran oil sanctions",
    "iran nuclear deal",
    "iran war",
    "oil price brent crude",
    "strait of hormuz shipping",
]


@dataclass
class NewsEvent:
    """A single news event from RSS or GDELT DOC API."""

    title: str
    url: str
    source: str  # "google_news", "gdelt_doc"
    published_at: datetime
    snippet: str = ""
    query: str = ""  # which search query matched
    event_hash: str = ""  # for dedup

    def __post_init__(self):
        if not self.event_hash:
            self.event_hash = hashlib.md5(self.url.encode()).hexdigest()


def _build_rss_url(query: str) -> str:
    """Build Google News RSS URL for a search query."""
    encoded = query.replace(" ", "+")
    return f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"


def _parse_rss_items(xml_text: str, query: str) -> list[NewsEvent]:
    """Parse RSS XML text into NewsEvent objects."""
    events = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        logger.warning("Failed to parse RSS XML for query=%s", query)
        return events

    for item in root.iter("item"):
        title_el = item.find("title")
        link_el = item.find("link")
        pub_date_el = item.find("pubDate")
        source_el = item.find("source")

        if title_el is None or link_el is None:
            continue

        title = title_el.text or ""
        url = link_el.text or ""
        snippet = ""

        # Parse publication date (RFC 2822 format)
        published_at = datetime.now(timezone.utc)
        if pub_date_el is not None and pub_date_el.text:
            try:
                published_at = parsedate_to_datetime(pub_date_el.text)
                if published_at.tzinfo is None:
                    published_at = published_at.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                pass

        source_name = ""
        if source_el is not None and source_el.text:
            source_name = source_el.text

        if source_name and title:
            snippet = f"Via {source_name}"

        events.append(
            NewsEvent(
                title=title.strip(),
                url=url.strip(),
                source="google_news",
                published_at=published_at,
                snippet=snippet,
                query=query,
            )
        )

    return events


async def fetch_google_news(
    queries: list[str] | None = None,
    max_age_hours: int = 24,
    seen_hashes: set[str] | None = None,
) -> list[NewsEvent]:
    """Fetch recent news from Google News RSS feeds.

    Args:
        queries: Search queries (defaults to FEED_QUERIES).
        max_age_hours: Only return articles from the last N hours.
        seen_hashes: Set of already-seen event hashes for dedup.

    Returns:
        List of deduplicated NewsEvent objects, newest first.
    """
    if queries is None:
        queries = FEED_QUERIES
    if seen_hashes is None:
        seen_hashes = set()

    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    all_events: list[NewsEvent] = []
    local_hashes: set[str] = set(seen_hashes)

    async with httpx.AsyncClient(timeout=15.0) as client:
        for query in queries:
            url = _build_rss_url(query)
            try:
                resp = await client.get(url, follow_redirects=True)
                resp.raise_for_status()
            except httpx.HTTPError as exc:
                logger.warning("Failed to fetch RSS for query=%s: %s", query, exc)
                continue

            items = _parse_rss_items(resp.text, query)

            for item in items:
                # Dedup by URL hash
                if item.event_hash in local_hashes:
                    continue
                # Filter by age
                if item.published_at < cutoff:
                    continue
                local_hashes.add(item.event_hash)
                all_events.append(item)

    # Sort newest first
    all_events.sort(key=lambda e: e.published_at, reverse=True)
    logger.info("Google News: fetched %d events from %d queries", len(all_events), len(queries))
    return all_events
