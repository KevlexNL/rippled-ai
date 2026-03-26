"""Tests for WO-RIPPLED-MEETING-PROCESSING-SPEC.

Verifies meeting-specific prompt building, action item extraction,
speaker→owner mapping, and no regression on email detection.
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.models.orm import SourceItem


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_meeting_item(
    content: str = "[Alice]: I'll prepare the report by Friday.\n[Bob]: Sounds good.",
    metadata: dict | None = None,
) -> SourceItem:
    item = MagicMock(spec=SourceItem)
    item.id = "meeting-item-001"
    item.content = content
    item.content_normalized = content
    item.source_type = "meeting"
    item.sender_name = "Alice"
    item.sender_email = "alice@example.com"
    item.direction = None
    item.metadata_ = metadata or {
        "title": "Sprint Planning",
        "segments": [
            {"speaker": "Alice", "text": "I'll prepare the report by Friday.", "start_seconds": 0, "end_seconds": 5},
            {"speaker": "Bob", "text": "Sounds good.", "start_seconds": 5, "end_seconds": 8},
        ],
    }
    return item


def _make_readai_meeting_item() -> SourceItem:
    """Meeting item with Read.ai action items in metadata."""
    item = _make_meeting_item(
        content="[Kevin]: I'll send the budget update by EOD.\n[Sarah]: Can you also check the vendor contract?",
        metadata={
            "title": "Budget Review",
            "reference_action_items": [
                {"title": "Send budget update", "assignee": "Kevin", "due": "EOD"},
                {"title": "Check vendor contract", "assignee": "Kevin"},
            ],
            "segments": [
                {"speaker": "Kevin", "text": "I'll send the budget update by EOD.", "start_seconds": 0, "end_seconds": 5},
                {"speaker": "Sarah", "text": "Can you also check the vendor contract?", "start_seconds": 5, "end_seconds": 10},
            ],
        },
    )
    return item


def _make_email_item(
    content: str = "I will send the report by Friday",
) -> SourceItem:
    item = MagicMock(spec=SourceItem)
    item.id = "email-item-001"
    item.content = content
    item.content_normalized = content
    item.source_type = "email"
    item.sender_name = "Alice"
    item.sender_email = "alice@example.com"
    item.direction = "inbound"
    item.metadata_ = {"subject": "Weekly report"}
    return item


def _mock_llm_response(commitments: list[dict] | None = None):
    """Build an Anthropic-style mock response."""
    payload = {"commitments": commitments or []}
    mock_content = SimpleNamespace(text=json.dumps(payload))
    return SimpleNamespace(
        content=[mock_content],
        usage=SimpleNamespace(input_tokens=100, output_tokens=50),
    )


# ---------------------------------------------------------------------------
# Test: meeting-specific prompt content
# ---------------------------------------------------------------------------

class TestMeetingPromptContent:
    """Seed detector must build meeting-specific context in the user message."""

    def test_meeting_prompt_includes_meeting_title(self):
        from app.services.detection.seed_detector import _extract_commitments

        client = MagicMock()
        client.messages.create.return_value = _mock_llm_response()

        item = _make_meeting_item()
        _extract_commitments(client, "claude-sonnet-4-6", item)

        call_args = client.messages.create.call_args
        user_msg = call_args.kwargs["messages"][0]["content"]
        assert "Sprint Planning" in user_msg, (
            "Meeting title must appear in the user message for context"
        )

    def test_meeting_prompt_includes_participants(self):
        from app.services.detection.seed_detector import _extract_commitments

        client = MagicMock()
        client.messages.create.return_value = _mock_llm_response()

        item = _make_meeting_item()
        _extract_commitments(client, "claude-sonnet-4-6", item)

        call_args = client.messages.create.call_args
        user_msg = call_args.kwargs["messages"][0]["content"]
        assert "Participants:" in user_msg or "Speakers:" in user_msg, (
            "Meeting prompt must list participants/speakers"
        )

    def test_meeting_prompt_includes_source_type_meeting(self):
        from app.services.detection.seed_detector import _extract_commitments

        client = MagicMock()
        client.messages.create.return_value = _mock_llm_response()

        item = _make_meeting_item()
        _extract_commitments(client, "claude-sonnet-4-6", item)

        call_args = client.messages.create.call_args
        user_msg = call_args.kwargs["messages"][0]["content"]
        assert "Source type: meeting" in user_msg

    def test_meeting_system_prompt_has_meeting_section(self):
        """System prompt must include meeting-specific instructions."""
        from app.services.detection.seed_detector import _extract_commitments

        client = MagicMock()
        client.messages.create.return_value = _mock_llm_response()

        item = _make_meeting_item()
        _extract_commitments(client, "claude-sonnet-4-6", item)

        call_args = client.messages.create.call_args
        system_prompt = call_args.kwargs["system"]
        assert "meeting" in system_prompt.lower(), (
            "System prompt must contain meeting-specific instructions"
        )
        assert "speaker" in system_prompt.lower(), (
            "System prompt must reference speaker labels"
        )


# ---------------------------------------------------------------------------
# Test: Read.ai action items as high-confidence hints
# ---------------------------------------------------------------------------

class TestReadAiActionItems:
    """Read.ai action items in metadata must be surfaced as hints in the prompt."""

    def test_action_items_included_in_prompt(self):
        from app.services.detection.seed_detector import _extract_commitments

        client = MagicMock()
        client.messages.create.return_value = _mock_llm_response()

        item = _make_readai_meeting_item()
        _extract_commitments(client, "claude-sonnet-4-6", item)

        call_args = client.messages.create.call_args
        user_msg = call_args.kwargs["messages"][0]["content"]
        assert "Send budget update" in user_msg, (
            "Read.ai action items must appear in the meeting prompt"
        )
        assert "Check vendor contract" in user_msg, (
            "All Read.ai action items must be included"
        )

    def test_action_items_labeled_as_high_confidence(self):
        from app.services.detection.seed_detector import _extract_commitments

        client = MagicMock()
        client.messages.create.return_value = _mock_llm_response()

        item = _make_readai_meeting_item()
        _extract_commitments(client, "claude-sonnet-4-6", item)

        call_args = client.messages.create.call_args
        user_msg = call_args.kwargs["messages"][0]["content"]
        # The action items section should indicate these are high-confidence
        assert "action item" in user_msg.lower() or "high-confidence" in user_msg.lower(), (
            "Action items must be labeled as high-confidence signals"
        )

    def test_no_action_items_section_when_none_present(self):
        from app.services.detection.seed_detector import _extract_commitments

        client = MagicMock()
        client.messages.create.return_value = _mock_llm_response()

        item = _make_meeting_item()  # no reference_action_items
        _extract_commitments(client, "claude-sonnet-4-6", item)

        call_args = client.messages.create.call_args
        user_msg = call_args.kwargs["messages"][0]["content"]
        assert "ACTION ITEMS" not in user_msg, (
            "Should not include action items section when none exist"
        )


# ---------------------------------------------------------------------------
# Test: no email regression
# ---------------------------------------------------------------------------

class TestNoEmailRegression:
    """Email source items must NOT receive meeting-specific prompt content."""

    def test_email_prompt_no_meeting_title(self):
        from app.services.detection.seed_detector import _extract_commitments

        client = MagicMock()
        client.messages.create.return_value = _mock_llm_response()

        item = _make_email_item()
        _extract_commitments(client, "claude-sonnet-4-6", item)

        call_args = client.messages.create.call_args
        user_msg = call_args.kwargs["messages"][0]["content"]
        assert "Meeting title:" not in user_msg
        assert "Participants:" not in user_msg or "Speakers:" not in user_msg

    def test_email_prompt_no_action_items(self):
        from app.services.detection.seed_detector import _extract_commitments

        client = MagicMock()
        client.messages.create.return_value = _mock_llm_response()

        item = _make_email_item()
        _extract_commitments(client, "claude-sonnet-4-6", item)

        call_args = client.messages.create.call_args
        user_msg = call_args.kwargs["messages"][0]["content"]
        assert "ACTION ITEMS" not in user_msg

    def test_email_uses_current_message_prior_context_format(self):
        from app.services.detection.seed_detector import _extract_commitments

        client = MagicMock()
        client.messages.create.return_value = _mock_llm_response()

        item = _make_email_item()
        _extract_commitments(client, "claude-sonnet-4-6", item)

        call_args = client.messages.create.call_args
        user_msg = call_args.kwargs["messages"][0]["content"]
        assert "[CURRENT MESSAGE]" in user_msg


# ---------------------------------------------------------------------------
# Test: speech act prompt meeting awareness
# ---------------------------------------------------------------------------

class TestSpeechActMeetingAwareness:
    """Speech act prompt must include meeting-specific guidance."""

    def test_meeting_user_prompt_includes_participants(self):
        from app.services.orchestration.prompts.speech_act import build_user_prompt

        result = build_user_prompt(
            latest_authored_text="[Kevin]: I'll handle the deployment.",
            prior_context_text=None,
            source_type="meeting",
            subject="Sprint Planning",
            direction=None,
            candidate_type="self_commitment",
            gate_confidence=0.85,
            participants=["Kevin", "Sarah", "Bob"],
        )
        assert "Kevin" in result
        assert "Sarah" in result

    def test_email_user_prompt_unchanged(self):
        """Email prompts must still work without participants param."""
        from app.services.orchestration.prompts.speech_act import build_user_prompt

        result = build_user_prompt(
            latest_authored_text="I will send the report.",
            prior_context_text=None,
            source_type="email",
            subject="Report",
            direction="inbound",
            candidate_type="self_commitment",
            gate_confidence=0.85,
        )
        assert "Source type: email" in result


# ---------------------------------------------------------------------------
# Test: extraction prompt meeting awareness
# ---------------------------------------------------------------------------

class TestExtractionMeetingAwareness:
    """Extraction prompt must map speakers to owner roles for meetings."""

    def test_meeting_extraction_prompt_includes_participants(self):
        from app.services.orchestration.prompts.extraction import build_user_prompt

        result = build_user_prompt(
            latest_authored_text="[Kevin]: I'll handle the deployment.",
            prior_context_text=None,
            source_type="meeting",
            subject="Sprint Planning",
            direction=None,
            speech_act="self_commitment",
            speech_act_confidence=0.85,
            candidate_type="self_commitment",
            participants=["Kevin", "Sarah"],
        )
        assert "Kevin" in result
        assert "Sarah" in result

    def test_email_extraction_prompt_unchanged(self):
        """Email prompts must still work without participants param."""
        from app.services.orchestration.prompts.extraction import build_user_prompt

        result = build_user_prompt(
            latest_authored_text="I will send the report.",
            prior_context_text=None,
            source_type="email",
            subject="Report",
            direction="inbound",
            speech_act="self_commitment",
            speech_act_confidence=0.85,
            candidate_type="self_commitment",
        )
        assert "Source type: email" in result
