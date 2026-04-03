"""Tests for Stage 0 — Eligibility check."""

import pytest
from datetime import datetime, timezone

from app.connectors.shared.normalized_signal import NormalizedParticipant, NormalizedSignal
from app.services.orchestration.contracts import EligibilityReason
from app.services.orchestration.stages.eligibility import check_eligibility


def _make_signal(**kwargs) -> NormalizedSignal:
    defaults = {
        "signal_id": "sig-001",
        "source_type": "email",
        "occurred_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "authored_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "latest_authored_text": "I'll send the report by Friday.",
    }
    defaults.update(kwargs)
    return NormalizedSignal(**defaults)


class TestEligibility:
    def test_eligible_email(self):
        result = check_eligibility(_make_signal())
        assert result.eligible is True
        assert result.reason == EligibilityReason.ok

    def test_eligible_slack(self):
        result = check_eligibility(_make_signal(source_type="slack"))
        assert result.eligible is True

    def test_eligible_meeting(self):
        result = check_eligibility(_make_signal(source_type="meeting"))
        assert result.eligible is True

    def test_ineligible_unsupported_source(self):
        result = check_eligibility(_make_signal(source_type="sms"))
        assert result.eligible is False
        assert result.reason == EligibilityReason.unsupported_source

    def test_ineligible_missing_text_both_empty(self):
        result = check_eligibility(_make_signal(
            latest_authored_text="",
            prior_context_text=None,
        ))
        assert result.eligible is False
        assert result.reason == EligibilityReason.missing_text

    def test_ineligible_missing_text_whitespace_only(self):
        result = check_eligibility(_make_signal(
            latest_authored_text="   ",
            prior_context_text="   ",
        ))
        assert result.eligible is False
        assert result.reason == EligibilityReason.missing_text

    def test_eligible_with_only_prior_context(self):
        result = check_eligibility(_make_signal(
            latest_authored_text="",
            prior_context_text="Some prior context here.",
        ))
        assert result.eligible is True

    def test_ineligible_missing_signal_id(self):
        result = check_eligibility(_make_signal(signal_id=""))
        assert result.eligible is False
        assert result.reason == EligibilityReason.invalid_normalized_signal


class TestBulkMailContentFilter:
    """Stage 0 must reject emails with bulk-mail content indicators."""

    def test_unsubscribe_link_plus_view_in_browser_rejects(self):
        """Two distinct bulk indicators → ineligible."""
        text = (
            "Get 50% off this week only!\n\n"
            "View this email in your browser\n\n"
            "To unsubscribe from these emails, click here."
        )
        result = check_eligibility(_make_signal(latest_authored_text=text))
        assert result.eligible is False
        assert result.reason == EligibilityReason.bulk_mail_content

    def test_unsubscribe_plus_receiving_because_rejects(self):
        """Unsubscribe + mailing list footer → ineligible."""
        text = (
            "Your weekly insurance digest is here.\n\n"
            "You are receiving this email because you signed up.\n\n"
            "Unsubscribe | Manage preferences"
        )
        result = check_eligibility(_make_signal(latest_authored_text=text))
        assert result.eligible is False
        assert result.reason == EligibilityReason.bulk_mail_content

    def test_digest_summary_plus_opt_out_rejects(self):
        """Digest structure + opt-out → ineligible."""
        text = (
            "Your daily digest from Read AI\n\n"
            "Meeting 1: Standup\nMeeting 2: Planning\n\n"
            "Opt out of these emails"
        )
        result = check_eligibility(_make_signal(latest_authored_text=text))
        assert result.eligible is False
        assert result.reason == EligibilityReason.bulk_mail_content

    def test_single_unsubscribe_mention_still_eligible(self):
        """One indicator alone is not enough — legitimate emails may have one."""
        text = (
            "I'll send the quarterly report by Friday.\n\n"
            "Unsubscribe from this thread"
        )
        result = check_eligibility(_make_signal(latest_authored_text=text))
        assert result.eligible is True
        assert result.reason == EligibilityReason.ok

    def test_normal_email_with_commitment_eligible(self):
        """Normal business email passes content filter."""
        text = "I'll have the budget draft ready by end of day Thursday."
        result = check_eligibility(_make_signal(latest_authored_text=text))
        assert result.eligible is True
        assert result.reason == EligibilityReason.ok

    def test_email_preferences_plus_sent_to_rejects(self):
        """Email preferences link + sent-to footer → ineligible."""
        text = (
            "done. 🔥 Check out these results!\n\n"
            "Update your email preferences\n\n"
            "This email was sent to you@example.com"
        )
        result = check_eligibility(_make_signal(latest_authored_text=text))
        assert result.eligible is False
        assert result.reason == EligibilityReason.bulk_mail_content

    def test_manage_subscription_plus_weekly_summary_rejects(self):
        """Manage subscription + digest keyword → ineligible."""
        text = (
            "Weekly summary of your meetings\n\n"
            "You had 5 meetings this week.\n\n"
            "Manage your subscription"
        )
        result = check_eligibility(_make_signal(latest_authored_text=text))
        assert result.eligible is False
        assert result.reason == EligibilityReason.bulk_mail_content

    def test_slack_source_skips_content_filter(self):
        """Content filter only applies to email source type."""
        text = (
            "View this email in your browser\n\n"
            "Unsubscribe from these emails"
        )
        result = check_eligibility(_make_signal(
            source_type="slack",
            latest_authored_text=text,
        ))
        assert result.eligible is True

    def test_case_insensitive_matching(self):
        """Bulk indicators should match case-insensitively."""
        text = (
            "UNSUBSCRIBE FROM THIS LIST\n\n"
            "VIEW THIS EMAIL IN YOUR BROWSER"
        )
        result = check_eligibility(_make_signal(latest_authored_text=text))
        assert result.eligible is False
        assert result.reason == EligibilityReason.bulk_mail_content


class TestNewsletterSenderFilter:
    """Stage 0 must reject emails from newsletter/noreply senders."""

    @pytest.mark.parametrize("sender_email", [
        "newsletter@substack.com",          # GD-E06
        "newsletter@realestate.com",        # GD-E10
        "noreply@calendly.com",             # GD-E15
        "no-reply@github.com",
        "notifications@linkedin.com",
        "updates@medium.com",
        "digest@readai.com",
        "marketing@company.com",
        "promo@deals.com",
        "mailer-daemon@gmail.com",
        "donotreply@service.com",
        "alerts@monitoring.io",
    ])
    def test_newsletter_sender_rejected(self, sender_email: str):
        """Emails from newsletter/noreply senders must be ineligible."""
        signal = _make_signal(
            sender=NormalizedParticipant(email=sender_email),
        )
        result = check_eligibility(signal)
        assert result.eligible is False
        assert result.reason == EligibilityReason.newsletter_sender

    def test_normal_sender_eligible(self):
        """Normal personal sender email passes."""
        signal = _make_signal(
            sender=NormalizedParticipant(email="alice@company.com"),
        )
        result = check_eligibility(signal)
        assert result.eligible is True

    def test_no_sender_still_eligible(self):
        """Missing sender doesn't trigger newsletter filter."""
        signal = _make_signal()  # no sender set
        result = check_eligibility(signal)
        assert result.eligible is True

    def test_slack_source_skips_sender_filter(self):
        """Newsletter sender filter only applies to email source type."""
        signal = _make_signal(
            source_type="slack",
            sender=NormalizedParticipant(email="noreply@service.com"),
        )
        result = check_eligibility(signal)
        assert result.eligible is True


class TestListUnsubscribeHeaderFilter:
    """Stage 0 must reject emails with List-Unsubscribe header."""

    def test_list_unsubscribe_header_rejects(self):
        """Email with List-Unsubscribe header must be ineligible."""
        signal = _make_signal(
            metadata={"headers": {"List-Unsubscribe": "<mailto:unsub@example.com>"}},
        )
        result = check_eligibility(signal)
        assert result.eligible is False
        assert result.reason == EligibilityReason.automated_sender_header

    def test_list_unsubscribe_case_insensitive(self):
        """Header check should be case-insensitive."""
        signal = _make_signal(
            metadata={"headers": {"list-unsubscribe": "<mailto:unsub@example.com>"}},
        )
        result = check_eligibility(signal)
        assert result.eligible is False
        assert result.reason == EligibilityReason.automated_sender_header

    def test_no_list_unsubscribe_header_eligible(self):
        """Email without List-Unsubscribe header passes."""
        signal = _make_signal(
            metadata={"headers": {"From": "alice@company.com"}},
        )
        result = check_eligibility(signal)
        assert result.eligible is True

    def test_empty_headers_eligible(self):
        """Email with empty headers dict passes."""
        signal = _make_signal(metadata={"headers": {}})
        result = check_eligibility(signal)
        assert result.eligible is True

    def test_slack_source_skips_header_filter(self):
        """Header filter only applies to email source type."""
        signal = _make_signal(
            source_type="slack",
            metadata={"headers": {"List-Unsubscribe": "<mailto:unsub@example.com>"}},
        )
        result = check_eligibility(signal)
        assert result.eligible is True


class TestFragmentTooShort:
    """Stage 0 must reject signals where text is too short (fragment gate)."""

    @pytest.mark.parametrize("fragment", [
        "done.",         # GD-E07 — 5 chars
        "done",          # 4 chars
        "We'll",         # 5 chars
        "well.",         # 5 chars
        "actually",      # 8 chars
        "instead?",      # 8 chars
        "Will you?",     # 9 chars
        "ok",
        "yes",
        "no",
    ])
    def test_short_fragment_rejected(self, fragment: str):
        """Text under 10 characters must be ineligible."""
        signal = _make_signal(latest_authored_text=fragment)
        result = check_eligibility(signal)
        assert result.eligible is False
        assert result.reason == EligibilityReason.fragment_too_short

    def test_exactly_10_chars_eligible(self):
        """Text with exactly 10 chars passes fragment check."""
        signal = _make_signal(latest_authored_text="a" * 10)
        result = check_eligibility(signal)
        assert result.eligible is True

    def test_whitespace_stripped_before_check(self):
        """Whitespace-padded short text is stripped before length check."""
        signal = _make_signal(latest_authored_text="   done   ")
        result = check_eligibility(signal)
        assert result.eligible is False
        assert result.reason == EligibilityReason.fragment_too_short

    def test_prior_context_not_affected(self):
        """Fragment check applies to latest_authored_text, not prior_context."""
        signal = _make_signal(
            latest_authored_text="",
            prior_context_text="ok",
        )
        # This should fail on missing_text (empty authored) or be eligible
        # prior_context alone satisfying text presence is OK; fragment
        # check only matters for authored text
        result = check_eligibility(signal)
        # prior_context "ok" is only 2 chars but fragment check is on authored text
        # With empty authored text — it hits missing_text check first
        # (only prior_context satisfies text presence)
        # Actually: has_prior is True ("ok" is truthy), has_authored is False
        # So it passes the text-presence check. Then fragment check on authored_text
        # should still be OK since prior_context provides the substance.
        assert result.eligible is True
