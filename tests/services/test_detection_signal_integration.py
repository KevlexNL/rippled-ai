"""Tests for detection services using NormalizedSignal contract."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from app.connectors.shared.normalized_signal import NormalizedSignal, Participant
from app.services.model_detection import ModelDetectionService


class TestSeedDetectorWithSignal:
    """Verify _extract_commitments uses NormalizedSignal when provided."""

    def _make_signal(self, latest_text="I'll send the report.", prior_context=None):
        return NormalizedSignal(
            signal_id="msg-001",
            source_type="email",
            source_thread_id=None,
            source_message_id="msg-001",
            occurred_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            authored_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            actor_participants=[Participant(name="Alice", email="alice@example.com", role="sender")],
            addressed_participants=[Participant(email="bob@example.com", role="recipient")],
            visible_participants=[],
            latest_authored_text=latest_text,
            prior_context_text=prior_context,
        )

    def _make_item(self):
        item = MagicMock()
        item.content = "Full raw body with quoted history"
        item.content_normalized = "Full raw body lowercased"
        item.source_type = "email"
        item.sender_name = "Alice"
        item.sender_email = "alice@example.com"
        item.direction = "inbound"
        item.metadata_ = {"prior_context": "old quoted stuff"}
        item.id = "item-001"
        return item

    def test_signal_latest_text_used_over_item_content(self):
        """When signal is provided, latest_authored_text is used for detection."""
        from app.services.detection.seed_detector import _extract_commitments

        signal = self._make_signal(latest_text="I'll follow up on the budget.")
        item = self._make_item()

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"commitments": []}')]
        mock_response.usage = MagicMock(input_tokens=100, output_tokens=50)
        mock_client.messages.create.return_value = mock_response

        _extract_commitments(mock_client, "claude-sonnet-4-6", item, signal=signal)

        # Verify the user message contains signal text, not item text
        call_args = mock_client.messages.create.call_args
        user_msg = call_args[1]["messages"][0]["content"]
        assert "I'll follow up on the budget." in user_msg
        assert "Full raw body" not in user_msg

    def test_signal_prior_context_labelled_as_reference(self):
        """Prior context from signal is explicitly labelled as reference-only."""
        from app.services.detection.seed_detector import _extract_commitments

        signal = self._make_signal(
            latest_text="I'll handle the deployment.",
            prior_context="Can you take care of the deployment? — Bob"
        )
        item = self._make_item()

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"commitments": []}')]
        mock_response.usage = MagicMock(input_tokens=100, output_tokens=50)
        mock_client.messages.create.return_value = mock_response

        _extract_commitments(mock_client, "claude-sonnet-4-6", item, signal=signal)

        call_args = mock_client.messages.create.call_args
        user_msg = call_args[1]["messages"][0]["content"]
        assert "PRIOR CONTEXT" in user_msg
        assert "reference only" in user_msg
        assert "Can you take care of the deployment?" in user_msg

    def test_signal_actor_participants_in_prompt(self):
        """Signal actor participants are used in the prompt."""
        from app.services.detection.seed_detector import _extract_commitments

        signal = self._make_signal()
        item = self._make_item()

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"commitments": []}')]
        mock_response.usage = MagicMock(input_tokens=100, output_tokens=50)
        mock_client.messages.create.return_value = mock_response

        _extract_commitments(mock_client, "claude-sonnet-4-6", item, signal=signal)

        call_args = mock_client.messages.create.call_args
        user_msg = call_args[1]["messages"][0]["content"]
        assert "Alice" in user_msg

    def test_signal_addressed_participants_in_prompt(self):
        """Signal addressed participants are included for owner resolution."""
        from app.services.detection.seed_detector import _extract_commitments

        signal = self._make_signal()
        item = self._make_item()

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"commitments": []}')]
        mock_response.usage = MagicMock(input_tokens=100, output_tokens=50)
        mock_client.messages.create.return_value = mock_response

        _extract_commitments(mock_client, "claude-sonnet-4-6", item, signal=signal)

        call_args = mock_client.messages.create.call_args
        user_msg = call_args[1]["messages"][0]["content"]
        assert "bob@example.com" in user_msg

    def test_fallback_to_item_when_no_signal(self):
        """Without signal, falls back to SourceItem content (backward compat)."""
        from app.services.detection.seed_detector import _extract_commitments

        item = self._make_item()

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"commitments": []}')]
        mock_response.usage = MagicMock(input_tokens=100, output_tokens=50)
        mock_client.messages.create.return_value = mock_response

        _extract_commitments(mock_client, "claude-sonnet-4-6", item)

        call_args = mock_client.messages.create.call_args
        user_msg = call_args[1]["messages"][0]["content"]
        assert "Full raw body lowercased" in user_msg

    def test_short_signal_text_skipped(self):
        """Signal with text < 10 chars is skipped."""
        from app.services.detection.seed_detector import _extract_commitments

        signal = self._make_signal(latest_text="Hi")
        item = self._make_item()
        mock_client = MagicMock()

        result = _extract_commitments(mock_client, "claude-sonnet-4-6", item, signal=signal)
        assert result.commitments is None
        mock_client.messages.create.assert_not_called()


class TestModelDetectionWithSignal:
    """Verify ModelDetectionService.classify uses NormalizedSignal."""

    def _make_signal(self, latest_text="I'll send the report."):
        return NormalizedSignal(
            signal_id="msg-001",
            source_type="email",
            source_thread_id=None,
            source_message_id="msg-001",
            occurred_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            authored_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            actor_participants=[Participant(name="Alice", email="alice@example.com", role="sender")],
            addressed_participants=[],
            visible_participants=[],
            latest_authored_text=latest_text,
            prior_context_text="Some prior thread context",
        )

    def test_signal_to_context_window_uses_latest_text(self):
        """_signal_to_context_window builds context from signal fields."""
        signal = self._make_signal(latest_text="I'll follow up on budget.")
        candidate = MagicMock()
        candidate.context_window = None

        cw = ModelDetectionService._signal_to_context_window(signal, candidate)
        assert cw["trigger_text"] == "I'll follow up on budget."
        assert cw["source_type"] == "email"
        assert cw["prior_context"] == "Some prior thread context"

    def test_signal_preserves_candidate_trigger_text(self):
        """When candidate has a trigger_text, it takes precedence."""
        signal = self._make_signal()
        candidate = MagicMock()
        candidate.context_window = {"trigger_text": "specific trigger", "pre_context": "", "post_context": ""}

        cw = ModelDetectionService._signal_to_context_window(signal, candidate)
        assert cw["trigger_text"] == "specific trigger"
        # But source_type and prior_context come from signal
        assert cw["source_type"] == "email"
        assert cw["prior_context"] == "Some prior thread context"
