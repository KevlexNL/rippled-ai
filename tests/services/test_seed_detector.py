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

    def test_skips_short_content(self):
        """Items with <10 chars of content should return empty list."""
        from app.services.detection.seed_detector import _extract_commitments

        mock_client = MagicMock()
        item = self._make_source_item(content="hi")

        result = _extract_commitments(mock_client, "claude-sonnet-4-6", item)

        assert result == []
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
