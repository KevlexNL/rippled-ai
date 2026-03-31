"""Tests for WO-RIPPLED-LEARNING-LOOP — three-tier detection funnel.

Test strategy:
- Profile matcher: Tier 1 pattern matching against user profile
- Sender suppression: newsletter detection and suppression list
- Learning loop: profile updates after LLM and after user dismissal
- Detection audit: tier usage logging
- Integration: full funnel flow with mocked DB

Uses SimpleNamespace to avoid SQLAlchemy instrumentation (same pattern as test_detection.py).
"""
from __future__ import annotations

import types
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_item(**kwargs):
    """Create a minimal SourceItem-like namespace for testing."""
    defaults = {
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


def _make_profile(**kwargs):
    """Create a minimal UserCommitmentProfile-like namespace."""
    defaults = {
        "id": "profile-001",
        "user_id": "user-001",
        "trigger_phrases": ["i'll send", "i will follow up", "let me handle"],
        "high_signal_senders": ["boss@company.com", "client@external.com"],
        "domains": ["follow_up", "send", "review"],
        "suppressed_senders": ["newsletter@marketing.com", "no-reply@github.com"],
        "sender_weights": {"boss@company.com": 5, "client@external.com": 3},
        "phrase_weights": {"i'll send": 8, "i will follow up": 4, "let me handle": 2},
        "total_items_processed": 100,
        "total_commitments_found": 25,
    }
    defaults.update(kwargs)
    return types.SimpleNamespace(**defaults)


# ---------------------------------------------------------------------------
# Tier 1 — Profile pattern matching
# ---------------------------------------------------------------------------

class TestProfileMatcher:
    """Tier 1: match source item content against user profile trigger phrases."""

    def test_matches_trigger_phrase_case_insensitive(self):
        from app.services.detection.profile_matcher import check_trigger_phrases

        profile = _make_profile()
        content = "Hey, I'll send the report by Monday"
        result = check_trigger_phrases(profile, content)
        assert result is not None
        assert result["matched_phrase"] == "i'll send"
        assert result["confidence"] > 0

    def test_no_match_returns_none(self):
        from app.services.detection.profile_matcher import check_trigger_phrases

        profile = _make_profile()
        content = "Just checking in on the project status"
        result = check_trigger_phrases(profile, content)
        assert result is None

    def test_higher_weight_phrase_gives_higher_confidence(self):
        from app.services.detection.profile_matcher import check_trigger_phrases

        profile = _make_profile()
        # "i'll send" has weight 8, "let me handle" has weight 2
        result_high = check_trigger_phrases(profile, "I'll send it tomorrow")
        result_low = check_trigger_phrases(profile, "Let me handle that")
        assert result_high is not None
        assert result_low is not None
        assert result_high["confidence"] > result_low["confidence"]

    def test_matches_high_signal_sender(self):
        from app.services.detection.profile_matcher import check_high_signal_sender

        profile = _make_profile()
        result = check_high_signal_sender(profile, "boss@company.com")
        assert result is True

    def test_sender_match_case_insensitive(self):
        from app.services.detection.profile_matcher import check_high_signal_sender

        profile = _make_profile()
        result = check_high_signal_sender(profile, "Boss@Company.com")
        assert result is True

    def test_unknown_sender_not_matched(self):
        from app.services.detection.profile_matcher import check_high_signal_sender

        profile = _make_profile()
        result = check_high_signal_sender(profile, "random@unknown.com")
        assert result is False

    def test_empty_profile_no_match(self):
        from app.services.detection.profile_matcher import check_trigger_phrases

        profile = _make_profile(trigger_phrases=[], phrase_weights={})
        result = check_trigger_phrases(profile, "I'll send the report")
        assert result is None

    def test_none_profile_no_match(self):
        from app.services.detection.profile_matcher import check_trigger_phrases

        profile = _make_profile(trigger_phrases=None, phrase_weights=None)
        result = check_trigger_phrases(profile, "I'll send the report")
        assert result is None

    def test_run_tier1_combines_phrase_and_sender(self):
        """Tier 1 should match on either trigger phrase or high signal sender + content."""
        from app.services.detection.profile_matcher import run_tier1

        profile = _make_profile()
        item = _make_item(
            sender_email="boss@company.com",
            content_normalized="I'll send the contract",
        )
        result = run_tier1(profile, item)
        assert result is not None
        assert result["tier"] == "tier_1"
        assert result["matched_phrase"] is not None

    def test_run_tier1_sender_only_not_sufficient(self):
        """A high-signal sender alone without a trigger phrase should not match Tier 1."""
        from app.services.detection.profile_matcher import run_tier1

        profile = _make_profile()
        item = _make_item(
            sender_email="boss@company.com",
            content_normalized="Thanks for the update",
        )
        result = run_tier1(profile, item)
        assert result is None

    def test_run_tier1_phrase_from_unknown_sender_still_matches(self):
        """A trigger phrase from an unknown sender should still match Tier 1."""
        from app.services.detection.profile_matcher import run_tier1

        profile = _make_profile()
        item = _make_item(
            sender_email="random@unknown.com",
            content_normalized="I'll send the report by Friday",
        )
        result = run_tier1(profile, item)
        assert result is not None
        assert result["matched_phrase"] == "i'll send"


# ---------------------------------------------------------------------------
# Sender suppression
# ---------------------------------------------------------------------------

class TestSenderSuppression:
    """Sender pre-filter: suppress newsletters, no-reply, etc."""

    def test_suppressed_sender_detected(self):
        from app.services.detection.profile_matcher import is_sender_suppressed

        profile = _make_profile()
        assert is_sender_suppressed(profile, "newsletter@marketing.com") is True

    def test_non_suppressed_sender_allowed(self):
        from app.services.detection.profile_matcher import is_sender_suppressed

        profile = _make_profile()
        assert is_sender_suppressed(profile, "boss@company.com") is False

    def test_auto_detect_newsletter_no_reply(self):
        from app.services.detection.profile_matcher import detect_newsletter_sender

        assert detect_newsletter_sender("no-reply@service.com") is True
        assert detect_newsletter_sender("noreply@service.com") is True
        assert detect_newsletter_sender("donotreply@service.com") is True

    def test_auto_detect_newsletter_patterns(self):
        from app.services.detection.profile_matcher import detect_newsletter_sender

        assert detect_newsletter_sender("newsletter@company.com") is True
        assert detect_newsletter_sender("notifications@github.com") is True
        assert detect_newsletter_sender("mailer-daemon@server.com") is True
        assert detect_newsletter_sender("updates@service.com") is True

    def test_auto_detect_plural_newsletter(self):
        """newsletters@ (plural) must be caught — WO-RIPPLED-ELIGIBILITY-FILTER."""
        from app.services.detection.profile_matcher import detect_newsletter_sender

        assert detect_newsletter_sender("newsletters@medium.com") is True

    def test_auto_detect_prefixed_noreply(self):
        """Prefixed noreply like CloudPlatform-noreply@ must be caught — WO-RIPPLED-ELIGIBILITY-FILTER."""
        from app.services.detection.profile_matcher import detect_newsletter_sender

        assert detect_newsletter_sender("CloudPlatform-noreply@google.com") is True
        assert detect_newsletter_sender("billing-noreply@google.com") is True
        assert detect_newsletter_sender("security-alerts@google.com") is True

    def test_auto_detect_prefixed_newsletter(self):
        """Prefixed newsletter like weekly-newsletter@ must be caught."""
        from app.services.detection.profile_matcher import detect_newsletter_sender

        assert detect_newsletter_sender("weekly-newsletter@company.com") is True
        assert detect_newsletter_sender("daily-digest@service.com") is True

    def test_normal_sender_not_newsletter(self):
        from app.services.detection.profile_matcher import detect_newsletter_sender

        assert detect_newsletter_sender("alice@company.com") is False
        assert detect_newsletter_sender("bob.smith@client.com") is False
        # Names that happen to contain filter words should NOT match
        assert detect_newsletter_sender("alice.noreply-team@company.com") is False

    def test_suppressed_sender_case_insensitive(self):
        from app.services.detection.profile_matcher import is_sender_suppressed

        profile = _make_profile()
        assert is_sender_suppressed(profile, "Newsletter@Marketing.com") is True

    def test_empty_suppressed_list_still_auto_detects(self):
        from app.services.detection.profile_matcher import is_sender_suppressed

        profile = _make_profile(suppressed_senders=[])
        # Auto-detection still catches newsletter patterns
        assert is_sender_suppressed(profile, "newsletter@marketing.com") is True
        # But normal senders pass through
        assert is_sender_suppressed(profile, "alice@company.com") is False

    def test_none_suppressed_list_still_auto_detects(self):
        from app.services.detection.profile_matcher import is_sender_suppressed

        profile = _make_profile(suppressed_senders=None)
        assert is_sender_suppressed(profile, "newsletter@marketing.com") is True
        assert is_sender_suppressed(profile, "alice@company.com") is False


# ---------------------------------------------------------------------------
# Learning loop — profile update after LLM detection
# ---------------------------------------------------------------------------

class TestLearningLoop:
    """Profile updates after LLM (Tier 3) decision and user dismissal."""

    def test_update_profile_adds_new_trigger_phrase(self):
        from app.services.detection.learning_loop import extract_and_update_phrases

        profile = _make_profile()
        old_phrases = list(profile.trigger_phrases)
        extract_and_update_phrases(profile, "I'll coordinate with the team")
        assert "i'll coordinate with the team" in profile.trigger_phrases
        assert len(profile.trigger_phrases) > len(old_phrases)

    def test_update_profile_does_not_duplicate_phrase(self):
        from app.services.detection.learning_loop import extract_and_update_phrases

        profile = _make_profile()
        original_len = len(profile.trigger_phrases)
        extract_and_update_phrases(profile, "I'll send the report")
        # "i'll send" is already in the profile; shouldn't add duplicate
        assert len(profile.trigger_phrases) == original_len

    def test_update_profile_increments_phrase_weight(self):
        from app.services.detection.learning_loop import extract_and_update_phrases

        profile = _make_profile()
        old_weight = profile.phrase_weights.get("i'll send", 0)
        extract_and_update_phrases(profile, "I'll send the documents tomorrow")
        assert profile.phrase_weights["i'll send"] == old_weight + 1

    def test_update_sender_weight(self):
        from app.services.detection.learning_loop import update_sender_weight

        profile = _make_profile()
        old_weight = profile.sender_weights.get("boss@company.com", 0)
        update_sender_weight(profile, "boss@company.com")
        assert profile.sender_weights["boss@company.com"] == old_weight + 1

    def test_update_sender_adds_new_sender(self):
        from app.services.detection.learning_loop import update_sender_weight

        profile = _make_profile()
        update_sender_weight(profile, "new-sender@example.com")
        assert "new-sender@example.com" in profile.sender_weights
        assert profile.sender_weights["new-sender@example.com"] == 1
        assert "new-sender@example.com" in profile.high_signal_senders

    def test_downweight_phrase_on_dismissal(self):
        from app.services.detection.learning_loop import downweight_phrase

        profile = _make_profile()
        old_weight = profile.phrase_weights.get("i'll send", 0)
        downweight_phrase(profile, "I'll send")
        assert profile.phrase_weights["i'll send"] == old_weight - 1

    def test_downweight_removes_phrase_at_zero(self):
        from app.services.detection.learning_loop import downweight_phrase

        profile = _make_profile(
            phrase_weights={"i'll send": 1},
            trigger_phrases=["i'll send"],
        )
        downweight_phrase(profile, "I'll send")
        assert "i'll send" not in profile.trigger_phrases
        assert profile.phrase_weights.get("i'll send", 0) == 0

    def test_downweight_sender_on_dismissal(self):
        from app.services.detection.learning_loop import downweight_sender

        profile = _make_profile()
        old_weight = profile.sender_weights.get("boss@company.com", 0)
        downweight_sender(profile, "boss@company.com")
        assert profile.sender_weights["boss@company.com"] == old_weight - 1

    def test_downweight_sender_removes_at_zero(self):
        from app.services.detection.learning_loop import downweight_sender

        profile = _make_profile(
            sender_weights={"boss@company.com": 1},
            high_signal_senders=["boss@company.com"],
        )
        downweight_sender(profile, "boss@company.com")
        assert "boss@company.com" not in profile.high_signal_senders

    def test_cap_trigger_phrases_at_50(self):
        """Profile should not grow unbounded."""
        from app.services.detection.learning_loop import extract_and_update_phrases

        phrases = [f"phrase_{i}" for i in range(50)]
        weights = {f"phrase_{i}": 1 for i in range(50)}
        profile = _make_profile(trigger_phrases=phrases, phrase_weights=weights)
        extract_and_update_phrases(profile, "I'll build the new feature")
        # Should be capped at 50 (lowest weight dropped)
        assert len(profile.trigger_phrases) <= 50


# ---------------------------------------------------------------------------
# Detection audit logging
# ---------------------------------------------------------------------------

class TestDetectionAudit:
    """Tier usage is logged and queryable."""

    def test_log_tier1_detection(self):
        from app.services.detection.audit import create_audit_entry

        entry = create_audit_entry(
            source_item_id="item-001",
            user_id="user-001",
            tier_used="tier_1",
            matched_phrase="i'll send",
            matched_sender="boss@company.com",
            confidence=Decimal("0.850"),
            commitment_created=True,
        )
        assert entry["tier_used"] == "tier_1"
        assert entry["matched_phrase"] == "i'll send"
        assert entry["commitment_created"] is True

    def test_log_tier3_detection(self):
        from app.services.detection.audit import create_audit_entry

        entry = create_audit_entry(
            source_item_id="item-002",
            user_id="user-001",
            tier_used="tier_3",
            confidence=Decimal("0.600"),
            commitment_created=True,
        )
        assert entry["tier_used"] == "tier_3"
        assert entry["matched_phrase"] is None
        assert entry["commitment_created"] is True

    def test_log_pattern_detection(self):
        from app.services.detection.audit import create_audit_entry

        entry = create_audit_entry(
            source_item_id="item-003",
            user_id="user-001",
            tier_used="pattern",
            matched_phrase="i will full",
            confidence=Decimal("0.800"),
            commitment_created=False,
        )
        assert entry["tier_used"] == "pattern"


# ---------------------------------------------------------------------------
# Full funnel integration
# ---------------------------------------------------------------------------

class TestDetectionFunnel:
    """Integration: three-tier funnel with profile check before pattern/LLM."""

    def test_suppressed_sender_skips_all_detection(self):
        from app.services.detection.profile_matcher import should_skip_detection

        profile = _make_profile()
        item = _make_item(sender_email="newsletter@marketing.com")
        assert should_skip_detection(profile, item) is True

    def test_auto_detected_newsletter_skips_detection(self):
        from app.services.detection.profile_matcher import should_skip_detection

        profile = _make_profile()
        item = _make_item(sender_email="no-reply@automated-service.com")
        assert should_skip_detection(profile, item) is True

    def test_normal_sender_does_not_skip(self):
        from app.services.detection.profile_matcher import should_skip_detection

        profile = _make_profile()
        item = _make_item(sender_email="boss@company.com")
        assert should_skip_detection(profile, item) is False

    def test_no_profile_falls_through(self):
        """If no user profile exists, all tiers should be skipped gracefully."""
        from app.services.detection.profile_matcher import run_tier1

        result = run_tier1(None, _make_item(content_normalized="I'll send the report"))
        assert result is None

    def test_suppressed_sender_with_none_profile(self):
        from app.services.detection.profile_matcher import should_skip_detection

        assert should_skip_detection(None, _make_item(sender_email="no-reply@service.com")) is True

    def test_wo_eligibility_filter_leak_senders_blocked(self):
        """Regression: exact senders from WO-RIPPLED-ELIGIBILITY-FILTER must be blocked."""
        from app.services.detection.profile_matcher import should_skip_detection

        leaked_senders = [
            "newsletters@medium.com",
            "CloudPlatform-noreply@google.com",
            "billing-noreply@google.com",
        ]
        for sender in leaked_senders:
            item = _make_item(sender_email=sender)
            assert should_skip_detection(None, item) is True, f"{sender} should be blocked"
