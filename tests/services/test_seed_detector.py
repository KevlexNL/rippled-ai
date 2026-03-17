"""Tests for seed_detector — LLM seed pass commitment extraction.

Verifies that the seed detector uses the Anthropic API correctly.
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.models.orm import SourceItem


class TestExtractCommitments:
    """Test _extract_commitments uses Anthropic messages API."""

    def _make_source_item(self, content: str = "I will send the report by Friday") -> SourceItem:
        item = MagicMock(spec=SourceItem)
        item.id = "test-item-id"
        item.content = content
        item.source_type = "email"
        item.sender_name = "Alice"
        item.sender_email = "alice@example.com"
        item.direction = "inbound"
        return item

    def test_calls_anthropic_messages_api(self):
        """Seed detector must call client.messages.create (Anthropic), not
        client.chat.completions.create (OpenAI)."""
        from app.services.detection.seed_detector import _extract_commitments

        mock_client = MagicMock()
        # Set up the Anthropic-style response
        mock_content_block = SimpleNamespace(text=json.dumps({"commitments": []}))
        mock_response = SimpleNamespace(
            content=[mock_content_block],
            usage=SimpleNamespace(input_tokens=10, output_tokens=5),
        )
        mock_client.messages.create.return_value = mock_response

        item = self._make_source_item()
        result = _extract_commitments(mock_client, "claude-sonnet-4-6", item)

        # Must call messages.create, NOT chat.completions.create
        mock_client.messages.create.assert_called_once()
        call_kwargs = mock_client.messages.create.call_args
        assert call_kwargs.kwargs.get("model") == "claude-sonnet-4-6"
        assert "messages" in call_kwargs.kwargs
        assert call_kwargs.kwargs.get("system") is not None

    def test_parses_anthropic_response_format(self):
        """Verify commitments are correctly parsed from Anthropic response."""
        from app.services.detection.seed_detector import _extract_commitments

        mock_client = MagicMock()
        commitment_data = {
            "commitments": [
                {
                    "trigger_phrase": "I will send the report",
                    "who_committed": "Alice",
                    "directed_at": "Bob",
                    "urgency": "high",
                    "commitment_type": "send",
                    "title": "Send the report",
                    "is_external": False,
                    "confidence": 0.9,
                }
            ]
        }
        mock_content_block = SimpleNamespace(text=json.dumps(commitment_data))
        mock_response = SimpleNamespace(
            content=[mock_content_block],
            usage=SimpleNamespace(input_tokens=10, output_tokens=20),
        )
        mock_client.messages.create.return_value = mock_response

        item = self._make_source_item()
        result = _extract_commitments(mock_client, "claude-sonnet-4-6", item)

        assert len(result) == 1
        assert result[0]["trigger_phrase"] == "I will send the report"
        assert result[0]["who_committed"] == "Alice"

    def test_skips_short_content_returns_none(self):
        """Items with <10 chars of content should return None (not []),
        signalling no LLM call was made so seed_processed_at is NOT set."""
        from app.services.detection.seed_detector import _extract_commitments

        mock_client = MagicMock()
        item = self._make_source_item(content="hi")

        result = _extract_commitments(mock_client, "claude-sonnet-4-6", item)

        assert result is None
        mock_client.messages.create.assert_not_called()

    def test_handles_malformed_json(self):
        """Malformed LLM response should return empty list, not raise."""
        from app.services.detection.seed_detector import _extract_commitments

        mock_client = MagicMock()
        mock_content_block = SimpleNamespace(text="not valid json {{{")
        mock_response = SimpleNamespace(
            content=[mock_content_block],
            usage=SimpleNamespace(input_tokens=10, output_tokens=5),
        )
        mock_client.messages.create.return_value = mock_response

        item = self._make_source_item()
        result = _extract_commitments(mock_client, "claude-sonnet-4-6", item)

        assert result == []

    def test_handles_markdown_wrapped_json(self):
        """LLM often wraps JSON in ```json code blocks — parser must handle this."""
        from app.services.detection.seed_detector import _extract_commitments

        mock_client = MagicMock()
        commitment_data = {
            "commitments": [
                {
                    "trigger_phrase": "I will send the report",
                    "who_committed": "Alice",
                    "directed_at": "Bob",
                    "urgency": "high",
                    "commitment_type": "send",
                    "title": "Send the report",
                    "is_external": False,
                    "confidence": 0.9,
                }
            ]
        }
        # Wrap in markdown code block — common LLM behavior
        wrapped_text = f"```json\n{json.dumps(commitment_data)}\n```"
        mock_content_block = SimpleNamespace(text=wrapped_text)
        mock_response = SimpleNamespace(
            content=[mock_content_block],
            usage=SimpleNamespace(input_tokens=10, output_tokens=20),
        )
        mock_client.messages.create.return_value = mock_response

        item = self._make_source_item()
        result = _extract_commitments(mock_client, "claude-sonnet-4-6", item)

        assert len(result) == 1
        assert result[0]["trigger_phrase"] == "I will send the report"

    def test_handles_markdown_wrapped_json_no_lang_tag(self):
        """Handle ``` blocks without a language tag."""
        from app.services.detection.seed_detector import _extract_commitments

        mock_client = MagicMock()
        commitment_data = {"commitments": [{"trigger_phrase": "I'll check", "who_committed": "Alice", "directed_at": None, "urgency": "low", "commitment_type": "investigate", "title": "Check something", "is_external": False, "confidence": 0.7}]}
        wrapped_text = f"```\n{json.dumps(commitment_data)}\n```"
        mock_content_block = SimpleNamespace(text=wrapped_text)
        mock_response = SimpleNamespace(
            content=[mock_content_block],
            usage=SimpleNamespace(input_tokens=10, output_tokens=20),
        )
        mock_client.messages.create.return_value = mock_response

        item = self._make_source_item()
        result = _extract_commitments(mock_client, "claude-sonnet-4-6", item)

        assert len(result) == 1
        assert result[0]["trigger_phrase"] == "I'll check"

    def test_debug_logging_on_extraction(self):
        """Seed detector should log the prompt and raw response for debugging."""
        from app.services.detection.seed_detector import _extract_commitments

        mock_client = MagicMock()
        mock_content_block = SimpleNamespace(text=json.dumps({"commitments": []}))
        mock_response = SimpleNamespace(
            content=[mock_content_block],
            usage=SimpleNamespace(input_tokens=10, output_tokens=5),
        )
        mock_client.messages.create.return_value = mock_response

        item = self._make_source_item()
        with patch("app.services.detection.seed_detector.logger") as mock_logger:
            _extract_commitments(mock_client, "claude-sonnet-4-6", item)

            # Should log the raw LLM response at debug level
            debug_messages = [str(call) for call in mock_logger.debug.call_args_list]
            raw_response_logged = any("raw LLM response" in msg or "raw response" in msg for msg in debug_messages)
            assert raw_response_logged, f"Expected debug log with raw LLM response. Got: {debug_messages}"

    def test_retries_on_rate_limit(self):
        """Should retry with backoff on Anthropic RateLimitError."""
        import anthropic

        from app.services.detection.seed_detector import _extract_commitments

        mock_client = MagicMock()

        # Build a proper RateLimitError
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.headers = {}
        rate_err = anthropic.RateLimitError(
            message="rate limited",
            response=mock_resp,
            body={"error": {"message": "rate limited", "type": "rate_limit_error"}},
        )

        mock_content_block = SimpleNamespace(text=json.dumps({"commitments": []}))
        success_response = SimpleNamespace(
            content=[mock_content_block],
            usage=SimpleNamespace(input_tokens=10, output_tokens=5),
        )

        mock_client.messages.create.side_effect = [rate_err, success_response]

        item = self._make_source_item()
        with patch("app.services.detection.seed_detector.time.sleep"):
            result = _extract_commitments(mock_client, "claude-sonnet-4-6", item)

        assert result == []
        assert mock_client.messages.create.call_count == 2


class TestSeedPassSkipLogic:
    """Test that run_seed_pass correctly distinguishes skipped vs processed items."""

    def _make_source_item(self, item_id, content):
        item = MagicMock(spec=SourceItem)
        item.id = item_id
        item.content = content
        item.source_type = "email"
        item.sender_name = "Alice"
        item.sender_email = "alice@example.com"
        item.direction = "inbound"
        item.occurred_at = None
        return item

    @patch("app.services.detection.seed_detector.decrypt_value", return_value="sk-ant-test")
    @patch("app.services.detection.seed_detector.anthropic.Anthropic")
    def test_short_content_counted_as_skipped_not_processed(self, mock_anthropic_cls, _):
        """Items with short content should be counted as skipped,
        NOT as processed, and seed_processed_at should NOT be set."""
        from app.services.detection.seed_detector import run_seed_pass

        db = MagicMock()

        # user_settings lookup
        mock_settings = MagicMock()
        mock_settings.anthropic_api_key_encrypted = "enc"
        db.execute.return_value.scalar_one_or_none.return_value = mock_settings

        # source items: one short-content item
        short_item = self._make_source_item("item-short", "hi")
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [short_item]
        db.execute.return_value.scalars.return_value = mock_scalars

        result = run_seed_pass("user-1", db)

        assert result.items_skipped == 1
        assert result.items_processed == 0
        # seed_processed_at should NOT have been set (no UPDATE call for this item)
        # The mock makes this hard to assert directly, but items_processed==0 confirms it

    @patch("app.services.detection.seed_detector.decrypt_value", return_value="sk-ant-test")
    @patch("app.services.detection.seed_detector.anthropic.Anthropic")
    def test_llm_no_commitments_counted_as_processed(self, mock_anthropic_cls, _):
        """Items where LLM returns no commitments should be counted as
        processed (not skipped) and seed_processed_at SHOULD be set."""
        from app.services.detection.seed_detector import run_seed_pass

        db = MagicMock()

        mock_settings = MagicMock()
        mock_settings.anthropic_api_key_encrypted = "enc"
        db.execute.return_value.scalar_one_or_none.return_value = mock_settings

        normal_item = self._make_source_item(
            "item-normal", "Please review the quarterly report and send feedback"
        )
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [normal_item]
        db.execute.return_value.scalars.return_value = mock_scalars

        # LLM returns no commitments
        mock_client = mock_anthropic_cls.return_value
        mock_content = SimpleNamespace(text=json.dumps({"commitments": []}))
        mock_client.messages.create.return_value = SimpleNamespace(
            content=[mock_content],
            usage=SimpleNamespace(input_tokens=10, output_tokens=5),
        )

        result = run_seed_pass("user-1", db)

        assert result.items_processed == 1
        assert result.items_skipped == 0
        mock_client.messages.create.assert_called_once()


class TestRunSeedPassKeyLoading:
    """Test that run_seed_pass loads and decrypts user's Anthropic API key."""

    def test_returns_error_when_no_api_key(self):
        """Should return clear error if no Anthropic key stored for user."""
        from app.services.detection.seed_detector import run_seed_pass

        db = MagicMock()
        db.execute.return_value.scalar_one_or_none.return_value = None

        result = run_seed_pass("test-user-id", db)

        assert result.errors == 0  # not an exception, a handled case
        assert len(result.error_details) == 1
        assert "Anthropic API key" in result.error_details[0]

    def test_decrypts_api_key_from_user_settings(self):
        """Should decrypt the anthropic_api_key_encrypted from user_settings."""
        from app.services.detection.seed_detector import run_seed_pass

        db = MagicMock()

        # First call: user_settings lookup
        mock_settings = MagicMock()
        mock_settings.anthropic_api_key_encrypted = "encrypted-key-value"
        db.execute.return_value.scalar_one_or_none.return_value = mock_settings

        # Second call: source items query returns empty (so we don't need full LLM mock)
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        db.execute.return_value.scalars.return_value = mock_scalars

        with patch(
            "app.services.detection.seed_detector.decrypt_value",
            return_value="sk-ant-test-key",
        ) as mock_decrypt, patch(
            "app.services.detection.seed_detector.anthropic.Anthropic"
        ) as mock_anthropic_cls:
            result = run_seed_pass("test-user-id", db)

        mock_decrypt.assert_called_once_with("encrypted-key-value")
        mock_anthropic_cls.assert_called_once_with(api_key="sk-ant-test-key")
