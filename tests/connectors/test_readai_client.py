"""Tests for Read.ai API client — WO-RIPPLED-MEETING-BACKFILL.

Verifies OAuth token refresh, meeting list pagination, meeting detail
fetching, and error handling.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestReadAIClient:
    """Read.ai API client unit tests."""

    def test_refresh_token_sends_correct_request(self):
        """Token refresh uses Basic auth with client_id:client_secret."""
        from app.connectors.meeting.readai_client import ReadAIClient

        client = ReadAIClient(
            access_token="old-token",
            refresh_token="refresh-123",
            client_id="cid",
            client_secret="csecret",
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "new-token",
            "refresh_token": "new-refresh",
        }

        with patch("app.connectors.meeting.readai_client.httpx.post", return_value=mock_response) as mock_post:
            client.refresh_access_token()

        assert client.access_token == "new-token"
        assert client.refresh_token == "new-refresh"

        # Verify Basic auth header
        call_kwargs = mock_post.call_args
        assert "Authorization" in call_kwargs.kwargs.get("headers", {}) or "Authorization" in call_kwargs[1].get("headers", {})

    def test_refresh_token_raises_on_failure(self):
        """Token refresh raises on non-200 response."""
        from app.connectors.meeting.readai_client import ReadAIClient, ReadAIAuthError

        client = ReadAIClient(
            access_token="old-token",
            refresh_token="refresh-123",
            client_id="cid",
            client_secret="csecret",
        )

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "invalid grant"

        with patch("app.connectors.meeting.readai_client.httpx.post", return_value=mock_response):
            with pytest.raises(ReadAIAuthError):
                client.refresh_access_token()

    def test_list_meetings_paginates(self):
        """list_meetings follows cursor pagination until no more pages."""
        from app.connectors.meeting.readai_client import ReadAIClient

        client = ReadAIClient(
            access_token="token",
            refresh_token="refresh",
            client_id="cid",
            client_secret="csecret",
        )

        page1 = MagicMock()
        page1.status_code = 200
        page1.json.return_value = {
            "meetings": [{"id": "m1"}, {"id": "m2"}],
            "next_cursor": "cursor-abc",
        }

        page2 = MagicMock()
        page2.status_code = 200
        page2.json.return_value = {
            "meetings": [{"id": "m3"}],
            "next_cursor": None,
        }

        with patch("app.connectors.meeting.readai_client.httpx.get", side_effect=[page1, page2]):
            meetings = client.list_meetings(since_ms=1000)

        assert len(meetings) == 3
        assert [m["id"] for m in meetings] == ["m1", "m2", "m3"]

    def test_list_meetings_retries_on_401(self):
        """list_meetings refreshes token on 401 and retries once."""
        from app.connectors.meeting.readai_client import ReadAIClient

        client = ReadAIClient(
            access_token="expired-token",
            refresh_token="refresh",
            client_id="cid",
            client_secret="csecret",
        )

        unauthorized = MagicMock()
        unauthorized.status_code = 401
        unauthorized.text = "unauthorized"

        success = MagicMock()
        success.status_code = 200
        success.json.return_value = {"meetings": [{"id": "m1"}], "next_cursor": None}

        refresh_resp = MagicMock()
        refresh_resp.status_code = 200
        refresh_resp.json.return_value = {
            "access_token": "new-token",
            "refresh_token": "new-refresh",
        }

        with patch("app.connectors.meeting.readai_client.httpx.get", side_effect=[unauthorized, success]):
            with patch("app.connectors.meeting.readai_client.httpx.post", return_value=refresh_resp):
                meetings = client.list_meetings(since_ms=1000)

        assert len(meetings) == 1
        assert client.access_token == "new-token"

    def test_get_meeting_detail_expands_fields(self):
        """get_meeting_detail requests expanded summary, action_items, transcript."""
        from app.connectors.meeting.readai_client import ReadAIClient

        client = ReadAIClient(
            access_token="token",
            refresh_token="refresh",
            client_id="cid",
            client_secret="csecret",
        )

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "id": "m1",
            "title": "Standup",
            "summary": {"overview": "Discussed tasks"},
            "action_items": [{"text": "Ship feature"}],
            "transcript": {"segments": []},
        }

        with patch("app.connectors.meeting.readai_client.httpx.get", return_value=mock_resp) as mock_get:
            detail = client.get_meeting_detail("m1")

        assert detail["id"] == "m1"
        # Verify expand params were passed
        call_args = mock_get.call_args
        params = call_args.kwargs.get("params", {}) or call_args[1].get("params", {})
        assert "expand[]" in str(params) or "expand" in str(params)


class TestReadAINormalizer:
    """Tests for normalizing Read.ai meeting data to SourceItemCreate."""

    def test_normalise_readai_meeting_creates_source_item(self):
        """Full Read.ai meeting payload normalizes to a SourceItemCreate."""
        from app.connectors.meeting.readai_normalizer import normalise_readai_meeting

        meeting = {
            "id": "meeting-abc-123",
            "title": "Weekly Standup",
            "start_time_ms": 1710000000000,  # 2024-03-09T...
            "end_time_ms": 1710003600000,
            "duration_ms": 3600000,
            "participants": [
                {"name": "Kevin", "email": "kevin@example.com"},
                {"name": "Alice", "email": "alice@external.com"},
            ],
            "summary": {"overview": "Discussed sprint goals"},
            "action_items": [
                {"text": "Ship the feature by Friday", "assignee": "Kevin"},
            ],
            "transcript": {
                "segments": [
                    {"speaker": "Kevin", "text": "Let's ship it", "start_seconds": 0, "end_seconds": 5},
                    {"speaker": "Alice", "text": "Sounds good", "start_seconds": 5, "end_seconds": 10},
                ]
            },
        }

        item, _signal = normalise_readai_meeting(meeting, source_id="src-001")

        assert item.source_type == "meeting"
        assert item.external_id == "meeting-abc-123"
        assert item.source_id == "src-001"
        assert "Kevin" in item.content
        assert "Let's ship it" in item.content
        assert item.occurred_at is not None
        # Action items stored as reference, not ground truth
        assert item.metadata_["reference_action_items"] == meeting["action_items"]
        assert item.metadata_["title"] == "Weekly Standup"
        assert item.metadata_["duration_ms"] == 3600000

    def test_normalise_readai_meeting_without_transcript(self):
        """Meeting with no transcript uses summary as content."""
        from app.connectors.meeting.readai_normalizer import normalise_readai_meeting

        meeting = {
            "id": "meeting-no-transcript",
            "title": "Quick Chat",
            "start_time_ms": 1710000000000,
            "end_time_ms": 1710001800000,
            "duration_ms": 1800000,
            "participants": [{"name": "Kevin", "email": "kevin@example.com"}],
            "summary": {"overview": "Brief catch-up about project status"},
            "action_items": [],
            "transcript": None,
        }

        item, _signal = normalise_readai_meeting(meeting, source_id="src-001")

        assert item.content is not None
        assert "Brief catch-up" in item.content
        assert item.metadata_["reference_action_items"] == []

    def test_normalise_readai_meeting_dedup_key(self):
        """external_id is the Read.ai meeting ID for deduplication."""
        from app.connectors.meeting.readai_normalizer import normalise_readai_meeting

        meeting = {
            "id": "unique-meeting-id",
            "title": "Test",
            "start_time_ms": 1710000000000,
            "participants": [],
            "summary": None,
            "action_items": [],
            "transcript": None,
        }

        item, _signal = normalise_readai_meeting(meeting, source_id="src-001")
        assert item.external_id == "unique-meeting-id"


class TestBackfillTask:
    """Tests for the run_source_backfill Celery task."""

    @patch("app.tasks.get_sync_session")
    def test_backfill_rejects_unknown_source_type(self, mock_session):
        """Backfill task rejects source_type that has no connector."""
        from app.tasks import run_source_backfill

        result = run_source_backfill("user-123", "fax", 90)

        assert result["status"] == "error"
        assert "unsupported" in result["reason"].lower()

    @patch("app.connectors.meeting.readai_backfill.backfill_meetings")
    @patch("app.tasks.get_sync_session")
    def test_backfill_meeting_calls_connector(self, mock_session, mock_backfill):
        """Backfill task delegates to readai backfill for source_type=meeting."""
        from app.tasks import run_source_backfill

        mock_db = MagicMock()
        mock_session.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session.return_value.__exit__ = MagicMock(return_value=False)

        mock_backfill.return_value = {
            "fetched": 10,
            "created": 8,
            "duplicates": 2,
            "errors": 0,
        }

        result = run_source_backfill("user-123", "meeting", 90)

        assert result["status"] == "complete"
        assert result["created"] == 8
        mock_backfill.assert_called_once()

    @patch("app.connectors.meeting.readai_backfill.backfill_meetings")
    @patch("app.tasks.get_sync_session")
    def test_backfill_returns_batch_id(self, mock_session, mock_backfill):
        """Backfill task returns a batch_id for tracking."""
        from app.tasks import run_source_backfill

        mock_db = MagicMock()
        mock_session.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session.return_value.__exit__ = MagicMock(return_value=False)

        mock_backfill.return_value = {
            "fetched": 5,
            "created": 5,
            "duplicates": 0,
            "errors": 0,
            "batch_id": "batch-abc",
        }

        result = run_source_backfill("user-123", "meeting", 30)

        assert "batch_id" in result


class TestBackfillEndpoint:
    """Tests for the BackfillSourceRequest Pydantic model and endpoint logic."""

    def test_backfill_request_validates_source_type(self):
        """BackfillSourceRequest rejects invalid source types."""
        from pydantic import ValidationError
        from app.api.routes.admin import BackfillSourceRequest

        with pytest.raises(ValidationError):
            BackfillSourceRequest(
                user_id="441f9c1f-0000-0000-0000-000000000000",
                source_type="fax",
                days=90,
            )

    def test_backfill_request_accepts_meeting(self):
        """BackfillSourceRequest accepts source_type=meeting."""
        from app.api.routes.admin import BackfillSourceRequest

        req = BackfillSourceRequest(
            user_id="441f9c1f-0000-0000-0000-000000000000",
            source_type="meeting",
            days=90,
        )
        assert req.source_type == "meeting"
        assert req.days == 90

    def test_backfill_request_validates_days_range(self):
        """BackfillSourceRequest rejects days outside 1-365."""
        from pydantic import ValidationError
        from app.api.routes.admin import BackfillSourceRequest

        with pytest.raises(ValidationError):
            BackfillSourceRequest(
                user_id="441f9c1f-0000-0000-0000-000000000000",
                source_type="meeting",
                days=0,
            )

        with pytest.raises(ValidationError):
            BackfillSourceRequest(
                user_id="441f9c1f-0000-0000-0000-000000000000",
                source_type="meeting",
                days=400,
            )

    def test_backfill_request_default_days(self):
        """BackfillSourceRequest defaults to 90 days."""
        from app.api.routes.admin import BackfillSourceRequest

        req = BackfillSourceRequest(
            user_id="441f9c1f-0000-0000-0000-000000000000",
            source_type="meeting",
        )
        assert req.days == 90


class TestBackfillMeetings:
    """Tests for the Read.ai backfill orchestrator."""

    @patch("app.connectors.meeting.readai_backfill._get_readai_client")
    @patch("app.connectors.meeting.readai_backfill.ingest_item")
    def test_backfill_fetches_and_ingests_meetings(self, mock_ingest, mock_get_client):
        """backfill_meetings fetches meetings, normalizes, and ingests."""
        from app.connectors.meeting.readai_backfill import backfill_meetings
        from unittest.mock import MagicMock

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_client.list_meetings.return_value = [
            {"id": "m1", "start_time_ms": 1710000000000},
            {"id": "m2", "start_time_ms": 1710100000000},
        ]

        mock_client.get_meeting_detail.side_effect = [
            {
                "id": "m1",
                "title": "Meeting 1",
                "start_time_ms": 1710000000000,
                "end_time_ms": 1710003600000,
                "duration_ms": 3600000,
                "participants": [{"name": "Kevin", "email": "k@ex.com"}],
                "summary": {"overview": "Discussed X"},
                "action_items": [],
                "transcript": {"segments": [{"speaker": "Kevin", "text": "Hello", "start_seconds": 0, "end_seconds": 1}]},
            },
            {
                "id": "m2",
                "title": "Meeting 2",
                "start_time_ms": 1710100000000,
                "end_time_ms": 1710103600000,
                "duration_ms": 3600000,
                "participants": [{"name": "Alice", "email": "a@ex.com"}],
                "summary": {"overview": "Discussed Y"},
                "action_items": [{"text": "Do Z"}],
                "transcript": None,
            },
        ]

        mock_ingest.return_value = (MagicMock(), True)

        mock_db = MagicMock()
        mock_source = MagicMock()
        mock_source.id = "source-123"
        mock_source.user_id = "user-456"
        mock_source.credentials = {"access_token": "t", "refresh_token": "r", "client_id": "c", "client_secret": "s"}

        result = backfill_meetings(mock_source, days=90, db=mock_db)

        assert result["fetched"] == 2
        assert result["created"] == 2
        assert mock_ingest.call_count == 2

    @patch("app.connectors.meeting.readai_backfill._get_readai_client")
    @patch("app.connectors.meeting.readai_backfill.ingest_item")
    def test_backfill_handles_duplicates(self, mock_ingest, mock_get_client):
        """backfill_meetings counts duplicates correctly."""
        from app.connectors.meeting.readai_backfill import backfill_meetings

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_client.list_meetings.return_value = [{"id": "m1", "start_time_ms": 1710000000000}]
        mock_client.get_meeting_detail.return_value = {
            "id": "m1",
            "title": "Meeting",
            "start_time_ms": 1710000000000,
            "duration_ms": 3600000,
            "participants": [],
            "summary": None,
            "action_items": [],
            "transcript": None,
        }

        # Simulate duplicate — ingest_item returns (None, False)
        mock_ingest.return_value = (None, False)

        mock_db = MagicMock()
        mock_source = MagicMock()
        mock_source.id = "source-123"
        mock_source.user_id = "user-456"
        mock_source.credentials = {"access_token": "t", "refresh_token": "r", "client_id": "c", "client_secret": "s"}

        result = backfill_meetings(mock_source, days=90, db=mock_db)

        assert result["duplicates"] == 1
        assert result["created"] == 0

    @patch("app.connectors.meeting.readai_backfill._get_readai_client")
    @patch("app.connectors.meeting.readai_backfill.ingest_item")
    def test_backfill_logs_progress(self, mock_ingest, mock_get_client, caplog):
        """backfill_meetings logs progress during processing."""
        import logging
        from app.connectors.meeting.readai_backfill import backfill_meetings

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.list_meetings.return_value = [{"id": "m1", "start_time_ms": 1710000000000}]
        mock_client.get_meeting_detail.return_value = {
            "id": "m1", "title": "Test", "start_time_ms": 1710000000000,
            "duration_ms": 1000, "participants": [], "summary": None,
            "action_items": [], "transcript": None,
        }
        mock_ingest.return_value = (MagicMock(), True)

        mock_db = MagicMock()
        mock_source = MagicMock()
        mock_source.id = "source-123"
        mock_source.user_id = "user-456"
        mock_source.credentials = {"access_token": "t", "refresh_token": "r", "client_id": "c", "client_secret": "s"}

        with caplog.at_level(logging.INFO):
            backfill_meetings(mock_source, days=90, db=mock_db)

        log_text = " ".join(caplog.messages)
        assert "backfill" in log_text.lower()
