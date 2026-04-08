"""GDELT DOC 2.0 API poller for structured geopolitical events.

Direct HTTP access to GDELT's article database. No API key needed.
~15-60 min latency, but provides structured themes, tone, entities.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import datetime, timezone

import httpx

from parallax.ingestion.google_news import NewsEvent

logger = logging.getLogger(__name__)

GDELT_DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"

# Queries targeting Iran/Hormuz crisis
DOC_QUERIES = [
    "iran ceasefire",
    "hormuz strait",
    "iran oil",
    "iran nuclear",
    "iran war military",
]


def _parse_seendate(date_str: str) -> datetime:
    """Parse GDELT seendate format: '20260408T063000Z'."""
    try:
        return datetime.strptime(date_str, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return datetime.now(timezone.utc)


def _parse_articles(data: dict, query: str) -> list[NewsEvent]:
    """Parse GDELT DOC API JSON response into NewsEvent objects."""
    events = []
    articles = data.get("articles", [])

    for article in articles:
        url = article.get("url", "")
        title = article.get("title", "")
        if not url or not title:
            continue

        seendate = article.get("seendate", "")
        published_at = _parse_seendate(seendate) if seendate else datetime.now(timezone.utc)

        domain = article.get("domain", "")
        language = article.get("language", "")
        country = article.get("sourcecountry", "")

        snippet_parts = []
        if domain:
            snippet_parts.append(f"Via {domain}")
        if country:
            snippet_parts.append(f"({country})")
        if language and language != "English":
            snippet_parts.append(f"[{language}]")

        events.append(
            NewsEvent(
                title=title.strip(),
                url=url.strip(),
                source="gdelt_doc",
                published_at=published_at,
                snippet=" ".join(snippet_parts),
                query=query,
            )
        )

    return events


async def fetch_gdelt_docs(
    queries: list[str] | None = None,
    max_records: int = 50,
    timespan: str = "24h",
    seen_hashes: set[str] | None = None,
) -> list[NewsEvent]:
    """Fetch articles from GDELT DOC 2.0 API.

    Args:
        queries: Search terms (defaults to DOC_QUERIES).
        max_records: Max articles per query.
        timespan: GDELT timespan parameter (e.g., "24h", "1h", "15min").
        seen_hashes: Already-seen hashes for dedup.

    Returns:
        List of deduplicated NewsEvent objects, newest first.
    """
    if queries is None:
        queries = DOC_QUERIES
    if seen_hashes is None:
        seen_hashes = set()

    all_events: list[NewsEvent] = []
    local_hashes: set[str] = set(seen_hashes)

    async with httpx.AsyncClient(timeout=30.0) as client:
        for i, query in enumerate(queries):
            # Rate limit: ~1 request per second
            if i > 0:
                await asyncio.sleep(1.0)

            params = {
                "query": query,
                "mode": "artlist",
                "maxrecords": str(max_records),
                "timespan": timespan,
                "format": "json",
            }

            try:
                resp = await client.get(GDELT_DOC_API, params=params, follow_redirects=True)
                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPError as exc:
                logger.warning("GDELT DOC fetch failed for query=%s: %s", query, exc)
                continue
            except ValueError:
                logger.warning("GDELT DOC returned invalid JSON for query=%s", query)
                continue

            items = _parse_articles(data, query)

            for item in items:
                if item.event_hash in local_hashes:
                    continue
                local_hashes.add(item.event_hash)
                all_events.append(item)

    # Sort newest first
    all_events.sort(key=lambda e: e.published_at, reverse=True)
    logger.info("GDELT DOC: fetched %d events from %d queries", len(all_events), len(queries))
    return all_events
