"""Tests for Slack thread enrichment — WO-RIPPLED-SLACK-THREAD-ENRICHMENT."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.connectors.shared.normalized_signal import (
    NormalizedParticipant,
    NormalizedSignal,
    Participant,
)
from app.connectors.slack.normalizer import enrich_signal_with_thread
from app.connectors.slack.thread_enricher import ThreadEnricher
from app.models.enums import Direction, ParticipantRole


def _make_signal(**kwargs) -> NormalizedSignal:
    """Build a minimal NormalizedSignal for testing."""
    defaults = dict(
        signal_id="1704067300.000002",
        source_type="slack",
        source_thread_id="1704067200.000001",
        source_message_id="1704067300.000002",
        occurred_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        authored_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        actor_participants=[Participant(name="U111", role="sender")],
        latest_authored_text="Got it, will do.",
        provider="slack",
        direction=Direction.inbound,
        is_inbound=True,
    )
    defaults.update(kwargs)
    return NormalizedSignal(**defaults)


class TestEnrichSignalWithThread:
    def test_enrich_sets_prior_context(self):
        """Mock a 3-message thread, verify prior_context_text is built correctly."""
        thread_messages = [
            {"ts": "1704067200.000001", "user": "Alice", "text": "Can you send the report?"},
            {"ts": "1704067250.000001", "user": "Bob", "text": "Which one?"},
            {"ts": "1704067300.000002", "user": "Alice", "text": "Got it, will do."},
        ]
        signal = _make_signal()
        enriched = enrich_signal_with_thread(signal, thread_messages)

        expected = "[Alice]: Can you send the report?\n[Bob]: Which one?"
        assert enriched.prior_context_text == expected

    def test_enrich_sets_thread_position(self):
        """Verify thread_position matches current message index (0-based)."""
        thread_messages = [
            {"ts": "1704067200.000001", "user": "Alice", "text": "Hello"},
            {"ts": "1704067250.000001", "user": "Bob", "text": "Hi"},
            {"ts": "1704067300.000002", "user": "Alice", "text": "Got it, will do."},
        ]
        signal = _make_signal()
        enriched = enrich_signal_with_thread(signal, thread_messages)

        assert enriched.thread_position == 2

    def test_enrich_empty_thread(self):
        """Signal unchanged when thread_messages is empty."""
        signal = _make_signal(prior_context_text="existing context", thread_position=5)
        enriched = enrich_signal_with_thread(signal, [])

        assert enriched.prior_context_text == "existing context"
        assert enriched.thread_position == 5

    def test_enrich_first_message_in_thread(self):
        """First message has no prior context, position 0."""
        thread_messages = [
            {"ts": "1704067200.000001", "user": "Alice", "text": "Hello"},
            {"ts": "1704067250.000001", "user": "Bob", "text": "Hi"},
        ]
        signal = _make_signal(source_message_id="1704067200.000001")
        enriched = enrich_signal_with_thread(signal, thread_messages)

        assert enriched.thread_position == 0
        assert enriched.prior_context_text is None


class TestThreadEnricher:
    def test_fetch_thread_returns_messages(self):
        """ThreadEnricher parses Slack API response into ordered message list."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            "messages": [
                {"ts": "1704067200.000001", "user": "U111", "text": "Start"},
                {"ts": "1704067300.000002", "user": "U222", "text": "Reply"},
            ],
        }

        with patch("app.connectors.slack.thread_enricher.httpx.get", return_value=mock_response):
            enricher = ThreadEnricher(bot_token="xoxb-test-token")
            result = enricher.fetch_thread("C12345", "1704067200.000001")

        assert len(result) == 2
        assert result[0] == {"ts": "1704067200.000001", "user": "U111", "text": "Start"}
        assert result[1] == {"ts": "1704067300.000002", "user": "U222", "text": "Reply"}

    def test_handles_api_error(self):
        """Enricher returns [] when Slack API raises an exception."""
        with patch(
            "app.connectors.slack.thread_enricher.httpx.get",
            side_effect=httpx.HTTPError("connection failed"),
        ):
            enricher = ThreadEnricher(bot_token="xoxb-test-token")
            result = enricher.fetch_thread("C12345", "1704067200.000001")

        assert result == []

    def test_handles_rate_limit(self):
        """Enricher returns [] on 429 response."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.json.return_value = {"ok": False, "error": "ratelimited"}

        with patch("app.connectors.slack.thread_enricher.httpx.get", return_value=mock_response):
            enricher = ThreadEnricher(bot_token="xoxb-test-token")
            result = enricher.fetch_thread("C12345", "1704067200.000001")

        assert result == []

    def test_caches_thread_within_instance(self):
        """Second call for same thread_ts returns cached result without API call."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            "messages": [{"ts": "1704067200.000001", "user": "U111", "text": "Cached"}],
        }

        with patch("app.connectors.slack.thread_enricher.httpx.get", return_value=mock_response) as mock_get:
            enricher = ThreadEnricher(bot_token="xoxb-test-token")
            result1 = enricher.fetch_thread("C12345", "1704067200.000001")
            result2 = enricher.fetch_thread("C12345", "1704067200.000001")

        assert result1 == result2
        assert mock_get.call_count == 1
