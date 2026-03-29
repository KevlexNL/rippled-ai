"""Tests for Slack prompt overlay — WO-RIPPLED-SLACK-SPECIFIC-PROMPT-OVERLAY.

Verifies:
1. Overlay module exports expected constants
2. Extraction stage appends hints for Slack signals, not for others
3. Speech-act stage appends hints for Slack signals, not for others
4. System prompt gets addendum for Slack signals
"""

import pytest

from app.services.orchestration.prompts.slack_overlay import (
    EXTRACTION_HINTS,
    SPEECH_ACT_HINTS,
    SYSTEM_ADDENDUM,
    VERSION,
)


class TestSlackOverlayConstants:
    """Overlay module must export the required constants."""

    def test_version_is_set(self):
        assert VERSION == "slack_overlay_v1"

    def test_system_addendum_not_empty(self):
        assert len(SYSTEM_ADDENDUM) > 100

    def test_extraction_hints_not_empty(self):
        assert len(EXTRACTION_HINTS) > 20

    def test_speech_act_hints_not_empty(self):
        assert len(SPEECH_ACT_HINTS) > 20

    def test_system_addendum_mentions_slack(self):
        assert "slack" in SYSTEM_ADDENDUM.lower()

    def test_extraction_hints_mentions_prior_context(self):
        assert "prior_context_text" in EXTRACTION_HINTS

    def test_speech_act_hints_mentions_commit(self):
        assert "COMMIT" in SPEECH_ACT_HINTS


class TestExtractionSlackOverlay:
    """Extraction stage appends Slack hints when source_type == 'slack'."""

    def test_slack_signal_gets_extraction_hints(self):
        from app.services.orchestration.prompts import extraction as prompt

        user_prompt = prompt.build_user_prompt(
            latest_authored_text="will do",
            prior_context_text="can you handle the deploy?",
            source_type="slack",
            subject=None,
            direction=None,
            speech_act="acceptance",
            speech_act_confidence=0.9,
            candidate_type="commitment_candidate",
        )
        assert EXTRACTION_HINTS in user_prompt

    def test_email_signal_no_extraction_hints(self):
        from app.services.orchestration.prompts import extraction as prompt

        user_prompt = prompt.build_user_prompt(
            latest_authored_text="I will send the report by Friday.",
            prior_context_text=None,
            source_type="email",
            subject="Report",
            direction="outbound",
            speech_act="self_commitment",
            speech_act_confidence=0.95,
            candidate_type="commitment_candidate",
        )
        assert EXTRACTION_HINTS not in user_prompt

    def test_meeting_signal_no_extraction_hints(self):
        from app.services.orchestration.prompts import extraction as prompt

        user_prompt = prompt.build_user_prompt(
            latest_authored_text="I'll take care of that.",
            prior_context_text=None,
            source_type="meeting",
            subject=None,
            direction=None,
            speech_act="self_commitment",
            speech_act_confidence=0.85,
            candidate_type="commitment_candidate",
            participants=["Alice", "Bob"],
        )
        assert EXTRACTION_HINTS not in user_prompt


class TestSpeechActSlackOverlay:
    """Speech-act stage appends Slack hints when source_type == 'slack'."""

    def test_slack_signal_gets_speech_act_hints(self):
        from app.services.orchestration.prompts import speech_act as prompt

        user_prompt = prompt.build_user_prompt(
            latest_authored_text="on it",
            prior_context_text="@kevin can you review this PR?",
            source_type="slack",
            subject=None,
            direction=None,
            candidate_type="commitment_candidate",
            gate_confidence=0.75,
        )
        assert SPEECH_ACT_HINTS in user_prompt

    def test_email_signal_no_speech_act_hints(self):
        from app.services.orchestration.prompts import speech_act as prompt

        user_prompt = prompt.build_user_prompt(
            latest_authored_text="I will handle it.",
            prior_context_text=None,
            source_type="email",
            subject="Task",
            direction="outbound",
            candidate_type="commitment_candidate",
            gate_confidence=0.9,
        )
        assert SPEECH_ACT_HINTS not in user_prompt


class TestSystemPromptSlackOverlay:
    """Extraction and speech-act stages use augmented system prompts for Slack."""

    def test_extraction_system_prompt_augmented_for_slack(self):
        from app.services.orchestration.prompts.extraction import (
            build_system_prompt,
        )

        system = build_system_prompt("slack")
        assert SYSTEM_ADDENDUM in system

    def test_extraction_system_prompt_unchanged_for_email(self):
        from app.services.orchestration.prompts.extraction import (
            SYSTEM_PROMPT,
            build_system_prompt,
        )

        system = build_system_prompt("email")
        assert system == SYSTEM_PROMPT

    def test_speech_act_system_prompt_augmented_for_slack(self):
        from app.services.orchestration.prompts.speech_act import (
            build_system_prompt,
        )

        system = build_system_prompt("slack")
        assert SYSTEM_ADDENDUM in system

    def test_speech_act_system_prompt_unchanged_for_meeting(self):
        from app.services.orchestration.prompts.speech_act import (
            SYSTEM_PROMPT,
            build_system_prompt,
        )

        system = build_system_prompt("meeting")
        assert system == SYSTEM_PROMPT
