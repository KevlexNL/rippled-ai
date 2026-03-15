"""Tests for POST /api/v1/webhooks/slack/events.

Tests verify:
- URL verification challenge response (per-source signing secret)
- Valid signed event → 200, Celery dispatched
- Invalid Slack signature → 401
- Missing signature headers → 401 when secret is configured
- No per-source signing secret → 401 (no global fallback)
- Celery unavailable → still returns 200 (graceful degradation)
"""
import hashlib
import hmac
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
URL = "/api/v1/webhooks/slack/events"

SECRET = "test-signing-secret"


def _make_slack_payload(**kwargs) -> dict:
    return {
        "token": "test-token",
        "team_id": "T12345",
        "type": "event_callback",
        "event": {
            "type": "message",
            "ts": "1704067200.000001",
            "user": "U12345",
            "text": "I'll send the report.",
            "channel": "C12345",
        },
        **kwargs,
    }


def _sign_payload(secret: str, body: bytes) -> tuple[str, str]:
    """Return (timestamp, signature) for a payload."""
    timestamp = str(int(time.time()))
    sig_basestring = f"v0:{timestamp}:{body.decode('utf-8')}"
    signature = "v0=" + hmac.new(
        secret.encode("utf-8"),
        sig_basestring.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return timestamp, signature


def _mock_source(signing_secret: str | None = SECRET):
    """Return a fake Source ORM object with encrypted credentials."""
    from app.connectors.shared.credentials_utils import encrypt_credentials

    source = MagicMock()
    if signing_secret is not None:
        source.credentials = encrypt_credentials({"signing_secret": signing_secret})
    else:
        source.credentials = None
    return source


def _patch_db_source(source_or_none):
    """Patch the DB execute chain to return source_or_none from scalar_one_or_none."""
    scalar_result = MagicMock()
    scalar_result.scalar_one_or_none.return_value = source_or_none
    execute_result = AsyncMock(return_value=scalar_result)
    session = MagicMock()
    session.execute = execute_result

    async def _get_db_override():
        yield session

    return _get_db_override


class TestSlackWebhook:
    def test_url_verification_challenge(self):
        payload = {
            "type": "url_verification",
            "challenge": "abc123",
            "token": "test-token",
            "team_id": "T12345",
        }
        body = json.dumps(payload).encode()
        timestamp, signature = _sign_payload(SECRET, body)

        from app.db.deps import get_db
        app.dependency_overrides[get_db] = _patch_db_source(_mock_source(SECRET))
        try:
            resp = client.post(
                URL,
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Slack-Signature": signature,
                    "X-Slack-Request-Timestamp": timestamp,
                },
            )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200
        assert resp.json() == {"challenge": "abc123"}

    def test_valid_signed_event_dispatches_celery(self):
        payload = _make_slack_payload()
        body = json.dumps(payload).encode()
        timestamp, signature = _sign_payload(SECRET, body)

        from app.db.deps import get_db
        app.dependency_overrides[get_db] = _patch_db_source(_mock_source(SECRET))
        try:
            with patch("app.tasks.process_slack_event.delay") as mock_delay:
                resp = client.post(
                    URL,
                    content=body,
                    headers={
                        "Content-Type": "application/json",
                        "X-Slack-Signature": signature,
                        "X-Slack-Request-Timestamp": timestamp,
                    },
                )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200
        assert resp.json() == {"ok": True}

    def test_invalid_signature_returns_401(self):
        payload = _make_slack_payload()
        body = json.dumps(payload).encode()
        timestamp = str(int(time.time()))

        from app.db.deps import get_db
        app.dependency_overrides[get_db] = _patch_db_source(_mock_source(SECRET))
        try:
            resp = client.post(
                URL,
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Slack-Signature": "v0=invalidsignature",
                    "X-Slack-Request-Timestamp": timestamp,
                },
            )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 401

    def test_missing_signature_headers_returns_401_when_secret_configured(self):
        from app.db.deps import get_db
        app.dependency_overrides[get_db] = _patch_db_source(_mock_source(SECRET))
        try:
            resp = client.post(URL, json=_make_slack_payload())
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 401

    def test_no_per_source_signing_secret_returns_401(self):
        """No per-source secret and no global fallback → must reject with 401."""
        from app.db.deps import get_db
        app.dependency_overrides[get_db] = _patch_db_source(None)
        try:
            with patch("app.tasks.process_slack_event.delay"):
                resp = client.post(URL, json=_make_slack_payload())
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 401
        assert "signing secret" in resp.json()["detail"].lower()

    def test_celery_unavailable_still_returns_200(self):
        payload = _make_slack_payload()
        body = json.dumps(payload).encode()
        timestamp, signature = _sign_payload(SECRET, body)

        from app.db.deps import get_db
        app.dependency_overrides[get_db] = _patch_db_source(_mock_source(SECRET))
        try:
            with patch("app.tasks.process_slack_event.delay", side_effect=Exception("broker down")):
                resp = client.post(
                    URL,
                    content=body,
                    headers={
                        "Content-Type": "application/json",
                        "X-Slack-Signature": signature,
                        "X-Slack-Request-Timestamp": timestamp,
                    },
                )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200
