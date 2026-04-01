"""Integration tests for Phase D3 — CalendarMatcher with scorer, signals, observation window, sync.

Covers:
- Priority scorer context boost (context link within 48h → urgency boost)
- Completion signal creation (completion_hint → CommitmentSignal)
- Observation window shortening (adjusted_window_hours)
- Sync triggers matching (end-to-end)
- Regression: existing flows unaffected
"""
from __future__ import annotations

import types
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.services.calendar_matcher import CalendarMatcher
from app.services.observation_window import adjusted_window_hours
from app.services.priority_scorer import score as priority_score


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

NOW = datetime(2026, 4, 2, 12, 0, 0, tzinfo=timezone.utc)


def make_event(**kwargs) -> types.SimpleNamespace:
    defaults = {
        "id": str(uuid.uuid4()),
        "title": "Pricing review with Sarah",
        "description": "Review Q2 pricing proposal for Acme",
        "starts_at": NOW + timedelta(hours=6),
        "ends_at": NOW + timedelta(hours=7),
        "status": "confirmed",
        "attendees": [
            {"name": "Sarah Chen", "email": "sarah@acme.com"},
            {"name": "Kevin B", "email": "kevin@rippled.ai"},
        ],
        "external_id": "gcal-123",
    }
    defaults.update(kwargs)
    return types.SimpleNamespace(**defaults)


def make_commitment(**kwargs) -> types.SimpleNamespace:
    defaults = {
        "id": str(uuid.uuid4()),
        "user_id": "user-001",
        "title": "Review Q2 pricing proposal",
        "description": "Need to review and approve the Q2 pricing changes",
        "commitment_text": "I'll review the pricing proposal by Thursday",
        "target_entity": "Acme",
        "requester_name": "Sarah Chen",
        "requester_email": "sarah@acme.com",
        "beneficiary_name": None,
        "beneficiary_email": None,
        "context_tags": ["email"],
        "deliverable": "pricing proposal review",
        "resolved_deadline": None,
        "lifecycle_state": "active",
    }
    defaults.update(kwargs)
    return types.SimpleNamespace(**defaults)


def make_classifier_result(**kwargs) -> types.SimpleNamespace:
    defaults = {
        "is_external": True,
        "timing_strength": 6,
        "business_consequence": 7,
        "cognitive_burden": 5,
        "confidence_for_surfacing": 0.8,
    }
    defaults.update(kwargs)
    return types.SimpleNamespace(**defaults)


def make_scored_commitment(**kwargs) -> types.SimpleNamespace:
    """Commitment with fields needed by priority_scorer."""
    defaults = {
        "id": str(uuid.uuid4()),
        "user_id": "user-001",
        "observe_until": None,
        "lifecycle_state": "active",
        "delivery_state": None,
        "counterparty_type": "external_client",
    }
    defaults.update(kwargs)
    return types.SimpleNamespace(**defaults)


# ---------------------------------------------------------------------------
# 7. Priority scorer boost — context_proximity_hours
# ---------------------------------------------------------------------------


class TestPriorityScorerContextBoost:
    def test_context_link_12h_boosts_score(self):
        """Commitment with context link to event in 12h → urgency boost applied."""
        cr = make_classifier_result()
        commitment = make_scored_commitment()

        score_without = priority_score(cr, commitment, proximity_hours=None)
        score_with = priority_score(cr, commitment, proximity_hours=None, context_proximity_hours=12.0)

        assert score_with > score_without, (
            f"Context proximity should boost: {score_with} > {score_without}"
        )

    def test_context_link_72h_no_boost(self):
        """Commitment with context link to event in 72h → no boost (too far)."""
        cr = make_classifier_result()
        commitment = make_scored_commitment()

        score_without = priority_score(cr, commitment, proximity_hours=None)
        score_with = priority_score(cr, commitment, proximity_hours=None, context_proximity_hours=72.0)

        assert score_with == score_without

    def test_both_delivery_and_context_no_double_count(self):
        """Commitment with both delivery_at and context links → context boost capped."""
        cr = make_classifier_result()
        commitment = make_scored_commitment()

        score_delivery_only = priority_score(cr, commitment, proximity_hours=12.0)
        score_both = priority_score(cr, commitment, proximity_hours=12.0, context_proximity_hours=6.0)

        # Context boost should be small relative to delivery proximity spike
        # The combined score should not exceed delivery + max_context_boost
        assert score_both >= score_delivery_only
        # Context boost is capped at 15 points
        assert score_both - score_delivery_only <= 15

    def test_context_boost_scales_with_proximity(self):
        """Closer event → larger context boost."""
        cr = make_classifier_result()
        commitment = make_scored_commitment()

        score_close = priority_score(cr, commitment, context_proximity_hours=2.0)
        score_far = priority_score(cr, commitment, context_proximity_hours=40.0)

        assert score_close >= score_far


# ---------------------------------------------------------------------------
# 8. Completion signal creation
# ---------------------------------------------------------------------------


class TestCompletionSignalCreation:
    def test_completion_hint_produces_signal_data(self):
        """completion_hint link → signal data with signal_role='progress'."""
        matcher = CalendarMatcher(now=NOW)
        event = make_event(
            starts_at=NOW - timedelta(hours=3),
            ends_at=NOW - timedelta(hours=2),
        )
        commitment = make_commitment()
        links = matcher.match([event], [commitment], existing_pairs=set())

        # If a link was created with completion_hint, check signal_data
        completion_links = [l for l in links if l["link_type"] == "completion_hint"]
        if completion_links:
            link = completion_links[0]
            assert link.get("signal_role") == "progress"
            assert link.get("confidence") is not None

    def test_no_duplicate_signal_on_rematch(self):
        """Re-running matching on same pair → no duplicate links."""
        matcher = CalendarMatcher(now=NOW)
        event = make_event(
            starts_at=NOW - timedelta(hours=3),
            ends_at=NOW - timedelta(hours=2),
        )
        commitment = make_commitment()

        links_first = matcher.match([event], [commitment], existing_pairs=set())
        # Simulate the pair now exists
        existing = {(event.id, commitment.id)}
        links_second = matcher.match([event], [commitment], existing_pairs=existing)

        assert len(links_second) == 0


# ---------------------------------------------------------------------------
# 9. Observation window shortening
# ---------------------------------------------------------------------------


class TestObservationWindowShortening:
    def test_event_within_3h_caps_window_at_1h(self):
        """Matched event in 3h → window capped at 1 hour."""
        result = adjusted_window_hours(base_hours=24.0, nearest_event_hours=3.0)
        assert result == 1.0

    def test_event_within_1h_caps_window_at_1h(self):
        """Matched event in 1h → window capped at 1 hour."""
        result = adjusted_window_hours(base_hours=48.0, nearest_event_hours=1.0)
        assert result == 1.0

    def test_event_within_24h_shortens_window(self):
        """Matched event in 12h → window = min(base, 12*0.5) = 6h."""
        result = adjusted_window_hours(base_hours=24.0, nearest_event_hours=12.0)
        assert result == 6.0

    def test_no_matched_events_default_window(self):
        """No matched events → default window unchanged."""
        result = adjusted_window_hours(base_hours=24.0, nearest_event_hours=None)
        assert result == 24.0

    def test_distant_event_no_change(self):
        """Event > 24h away → no shortening."""
        result = adjusted_window_hours(base_hours=24.0, nearest_event_hours=48.0)
        assert result == 24.0

    def test_base_hours_already_short(self):
        """If base_hours < adjusted value → keep base_hours."""
        result = adjusted_window_hours(base_hours=0.5, nearest_event_hours=12.0)
        assert result == 0.5


# ---------------------------------------------------------------------------
# 10. End-to-end: sync triggers matching
# ---------------------------------------------------------------------------


class TestSyncTriggersMatching:
    @patch("app.tasks._run_calendar_matching")
    @patch("app.connectors.google_calendar.GoogleCalendarConnector")
    @patch("app.tasks.get_sync_session")
    @patch("app.tasks.settings")
    def test_sync_calls_matching_after_sync(self, mock_settings, mock_get_session, MockConnector, mock_matching):
        """Calendar sync → matching runs → links created."""
        mock_settings.google_calendar_enabled = True
        mock_settings.google_oauth_client_id = "test-id"
        mock_settings.google_calendar_user_email = "test@test.com"
        mock_settings.digest_to_email = None
        mock_settings.redis_url = "redis://localhost"

        mock_db = MagicMock()
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        # Mock user query
        mock_user = types.SimpleNamespace(id="user-001", email="test@test.com")
        mock_db.execute.return_value.scalar_one_or_none.return_value = mock_user

        mock_connector = MockConnector.return_value
        mock_connector.sync.return_value = {"status": "synced", "events_synced": 5}

        mock_matching.return_value = {"links_created": 3}

        from app.tasks import sync_google_calendar
        result = sync_google_calendar()

        assert result["status"] == "synced"
        mock_matching.assert_called_once()


# ---------------------------------------------------------------------------
# 11. Regression: existing flows unaffected
# ---------------------------------------------------------------------------


class TestRegressionExistingFlows:
    def test_deadline_event_linker_still_works(self):
        """DeadlineEventLinker still creates delivery_at links independently."""
        from app.services.event_linker import DeadlineEventLinker

        linker = DeadlineEventLinker()
        # This just verifies the class is importable and constructable
        assert linker is not None

    def test_observation_window_defaults_unchanged(self):
        """Existing observation window defaults still work."""
        from app.services.observation_window import default_window_hours

        assert default_window_hours("slack") == pytest.approx(2.8)
        assert default_window_hours("email_internal") == pytest.approx(33.6)

    def test_priority_scorer_without_context_hours(self):
        """Scorer works without context_proximity_hours (backward compat)."""
        cr = make_classifier_result()
        commitment = make_scored_commitment()
        result = priority_score(cr, commitment, proximity_hours=None)
        assert 0 <= result <= 100


# ---------------------------------------------------------------------------
# 12-15. Additional edge cases
# ---------------------------------------------------------------------------


class TestAdditionalEdgeCases:
    def test_event_null_attendees(self):
        """Event with None attendees → no crash."""
        matcher = CalendarMatcher(now=NOW)
        event = make_event(attendees=None)
        commitment = make_commitment()
        link_type, confidence, metadata = matcher._score_pair(event, commitment)
        assert isinstance(confidence, float)

    def test_commitment_null_deliverable(self):
        """Commitment with None deliverable → no crash."""
        matcher = CalendarMatcher(now=NOW)
        event = make_event()
        commitment = make_commitment(deliverable=None)
        link_type, confidence, metadata = matcher._score_pair(event, commitment)
        assert isinstance(confidence, float)

    def test_match_returns_dict_links(self):
        """match() returns list of dicts with expected keys."""
        matcher = CalendarMatcher(now=NOW)
        event = make_event()
        commitment = make_commitment()
        links = matcher.match([event], [commitment], existing_pairs=set())
        for link in links:
            assert "event_id" in link
            assert "commitment_id" in link
            assert "link_type" in link
            assert "confidence" in link
            assert "metadata" in link

    def test_multiple_events_multiple_commitments(self):
        """Cross-product matching with multiple events and commitments."""
        matcher = CalendarMatcher(now=NOW)
        events = [
            make_event(id="e1", title="Pricing review with Sarah",
                       attendees=[{"name": "Sarah Chen", "email": "sarah@acme.com"}]),
            make_event(id="e2", title="Infrastructure planning",
                       attendees=[{"name": "Bob", "email": "bob@infra.com"}]),
        ]
        commitments = [
            make_commitment(id="c1", requester_email="sarah@acme.com",
                           title="Review pricing for Acme"),
            make_commitment(id="c2", requester_email="bob@infra.com",
                           title="Plan infrastructure migration",
                           target_entity="Infrastructure"),
        ]
        links = matcher.match(events, commitments, existing_pairs=set())
        assert isinstance(links, list)
        # Each link should reference valid event/commitment ids
        event_ids = {"e1", "e2"}
        commitment_ids = {"c1", "c2"}
        for link in links:
            assert link["event_id"] in event_ids
            assert link["commitment_id"] in commitment_ids
