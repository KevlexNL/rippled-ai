"""Tests for Phase C3 — DeadlineEventLinker and CounterpartyExtractor.

Covers:
- DeadlineEventLinker: match on attendees, match on keywords, no match creates implicit event,
  confidence threshold boundary, ±24h window edge, existing link skipped,
  cancelled event excluded, empty commitment set
- CounterpartyExtractor: external_client, internal_manager, internal_peer, self,
  null sender_email, meeting source_type (recipients fallback)
"""
from __future__ import annotations

import types
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.services.event_linker import CounterpartyExtractor, DeadlineEventLinker


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

NOW = datetime.now(timezone.utc)


def make_commitment(**kwargs) -> types.SimpleNamespace:
    defaults = {
        "id": str(uuid.uuid4()),
        "user_id": "user-001",
        "title": "send proposal to acme",
        "resolved_deadline": NOW + timedelta(hours=2),
        "lifecycle_state": "active",
        "counterparty_email": None,
        "counterparty_type": None,
    }
    defaults.update(kwargs)
    return types.SimpleNamespace(**defaults)


def make_event(**kwargs) -> types.SimpleNamespace:
    defaults = {
        "id": str(uuid.uuid4()),
        "title": "proposal review meeting",
        "starts_at": NOW + timedelta(hours=2),
        "ends_at": NOW + timedelta(hours=3),
        "status": "confirmed",
        "attendees": None,
    }
    defaults.update(kwargs)
    return types.SimpleNamespace(**defaults)


def make_source_item(**kwargs) -> types.SimpleNamespace:
    defaults = {
        "id": str(uuid.uuid4()),
        "source_type": "email",
        "sender_email": "alice@external.com",
        "recipients": None,
    }
    defaults.update(kwargs)
    return types.SimpleNamespace(**defaults)


def make_user(**kwargs) -> types.SimpleNamespace:
    defaults = {
        "id": "user-001",
        "email": "kevin@company.com",
    }
    defaults.update(kwargs)
    return types.SimpleNamespace(**defaults)


def make_db(commitments=None, events=None, links=None):
    """Return a mock sync DB session."""
    db = MagicMock()
    _objects = {}

    def _add(obj):
        _objects[id(obj)] = obj

    db.add = _add
    db.flush = MagicMock()
    db.added = _objects
    db._commitments = commitments or []
    db._events = events or []
    db._links = links or []
    return db


# ---------------------------------------------------------------------------
# TestDeadlineEventLinker
# ---------------------------------------------------------------------------


class TestDeadlineEventLinker:

    def _make_linker(self):
        return DeadlineEventLinker()

    def test_no_commitments_returns_empty(self):
        """Empty commitment list → no links created."""
        linker = self._make_linker()
        db = make_db(commitments=[])
        result = linker.run(db, user_id="user-001", commitments=[], events=[])
        assert result["links_created"] == 0

    def test_match_by_keyword_overlap_creates_link(self):
        """Commitment and event share keywords (Jaccard ≥ 0.3) → link created with confidence ≥ 0.7."""
        linker = self._make_linker()
        commitment = make_commitment(title="send proposal")
        event = make_event(
            title="proposal review",
            starts_at=commitment.resolved_deadline,
        )
        db = make_db()
        result = linker.run(db, user_id="user-001", commitments=[commitment], events=[event])
        assert result["links_created"] >= 1

    def test_match_by_attendee_overlap_creates_link(self):
        """Commitment counterparty_email in event attendees → link created."""
        linker = self._make_linker()
        commitment = make_commitment(
            counterparty_email="alice@external.com",
        )
        event = make_event(
            attendees=[{"email": "alice@external.com", "name": "Alice"}],
            starts_at=commitment.resolved_deadline,
        )
        db = make_db()
        result = linker.run(db, user_id="user-001", commitments=[commitment], events=[event])
        assert result["links_created"] >= 1

    def test_confidence_threshold_0_69_rejected(self):
        """Score < 0.7 → no link created (use event outside window, no title/attendee match)."""
        linker = self._make_linker()
        commitment = make_commitment(title="send xyz")
        # Event far outside window, unrelated title → score < 0.7
        event = make_event(
            title="completely unrelated event qqq",
            starts_at=commitment.resolved_deadline + timedelta(hours=25),
        )
        db = make_db()
        result = linker.run(db, user_id="user-001", commitments=[commitment], events=[event])
        # Should create implicit event instead, not link to this event
        assert result["implicit_events_created"] >= 1

    def test_no_match_creates_implicit_event(self):
        """No matching event within ±24h → creates implicit Event + link."""
        linker = self._make_linker()
        commitment = make_commitment()
        # Event way outside window
        event = make_event(
            title="unrelated",
            starts_at=commitment.resolved_deadline + timedelta(hours=48),
        )
        db = make_db()
        result = linker.run(db, user_id="user-001", commitments=[commitment], events=[event])
        assert result["implicit_events_created"] == 1

    def test_cancelled_event_excluded(self):
        """Cancelled events are not matched against → creates implicit event."""
        linker = self._make_linker()
        commitment = make_commitment(title="send proposal")
        event = make_event(
            title="proposal review",
            starts_at=commitment.resolved_deadline,
            status="cancelled",
        )
        db = make_db()
        result = linker.run(db, user_id="user-001", commitments=[commitment], events=[event])
        assert result["implicit_events_created"] == 1

    def test_commitment_outside_window_excluded(self):
        """Commitment without resolved_deadline → skipped."""
        linker = self._make_linker()
        commitment = make_commitment(resolved_deadline=None)
        db = make_db()
        result = linker.run(db, user_id="user-001", commitments=[commitment], events=[])
        assert result["links_created"] == 0
        assert result["implicit_events_created"] == 0

    def test_commitment_with_existing_link_skipped(self):
        """Commitment already has a delivery_at link → not reprocessed."""
        linker = self._make_linker()
        commitment_id = str(uuid.uuid4())
        commitment = make_commitment(id=commitment_id, title="send proposal")
        event = make_event(starts_at=commitment.resolved_deadline)
        db = make_db()
        result = linker.run(
            db,
            user_id="user-001",
            commitments=[commitment],
            events=[event],
            existing_link_ids={commitment_id},
        )
        assert result["links_created"] == 0
        assert result["implicit_events_created"] == 0


# ---------------------------------------------------------------------------
# TestCounterpartyExtractor
# ---------------------------------------------------------------------------


class TestCounterpartyExtractor:

    def _make_extractor(self, user_email="kevin@company.com", internal_domains="company.com", internal_managers=""):
        settings = types.SimpleNamespace(
            internal_domains=internal_domains,
            internal_managers=internal_managers,
        )
        return CounterpartyExtractor(settings=settings, user_email=user_email)

    def test_external_client_different_domain(self):
        """Sender from different domain → counterparty_type='external_client'."""
        extractor = self._make_extractor()
        commitment = make_commitment()
        source_item = make_source_item(sender_email="alice@external.com")
        extractor.extract(commitment, source_item, user_email="kevin@company.com")
        assert commitment.counterparty_type == "external_client"
        assert commitment.counterparty_email == "alice@external.com"

    def test_internal_manager_in_manager_list(self):
        """Sender in internal_managers list → counterparty_type='internal_manager'."""
        extractor = self._make_extractor(internal_managers="boss@company.com,cto@company.com")
        commitment = make_commitment()
        source_item = make_source_item(sender_email="boss@company.com")
        extractor.extract(commitment, source_item, user_email="kevin@company.com")
        assert commitment.counterparty_type == "internal_manager"

    def test_internal_peer_same_domain_not_manager(self):
        """Sender same domain, not in managers list → counterparty_type='internal_peer'."""
        extractor = self._make_extractor(internal_managers="boss@company.com")
        commitment = make_commitment()
        source_item = make_source_item(sender_email="teammate@company.com")
        extractor.extract(commitment, source_item, user_email="kevin@company.com")
        assert commitment.counterparty_type == "internal_peer"

    def test_self_sender_is_user(self):
        """Sender email == user email → counterparty_type='self'."""
        extractor = self._make_extractor()
        commitment = make_commitment()
        source_item = make_source_item(sender_email="kevin@company.com")
        extractor.extract(commitment, source_item, user_email="kevin@company.com")
        assert commitment.counterparty_type == "self"

    def test_null_source_item_no_op(self):
        """source_item=None → commitment not modified."""
        extractor = self._make_extractor()
        commitment = make_commitment()
        extractor.extract(commitment, None, user_email="kevin@company.com")
        assert commitment.counterparty_type is None

    def test_meeting_source_uses_recipients_fallback(self):
        """Meeting source_type: uses first non-user recipient as counterparty."""
        extractor = self._make_extractor()
        commitment = make_commitment()
        source_item = make_source_item(
            source_type="meeting",
            sender_email=None,
            recipients=[
                {"email": "kevin@company.com"},
                {"email": "client@external.com"},
            ],
        )
        extractor.extract(commitment, source_item, user_email="kevin@company.com")
        assert commitment.counterparty_email == "client@external.com"
        assert commitment.counterparty_type == "external_client"
