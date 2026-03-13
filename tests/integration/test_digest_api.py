"""Integration tests for Phase C2 — Daily Digest API endpoints.

Endpoints tested:
- POST /api/v1/digest/trigger
- GET  /api/v1/digest/log
- GET  /api/v1/digest/preview

Uses real Supabase DB via the conftest.py fixtures.
All test data is scoped to a unique test user and cleaned up via CASCADE.
"""
from __future__ import annotations

import pytest


# Re-use the shared integration conftest fixtures:
#   client, test_user_id, test_user_headers


API = "/api/v1"


# ---------------------------------------------------------------------------
# POST /digest/trigger
# ---------------------------------------------------------------------------

class TestDigestTrigger:
    def test_trigger_returns_200(self, client, test_user_headers):
        response = client.post(f"{API}/digest/trigger", headers=test_user_headers)
        assert response.status_code == 200

    def test_trigger_returns_status_field(self, client, test_user_headers):
        response = client.post(f"{API}/digest/trigger", headers=test_user_headers)
        data = response.json()
        assert "status" in data
        assert data["status"] in ("sent", "skipped", "failed")

    def test_trigger_returns_commitment_count(self, client, test_user_headers):
        response = client.post(f"{API}/digest/trigger", headers=test_user_headers)
        data = response.json()
        assert "commitment_count" in data
        assert isinstance(data["commitment_count"], int)

    def test_trigger_returns_message_field(self, client, test_user_headers):
        response = client.post(f"{API}/digest/trigger", headers=test_user_headers)
        data = response.json()
        assert "message" in data

    def test_trigger_requires_user_id_header(self, client):
        response = client.post(f"{API}/digest/trigger")
        assert response.status_code == 422

    def test_trigger_skips_when_no_commitments(self, client, test_user_headers):
        """With a fresh test user, there are no surfaced commitments — digest is skipped."""
        response = client.post(f"{API}/digest/trigger", headers=test_user_headers)
        data = response.json()
        # Fresh user has no commitments — should be skipped or sent with 0 items
        assert data["status"] in ("skipped", "sent")


# ---------------------------------------------------------------------------
# GET /digest/log
# ---------------------------------------------------------------------------

class TestDigestLog:
    def test_log_returns_200(self, client, test_user_headers):
        response = client.get(f"{API}/digest/log", headers=test_user_headers)
        assert response.status_code == 200

    def test_log_returns_list(self, client, test_user_headers):
        response = client.get(f"{API}/digest/log", headers=test_user_headers)
        data = response.json()
        assert isinstance(data, list)

    def test_log_requires_user_id_header(self, client):
        response = client.get(f"{API}/digest/log")
        assert response.status_code == 422

    def test_log_entries_have_expected_fields(self, client, test_user_headers):
        """Trigger a digest first, then check the log entry shape."""
        client.post(f"{API}/digest/trigger", headers=test_user_headers)
        response = client.get(f"{API}/digest/log", headers=test_user_headers)
        data = response.json()
        if data:
            entry = data[0]
            assert "sent_at" in entry
            assert "status" in entry
            assert "commitment_count" in entry
            assert "delivery_method" in entry

    def test_log_returns_at_most_10_entries(self, client, test_user_headers):
        response = client.get(f"{API}/digest/log", headers=test_user_headers)
        data = response.json()
        assert len(data) <= 10


# ---------------------------------------------------------------------------
# GET /digest/preview
# ---------------------------------------------------------------------------

class TestDigestPreview:
    def test_preview_returns_200(self, client, test_user_headers):
        response = client.get(f"{API}/digest/preview", headers=test_user_headers)
        assert response.status_code == 200

    def test_preview_returns_digest_structure(self, client, test_user_headers):
        response = client.get(f"{API}/digest/preview", headers=test_user_headers)
        data = response.json()
        assert "main" in data
        assert "shortlist" in data
        assert "clarifications" in data
        assert "generated_at" in data

    def test_preview_main_is_list(self, client, test_user_headers):
        response = client.get(f"{API}/digest/preview", headers=test_user_headers)
        data = response.json()
        assert isinstance(data["main"], list)

    def test_preview_does_not_write_to_digest_log(self, client, test_user_headers):
        """Preview must be read-only — no DigestLog rows created."""
        # Count logs before
        before = client.get(f"{API}/digest/log", headers=test_user_headers).json()
        before_count = len(before)

        # Call preview
        client.get(f"{API}/digest/preview", headers=test_user_headers)

        # Count logs after
        after = client.get(f"{API}/digest/log", headers=test_user_headers).json()
        after_count = len(after)

        assert after_count == before_count

    def test_preview_requires_user_id_header(self, client):
        response = client.get(f"{API}/digest/preview")
        assert response.status_code == 422

    def test_preview_includes_subject_when_not_empty(self, client, test_user_headers):
        response = client.get(f"{API}/digest/preview", headers=test_user_headers)
        data = response.json()
        # subject may be None if empty digest, or a string
        assert "subject" in data
