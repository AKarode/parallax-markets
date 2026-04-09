"""Tests for Truth Social ingestion module."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import pytest

from parallax.ingestion.truth_social import (
    fetch_truth_social,
    TRUTH_SOCIAL_ACCOUNTS,
    _matches_iran_topic,
)
from parallax.ingestion.google_news import NewsEvent


class TestMatchesIranTopic:
    def test_matches_iran_keyword(self):
        assert _matches_iran_topic("Iran is in the news today") is True

    def test_matches_hormuz(self):
        assert _matches_iran_topic("Strait of Hormuz shipping blocked") is True

    def test_matches_oil(self):
        assert _matches_iran_topic("Oil prices surge amid tensions") is True

    def test_matches_ceasefire(self):
        assert _matches_iran_topic("Ceasefire talks continue in Oman") is True

    def test_matches_case_insensitive(self):
        assert _matches_iran_topic("IRAN SANCTIONS lifted") is True

    def test_no_match_unrelated(self):
        assert _matches_iran_topic("Great weather in Florida today!") is False

    def test_no_match_empty(self):
        assert _matches_iran_topic("") is False


class TestFetchTruthSocial:
    async def test_empty_accounts_returns_empty(self):
        result = await fetch_truth_social(accounts=[])
        assert result == []

    @patch("parallax.ingestion.truth_social.Api")
    async def test_converts_statuses_to_news_events(self, mock_api_cls):
        now = datetime.now(timezone.utc)
        mock_api = MagicMock()
        mock_api_cls.return_value = mock_api
        mock_api.pull_statuses.return_value = iter([
            {
                "id": "12345",
                "created_at": now.isoformat(),
                "content": "Iran sanctions will be lifted soon. Big deal coming!",
            },
        ])

        result = await fetch_truth_social(accounts=["realDonaldTrump"])

        assert len(result) == 1
        event = result[0]
        assert isinstance(event, NewsEvent)
        assert event.source == "truth_social"
        assert event.query == "realDonaldTrump"
        assert "truthsocial.com/@realDonaldTrump/posts/12345" in event.url
        assert "Iran sanctions" in event.title
        assert "Iran sanctions" in event.snippet

    @patch("parallax.ingestion.truth_social.Api")
    async def test_filters_old_posts(self, mock_api_cls):
        old_time = datetime.now(timezone.utc) - timedelta(hours=48)
        mock_api = MagicMock()
        mock_api_cls.return_value = mock_api
        mock_api.pull_statuses.return_value = iter([
            {
                "id": "99999",
                "created_at": old_time.isoformat(),
                "content": "Iran deal update from yesterday",
            },
        ])

        result = await fetch_truth_social(
            accounts=["realDonaldTrump"], max_age_hours=24
        )
        assert result == []

    @patch("parallax.ingestion.truth_social.Api")
    async def test_dedup_with_seen_hashes(self, mock_api_cls):
        now = datetime.now(timezone.utc)
        mock_api = MagicMock()
        mock_api_cls.return_value = mock_api
        mock_api.pull_statuses.return_value = iter([
            {
                "id": "12345",
                "created_at": now.isoformat(),
                "content": "Iran ceasefire happening now",
            },
        ])

        # Pre-compute the hash that would be generated for this URL
        import hashlib
        url = "https://truthsocial.com/@realDonaldTrump/posts/12345"
        expected_hash = hashlib.md5(url.encode()).hexdigest()

        result = await fetch_truth_social(
            accounts=["realDonaldTrump"],
            seen_hashes={expected_hash},
        )
        assert result == []

    @patch("parallax.ingestion.truth_social.Api")
    async def test_filters_non_iran_posts(self, mock_api_cls):
        now = datetime.now(timezone.utc)
        mock_api = MagicMock()
        mock_api_cls.return_value = mock_api
        mock_api.pull_statuses.return_value = iter([
            {
                "id": "11111",
                "created_at": now.isoformat(),
                "content": "Great golf game today at Mar-a-Lago!",
            },
        ])

        result = await fetch_truth_social(accounts=["realDonaldTrump"])
        assert result == []

    @patch("parallax.ingestion.truth_social.Api")
    async def test_exception_returns_empty_gracefully(self, mock_api_cls):
        mock_api = MagicMock()
        mock_api_cls.return_value = mock_api
        mock_api.pull_statuses.side_effect = Exception("CF blocked")

        result = await fetch_truth_social(accounts=["realDonaldTrump"])
        assert result == []

    @patch("parallax.ingestion.truth_social.Api")
    async def test_snippet_truncated_to_500_chars(self, mock_api_cls):
        now = datetime.now(timezone.utc)
        mock_api = MagicMock()
        mock_api_cls.return_value = mock_api
        long_content = "Iran sanctions " + "x" * 600
        mock_api.pull_statuses.return_value = iter([
            {
                "id": "22222",
                "created_at": now.isoformat(),
                "content": long_content,
            },
        ])

        result = await fetch_truth_social(accounts=["realDonaldTrump"])
        assert len(result) == 1
        assert len(result[0].snippet) <= 500

    @patch("parallax.ingestion.truth_social.Api")
    async def test_title_truncated_to_120_chars(self, mock_api_cls):
        now = datetime.now(timezone.utc)
        mock_api = MagicMock()
        mock_api_cls.return_value = mock_api
        long_content = "Iran deal " + "y" * 200
        mock_api.pull_statuses.return_value = iter([
            {
                "id": "33333",
                "created_at": now.isoformat(),
                "content": long_content,
            },
        ])

        result = await fetch_truth_social(accounts=["realDonaldTrump"])
        assert len(result) == 1
        assert len(result[0].title) <= 120

    @patch("parallax.ingestion.truth_social.Api")
    async def test_sorts_newest_first(self, mock_api_cls):
        now = datetime.now(timezone.utc)
        older = now - timedelta(hours=2)
        mock_api = MagicMock()
        mock_api_cls.return_value = mock_api
        mock_api.pull_statuses.return_value = iter([
            {
                "id": "10001",
                "created_at": older.isoformat(),
                "content": "Iran sanctions update from earlier",
            },
            {
                "id": "10002",
                "created_at": now.isoformat(),
                "content": "Iran ceasefire breaking now",
            },
        ])

        result = await fetch_truth_social(accounts=["realDonaldTrump"])
        assert len(result) == 2
        assert result[0].published_at >= result[1].published_at

    @patch("parallax.ingestion.truth_social.Api")
    async def test_html_tags_stripped_from_title(self, mock_api_cls):
        now = datetime.now(timezone.utc)
        mock_api = MagicMock()
        mock_api_cls.return_value = mock_api
        mock_api.pull_statuses.return_value = iter([
            {
                "id": "44444",
                "created_at": now.isoformat(),
                "content": "<p>Iran <b>sanctions</b> are being reviewed</p>",
            },
        ])

        result = await fetch_truth_social(accounts=["realDonaldTrump"])
        assert len(result) == 1
        assert "<" not in result[0].title
        assert ">" not in result[0].title


class TestConstants:
    def test_default_accounts_include_trump(self):
        assert "realDonaldTrump" in TRUTH_SOCIAL_ACCOUNTS
