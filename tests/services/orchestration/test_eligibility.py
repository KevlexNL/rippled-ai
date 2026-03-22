"""Tests for Stage 0 — Eligibility check."""

import pytest
from datetime import datetime, timezone

from app.connectors.shared.normalized_signal import NormalizedSignal
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
