"""Tests for GDELT DOC 2.0 API poller."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from parallax.ingestion.gdelt_doc import (
    _parse_seendate,
    _parse_articles,
    fetch_gdelt_docs,
)
from parallax.ingestion.google_news import NewsEvent

# ---------------------------------------------------------------------------
# Canned GDELT DOC API response
# ---------------------------------------------------------------------------

CANNED_RESPONSE = {
    "articles": [
        {
            "url": "https://reuters.com/iran-talks-2026",
            "title": "Iran ceasefire talks enter final round",
            "seendate": "20260408T063000Z",
            "domain": "reuters.com",
            "language": "English",
            "sourcecountry": "United States",
        },
        {
            "url": "https://bbc.com/hormuz-shipping",
            "title": "Shipping resumes through Strait of Hormuz",
            "seendate": "20260408T050000Z",
            "domain": "bbc.com",
            "language": "English",
            "sourcecountry": "United Kingdom",
        },
        {
            "url": "https://aljazeera.com/iran-oil",
            "title": "Oil prices stabilize as Iran tensions ease",
            "seendate": "20260407T230000Z",
            "domain": "aljazeera.com",
            "language": "English",
            "sourcecountry": "Qatar",
        },
    ]
}

CANNED_RESPONSE_2 = {
    "articles": [
        {
            "url": "https://reuters.com/iran-talks-2026",
            "title": "Iran ceasefire talks enter final round (updated)",
            "seendate": "20260408T070000Z",
            "domain": "reuters.com",
            "language": "English",
            "sourcecountry": "United States",
        },
        {
            "url": "https://ft.com/oil-surge",
            "title": "Brent crude jumps on supply fears",
            "seendate": "20260408T060000Z",
            "domain": "ft.com",
            "language": "English",
            "sourcecountry": "United Kingdom",
        },
    ]
}


class TestParseSeendate:
    def test_valid_date(self):
        dt = _parse_seendate("20260408T063000Z")
        assert dt.year == 2026
        assert dt.month == 4
        assert dt.day == 8
        assert dt.hour == 6
        assert dt.minute == 30
        assert dt.tzinfo == timezone.utc

    def test_invalid_date_returns_now(self):
        dt = _parse_seendate("not-a-date")
        assert dt.tzinfo == timezone.utc
        # Should be close to now
        diff = abs((datetime.now(timezone.utc) - dt).total_seconds())
        assert diff < 5

    def test_empty_string(self):
        dt = _parse_seendate("")
        assert dt.tzinfo == timezone.utc


class TestParseArticles:
    def test_parses_articles(self):
        events = _parse_articles(CANNED_RESPONSE, "iran ceasefire")
        assert len(events) == 3

    def test_extracts_title(self):
        events = _parse_articles(CANNED_RESPONSE, "iran ceasefire")
        assert events[0].title == "Iran ceasefire talks enter final round"

    def test_extracts_url(self):
        events = _parse_articles(CANNED_RESPONSE, "iran ceasefire")
        assert events[0].url == "https://reuters.com/iran-talks-2026"

    def test_sets_source_gdelt_doc(self):
        events = _parse_articles(CANNED_RESPONSE, "iran ceasefire")
        assert all(e.source == "gdelt_doc" for e in events)

    def test_parses_seendate(self):
        events = _parse_articles(CANNED_RESPONSE, "iran ceasefire")
        assert events[0].published_at.year == 2026
        assert events[0].published_at.month == 4

    def test_sets_query(self):
        events = _parse_articles(CANNED_RESPONSE, "hormuz strait")
        assert all(e.query == "hormuz strait" for e in events)

    def test_snippet_includes_domain(self):
        events = _parse_articles(CANNED_RESPONSE, "test")
        assert "reuters.com" in events[0].snippet

    def test_snippet_includes_country(self):
        events = _parse_articles(CANNED_RESPONSE, "test")
        assert "United States" in events[0].snippet

    def test_computes_event_hash(self):
        events = _parse_articles(CANNED_RESPONSE, "test")
        expected = hashlib.md5("https://reuters.com/iran-talks-2026".encode()).hexdigest()
        assert events[0].event_hash == expected

    def test_empty_articles(self):
        events = _parse_articles({"articles": []}, "test")
        assert events == []

    def test_missing_articles_key(self):
        events = _parse_articles({}, "test")
        assert events == []

    def test_skips_missing_url(self):
        data = {"articles": [{"title": "No URL article"}]}
        events = _parse_articles(data, "test")
        assert events == []

    def test_skips_missing_title(self):
        data = {"articles": [{"url": "https://x.com/1"}]}
        events = _parse_articles(data, "test")
        assert events == []


class TestFetchGdeltDocs:
    @pytest.mark.asyncio
    async def test_fetches_and_deduplicates(self):
        """Test that duplicate URLs across queries are deduplicated."""

        class MockResponse:
            status_code = 200
            def __init__(self, data):
                self._data = data
            def raise_for_status(self):
                pass
            def json(self):
                return self._data

        call_count = 0

        async def mock_get(url, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return MockResponse(CANNED_RESPONSE)
            return MockResponse(CANNED_RESPONSE_2)

        mock_client = AsyncMock()
        mock_client.get = mock_get
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("parallax.ingestion.gdelt_doc.httpx.AsyncClient", return_value=mock_client):
            with patch("parallax.ingestion.gdelt_doc.asyncio.sleep", new_callable=AsyncMock):
                events = await fetch_gdelt_docs(
                    queries=["iran ceasefire", "iran oil"],
                )

        # reuters.com/iran-talks-2026 appears in both, should be deduped
        urls = [e.url for e in events]
        assert urls.count("https://reuters.com/iran-talks-2026") == 1
        # Total unique: 3 from first + 1 new from second = 4
        assert len(events) == 4

    @pytest.mark.asyncio
    async def test_seen_hashes_excluded(self):
        """Test that pre-seen hashes are excluded."""

        class MockResponse:
            status_code = 200
            def __init__(self, data):
                self._data = data
            def raise_for_status(self):
                pass
            def json(self):
                return self._data

        async def mock_get(url, **kwargs):
            return MockResponse(CANNED_RESPONSE)

        mock_client = AsyncMock()
        mock_client.get = mock_get
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        seen = {hashlib.md5("https://reuters.com/iran-talks-2026".encode()).hexdigest()}

        with patch("parallax.ingestion.gdelt_doc.httpx.AsyncClient", return_value=mock_client):
            with patch("parallax.ingestion.gdelt_doc.asyncio.sleep", new_callable=AsyncMock):
                events = await fetch_gdelt_docs(
                    queries=["iran ceasefire"],
                    seen_hashes=seen,
                )

        urls = [e.url for e in events]
        assert "https://reuters.com/iran-talks-2026" not in urls
        assert len(events) == 2

    @pytest.mark.asyncio
    async def test_sorted_newest_first(self):
        """Test events are sorted newest first."""

        class MockResponse:
            status_code = 200
            def __init__(self, data):
                self._data = data
            def raise_for_status(self):
                pass
            def json(self):
                return self._data

        async def mock_get(url, **kwargs):
            return MockResponse(CANNED_RESPONSE)

        mock_client = AsyncMock()
        mock_client.get = mock_get
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("parallax.ingestion.gdelt_doc.httpx.AsyncClient", return_value=mock_client):
            with patch("parallax.ingestion.gdelt_doc.asyncio.sleep", new_callable=AsyncMock):
                events = await fetch_gdelt_docs(queries=["iran ceasefire"])

        for i in range(len(events) - 1):
            assert events[i].published_at >= events[i + 1].published_at

    @pytest.mark.asyncio
    async def test_handles_http_error(self):
        """Test graceful handling of HTTP errors."""
        import httpx

        async def mock_get(url, **kwargs):
            raise httpx.HTTPError("Connection failed")

        mock_client = AsyncMock()
        mock_client.get = mock_get
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("parallax.ingestion.gdelt_doc.httpx.AsyncClient", return_value=mock_client):
            with patch("parallax.ingestion.gdelt_doc.asyncio.sleep", new_callable=AsyncMock):
                events = await fetch_gdelt_docs(queries=["iran ceasefire"])

        assert events == []

    @pytest.mark.asyncio
    async def test_rate_limiting(self):
        """Test that sleep is called between queries for rate limiting."""

        class MockResponse:
            status_code = 200
            def raise_for_status(self):
                pass
            def json(self):
                return {"articles": []}

        async def mock_get(url, **kwargs):
            return MockResponse()

        mock_client = AsyncMock()
        mock_client.get = mock_get
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        mock_sleep = AsyncMock()

        with patch("parallax.ingestion.gdelt_doc.httpx.AsyncClient", return_value=mock_client):
            with patch("parallax.ingestion.gdelt_doc.asyncio.sleep", mock_sleep):
                await fetch_gdelt_docs(queries=["q1", "q2", "q3"])

        # Sleep should be called between queries (not before the first one)
        assert mock_sleep.call_count == 2
        mock_sleep.assert_any_call(1.0)
