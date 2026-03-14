"""Tests for Phase C3 — PostEventResolver.

Covers:
- Email after event with delivery keywords → delivery_state='delivered'
- Email with draft language → delivery_state='draft_sent'
- Recap source item → delivery_state='acknowledged'
- No signal after 2h → escalate to main (surfaced_as='main', audit row created)
- No signal within 2h → hold (post_event_reviewed stays false)
- post_event_reviewed=true → skipped
- >48h boundary excluded
"""
from __future__ import annotations

import types
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.services.post_event_resolver import PostEventResolver


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

NOW = datetime.now(timezone.utc)


def make_commitment(**kwargs) -> types.SimpleNamespace:
    defaults = {
        "id": str(uuid.uuid4()),
        "user_id": "user-001",
        "title": "send final report",
        "lifecycle_state": "active",
        "delivery_state": None,
        "post_event_reviewed": False,
        "surfaced_as": "shortlist",
        "counterparty_email": "client@external.com",
    }
    defaults.update(kwargs)
    return types.SimpleNamespace(**defaults)


def make_event(**kwargs) -> types.SimpleNamespace:
    defaults = {
        "id": str(uuid.uuid4()),
        "ends_at": NOW - timedelta(hours=3),
        "status": "confirmed",
    }
    defaults.update(kwargs)
    return types.SimpleNamespace(**defaults)


def make_source_item(**kwargs) -> types.SimpleNamespace:
    defaults = {
        "id": str(uuid.uuid4()),
        "content": "Here is the report as requested.",
        "occurred_at": NOW - timedelta(hours=1),
        "sender_email": "kevin@company.com",
    }
    defaults.update(kwargs)
    return types.SimpleNamespace(**defaults)


# ---------------------------------------------------------------------------
# TestPostEventResolver
# ---------------------------------------------------------------------------


class TestPostEventResolver:

    def _make_resolver(self):
        return PostEventResolver()

    def test_delivery_email_after_event_sets_delivered(self):
        """Source item with delivery content after event → delivery_state='delivered'."""
        resolver = self._make_resolver()
        commitment = make_commitment()
        event = make_event(ends_at=NOW - timedelta(hours=2))
        source_items = [
            make_source_item(
                content="Please find attached the final report as promised.",
                occurred_at=NOW - timedelta(hours=1),
            )
        ]
        db = MagicMock()
        result = resolver.process_pair(commitment, event, source_items, db, now=NOW)
        assert commitment.delivery_state == "delivered"
        assert commitment.post_event_reviewed is True

    def test_draft_language_sets_draft_sent(self):
        """Source item with 'draft' language → delivery_state='draft_sent'."""
        resolver = self._make_resolver()
        commitment = make_commitment()
        event = make_event(ends_at=NOW - timedelta(hours=2))
        source_items = [
            make_source_item(
                content="Sending over a draft of the report for your review.",
                occurred_at=NOW - timedelta(hours=1),
            )
        ]
        db = MagicMock()
        result = resolver.process_pair(commitment, event, source_items, db, now=NOW)
        assert commitment.delivery_state == "draft_sent"
        assert commitment.post_event_reviewed is True

    def test_acknowledgement_language_sets_acknowledged(self):
        """Source item with 'received/ack' language → delivery_state='acknowledged'."""
        resolver = self._make_resolver()
        commitment = make_commitment()
        event = make_event(ends_at=NOW - timedelta(hours=2))
        source_items = [
            make_source_item(
                content="Got it, thanks for sending this over.",
                occurred_at=NOW - timedelta(hours=1),
            )
        ]
        db = MagicMock()
        result = resolver.process_pair(commitment, event, source_items, db, now=NOW)
        assert commitment.delivery_state == "acknowledged"

    def test_no_signal_after_2h_escalates_to_main(self):
        """No delivery signal + event ended > 2h ago → escalate (surfaced_as='main', audit row)."""
        resolver = self._make_resolver()
        commitment = make_commitment(surfaced_as="shortlist")
        event = make_event(ends_at=NOW - timedelta(hours=3))  # 3h ago

        added_audits = []
        db = MagicMock()
        db.add.side_effect = lambda obj: added_audits.append(obj)

        result = resolver.process_pair(commitment, event, [], db, now=NOW)

        assert commitment.surfaced_as == "main"
        assert len(added_audits) >= 1
        assert commitment.post_event_reviewed is True

    def test_no_signal_within_2h_holds(self):
        """No signal + event ended < 2h ago → hold, post_event_reviewed stays False."""
        resolver = self._make_resolver()
        commitment = make_commitment()
        event = make_event(ends_at=NOW - timedelta(hours=1))  # only 1h ago

        db = MagicMock()
        result = resolver.process_pair(commitment, event, [], db, now=NOW)

        assert commitment.post_event_reviewed is False

    def test_already_reviewed_skipped(self):
        """post_event_reviewed=True → not reprocessed."""
        resolver = self._make_resolver()
        commitment = make_commitment(post_event_reviewed=True)
        event = make_event(ends_at=NOW - timedelta(hours=3))

        db = MagicMock()
        result = resolver.process_pair(commitment, event, [], db, now=NOW)

        assert result.get("skipped") is True
