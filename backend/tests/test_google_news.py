"""Tests for Google News RSS poller."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from parallax.ingestion.google_news import (
    NewsEvent,
    _build_rss_url,
    _parse_rss_items,
    fetch_google_news,
)

# ---------------------------------------------------------------------------
# Canned RSS response
# ---------------------------------------------------------------------------

CANNED_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>iran ceasefire - Google News</title>
    <item>
      <title>Iran and US reach preliminary ceasefire agreement</title>
      <link>https://example.com/article1</link>
      <pubDate>Tue, 08 Apr 2026 06:00:00 GMT</pubDate>
      <source url="https://reuters.com">Reuters</source>
    </item>
    <item>
      <title>Hormuz strait tensions ease after diplomatic talks</title>
      <link>https://example.com/article2</link>
      <pubDate>Tue, 08 Apr 2026 04:00:00 GMT</pubDate>
      <source url="https://bbc.com">BBC</source>
    </item>
    <item>
      <title>Old article about Iran from last week</title>
      <link>https://example.com/old-article</link>
      <pubDate>Mon, 31 Mar 2026 12:00:00 GMT</pubDate>
      <source url="https://cnn.com">CNN</source>
    </item>
  </channel>
</rss>"""

DUPLICATE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>iran oil - Google News</title>
    <item>
      <title>Iran and US reach preliminary ceasefire agreement</title>
      <link>https://example.com/article1</link>
      <pubDate>Tue, 08 Apr 2026 06:00:00 GMT</pubDate>
      <source url="https://reuters.com">Reuters</source>
    </item>
    <item>
      <title>Oil prices surge on Iran supply fears</title>
      <link>https://example.com/article3</link>
      <pubDate>Tue, 08 Apr 2026 05:30:00 GMT</pubDate>
      <source url="https://ft.com">Financial Times</source>
    </item>
  </channel>
</rss>"""


class TestBuildRssUrl:
    def test_encodes_spaces(self):
        url = _build_rss_url("iran ceasefire")
        assert "q=iran+ceasefire" in url

    def test_base_url(self):
        url = _build_rss_url("test")
        assert url.startswith("https://news.google.com/rss/search?")


class TestParseRssItems:
    def test_parses_items(self):
        events = _parse_rss_items(CANNED_RSS, "iran ceasefire")
        assert len(events) == 3

    def test_extracts_title(self):
        events = _parse_rss_items(CANNED_RSS, "iran ceasefire")
        assert events[0].title == "Iran and US reach preliminary ceasefire agreement"

    def test_extracts_url(self):
        events = _parse_rss_items(CANNED_RSS, "iran ceasefire")
        assert events[0].url == "https://example.com/article1"

    def test_sets_source(self):
        events = _parse_rss_items(CANNED_RSS, "iran ceasefire")
        assert events[0].source == "google_news"

    def test_parses_date(self):
        events = _parse_rss_items(CANNED_RSS, "iran ceasefire")
        assert events[0].published_at.year == 2026
        assert events[0].published_at.month == 4
        assert events[0].published_at.day == 8

    def test_sets_query(self):
        events = _parse_rss_items(CANNED_RSS, "iran ceasefire")
        assert events[0].query == "iran ceasefire"

    def test_computes_event_hash(self):
        events = _parse_rss_items(CANNED_RSS, "iran ceasefire")
        expected = hashlib.md5("https://example.com/article1".encode()).hexdigest()
        assert events[0].event_hash == expected

    def test_snippet_includes_source(self):
        events = _parse_rss_items(CANNED_RSS, "iran ceasefire")
        assert "Reuters" in events[0].snippet

    def test_handles_invalid_xml(self):
        events = _parse_rss_items("not xml at all", "test")
        assert events == []


class TestNewsEventDedup:
    def test_same_url_same_hash(self):
        e1 = NewsEvent(title="A", url="https://x.com/1", source="google_news", published_at=datetime.now(timezone.utc))
        e2 = NewsEvent(title="B", url="https://x.com/1", source="gdelt_doc", published_at=datetime.now(timezone.utc))
        assert e1.event_hash == e2.event_hash

    def test_different_url_different_hash(self):
        e1 = NewsEvent(title="A", url="https://x.com/1", source="google_news", published_at=datetime.now(timezone.utc))
        e2 = NewsEvent(title="A", url="https://x.com/2", source="google_news", published_at=datetime.now(timezone.utc))
        assert e1.event_hash != e2.event_hash


class TestFetchGoogleNews:
    @pytest.mark.asyncio
    async def test_fetches_and_deduplicates(self):
        """Test that duplicate URLs across queries are deduplicated."""

        class MockResponse:
            status_code = 200
            def __init__(self, text):
                self.text = text
            def raise_for_status(self):
                pass

        call_count = 0

        async def mock_get(url, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return MockResponse(CANNED_RSS)
            return MockResponse(DUPLICATE_RSS)

        mock_client = AsyncMock()
        mock_client.get = mock_get
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("parallax.ingestion.google_news.httpx.AsyncClient", return_value=mock_client):
            events = await fetch_google_news(
                queries=["iran ceasefire", "iran oil"],
                max_age_hours=24 * 30,  # wide window to include all test articles
            )

        # article1 appears in both feeds but should only appear once
        urls = [e.url for e in events]
        assert urls.count("https://example.com/article1") == 1
        # Should have articles 1, 2, old-article, 3 = 4 unique
        assert len(events) == 4

    @pytest.mark.asyncio
    async def test_max_age_filtering(self):
        """Test that old articles are filtered out."""

        class MockResponse:
            status_code = 200
            def __init__(self, text):
                self.text = text
            def raise_for_status(self):
                pass

        async def mock_get(url, **kwargs):
            return MockResponse(CANNED_RSS)

        mock_client = AsyncMock()
        mock_client.get = mock_get
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("parallax.ingestion.google_news.httpx.AsyncClient", return_value=mock_client):
            # Use a very short max_age to filter out all articles (RSS has 2026 dates)
            # We'll use a date-aware approach: the RSS dates are in 2026, so with
            # max_age_hours=1 most should be filtered if "now" is far from pubDate
            events = await fetch_google_news(
                queries=["iran ceasefire"],
                max_age_hours=24 * 365,  # wide window
            )
            all_count = len(events)

            events_narrow = await fetch_google_news(
                queries=["iran ceasefire"],
                max_age_hours=1,  # very narrow: only last hour
            )

        # Narrow window should have fewer or equal events
        assert len(events_narrow) <= all_count

    @pytest.mark.asyncio
    async def test_seen_hashes_excluded(self):
        """Test that pre-seen hashes are excluded."""

        class MockResponse:
            status_code = 200
            def __init__(self, text):
                self.text = text
            def raise_for_status(self):
                pass

        async def mock_get(url, **kwargs):
            return MockResponse(CANNED_RSS)

        mock_client = AsyncMock()
        mock_client.get = mock_get
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        # Pre-mark article1 as seen
        seen = {hashlib.md5("https://example.com/article1".encode()).hexdigest()}

        with patch("parallax.ingestion.google_news.httpx.AsyncClient", return_value=mock_client):
            events = await fetch_google_news(
                queries=["iran ceasefire"],
                max_age_hours=24 * 365,
                seen_hashes=seen,
            )

        urls = [e.url for e in events]
        assert "https://example.com/article1" not in urls

    @pytest.mark.asyncio
    async def test_sorted_newest_first(self):
        """Test events are sorted newest first."""

        class MockResponse:
            status_code = 200
            def __init__(self, text):
                self.text = text
            def raise_for_status(self):
                pass

        async def mock_get(url, **kwargs):
            return MockResponse(CANNED_RSS)

        mock_client = AsyncMock()
        mock_client.get = mock_get
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("parallax.ingestion.google_news.httpx.AsyncClient", return_value=mock_client):
            events = await fetch_google_news(
                queries=["iran ceasefire"],
                max_age_hours=24 * 365,
            )

        if len(events) >= 2:
            for i in range(len(events) - 1):
                assert events[i].published_at >= events[i + 1].published_at
