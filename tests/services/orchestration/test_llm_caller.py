"""Tests for the LLM caller — JSON parsing, markdown stripping, retry logic."""

import json
import pytest
from unittest.mock import MagicMock, patch

from pydantic import BaseModel

from app.services.orchestration.stages.llm_caller import (
    LLMCallResult,
    _strip_markdown_json,
    call_llm_structured,
)
from app.services.orchestration.contracts import CandidateGateResult


class TestStripMarkdownJson:
    def test_plain_json(self):
        assert _strip_markdown_json('{"key": "value"}') == '{"key": "value"}'

    def test_json_code_fence(self):
        raw = '```json\n{"key": "value"}\n```'
        assert _strip_markdown_json(raw) == '{"key": "value"}'

    def test_plain_code_fence(self):
        raw = '```\n{"key": "value"}\n```'
        assert _strip_markdown_json(raw) == '{"key": "value"}'

    def test_whitespace_handling(self):
        raw = '  ```json\n  {"key": "value"}  \n```  '
        result = _strip_markdown_json(raw)
        assert '"key"' in result

    def test_no_fence_no_change(self):
        raw = '{"candidate_type": "none", "confidence": 0.1, "rationale_short": "test"}'
        assert _strip_markdown_json(raw) == raw


class TestLLMCallResult:
    def test_success(self):
        model = CandidateGateResult(
            candidate_type="none", confidence=0.1, rationale_short="test"
        )
        r = LLMCallResult(parsed=model, raw_response='{}', model_name="test")
        assert r.success is True

    def test_failure(self):
        r = LLMCallResult(error="some error")
        assert r.success is False


class TestCallLlmStructured:
    @patch("app.services.orchestration.stages.llm_caller.get_settings")
    def test_no_api_key_returns_error(self, mock_settings):
        mock_settings.return_value = MagicMock(openai_api_key="")
        result = call_llm_structured(
            system_prompt="test",
            user_prompt="test",
            output_type=CandidateGateResult,
        )
        assert result.success is False
        assert "No OpenAI API key" in result.error

    @patch("app.services.orchestration.stages.llm_caller.get_settings")
    def test_valid_response_parsed(self, mock_settings):
        mock_settings.return_value = MagicMock(openai_api_key="sk-test", openai_model="gpt-test")

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "candidate_type": "commitment_candidate",
            "confidence": 0.85,
            "rationale_short": "Sender commits to action",
            "escalate_recommended": False,
        })
        mock_response.usage = MagicMock(prompt_tokens=100, completion_tokens=50)

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        result = call_llm_structured(
            system_prompt="test",
            user_prompt="test",
            output_type=CandidateGateResult,
            client=mock_client,
        )

        assert result.success is True
        assert result.parsed.candidate_type.value == "commitment_candidate"
        assert result.parsed.confidence == 0.85
        assert result.tokens_in == 100
        assert result.tokens_out == 50

    @patch("app.services.orchestration.stages.llm_caller.get_settings")
    def test_markdown_wrapped_response_parsed(self, mock_settings):
        mock_settings.return_value = MagicMock(openai_api_key="sk-test", openai_model="gpt-test")

        json_content = json.dumps({
            "candidate_type": "none",
            "confidence": 0.1,
            "rationale_short": "Just a greeting",
            "escalate_recommended": False,
        })

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = f"```json\n{json_content}\n```"
        mock_response.usage = MagicMock(prompt_tokens=50, completion_tokens=30)

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        result = call_llm_structured(
            system_prompt="test",
            user_prompt="test",
            output_type=CandidateGateResult,
            client=mock_client,
        )

        assert result.success is True
        assert result.parsed.candidate_type.value == "none"

    @patch("app.services.orchestration.stages.llm_caller.get_settings")
    def test_invalid_json_returns_error(self, mock_settings):
        mock_settings.return_value = MagicMock(openai_api_key="sk-test", openai_model="gpt-test")

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "This is not JSON at all"
        mock_response.usage = MagicMock(prompt_tokens=50, completion_tokens=30)

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        result = call_llm_structured(
            system_prompt="test",
            user_prompt="test",
            output_type=CandidateGateResult,
            client=mock_client,
        )

        assert result.success is False
        assert "JSON parse error" in result.error
