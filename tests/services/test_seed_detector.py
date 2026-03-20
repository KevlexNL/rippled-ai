"""Tests for seed_detector — LLM seed pass commitment extraction.

Verifies that the seed detector uses the Anthropic API correctly
and writes detection_audit rows with full prompt/response logging.
"""
from __future__ import annotations

import json
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import pytest

from app.models.orm import SourceItem


class TestExtractCommitments:
    """Test _extract_commitments uses Anthropic messages API and returns _LLMResult."""

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

        assert len(result.commitments) == 1
        assert result.commitments[0]["trigger_phrase"] == "I will send the report"
        assert result.commitments[0]["who_committed"] == "Alice"

    def test_skips_short_content_returns_none(self):
        """Items with <10 chars of content should return commitments=None,
        signalling no LLM call was made so seed_processed_at is NOT set."""
        from app.services.detection.seed_detector import _extract_commitments

        mock_client = MagicMock()
        item = self._make_source_item(content="hi")

        result = _extract_commitments(mock_client, "claude-sonnet-4-6", item)

        assert result.commitments is None
        mock_client.messages.create.assert_not_called()

    def test_handles_malformed_json(self):
        """Malformed LLM response should return empty commitments, not raise."""
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

        assert result.commitments == []
        assert result.error_detail is not None

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

        assert len(result.commitments) == 1
        assert result.commitments[0]["trigger_phrase"] == "I will send the report"

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

        assert len(result.commitments) == 1
        assert result.commitments[0]["trigger_phrase"] == "I'll check"

    def test_info_logging_on_extraction(self):
        """Seed detector should log the raw LLM response at INFO level for production visibility."""
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

            # Should log the raw LLM response at INFO level
            info_messages = [str(call) for call in mock_logger.info.call_args_list]
            raw_response_logged = any("raw LLM response" in msg for msg in info_messages)
            assert raw_response_logged, f"Expected info log with raw LLM response. Got: {info_messages}"

    def test_handles_uppercase_json_code_fence(self):
        """Handle ```JSON blocks (uppercase language tag)."""
        from app.services.detection.seed_detector import _extract_commitments

        mock_client = MagicMock()
        commitment_data = {"commitments": [{"trigger_phrase": "I'll try to get it done", "who_committed": "Alice", "directed_at": "Bob", "urgency": "medium", "commitment_type": "deliver", "title": "Try to deliver", "is_external": False, "confidence": 0.5}]}
        wrapped_text = f"```JSON\n{json.dumps(commitment_data)}\n```"
        mock_content_block = SimpleNamespace(text=wrapped_text)
        mock_response = SimpleNamespace(
            content=[mock_content_block],
            usage=SimpleNamespace(input_tokens=10, output_tokens=20),
        )
        mock_client.messages.create.return_value = mock_response

        item = self._make_source_item()
        result = _extract_commitments(mock_client, "claude-sonnet-4-6", item)

        assert len(result.commitments) == 1
        assert result.commitments[0]["trigger_phrase"] == "I'll try to get it done"

    def test_prompt_includes_tentative_language(self):
        """System prompt should include tentative language as commitment indicators."""
        from app.services.detection.seed_detector import _SYSTEM_PROMPT

        assert "Tentative" in _SYSTEM_PROMPT
        assert "I'll try" in _SYSTEM_PROMPT
        assert "Let me check" in _SYSTEM_PROMPT
        assert "I'll get back to you" in _SYSTEM_PROMPT

    def test_prompt_encourages_broad_detection(self):
        """System prompt should encourage broad detection per product principle."""
        from app.services.detection.seed_detector import _SYSTEM_PROMPT

        assert "WIDE net" in _SYSTEM_PROMPT
        assert "When in doubt" in _SYSTEM_PROMPT

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

        assert result.commitments == []
        assert mock_client.messages.create.call_count == 2


class TestExtractCommitmentsAuditMetadata:
    """Test that _extract_commitments returns full audit metadata in _LLMResult."""

    def _make_source_item(self, content: str = "I will send the report by Friday") -> SourceItem:
        item = MagicMock(spec=SourceItem)
        item.id = "test-item-id"
        item.content = content
        item.source_type = "email"
        item.sender_name = "Alice"
        item.sender_email = "alice@example.com"
        item.direction = "inbound"
        return item

    def test_returns_raw_prompt(self):
        """_LLMResult must contain the full prompt sent to the LLM."""
        from app.services.detection.seed_detector import _extract_commitments

        mock_client = MagicMock()
        mock_content_block = SimpleNamespace(text=json.dumps({"commitments": []}))
        mock_response = SimpleNamespace(
            content=[mock_content_block],
            usage=SimpleNamespace(input_tokens=10, output_tokens=5),
        )
        mock_client.messages.create.return_value = mock_response

        item = self._make_source_item()
        result = _extract_commitments(mock_client, "claude-sonnet-4-6", item)

        assert result.raw_prompt is not None
        assert "[system]" in result.raw_prompt
        assert "[user]" in result.raw_prompt
        assert "I will send the report by Friday" in result.raw_prompt

    def test_returns_raw_response(self):
        """_LLMResult must contain the raw response text from the LLM."""
        from app.services.detection.seed_detector import _extract_commitments

        mock_client = MagicMock()
        response_text = json.dumps({"commitments": []})
        mock_content_block = SimpleNamespace(text=response_text)
        mock_response = SimpleNamespace(
            content=[mock_content_block],
            usage=SimpleNamespace(input_tokens=10, output_tokens=5),
        )
        mock_client.messages.create.return_value = mock_response

        item = self._make_source_item()
        result = _extract_commitments(mock_client, "claude-sonnet-4-6", item)

        assert result.raw_response == response_text

    def test_returns_token_counts(self):
        """_LLMResult must contain input and output token counts."""
        from app.services.detection.seed_detector import _extract_commitments

        mock_client = MagicMock()
        mock_content_block = SimpleNamespace(text=json.dumps({"commitments": []}))
        mock_response = SimpleNamespace(
            content=[mock_content_block],
            usage=SimpleNamespace(input_tokens=150, output_tokens=42),
        )
        mock_client.messages.create.return_value = mock_response

        item = self._make_source_item()
        result = _extract_commitments(mock_client, "claude-sonnet-4-6", item)

        assert result.tokens_in == 150
        assert result.tokens_out == 42

    def test_returns_model_name(self):
        """_LLMResult must contain the model name used."""
        from app.services.detection.seed_detector import _extract_commitments

        mock_client = MagicMock()
        mock_content_block = SimpleNamespace(text=json.dumps({"commitments": []}))
        mock_response = SimpleNamespace(
            content=[mock_content_block],
            usage=SimpleNamespace(input_tokens=10, output_tokens=5),
        )
        mock_client.messages.create.return_value = mock_response

        item = self._make_source_item()
        result = _extract_commitments(mock_client, "claude-sonnet-4-6", item)

        assert result.model == "claude-sonnet-4-6"

    def test_returns_duration_ms(self):
        """_LLMResult must contain duration in milliseconds."""
        from app.services.detection.seed_detector import _extract_commitments

        mock_client = MagicMock()
        mock_content_block = SimpleNamespace(text=json.dumps({"commitments": []}))
        mock_response = SimpleNamespace(
            content=[mock_content_block],
            usage=SimpleNamespace(input_tokens=10, output_tokens=5),
        )
        mock_client.messages.create.return_value = mock_response

        item = self._make_source_item()
        result = _extract_commitments(mock_client, "claude-sonnet-4-6", item)

        assert result.duration_ms is not None
        assert result.duration_ms >= 0

    def test_returns_parsed_result(self):
        """_LLMResult must contain the parsed commitments list."""
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

        assert result.parsed_result is not None
        assert len(result.parsed_result) == 1
        assert result.parsed_result[0]["trigger_phrase"] == "I will send the report"

    def test_error_detail_on_malformed_json(self):
        """_LLMResult should include error_detail when JSON parsing fails."""
        from app.services.detection.seed_detector import _extract_commitments

        mock_client = MagicMock()
        mock_content_block = SimpleNamespace(text="not json {{{")
        mock_response = SimpleNamespace(
            content=[mock_content_block],
            usage=SimpleNamespace(input_tokens=10, output_tokens=5),
        )
        mock_client.messages.create.return_value = mock_response

        item = self._make_source_item()
        result = _extract_commitments(mock_client, "claude-sonnet-4-6", item)

        assert result.error_detail is not None
        assert "Parse error" in result.error_detail

    def test_skipped_item_has_no_audit_metadata(self):
        """Items skipped (content too short) should have minimal audit metadata."""
        from app.services.detection.seed_detector import _extract_commitments

        mock_client = MagicMock()
        item = self._make_source_item(content="hi")

        result = _extract_commitments(mock_client, "claude-sonnet-4-6", item)

        assert result.commitments is None
        assert result.raw_prompt is None
        assert result.tokens_in is None


class TestSeedPassAuditWriting:
    """Test that run_seed_pass writes detection_audit rows for LLM calls."""

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

    @patch("app.services.detection.seed_detector.write_audit_entry")
    @patch("app.services.detection.seed_detector.decrypt_value", return_value="sk-ant-test")
    @patch("app.services.detection.seed_detector.anthropic.Anthropic")
    def test_writes_audit_row_on_successful_llm_call(
        self, mock_anthropic_cls, _, mock_write_audit
    ):
        """Each LLM call must produce a detection_audit row."""
        from app.services.detection.seed_detector import run_seed_pass

        db = MagicMock()
        mock_settings = MagicMock()
        mock_settings.anthropic_api_key_encrypted = "enc"
        db.execute.return_value.scalar_one_or_none.return_value = mock_settings

        item = self._make_source_item("item-1", "I will send the quarterly report by Friday")
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [item]
        db.execute.return_value.scalars.return_value = mock_scalars

        mock_client = mock_anthropic_cls.return_value
        response_text = json.dumps({"commitments": []})
        mock_content = SimpleNamespace(text=response_text)
        mock_client.messages.create.return_value = SimpleNamespace(
            content=[mock_content],
            usage=SimpleNamespace(input_tokens=100, output_tokens=20),
        )

        run_seed_pass("user-1", db)

        mock_write_audit.assert_called_once()
        audit_kwargs = mock_write_audit.call_args
        assert audit_kwargs.kwargs.get("tier_used") or audit_kwargs[1].get("tier_used") == "tier_3" or (len(audit_kwargs[0]) > 3 and audit_kwargs[0][3] == "tier_3")

    @patch("app.services.detection.seed_detector.write_audit_entry")
    @patch("app.services.detection.seed_detector.decrypt_value", return_value="sk-ant-test")
    @patch("app.services.detection.seed_detector.anthropic.Anthropic")
    def test_audit_row_contains_raw_prompt_and_response(
        self, mock_anthropic_cls, _, mock_write_audit
    ):
        """Audit row must include raw_prompt, raw_response, and model."""
        from app.services.detection.seed_detector import run_seed_pass

        db = MagicMock()
        mock_settings = MagicMock()
        mock_settings.anthropic_api_key_encrypted = "enc"
        db.execute.return_value.scalar_one_or_none.return_value = mock_settings

        item = self._make_source_item("item-1", "I will send the quarterly report by Friday")
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [item]
        db.execute.return_value.scalars.return_value = mock_scalars

        mock_client = mock_anthropic_cls.return_value
        response_text = json.dumps({"commitments": []})
        mock_content = SimpleNamespace(text=response_text)
        mock_client.messages.create.return_value = SimpleNamespace(
            content=[mock_content],
            usage=SimpleNamespace(input_tokens=100, output_tokens=20),
        )

        run_seed_pass("user-1", db)

        mock_write_audit.assert_called_once()
        kw = mock_write_audit.call_args.kwargs
        assert kw["raw_prompt"] is not None
        assert kw["raw_response"] == response_text
        assert kw["model"] == "claude-sonnet-4-6"
        assert kw["prompt_version"] == "seed-v6"
        assert kw["tokens_in"] == 100
        assert kw["tokens_out"] == 20

    @patch("app.services.detection.seed_detector.write_audit_entry")
    @patch("app.services.detection.seed_detector.decrypt_value", return_value="sk-ant-test")
    @patch("app.services.detection.seed_detector.anthropic.Anthropic")
    def test_audit_row_has_cost_estimate(
        self, mock_anthropic_cls, _, mock_write_audit
    ):
        """Audit row must include a cost estimate."""
        from app.services.detection.seed_detector import run_seed_pass

        db = MagicMock()
        mock_settings = MagicMock()
        mock_settings.anthropic_api_key_encrypted = "enc"
        db.execute.return_value.scalar_one_or_none.return_value = mock_settings

        item = self._make_source_item("item-1", "I will send the quarterly report by Friday")
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [item]
        db.execute.return_value.scalars.return_value = mock_scalars

        mock_client = mock_anthropic_cls.return_value
        mock_content = SimpleNamespace(text=json.dumps({"commitments": []}))
        mock_client.messages.create.return_value = SimpleNamespace(
            content=[mock_content],
            usage=SimpleNamespace(input_tokens=1000, output_tokens=500),
        )

        run_seed_pass("user-1", db)

        kw = mock_write_audit.call_args.kwargs
        assert kw["cost_estimate"] is not None
        # claude-sonnet-4-6: $3/M input, $15/M output
        # 1000 input = $0.003, 500 output = $0.0075 => total $0.0105
        assert float(kw["cost_estimate"]) == pytest.approx(0.0105, abs=0.0001)

    @patch("app.services.detection.seed_detector.write_audit_entry")
    @patch("app.services.detection.seed_detector.decrypt_value", return_value="sk-ant-test")
    @patch("app.services.detection.seed_detector.anthropic.Anthropic")
    def test_no_audit_row_for_skipped_items(
        self, mock_anthropic_cls, _, mock_write_audit
    ):
        """Skipped items (too short) should NOT produce audit rows."""
        from app.services.detection.seed_detector import run_seed_pass

        db = MagicMock()
        mock_settings = MagicMock()
        mock_settings.anthropic_api_key_encrypted = "enc"
        db.execute.return_value.scalar_one_or_none.return_value = mock_settings

        item = self._make_source_item("item-short", "hi")
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [item]
        db.execute.return_value.scalars.return_value = mock_scalars

        run_seed_pass("user-1", db)

        mock_write_audit.assert_not_called()


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

    @patch("app.services.detection.seed_detector.write_audit_entry")
    @patch("app.services.detection.seed_detector.decrypt_value", return_value="sk-ant-test")
    @patch("app.services.detection.seed_detector.anthropic.Anthropic")
    def test_short_content_counted_as_skipped_not_processed(self, mock_anthropic_cls, _, __):
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

    @patch("app.services.detection.seed_detector.write_audit_entry")
    @patch("app.services.detection.seed_detector.decrypt_value", return_value="sk-ant-test")
    @patch("app.services.detection.seed_detector.anthropic.Anthropic")
    def test_llm_no_commitments_counted_as_processed(self, mock_anthropic_cls, _, __):
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


class TestPromptImprovementWOPromptImprovement:
    """Tests for WO-RIPPLED-PROMPT-IMPROVEMENT: seed prompt covers
    follow-up phrases and explicitly excludes greetings."""

    def test_prompt_includes_bare_follow_up_on_topic_example(self):
        """Prompt must include 'follow up on [topic]' as an explicit example
        so the LLM doesn't miss phrases like 'follow up on budget'."""
        from app.services.detection.seed_detector import _SYSTEM_PROMPT

        # Must mention follow up on [topic] explicitly
        assert "follow up on" in _SYSTEM_PROMPT.lower(), (
            "Seed prompt must explicitly include 'follow up on' as a follow-up example"
        )

    def test_prompt_includes_need_to_follow_up_example(self):
        """Prompt must include 'need to follow up' as a commitment example."""
        from app.services.detection.seed_detector import _SYSTEM_PROMPT

        assert "need to follow up" in _SYSTEM_PROMPT.lower(), (
            "Seed prompt must include 'need to follow up' as a follow-up example"
        )

    def test_prompt_greeting_exclusion_has_concrete_examples(self):
        """Prompt must list concrete greeting phrases that are NOT commitments,
        including multi-word greetings that the LLM was extracting as false positives."""
        from app.services.detection.seed_detector import _SYSTEM_PROMPT

        lower = _SYSTEM_PROMPT.lower()
        # Must explicitly say "Hope you're doing well" or similar pleasantries are not commitments
        assert "hope you" in lower or "hope this" in lower, (
            "Seed prompt must list pleasantry phrases like 'Hope you're well' as NOT commitments"
        )

    def test_prompt_greeting_exclusion_has_sign_offs(self):
        """Sign-offs like 'Best regards', 'Thanks' must be excluded."""
        from app.services.detection.seed_detector import _SYSTEM_PROMPT

        lower = _SYSTEM_PROMPT.lower()
        assert "best regards" in lower or "regards" in lower or "sign-off" in lower, (
            "Seed prompt must list sign-offs as NOT commitments"
        )

    def test_prompt_version_updated(self):
        """Prompt version should be bumped after improvements."""
        from app.services.detection.seed_detector import _PROMPT_VERSION

        assert _PROMPT_VERSION != "seed-v1", (
            "Prompt version must be bumped after WO-RIPPLED-PROMPT-IMPROVEMENT changes"
        )

    def test_prompt_version_is_v6(self):
        """Seed prompt version must be seed-v6 after WO-RIPPLED-PROMPT-IMPROVEMENT v6 changes."""
        from app.services.detection.seed_detector import _PROMPT_VERSION

        assert _PROMPT_VERSION == "seed-v6", (
            f"Expected seed-v6 but got {_PROMPT_VERSION}"
        )

    def test_prompt_includes_business_follow_up_topics(self):
        """Prompt must include business-topic follow-up examples like budget, headcount."""
        from app.services.detection.seed_detector import _SYSTEM_PROMPT

        lower = _SYSTEM_PROMPT.lower()
        assert "follow up on budget" in lower or "follow up on the budget" in lower, (
            "Seed prompt must include 'follow up on budget' as a follow-up example"
        )

    def test_prompt_excludes_meta_greeting_references(self):
        """Prompt must explicitly state that meta-references like 'greeting' are not commitments."""
        from app.services.detection.seed_detector import _SYSTEM_PROMPT

        lower = _SYSTEM_PROMPT.lower()
        assert "classification label" in lower or "meta-reference" in lower or "label" in lower, (
            "Seed prompt must exclude meta-references/classification labels as commitments"
        )

    def test_prompt_includes_checking_in_on_as_follow_up(self):
        """'Checking in on [topic]' should be treated as a follow-up commitment."""
        from app.services.detection.seed_detector import _SYSTEM_PROMPT

        lower = _SYSTEM_PROMPT.lower()
        assert "checking in on" in lower, (
            "Seed prompt must include 'checking in on' as a follow-up variant"
        )

    def test_prompt_has_self_validation_section(self):
        """Seed prompt must include a self-validation step at the end to catch
        false positives before outputting."""
        from app.services.detection.seed_detector import _SYSTEM_PROMPT

        lower = _SYSTEM_PROMPT.lower()
        assert "before you respond" in lower or "before outputting" in lower or "self-check" in lower, (
            "Seed prompt must have a self-validation section near the end"
        )

    def test_prompt_follow_up_rule_is_highlighted(self):
        """Follow-up rule must be explicitly highlighted as a critical rule,
        not just a bullet point in a list."""
        from app.services.detection.seed_detector import _SYSTEM_PROMPT

        # Must have a strong emphasis marker near "follow up" — either CRITICAL, RULE, ALWAYS, or IMPORTANT
        assert 'ANY form of "follow up"' in _SYSTEM_PROMPT or "ALWAYS a commitment" in _SYSTEM_PROMPT, (
            "Follow-up detection must be prominently highlighted as a critical rule"
        )


class TestModelDetectionPromptImprovement:
    """Tests for WO-RIPPLED-PROMPT-IMPROVEMENT: model detection prompt improvements."""

    def test_model_prompt_includes_follow_up_example(self):
        """Model detection prompt must include follow-up as a commitment type."""
        from app.services.model_detection import _SYSTEM_PROMPT

        lower = _SYSTEM_PROMPT.lower()
        assert "follow up" in lower or "follow-up" in lower, (
            "Model detection prompt must mention follow-up commitments"
        )

    def test_model_prompt_excludes_pleasantries(self):
        """Model detection prompt must exclude pleasantries like 'Hope you're well'."""
        from app.services.model_detection import _SYSTEM_PROMPT

        lower = _SYSTEM_PROMPT.lower()
        assert "hope you" in lower or "hope this" in lower or "pleasantr" in lower, (
            "Model detection prompt must list pleasantries as NOT commitments"
        )

    def test_model_prompt_version_updated(self):
        """Model detection prompt version should be bumped."""
        from app.services.model_detection import _PROMPT_VERSION

        assert _PROMPT_VERSION != "ongoing-v1", (
            "Model detection prompt version must be bumped after improvements"
        )

    def test_model_prompt_version_is_v6(self):
        """Model detection prompt version must be ongoing-v6."""
        from app.services.model_detection import _PROMPT_VERSION

        assert _PROMPT_VERSION == "ongoing-v6", (
            f"Expected ongoing-v6 but got {_PROMPT_VERSION}"
        )

    def test_model_prompt_excludes_meta_references(self):
        """Model detection prompt must exclude classification labels as commitments."""
        from app.services.model_detection import _SYSTEM_PROMPT

        lower = _SYSTEM_PROMPT.lower()
        assert "classification label" in lower or "meta-reference" in lower or "label" in lower, (
            "Model detection prompt must exclude meta-references as commitments"
        )

    def test_model_prompt_includes_checking_in_on(self):
        """Model detection prompt must include 'checking in on' as a follow-up variant."""
        from app.services.model_detection import _SYSTEM_PROMPT

        lower = _SYSTEM_PROMPT.lower()
        assert "checking in on" in lower, (
            "Model detection prompt must include 'checking in on' as a follow-up variant"
        )

    def test_model_prompt_has_self_validation_section(self):
        """Model detection prompt must include a self-validation step."""
        from app.services.model_detection import _SYSTEM_PROMPT

        lower = _SYSTEM_PROMPT.lower()
        assert "before you respond" in lower or "before outputting" in lower or "self-check" in lower, (
            "Model detection prompt must have a self-validation section"
        )


class TestFollowUpBarePattern:
    """Tests for new follow_up_bare pattern that catches standalone 'follow up' without preposition."""

    def test_follow_up_bare_pattern_exists(self):
        """A follow_up_bare pattern must exist for standalone follow-up phrases."""
        from app.services.detection.patterns import UNIVERSAL_EXPLICIT_PATTERNS

        names = {p.name for p in UNIVERSAL_EXPLICIT_PATTERNS}
        assert "follow_up_bare" in names, (
            "Expected 'follow_up_bare' pattern in UNIVERSAL_EXPLICIT_PATTERNS"
        )

    def test_follow_up_bare_matches_will_follow_up(self):
        from app.services.detection.patterns import UNIVERSAL_EXPLICIT_PATTERNS

        pattern = next(p for p in UNIVERSAL_EXPLICIT_PATTERNS if p.name == "follow_up_bare")
        assert pattern.pattern.search("will follow up")

    def test_follow_up_bare_matches_need_to_follow_up(self):
        from app.services.detection.patterns import UNIVERSAL_EXPLICIT_PATTERNS

        pattern = next(p for p in UNIVERSAL_EXPLICIT_PATTERNS if p.name == "follow_up_bare")
        assert pattern.pattern.search("I need to follow up")

    def test_follow_up_bare_matches_should_follow_up(self):
        from app.services.detection.patterns import UNIVERSAL_EXPLICIT_PATTERNS

        pattern = next(p for p in UNIVERSAL_EXPLICIT_PATTERNS if p.name == "follow_up_bare")
        assert pattern.pattern.search("we should follow up")

    def test_follow_up_bare_matches_follow_up_on_budget(self):
        """The specific false negative from WO audit aud-42."""
        from app.services.detection.patterns import UNIVERSAL_EXPLICIT_PATTERNS

        pattern = next(p for p in UNIVERSAL_EXPLICIT_PATTERNS if p.name == "follow_up_bare")
        assert pattern.pattern.search("follow up on budget")

    def test_follow_up_bare_is_follow_up_class(self):
        from app.services.detection.patterns import UNIVERSAL_EXPLICIT_PATTERNS

        pattern = next(p for p in UNIVERSAL_EXPLICIT_PATTERNS if p.name == "follow_up_bare")
        assert pattern.trigger_class == "follow_up_commitment"


class TestCostEstimation:
    """Test the estimate_cost utility function."""

    def test_estimate_cost_claude_sonnet(self):
        from app.services.detection.audit import estimate_cost

        cost = estimate_cost("claude-sonnet-4-6", 1000, 500)
        # $3/M input * 1000 = $0.003, $15/M output * 500 = $0.0075
        assert cost is not None
        assert float(cost) == pytest.approx(0.0105, abs=0.0001)

    def test_estimate_cost_gpt4_mini(self):
        from app.services.detection.audit import estimate_cost

        cost = estimate_cost("gpt-4.1-mini", 1000, 500)
        # $0.40/M input * 1000 = $0.0004, $1.60/M output * 500 = $0.0008
        assert cost is not None
        assert float(cost) == pytest.approx(0.0012, abs=0.0001)

    def test_estimate_cost_unknown_model(self):
        from app.services.detection.audit import estimate_cost

        cost = estimate_cost("unknown-model", 1000, 500)
        assert cost is None

    def test_estimate_cost_none_tokens(self):
        from app.services.detection.audit import estimate_cost

        assert estimate_cost("claude-sonnet-4-6", None, 500) is None
        assert estimate_cost("claude-sonnet-4-6", 1000, None) is None
