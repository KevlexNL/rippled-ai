"""Tests for EmailRawIngestService — WO Deliverable A ingest layer."""

import hashlib
import json
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from app.connectors.email.schemas import RawEmailPayload
from app.services.normalization.email_raw_ingest_service import EmailRawIngestService


def _make_payload(**kwargs) -> RawEmailPayload:
    defaults = {
        "message_id": "<msg001@example.com>",
        "from_email": "alice@example.com",
        "from_name": "Alice Smith",
        "to": ["bob@example.com"],
        "cc": [],
        "subject": "Project Update",
        "body_plain": "Hello Bob, I'll send the report by Friday.",
        "date": datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        "direction": "inbound",
    }
    defaults.update(kwargs)
    return RawEmailPayload(**defaults)


class TestEmailRawIngestService:
    def test_creates_raw_signal_ingest(self):
        service = EmailRawIngestService()
        payload = _make_payload()
        ingest = service.create_ingest(payload, provider="imap")
        assert ingest.source_type == "email"
        assert ingest.provider == "imap"
        assert ingest.provider_message_id == "<msg001@example.com>"
        assert ingest.payload_json is not None
        assert ingest.payload_hash is not None
        assert len(ingest.payload_hash) == 64  # SHA256 hex

    def test_payload_hash_deterministic(self):
        service = EmailRawIngestService()
        payload = _make_payload()
        ingest1 = service.create_ingest(payload, provider="imap")
        ingest2 = service.create_ingest(payload, provider="imap")
        assert ingest1.payload_hash == ingest2.payload_hash

    def test_different_payloads_different_hashes(self):
        service = EmailRawIngestService()
        ingest1 = service.create_ingest(
            _make_payload(body_plain="Hello"), provider="imap"
        )
        ingest2 = service.create_ingest(
            _make_payload(body_plain="Goodbye"), provider="imap"
        )
        assert ingest1.payload_hash != ingest2.payload_hash

    def test_received_at_from_payload_date(self):
        service = EmailRawIngestService()
        dt = datetime(2024, 6, 15, 10, 30, 0, tzinfo=timezone.utc)
        payload = _make_payload(date=dt)
        ingest = service.create_ingest(payload, provider="imap")
        assert ingest.received_at == dt

    def test_provider_thread_id_extracted(self):
        service = EmailRawIngestService()
        payload = _make_payload(
            references="<root@example.com> <parent@example.com>"
        )
        ingest = service.create_ingest(payload, provider="imap")
        assert ingest.provider_thread_id == "<root@example.com>"
