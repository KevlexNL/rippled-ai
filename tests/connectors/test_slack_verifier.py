"""Tests for app/connectors/slack/verifier.py"""

import hashlib
import hmac
import time

import pytest

from app.connectors.slack.verifier import verify_slack_signature


def _make_valid_signature(secret: str, timestamp: str, body: bytes) -> str:
    """Generate a valid Slack HMAC-SHA256 signature for testing."""
    sig_basestring = f"v0:{timestamp}:{body.decode('utf-8')}"
    return "v0=" + hmac.new(
        secret.encode("utf-8"),
        sig_basestring.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


class TestVerifySlackSignature:
    def test_valid_signature_recent_timestamp(self):
        secret = "test-signing-secret"
        body = b'{"type": "event_callback"}'
        timestamp = str(int(time.time()))
        sig = _make_valid_signature(secret, timestamp, body)
        assert verify_slack_signature(secret, timestamp, body, sig) is True

    def test_invalid_signature_returns_false(self):
        secret = "test-signing-secret"
        body = b'{"type": "event_callback"}'
        timestamp = str(int(time.time()))
        assert verify_slack_signature(secret, timestamp, body, "v0=invalidsignature") is False

    def test_stale_timestamp_returns_false(self):
        secret = "test-signing-secret"
        body = b'{"type": "event_callback"}'
        # 400 seconds ago — beyond 300s replay window
        old_timestamp = str(int(time.time()) - 400)
        sig = _make_valid_signature(secret, old_timestamp, body)
        assert verify_slack_signature(secret, old_timestamp, body, sig) is False

    def test_empty_signing_secret_raises_value_error(self):
        with pytest.raises(ValueError, match="not configured"):
            verify_slack_signature("", "123456", b"body", "v0=sig")

    def test_non_integer_timestamp_returns_false(self):
        assert verify_slack_signature("secret", "not-a-number", b"body", "v0=sig") is False

    def test_tampered_body_fails_verification(self):
        secret = "test-signing-secret"
        body = b'{"type": "event_callback"}'
        timestamp = str(int(time.time()))
        sig = _make_valid_signature(secret, timestamp, body)
        # Different body content should fail
        different_body = b'{"type": "tampered"}'
        assert verify_slack_signature(secret, timestamp, different_body, sig) is False
