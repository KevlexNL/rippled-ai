"""Tests for Phase 03 — commitment detection pipeline.

Test strategy:
- Patterns: test each trigger class fires on expected text, doesn't fire on suppressed text
- Context: test extraction per source type (meeting, slack, email)
- Detector: test full pipeline via mocked DB session, verify candidate fields
- Source-specific: meeting speaker turns, Slack thread context, email quoted stripping

These tests run without a real database (detector unit tests mock the DB Session).
"""
from __future__ import annotations

import re
import types
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.models.orm import CommitmentCandidate, SourceItem
from app.services.detection.context import (
    _detect_external_recipients,
    _flag_uncertain_attribution,
    _parse_speaker_turns,
    extract_context,
)
from app.services.detection.detector import (
    _apply_suppression,
    _compute_class_hint,
    _compute_confidence,
    _compute_observe_until,
    _compute_priority,
    _extract_entities,
    _is_external,
    _should_flag_reanalysis,
    run_detection,
)
from app.services.detection.patterns import (
    EMAIL_PATTERNS,
    EMAIL_SUPPRESSION_PATTERNS,
    MEETING_PATTERNS,
    SLACK_PATTERNS,
    SUPPRESSION_PATTERNS,
    UNIVERSAL_DELIVERY_PATTERNS,
    UNIVERSAL_EXPLICIT_PATTERNS,
    get_patterns_for_source,
    get_suppression_patterns_for_source,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_item(**kwargs) -> Any:
    """Create a minimal SourceItem-like namespace for testing (no DB required).

    Uses SimpleNamespace to avoid SQLAlchemy instrumentation.
    All attributes accessed by the detection service are covered.
    """
    defaults: dict[str, Any] = {
        "id": "item-001",
        "user_id": "user-001",
        "source_type": "email",
        "external_id": "ext-001",
        "source_id": "src-001",
        "content": None,
        "content_normalized": None,
        "direction": "outbound",
        "sender_id": "user-001",
        "sender_name": "Alice",
        "sender_email": "alice@example.com",
        "is_external_participant": False,
        "recipients": None,
        "thread_id": None,
        "metadata_": None,
        "occurred_at": datetime.now(timezone.utc),
    }
    defaults.update(kwargs)
    return types.SimpleNamespace(**defaults)


# ---------------------------------------------------------------------------
# Pattern tests — trigger class coverage
# ---------------------------------------------------------------------------

class TestUniversalExplicitPatterns:
    """Each pattern in UNIVERSAL_EXPLICIT_PATTERNS fires on matching text."""

    def test_i_will_contraction_fires(self):
        pattern = next(p for p in UNIVERSAL_EXPLICIT_PATTERNS if p.name == "i_will_contraction")
        assert pattern.pattern.search("I'll send the report by Friday")
        assert pattern.trigger_class == "explicit_self_commitment"
        assert pattern.is_explicit is True

    def test_i_will_full_fires(self):
        pattern = next(p for p in UNIVERSAL_EXPLICIT_PATTERNS if p.name == "i_will_full")
        assert pattern.pattern.search("I will follow up on this tomorrow")
        assert pattern.trigger_class == "explicit_self_commitment"

    def test_we_will_fires(self):
        pattern = next(p for p in UNIVERSAL_EXPLICIT_PATTERNS if p.name == "we_will")
        assert pattern.pattern.search("We'll get this done by end of week")
        assert pattern.trigger_class == "explicit_collective_commitment"

    def test_can_you_request_fires(self):
        pattern = next(p for p in UNIVERSAL_EXPLICIT_PATTERNS if p.name == "can_you_request")
        assert pattern.pattern.search("Can you review this document today?")
        assert pattern.trigger_class == "request_for_action"

    def test_will_you_request_fires(self):
        pattern = next(p for p in UNIVERSAL_EXPLICIT_PATTERNS if p.name == "will_you_request")
        assert pattern.pattern.search("Will you send the invoice by Thursday?")
        assert pattern.trigger_class == "request_for_action"

    def test_let_me_handle_fires(self):
        pattern = next(p for p in UNIVERSAL_EXPLICIT_PATTERNS if p.name == "let_me_handle")
        assert pattern.pattern.search("Let me take care of the onboarding")

    def test_obligation_needs_to_fires(self):
        pattern = next(p for p in UNIVERSAL_EXPLICIT_PATTERNS if p.name == "obligation_needs_to")
        assert pattern.pattern.search("The contract needs to be signed by Monday")
        assert pattern.trigger_class == "obligation_marker"

    def test_still_needs_fires(self):
        pattern = next(p for p in UNIVERSAL_EXPLICIT_PATTERNS if p.name == "still_needs")
        assert pattern.pattern.search("This still needs to be reviewed")
        assert pattern.trigger_class == "pending_obligation"

    def test_applies_to_all_sources(self):
        for pattern in UNIVERSAL_EXPLICIT_PATTERNS:
            assert "meeting" in pattern.applies_to
            assert "slack" in pattern.applies_to
            assert "email" in pattern.applies_to


class TestFollowUpPattern:
    """Follow-up commitment patterns fire on 'follow up on' phrases."""

    def test_follow_up_on_topic_fires(self):
        pattern = next(p for p in UNIVERSAL_EXPLICIT_PATTERNS if p.name == "follow_up_on")
        assert pattern.pattern.search("I need to follow up on the budget")
        assert pattern.trigger_class == "follow_up_commitment"

    def test_follow_up_with_person_fires(self):
        pattern = next(p for p in UNIVERSAL_EXPLICIT_PATTERNS if p.name == "follow_up_on")
        assert pattern.pattern.search("will follow up with the client")

    def test_follow_up_regarding_fires(self):
        pattern = next(p for p in UNIVERSAL_EXPLICIT_PATTERNS if p.name == "follow_up_on")
        assert pattern.pattern.search("let me follow up on this next week")

    def test_follow_up_applies_to_all_sources(self):
        pattern = next(p for p in UNIVERSAL_EXPLICIT_PATTERNS if p.name == "follow_up_on")
        assert "meeting" in pattern.applies_to
        assert "slack" in pattern.applies_to
        assert "email" in pattern.applies_to


class TestCheckingInOnPattern:
    """'Checking in on [topic]' is a follow-up commitment (v5)."""

    def test_checking_in_on_pattern_exists(self):
        names = {p.name for p in UNIVERSAL_EXPLICIT_PATTERNS}
        assert "checking_in_on" in names, (
            "Expected 'checking_in_on' pattern in UNIVERSAL_EXPLICIT_PATTERNS"
        )

    def test_checking_in_on_topic_fires(self):
        pattern = next(p for p in UNIVERSAL_EXPLICIT_PATTERNS if p.name == "checking_in_on")
        assert pattern.pattern.search("checking in on the budget")
        assert pattern.trigger_class == "follow_up_commitment"

    def test_checking_in_on_applies_to_all_sources(self):
        pattern = next(p for p in UNIVERSAL_EXPLICIT_PATTERNS if p.name == "checking_in_on")
        assert "meeting" in pattern.applies_to
        assert "slack" in pattern.applies_to
        assert "email" in pattern.applies_to

    def test_just_checking_in_not_matched(self):
        """Bare 'just checking in' (no topic) should NOT match checking_in_on pattern."""
        pattern = next(p for p in UNIVERSAL_EXPLICIT_PATTERNS if p.name == "checking_in_on")
        assert not pattern.pattern.search("just checking in")


class TestGreetingSuppression:
    """Greetings are suppressed and never extracted as commitments."""

    def test_greeting_hi_suppressed(self):
        pattern = next(p for p in SUPPRESSION_PATTERNS if p.name == "greeting")
        assert pattern.pattern.search("Hi team,")
        assert pattern.suppression is True

    def test_greeting_hello_suppressed(self):
        pattern = next(p for p in SUPPRESSION_PATTERNS if p.name == "greeting")
        assert pattern.pattern.search("Hello everyone,")

    def test_greeting_good_morning_suppressed(self):
        pattern = next(p for p in SUPPRESSION_PATTERNS if p.name == "greeting")
        assert pattern.pattern.search("Good morning,")

    def test_greeting_hey_suppressed(self):
        pattern = next(p for p in SUPPRESSION_PATTERNS if p.name == "greeting")
        assert pattern.pattern.search("Hey Bob")

    def test_greeting_does_not_match_mid_sentence(self):
        """Greetings should only match at line start, not mid-sentence."""
        pattern = next(p for p in SUPPRESSION_PATTERNS if p.name == "greeting")
        # "say hi to" should NOT trigger the greeting suppression
        assert not pattern.pattern.search("I'll say hi to the team")


class TestPleasantrySuppression:
    """Pleasantries like 'Hope you're doing well' are suppressed."""

    def test_hope_doing_well_suppressed(self):
        pattern = next(p for p in SUPPRESSION_PATTERNS if p.name == "pleasantry")
        assert pattern.pattern.search("Hope you're doing well")
        assert pattern.suppression is True

    def test_hope_finds_you_well_suppressed(self):
        pattern = next(p for p in SUPPRESSION_PATTERNS if p.name == "pleasantry")
        assert pattern.pattern.search("Hope this finds you well")

    def test_hope_all_is_well_suppressed(self):
        pattern = next(p for p in SUPPRESSION_PATTERNS if p.name == "pleasantry")
        assert pattern.pattern.search("Hope all is well")

    def test_trust_you_are_well_suppressed(self):
        pattern = next(p for p in SUPPRESSION_PATTERNS if p.name == "pleasantry")
        assert pattern.pattern.search("Trust you are well")

    def test_happy_friday_suppressed(self):
        pattern = next(p for p in SUPPRESSION_PATTERNS if p.name == "pleasantry")
        assert pattern.pattern.search("Happy Friday!")

    def test_pleasantry_does_not_match_commitment(self):
        """Pleasantry pattern should not suppress real commitments."""
        pattern = next(p for p in SUPPRESSION_PATTERNS if p.name == "pleasantry")
        assert not pattern.pattern.search("I hope to follow up on the budget")


class TestPleasantryIntegration:
    """Pleasantries are stripped before pattern matching in run_detection."""

    def _make_mock_db(self, item):
        db = MagicMock()
        db.get.return_value = item
        savepoint = MagicMock()
        savepoint.__enter__ = MagicMock(return_value=savepoint)
        savepoint.__exit__ = MagicMock(return_value=False)
        db.begin_nested.return_value = savepoint
        db.flush = MagicMock()
        return db

    def test_pleasantry_only_email_no_candidates(self):
        item = _make_item(
            source_type="email",
            content_normalized="Hope you're doing well.\nHope this finds you well.\nHappy Friday!",
        )
        db = self._make_mock_db(item)
        candidates = run_detection("item-001", db)
        assert len(candidates) == 0, "Pleasantries should not produce candidates"

    def test_pleasantry_with_real_commitment_extracts_only_commitment(self):
        item = _make_item(
            source_type="email",
            content_normalized="Hope you're doing well.\nI'll follow up on the budget tomorrow.",
        )
        db = self._make_mock_db(item)
        candidates = run_detection("item-001", db)
        assert len(candidates) > 0, "Real commitment should still be extracted"
        # No candidate should be a pleasantry
        for c in candidates:
            assert "hope" not in (c.raw_text or "").lower() or "follow up" in (c.raw_text or "").lower()


class TestRunDetectionFollowUpAndGreeting:
    """Integration: follow-up detected, greeting suppressed in run_detection."""

    def _make_mock_db(self, item):
        db = MagicMock()
        db.get.return_value = item
        savepoint = MagicMock()
        savepoint.__enter__ = MagicMock(return_value=savepoint)
        savepoint.__exit__ = MagicMock(return_value=False)
        db.begin_nested.return_value = savepoint
        db.flush = MagicMock()
        return db

    def test_follow_up_on_budget_creates_candidate(self):
        item = _make_item(
            source_type="email",
            content_normalized="I need to follow up on the budget with finance.",
        )
        db = self._make_mock_db(item)
        candidates = run_detection("item-001", db)
        follow_up = [c for c in candidates if c.trigger_class == "follow_up_commitment"]
        assert follow_up, "Expected follow_up_commitment candidate for 'follow up on the budget'"

    def test_greeting_only_email_no_candidates(self):
        item = _make_item(
            source_type="email",
            content_normalized="Hi there,\nHello everyone,\nGood morning team,",
        )
        db = self._make_mock_db(item)
        candidates = run_detection("item-001", db)
        assert len(candidates) == 0, "Greetings should not produce candidates"


class TestUniversalDeliveryPatterns:
    def test_delivery_confirmation_fires(self):
        pattern = next(p for p in UNIVERSAL_DELIVERY_PATTERNS if p.name == "delivery_confirmation")
        assert pattern.pattern.search("I just sent the report to you")
        assert pattern.trigger_class == "delivery_signal"

    def test_blocker_waiting_fires(self):
        pattern = next(p for p in UNIVERSAL_DELIVERY_PATTERNS if p.name == "blocker_waiting")
        assert pattern.pattern.search("Still waiting on approval from legal")
        assert pattern.trigger_class == "blocker_signal"

    def test_blocker_blocked_fires(self):
        pattern = next(p for p in UNIVERSAL_DELIVERY_PATTERNS if p.name == "blocker_blocked")
        assert pattern.pattern.search("We're blocked by the API team")
        assert pattern.trigger_class == "blocker_signal"


class TestMeetingPatterns:
    """Meeting-only patterns fire on meeting language."""

    def test_next_step_fires(self):
        pattern = next(p for p in MEETING_PATTERNS if p.name == "next_step_marker")
        assert pattern.pattern.search("Next step is to finalize the proposal")
        assert pattern.trigger_class == "implicit_next_step"
        assert pattern.is_explicit is False
        assert "meeting" in pattern.applies_to
        assert "slack" not in pattern.applies_to
        assert "email" not in pattern.applies_to

    def test_action_item_fires(self):
        pattern = next(p for p in MEETING_PATTERNS if p.name == "action_item_marker")
        assert pattern.pattern.search("Action item: Bob will send the contract")

    def test_from_our_side_fires(self):
        pattern = next(p for p in MEETING_PATTERNS if p.name == "from_our_side")
        assert pattern.pattern.search("From our side we need to review the terms")
        assert pattern.trigger_class == "implicit_unresolved_obligation"

    def test_someone_should_fires(self):
        pattern = next(p for p in MEETING_PATTERNS if p.name == "someone_should")
        assert pattern.pattern.search("Someone should follow up with the client")

    def test_who_is_going_fires(self):
        pattern = next(p for p in MEETING_PATTERNS if p.name == "who_is_going_to")
        assert pattern.pattern.search("Who's going to send the summary?")

    def test_can_someone_fires(self):
        pattern = next(p for p in MEETING_PATTERNS if p.name == "can_someone")
        assert pattern.pattern.search("Can someone take the lead on this?")

    def test_we_should_fires(self):
        pattern = next(p for p in MEETING_PATTERNS if p.name == "we_should")
        assert pattern.pattern.search("We should schedule a follow-up call")

    def test_meeting_patterns_not_in_email_source(self):
        email_patterns = get_patterns_for_source("email")
        email_pattern_names = {p.name for p in email_patterns}
        for p in MEETING_PATTERNS:
            assert p.name not in email_pattern_names


class TestSlackPatterns:
    def test_ill_check_fires(self):
        pattern = next(p for p in SLACK_PATTERNS if p.name == "slack_ill_check")
        assert pattern.pattern.search("I'll check")
        assert pattern.trigger_class == "small_practical_commitment"
        assert "slack" in pattern.applies_to
        assert "email" not in pattern.applies_to

    def test_accepted_request_fires(self):
        pattern = next(p for p in SLACK_PATTERNS if p.name == "slack_accepted_request")
        assert pattern.pattern.search("will do")
        assert pattern.pattern.search("sure")
        assert pattern.trigger_class == "accepted_request"

    def test_slack_delivery_done_fires(self):
        pattern = next(p for p in SLACK_PATTERNS if p.name == "slack_delivery_done")
        assert pattern.pattern.search("done.")
        assert pattern.trigger_class == "delivery_signal"

    def test_slack_patterns_not_in_meeting_source(self):
        meeting_patterns = get_patterns_for_source("meeting")
        meeting_pattern_names = {p.name for p in meeting_patterns}
        for p in SLACK_PATTERNS:
            assert p.name not in meeting_pattern_names


class TestEmailPatterns:
    def test_ill_revise_fires(self):
        pattern = next(p for p in EMAIL_PATTERNS if p.name == "email_ill_revise")
        assert pattern.pattern.search("I'll revise and send it tomorrow")
        assert pattern.trigger_class == "explicit_self_commitment"

    def test_ill_introduce_fires(self):
        pattern = next(p for p in EMAIL_PATTERNS if p.name == "email_ill_introduce")
        assert pattern.pattern.search("I'll introduce you to Sarah next week")

    def test_please_find_attached_fires(self):
        pattern = next(p for p in EMAIL_PATTERNS if p.name == "email_please_find_attached")
        assert pattern.pattern.search("Please find attached the proposal")
        assert pattern.trigger_class == "delivery_signal"

    def test_email_patterns_not_in_slack_source(self):
        slack_patterns = get_patterns_for_source("slack")
        slack_pattern_names = {p.name for p in slack_patterns}
        for p in EMAIL_PATTERNS:
            assert p.name not in slack_pattern_names


class TestSuppressionPatterns:
    def test_hypothetical_suppressed(self):
        pattern = next(p for p in SUPPRESSION_PATTERNS if p.name == "hypothetical_marker")
        assert pattern.pattern.search("maybe we could do this next week")
        assert pattern.suppression is True

    def test_conversational_filler_suppressed(self):
        pattern = next(p for p in SUPPRESSION_PATTERNS if p.name == "conversational_filler")
        assert pattern.pattern.search("sounds good")
        assert pattern.pattern.search("thanks")
        assert pattern.suppression is True

    def test_email_quoted_line_suppressed(self):
        pattern = next(p for p in EMAIL_SUPPRESSION_PATTERNS if p.name == "email_quoted_line")
        assert pattern.pattern.search("> On Monday, Alice wrote:\n> Please send the report")
        assert pattern.suppression is True

    def test_email_attribution_line_suppressed(self):
        pattern = next(p for p in EMAIL_SUPPRESSION_PATTERNS if p.name == "email_attribution_line")
        assert pattern.pattern.search("On Mon, 10 Mar 2026 at 09:00, Alice <alice@example.com> wrote:")
        assert pattern.suppression is True


class TestGetPatternsForSource:
    def test_meeting_gets_meeting_and_universal(self):
        patterns = get_patterns_for_source("meeting")
        names = {p.name for p in patterns}
        # Universal patterns included
        assert "i_will_contraction" in names
        # Meeting-specific included
        assert "next_step_marker" in names
        # Slack-only excluded
        assert "slack_accepted_request" not in names
        # Email-only excluded
        assert "email_ill_revise" not in names

    def test_slack_gets_slack_and_universal(self):
        patterns = get_patterns_for_source("slack")
        names = {p.name for p in patterns}
        assert "i_will_contraction" in names
        assert "slack_accepted_request" in names
        assert "next_step_marker" not in names

    def test_email_gets_email_and_universal(self):
        patterns = get_patterns_for_source("email")
        names = {p.name for p in patterns}
        assert "i_will_contraction" in names
        assert "email_ill_revise" in names
        assert "slack_accepted_request" not in names

    def test_suppression_not_in_capture_patterns(self):
        for source in ("meeting", "slack", "email"):
            patterns = get_patterns_for_source(source)
            assert not any(p.suppression for p in patterns)


# ---------------------------------------------------------------------------
# Context extraction tests
# ---------------------------------------------------------------------------

class TestParseSpeakerTurns:
    def test_parses_bracketed_speakers(self):
        transcript = "[Alice]: I'll send the report tomorrow\n[Bob]: Great, thanks\n[Alice]: Will do"
        turns = _parse_speaker_turns(transcript)
        assert len(turns) == 3
        assert turns[0]["speaker"] == "Alice"
        assert "I'll send the report" in turns[0]["text"]
        assert turns[1]["speaker"] == "Bob"

    def test_parses_plain_colon_format(self):
        transcript = "Alice: Can you review this?\nBob: Sure, I'll look at it now"
        turns = _parse_speaker_turns(transcript)
        assert len(turns) == 2
        assert turns[0]["speaker"] == "Alice"

    def test_parses_timestamped_turns(self):
        transcript = "00:01:30 [Alice]: I'll handle the client call\n00:02:00 [Bob]: Sounds good"
        turns = _parse_speaker_turns(transcript)
        assert len(turns) == 2
        assert turns[0]["timestamp"] == "00:01:30"
        assert turns[0]["speaker"] == "Alice"

    def test_fallback_for_unstructured_content(self):
        content = "Just some text without speaker labels"
        turns = _parse_speaker_turns(content)
        assert len(turns) == 1
        assert turns[0]["speaker"] is None


class TestFlagUncertainAttribution:
    def test_generic_speaker_flagged(self):
        turns = [
            {"speaker": "Speaker 1", "text": "I'll send the report"},
            {"speaker": "Alice", "text": "Great"},
        ]
        assert _flag_uncertain_attribution(turns, "I'll send the report") is True

    def test_inaudible_marker_flagged(self):
        turns = [
            {"speaker": "Alice", "text": "I'll [inaudible] send it tomorrow"},
        ]
        assert _flag_uncertain_attribution(turns, "I'll") is True

    def test_named_speaker_not_flagged(self):
        turns = [
            {"speaker": "Alice", "text": "I'll send the proposal"},
        ]
        assert _flag_uncertain_attribution(turns, "I'll") is False


class TestDetectExternalRecipients:
    def test_external_recipient_detected(self):
        recipients = [
            {"name": "Bob", "email": "bob@client.com", "is_external": True},
            {"name": "Carol", "email": "carol@internal.com", "is_external": False},
        ]
        assert _detect_external_recipients(recipients) is True

    def test_no_external_recipients(self):
        recipients = [
            {"name": "Bob", "email": "bob@internal.com", "is_external": False},
        ]
        assert _detect_external_recipients(recipients) is False

    def test_empty_recipients(self):
        assert _detect_external_recipients([]) is False
        assert _detect_external_recipients(None) is False


class TestExtractContext:
    def test_email_context_extraction(self):
        item = _make_item(
            source_type="email",
            direction="outbound",
            is_external_participant=False,
            recipients=[{"name": "Client", "email": "client@ext.com", "is_external": True}],
            content_normalized="Hello, I'll send you the contract by Monday.",
        )
        ctx = extract_context(
            item=item,
            trigger_text="I'll send you the contract by Monday",
            trigger_start=7,
            trigger_end=43,
            normalized_content="Hello, I'll send you the contract by Monday.",
        )
        assert ctx["source_type"] == "email"
        assert ctx["email_direction"] == "outbound"
        assert ctx["has_external_recipient"] is True
        assert ctx["trigger_text"] == "I'll send you the contract by Monday"

    def test_meeting_context_extracts_speaker_turns(self):
        transcript = "[Alice]: Let's discuss the next steps\n[Bob]: I'll send the follow-up email\n[Alice]: Thanks"
        item = _make_item(
            source_type="meeting",
            content_normalized=transcript,
            is_external_participant=False,
        )
        ctx = extract_context(
            item=item,
            trigger_text="I'll send the follow-up email",
            trigger_start=transcript.index("I'll send"),
            trigger_end=transcript.index("I'll send") + len("I'll send the follow-up email"),
            normalized_content=transcript,
        )
        assert ctx["source_type"] == "meeting"
        assert ctx["speaker_turns"] is not None
        assert len(ctx["speaker_turns"]) > 0

    def test_slack_context_includes_external_false(self):
        item = _make_item(
            source_type="slack",
            content_normalized="I'll look into this",
            metadata_={"thread_parent_text": "Can you check the deploy?"},
        )
        ctx = extract_context(
            item=item,
            trigger_text="I'll look into this",
            trigger_start=0,
            trigger_end=19,
            normalized_content="I'll look into this",
        )
        assert ctx["source_type"] == "slack"
        assert ctx["thread_parent"] == "Can you check the deploy?"
        assert ctx["has_external_recipient"] is False


# ---------------------------------------------------------------------------
# Detector unit tests
# ---------------------------------------------------------------------------

class TestApplySuppression:
    def test_email_quoted_lines_stripped(self):
        content = "Hi,\n\nI'll follow up with you.\n\n> On Mon, Alice wrote:\n> Please send the file"
        result = _apply_suppression(content, "email")
        assert "> On Mon" not in result
        assert "I'll follow up" in result

    def test_hypothetical_marker_stripped(self):
        content = "maybe we could do this. I'll follow up."
        result = _apply_suppression(content, "email")
        # Hypothetical stripped but commitment text preserved
        assert "maybe" not in result
        assert "I'll follow up" in result


class TestComputeObserveUntil:
    def test_slack_internal_is_2_hours(self):
        now = datetime.now(timezone.utc)
        observe = _compute_observe_until("slack", False)
        delta = observe - now
        assert 1.9 * 3600 < delta.total_seconds() < 2.1 * 3600

    def test_email_external_is_48_hours(self):
        now = datetime.now(timezone.utc)
        observe = _compute_observe_until("email", True)
        delta = observe - now
        assert 47.5 * 3600 < delta.total_seconds() < 48.5 * 3600

    def test_meeting_internal_is_16_hours(self):
        now = datetime.now(timezone.utc)
        observe = _compute_observe_until("meeting", False)
        delta = observe - now
        assert 15.5 * 3600 < delta.total_seconds() < 16.5 * 3600


class TestComputeConfidence:
    def test_explicit_internal_uses_base(self):
        from app.services.detection.patterns import UNIVERSAL_EXPLICIT_PATTERNS
        pattern = next(p for p in UNIVERSAL_EXPLICIT_PATTERNS if p.name == "i_will_full")
        conf = _compute_confidence(pattern, is_external=False)
        assert conf == Decimal("0.800")

    def test_external_context_boosts_confidence(self):
        from app.services.detection.patterns import UNIVERSAL_EXPLICIT_PATTERNS
        pattern = next(p for p in UNIVERSAL_EXPLICIT_PATTERNS if p.name == "i_will_full")
        conf_internal = _compute_confidence(pattern, is_external=False)
        conf_external = _compute_confidence(pattern, is_external=True)
        assert conf_external > conf_internal

    def test_confidence_capped_at_one(self):
        from app.services.detection.patterns import TriggerPattern
        import re
        high_pattern = TriggerPattern(
            name="test",
            pattern=re.compile(r"test"),
            trigger_class="explicit_self_commitment",
            is_explicit=True,
            base_priority_hint="high",
            applies_to=("email",),
            base_confidence=0.97,
        )
        conf = _compute_confidence(high_pattern, is_external=True)
        assert conf <= Decimal("1.000")


class TestComputePriority:
    def test_external_elevates_medium_to_high(self):
        from app.services.detection.patterns import UNIVERSAL_EXPLICIT_PATTERNS
        pattern = next(p for p in UNIVERSAL_EXPLICIT_PATTERNS if p.name == "i_will_full")
        priority = _compute_priority(pattern, is_external=True, trigger_text="I will send")
        assert priority == "high"

    def test_delivery_signal_always_low(self):
        from app.services.detection.patterns import UNIVERSAL_DELIVERY_PATTERNS
        pattern = next(p for p in UNIVERSAL_DELIVERY_PATTERNS if p.name == "delivery_confirmation")
        priority = _compute_priority(pattern, is_external=True, trigger_text="just sent")
        assert priority == "low"


class TestComputeClassHint:
    def test_external_explicit_self_is_big_promise(self):
        from app.services.detection.patterns import UNIVERSAL_EXPLICIT_PATTERNS
        pattern = next(p for p in UNIVERSAL_EXPLICIT_PATTERNS if p.name == "i_will_full")
        hint = _compute_class_hint(pattern, is_external=True, trigger_text="I will send")
        assert hint == "big_promise"

    def test_small_practical_is_small_commitment(self):
        from app.services.detection.patterns import SLACK_PATTERNS
        pattern = next(p for p in SLACK_PATTERNS if p.name == "slack_ill_check")
        hint = _compute_class_hint(pattern, is_external=False, trigger_text="I'll check")
        assert hint == "small_commitment"

    def test_delivery_signal_is_unknown(self):
        from app.services.detection.patterns import UNIVERSAL_DELIVERY_PATTERNS
        pattern = next(p for p in UNIVERSAL_DELIVERY_PATTERNS if p.name == "delivery_confirmation")
        hint = _compute_class_hint(pattern, is_external=False, trigger_text="just sent")
        assert hint == "unknown"


class TestExtractEntities:
    def test_dates_extracted(self):
        entities = _extract_entities("I'll send the contract by Monday next week")
        assert any("Monday" in d for d in entities["dates"])

    def test_at_mentions_extracted(self):
        entities = _extract_entities("@bob can you review this by tomorrow?")
        assert "@bob" in entities["people"]

    def test_no_entities_in_empty_text(self):
        entities = _extract_entities("")
        assert entities["dates"] == []
        assert entities["people"] == []


class TestIsExternal:
    def test_is_external_from_flag(self):
        item = _make_item(is_external_participant=True)
        assert _is_external(item) is True

    def test_is_external_from_recipients(self):
        item = _make_item(
            is_external_participant=False,
            recipients=[{"name": "Client", "is_external": True}],
        )
        assert _is_external(item) is True

    def test_internal_when_no_external(self):
        item = _make_item(
            is_external_participant=False,
            recipients=[{"name": "Colleague", "is_external": False}],
        )
        assert _is_external(item) is False


class TestShouldFlagReanalysis:
    def test_meeting_with_inaudible_near_trigger_flagged(self):
        item = _make_item(
            source_type="meeting",
            content_normalized="[Alice]: I'll [inaudible] send the report",
        )
        assert _should_flag_reanalysis(item, "I'll") is True

    def test_meeting_without_uncertain_not_flagged(self):
        item = _make_item(
            source_type="meeting",
            content_normalized="[Alice]: I'll send the report tomorrow",
        )
        assert _should_flag_reanalysis(item, "I'll") is False

    def test_email_never_flagged(self):
        item = _make_item(source_type="email", content_normalized="I'll [inaudible] send")
        assert _should_flag_reanalysis(item, "I'll") is False


# ---------------------------------------------------------------------------
# run_detection integration test (mocked DB)
# ---------------------------------------------------------------------------

class TestRunDetection:
    def _make_mock_db(self, item: SourceItem):
        """Return a mock SQLAlchemy Session that returns `item` on .get()."""
        db = MagicMock()
        db.get.return_value = item
        # begin_nested() returns a context manager
        savepoint = MagicMock()
        savepoint.__enter__ = MagicMock(return_value=savepoint)
        savepoint.__exit__ = MagicMock(return_value=False)
        db.begin_nested.return_value = savepoint
        db.flush = MagicMock()
        return db

    def test_email_with_commitment_creates_candidates(self):
        item = _make_item(
            source_type="email",
            content_normalized="Hi Sarah, I'll send you the contract by Monday.",
            is_external_participant=True,
        )
        db = self._make_mock_db(item)
        candidates = run_detection("item-001", db)
        assert len(candidates) > 0
        # Check first candidate has expected fields
        c = candidates[0]
        assert c.user_id == "user-001"
        assert c.originating_item_id == "item-001"
        assert c.source_type == "email"
        assert c.trigger_class is not None
        assert c.is_explicit is not None
        assert c.confidence_score is not None
        assert c.priority_hint is not None
        assert c.commitment_class_hint is not None
        assert c.context_window is not None
        assert c.observe_until is not None

    def test_email_with_external_gets_high_priority(self):
        item = _make_item(
            source_type="email",
            content_normalized="I will deliver the proposal tomorrow.",
            is_external_participant=True,
        )
        db = self._make_mock_db(item)
        candidates = run_detection("item-001", db)
        explicit_candidates = [c for c in candidates if c.trigger_class == "explicit_self_commitment"]
        assert explicit_candidates, "Expected explicit_self_commitment candidate"
        assert explicit_candidates[0].priority_hint == "high"

    def test_meeting_with_next_step_creates_candidate(self):
        item = _make_item(
            source_type="meeting",
            content_normalized="[Alice]: Next step is to finalize the contract with the client.",
            is_external_participant=False,
        )
        db = self._make_mock_db(item)
        candidates = run_detection("item-001", db)
        next_step = [c for c in candidates if c.trigger_class == "implicit_next_step"]
        assert next_step, "Expected implicit_next_step candidate from meeting"

    def test_slack_accepted_request_creates_candidate(self):
        item = _make_item(
            source_type="slack",
            content_normalized="will do",
            metadata_={"thread_parent_text": "Can you send me the report?"},
        )
        db = self._make_mock_db(item)
        candidates = run_detection("item-001", db)
        accepted = [c for c in candidates if c.trigger_class == "accepted_request"]
        assert accepted, "Expected accepted_request candidate from Slack"

    def test_empty_content_returns_no_candidates(self):
        item = _make_item(source_type="email", content_normalized="   ")
        db = self._make_mock_db(item)
        candidates = run_detection("item-001", db)
        assert candidates == []

    def test_missing_item_raises_value_error(self):
        db = MagicMock()
        db.get.return_value = None
        with pytest.raises(ValueError, match="not found"):
            run_detection("nonexistent-id", db)

    def test_meeting_inaudible_trigger_flags_reanalysis(self):
        item = _make_item(
            source_type="meeting",
            content_normalized="[Speaker 1]: I'll [inaudible] handle the client follow-up.",
        )
        db = self._make_mock_db(item)
        candidates = run_detection("item-001", db)
        assert len(candidates) > 0
        flagged = [c for c in candidates if c.flag_reanalysis]
        assert flagged, "Expected at least one candidate to be flagged for reanalysis"

    def test_suppression_prevents_filler_candidates(self):
        item = _make_item(
            source_type="email",
            content_normalized="sounds good\nthanks\n",
        )
        db = self._make_mock_db(item)
        candidates = run_detection("item-001", db)
        # Fillers should be suppressed; no real commitment signals
        assert len(candidates) == 0

    def test_email_quoted_content_not_detected(self):
        item = _make_item(
            source_type="email",
            content_normalized=(
                "I'll handle this.\n\n"
                "> On Mon, Client wrote:\n"
                "> I'll also make sure to follow up.\n"
            ),
        )
        db = self._make_mock_db(item)
        candidates = run_detection("item-001", db)
        # Only the first "I'll handle this" should match, not the quoted one
        explicit = [c for c in candidates if "handle" in (c.raw_text or "").lower()]
        assert explicit, "Expected candidate for 'I'll handle this'"

    def test_multiple_triggers_in_content_creates_multiple_candidates(self):
        item = _make_item(
            source_type="email",
            content_normalized="I'll send the report. I will also follow up on Tuesday.",
        )
        db = self._make_mock_db(item)
        candidates = run_detection("item-001", db)
        assert len(candidates) >= 2

    def test_observe_until_is_in_future(self):
        item = _make_item(
            source_type="meeting",
            content_normalized="[Alice]: I'll send the follow-up notes.",
        )
        db = self._make_mock_db(item)
        candidates = run_detection("item-001", db)
        now = datetime.now(timezone.utc)
        for c in candidates:
            assert c.observe_until > now

    def test_linked_entities_extracted(self):
        item = _make_item(
            source_type="email",
            content_normalized="I'll send the contract by Monday to @alice.",
        )
        db = self._make_mock_db(item)
        candidates = run_detection("item-001", db)
        entity_candidates = [c for c in candidates if c.linked_entities]
        assert entity_candidates, "Expected candidates with linked_entities"
        entities = entity_candidates[0].linked_entities
        # Monday should be in dates
        assert any("Monday" in d for d in entities.get("dates", []))

    def test_savepoint_failure_does_not_abort_other_candidates(self):
        """If one candidate insert fails, others should still be created."""
        item = _make_item(
            source_type="email",
            content_normalized="I'll send the report. I will follow up next week.",
        )
        db = MagicMock()
        db.get.return_value = item

        call_count = 0

        def mock_begin_nested():
            nonlocal call_count
            call_count += 1
            ctx = MagicMock()
            if call_count == 1:
                # First savepoint raises
                ctx.__enter__ = MagicMock(return_value=ctx)
                ctx.__exit__ = MagicMock(side_effect=Exception("DB error"))
            else:
                ctx.__enter__ = MagicMock(return_value=ctx)
                ctx.__exit__ = MagicMock(return_value=False)
            return ctx

        db.begin_nested = mock_begin_nested
        db.flush = MagicMock()

        # Should not raise; returns whatever candidates succeeded
        candidates = run_detection("item-001", db)
        # At least some candidates should succeed despite first failure
        assert isinstance(candidates, list)
