"""Tests for app/connectors/shared/participant_classifier.py"""

from unittest.mock import MagicMock, patch

from app.connectors.shared.participant_classifier import (
    classify_participants,
    is_external_participant,
)


def _mock_settings(internal_domains: str) -> MagicMock:
    m = MagicMock()
    m.internal_domains = internal_domains
    return m


class TestIsExternalParticipant:
    def test_internal_domain_returns_false(self):
        with patch(
            "app.connectors.shared.participant_classifier.get_settings",
            return_value=_mock_settings("example.com,internal.io"),
        ):
            assert is_external_participant("alice@example.com") is False

    def test_external_domain_returns_true(self):
        with patch(
            "app.connectors.shared.participant_classifier.get_settings",
            return_value=_mock_settings("example.com"),
        ):
            assert is_external_participant("bob@otherdomain.com") is True

    def test_none_email_is_external(self):
        with patch(
            "app.connectors.shared.participant_classifier.get_settings",
            return_value=_mock_settings("example.com"),
        ):
            assert is_external_participant(None) is True

    def test_no_internal_domains_configured_treats_all_as_external(self):
        with patch(
            "app.connectors.shared.participant_classifier.get_settings",
            return_value=_mock_settings(""),
        ):
            assert is_external_participant("alice@example.com") is True

    def test_classify_participants_mixed_list(self):
        with patch(
            "app.connectors.shared.participant_classifier.get_settings",
            return_value=_mock_settings("example.com"),
        ):
            results = classify_participants(["alice@example.com", "bob@other.com"])
            assert results == [False, True]
