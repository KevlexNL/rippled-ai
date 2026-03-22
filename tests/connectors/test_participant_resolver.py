"""Tests for ParticipantResolver — WO sections 4.7.4, 4.7.5."""

import pytest

from app.connectors.shared.normalized_signal import NormalizedParticipant
from app.models.enums import Direction, ParticipantRole
from app.services.normalization.participant_resolver import ParticipantResolver


class TestDirectionDetection:
    """4.7.4 — Direction detection from account identity."""

    def test_outbound_when_sender_is_user(self):
        direction = ParticipantResolver.detect_direction(
            sender_email="me@company.com",
            user_email="me@company.com",
            recipient_emails=["them@external.com"],
        )
        assert direction == Direction.outbound

    def test_inbound_when_sender_is_not_user(self):
        direction = ParticipantResolver.detect_direction(
            sender_email="them@external.com",
            user_email="me@company.com",
            recipient_emails=["me@company.com"],
        )
        assert direction == Direction.inbound

    def test_unknown_when_user_not_in_participants(self):
        direction = ParticipantResolver.detect_direction(
            sender_email="alice@example.com",
            user_email="me@company.com",
            recipient_emails=["bob@example.com"],
        )
        assert direction == Direction.unknown

    def test_case_insensitive_matching(self):
        direction = ParticipantResolver.detect_direction(
            sender_email="Me@Company.com",
            user_email="me@company.com",
            recipient_emails=["them@external.com"],
        )
        assert direction == Direction.outbound

    def test_none_sender_returns_unknown(self):
        direction = ParticipantResolver.detect_direction(
            sender_email=None,
            user_email="me@company.com",
            recipient_emails=["me@company.com"],
        )
        assert direction == Direction.unknown


class TestParticipantNormalization:
    """4.7.5 — Normalize participants into NormalizedParticipant objects."""

    def test_normalize_sender(self):
        p = ParticipantResolver.normalize_participant(
            email="  Alice@Example.COM ",
            display_name="  Alice Smith  ",
            role=ParticipantRole.sender,
            user_email="me@company.com",
        )
        assert p.email == "alice@example.com"
        assert p.display_name == "Alice Smith"
        assert p.role == ParticipantRole.sender
        assert p.is_primary_user is False

    def test_normalize_trims_whitespace(self):
        p = ParticipantResolver.normalize_participant(
            email="  bob@test.com  ",
            display_name="  Bob  ",
            role=ParticipantRole.to,
            user_email="me@company.com",
        )
        assert p.email == "bob@test.com"
        assert p.display_name == "Bob"

    def test_normalize_lowercase_email(self):
        p = ParticipantResolver.normalize_participant(
            email="BOB@TEST.COM",
            display_name="Bob",
            role=ParticipantRole.to,
            user_email="me@company.com",
        )
        assert p.email == "bob@test.com"

    def test_primary_user_flag_set(self):
        p = ParticipantResolver.normalize_participant(
            email="me@company.com",
            display_name="Me",
            role=ParticipantRole.sender,
            user_email="me@company.com",
        )
        assert p.is_primary_user is True

    def test_primary_user_case_insensitive(self):
        p = ParticipantResolver.normalize_participant(
            email="Me@Company.COM",
            display_name="Me",
            role=ParticipantRole.sender,
            user_email="me@company.com",
        )
        assert p.is_primary_user is True

    def test_does_not_invent_missing_email(self):
        p = ParticipantResolver.normalize_participant(
            email=None,
            display_name="Unknown Person",
            role=ParticipantRole.to,
            user_email="me@company.com",
        )
        assert p.email is None
        assert p.display_name == "Unknown Person"

    def test_normalize_all_participants(self):
        result = ParticipantResolver.normalize_all(
            sender_email="alice@example.com",
            sender_name="Alice",
            to_emails=["bob@example.com", "carol@example.com"],
            cc_emails=["dave@example.com"],
            bcc_emails=[],
            reply_to_emails=[],
            user_email="alice@example.com",
        )
        assert result.sender is not None
        assert result.sender.email == "alice@example.com"
        assert result.sender.is_primary_user is True
        assert len(result.to_list) == 2
        assert len(result.cc_list) == 1
        assert len(result.bcc_list) == 0
        # All participants includes sender + all recipients
        assert len(result.all_participants) == 4
