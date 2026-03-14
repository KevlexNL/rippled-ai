"""Tests for Phase C3 — NudgeService.

Covers:
- Correct selection of commitments with delivery_at event in next 25h
- shortlist → main promotion with SurfacingAudit log
- Already-main commitment: no duplicate audit row
- delivered state skipped
- draft_sent state skipped
"""
from __future__ import annotations

import types
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.services.nudge import NudgeService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

NOW = datetime.now(timezone.utc)


def make_commitment(**kwargs) -> types.SimpleNamespace:
    defaults = {
        "id": str(uuid.uuid4()),
        "user_id": "user-001",
        "title": "send report",
        "lifecycle_state": "active",
        "surfaced_as": "shortlist",
        "delivery_state": None,
        "priority_score": Decimal("45"),
        "counterparty_type": None,
    }
    defaults.update(kwargs)
    return types.SimpleNamespace(**defaults)


def make_event(**kwargs) -> types.SimpleNamespace:
    defaults = {
        "id": str(uuid.uuid4()),
        "starts_at": NOW + timedelta(hours=12),
        "status": "confirmed",
    }
    defaults.update(kwargs)
    return types.SimpleNamespace(**defaults)


# ---------------------------------------------------------------------------
# TestNudgeService
# ---------------------------------------------------------------------------


class TestNudgeService:

    def _make_service(self):
        return NudgeService()

    def test_shortlist_promoted_to_main(self):
        """Commitment on shortlist with delivery_at event in next 25h → promoted to main."""
        service = self._make_service()
        commitment = make_commitment(surfaced_as="shortlist")
        event = make_event(starts_at=NOW + timedelta(hours=12))

        added_audits = []
        db = MagicMock()
        db.add.side_effect = lambda obj: added_audits.append(obj)

        result = service.process_commitment(commitment, event, db)

        assert commitment.surfaced_as == "main"
        assert result["promoted"] is True
        # Audit row was created
        assert len(added_audits) == 1

    def test_already_main_no_audit_row(self):
        """Commitment already on main → surfaced_as unchanged, no audit created."""
        service = self._make_service()
        commitment = make_commitment(surfaced_as="main")
        event = make_event(starts_at=NOW + timedelta(hours=12))

        added_audits = []
        db = MagicMock()
        db.add.side_effect = lambda obj: added_audits.append(obj)

        result = service.process_commitment(commitment, event, db)

        assert commitment.surfaced_as == "main"
        assert result["promoted"] is False
        assert len(added_audits) == 0

    def test_delivered_state_skipped(self):
        """Commitment with delivery_state='delivered' → skipped."""
        service = self._make_service()
        commitment = make_commitment(delivery_state="delivered")
        event = make_event()

        result = service.process_commitment(commitment, event, MagicMock())
        assert result["skipped"] is True

    def test_draft_sent_state_skipped(self):
        """Commitment with delivery_state='draft_sent' → skipped (already delivered in part)."""
        service = self._make_service()
        commitment = make_commitment(delivery_state="draft_sent")
        event = make_event()

        result = service.process_commitment(commitment, event, MagicMock())
        assert result["skipped"] is True

    def test_closed_no_delivery_skipped(self):
        """Commitment with delivery_state='closed_no_delivery' → skipped."""
        service = self._make_service()
        commitment = make_commitment(delivery_state="closed_no_delivery")
        event = make_event()

        result = service.process_commitment(commitment, event, MagicMock())
        assert result["skipped"] is True
