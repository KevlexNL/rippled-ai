"""Tests for the voice interface service layer.

Tests cover:
- stt_service: Whisper API call + extension detection
- intent_parser: JSON response parsing + fallback
- tts_service: TTS API call + base64 output
- query_service: commitment DB query + summary generation

All tests mock external APIs (OpenAI). No real DB or network calls.
"""
from __future__ import annotations

import base64
import io
import types
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# stt_service
# ---------------------------------------------------------------------------

class TestExtFromMime:
    def test_mp3_mime(self):
        from app.services.voice.stt_service import _ext_from_mime
        assert _ext_from_mime("audio/mpeg", None) == "mp3"

    def test_m4a_mime(self):
        from app.services.voice.stt_service import _ext_from_mime
        assert _ext_from_mime("audio/x-m4a", None) == "m4a"

    def test_wav_mime(self):
        from app.services.voice.stt_service import _ext_from_mime
        assert _ext_from_mime("audio/wav", None) == "wav"

    def test_filename_takes_priority(self):
        from app.services.voice.stt_service import _ext_from_mime
        assert _ext_from_mime("audio/mpeg", "voice_note.ogg") == "ogg"

    def test_unknown_mime_fallback(self):
        from app.services.voice.stt_service import _ext_from_mime
        assert _ext_from_mime("application/xyz", None) == "mp3"


class TestTranscribe:
    def test_transcribe_calls_whisper_api(self):
        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.return_value = "Hello Matt, what's due this week?"

        with patch("app.services.voice.stt_service.get_openai_client", return_value=mock_client):
            from app.services.voice import stt_service
            result = stt_service.transcribe(b"fake_audio", "audio/mpeg", "voice.mp3")

        assert result == "Hello Matt, what's due this week?"
        mock_client.audio.transcriptions.create.assert_called_once()
        call_kwargs = mock_client.audio.transcriptions.create.call_args
        assert call_kwargs.kwargs["model"] == "whisper-1"
        assert call_kwargs.kwargs["response_format"] == "text"

    def test_transcribe_strips_whitespace(self):
        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.return_value = "  What's overdue?  "

        with patch("app.services.voice.stt_service.get_openai_client", return_value=mock_client):
            from app.services.voice import stt_service
            result = stt_service.transcribe(b"fake_audio")

        assert result == "What's overdue?"

    def test_transcribe_raises_if_no_client(self):
        with patch("app.services.voice.stt_service.get_openai_client", return_value=None):
            from app.services.voice import stt_service
            with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
                stt_service.transcribe(b"audio")


# ---------------------------------------------------------------------------
# intent_parser
# ---------------------------------------------------------------------------

class TestParseIntent:
    def test_query_commitments_intent(self):
        mock_client = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = '{"intent": "query_commitments", "time_window": "this_week", "counterparty": "Matt"}'
        mock_client.chat.completions.create.return_value = MagicMock(choices=[mock_choice])

        with patch("app.services.voice.intent_parser.get_openai_client", return_value=mock_client):
            from app.services.voice import intent_parser
            result = intent_parser.parse_intent("What did I promise Matt this week?")

        assert result["intent"] == "query_commitments"
        assert result["time_window"] == "this_week"
        assert result["counterparty"] == "Matt"

    def test_overdue_intent(self):
        mock_client = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = '{"intent": "query_commitments", "time_window": "overdue"}'
        mock_client.chat.completions.create.return_value = MagicMock(choices=[mock_choice])

        with patch("app.services.voice.intent_parser.get_openai_client", return_value=mock_client):
            from app.services.voice import intent_parser
            result = intent_parser.parse_intent("What's overdue?")

        assert result["intent"] == "query_commitments"
        assert result["time_window"] == "overdue"
        assert "counterparty" not in result

    def test_invalid_intent_defaults_to_unknown(self):
        mock_client = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = '{"intent": "fly_to_moon", "time_window": "all"}'
        mock_client.chat.completions.create.return_value = MagicMock(choices=[mock_choice])

        with patch("app.services.voice.intent_parser.get_openai_client", return_value=mock_client):
            from app.services.voice import intent_parser
            result = intent_parser.parse_intent("Book me a flight to Mars")

        assert result["intent"] == "unknown"

    def test_empty_transcript_returns_unknown(self):
        with patch("app.services.voice.intent_parser.get_openai_client", return_value=MagicMock()):
            from app.services.voice import intent_parser
            result = intent_parser.parse_intent("")
        assert result["intent"] == "unknown"

    def test_no_client_defaults_to_query_commitments(self):
        with patch("app.services.voice.intent_parser.get_openai_client", return_value=None):
            from app.services.voice import intent_parser
            result = intent_parser.parse_intent("What's due today?")
        assert result["intent"] == "query_commitments"

    def test_llm_exception_returns_fallback(self):
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API error")

        with patch("app.services.voice.intent_parser.get_openai_client", return_value=mock_client):
            from app.services.voice import intent_parser
            result = intent_parser.parse_intent("What's due?")

        assert result["intent"] == "query_commitments"


# ---------------------------------------------------------------------------
# tts_service
# ---------------------------------------------------------------------------

class TestTtsService:
    def test_synthesize_returns_mp3_bytes(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.read.return_value = b"fake_mp3_bytes"
        mock_client.audio.speech.create.return_value = mock_response

        with patch("app.services.voice.tts_service.get_openai_client", return_value=mock_client):
            from app.services.voice import tts_service
            result = tts_service.synthesize("You have 2 overdue commitments.")

        assert result == b"fake_mp3_bytes"
        call_kwargs = mock_client.audio.speech.create.call_args.kwargs
        assert call_kwargs["model"] == "tts-1"
        assert call_kwargs["voice"] == "nova"
        assert call_kwargs["response_format"] == "mp3"

    def test_synthesize_b64_returns_base64_string(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.read.return_value = b"audio_data"
        mock_client.audio.speech.create.return_value = mock_response

        with patch("app.services.voice.tts_service.get_openai_client", return_value=mock_client):
            from app.services.voice import tts_service
            result = tts_service.synthesize_b64("Test text")

        expected = base64.b64encode(b"audio_data").decode("utf-8")
        assert result == expected

    def test_synthesize_truncates_long_text(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.read.return_value = b"mp3"
        mock_client.audio.speech.create.return_value = mock_response

        with patch("app.services.voice.tts_service.get_openai_client", return_value=mock_client):
            from app.services.voice import tts_service
            long_text = "x" * 5000
            tts_service.synthesize(long_text)

        call_kwargs = mock_client.audio.speech.create.call_args.kwargs
        assert len(call_kwargs["input"]) == 4096

    def test_synthesize_raises_if_no_client(self):
        with patch("app.services.voice.tts_service.get_openai_client", return_value=None):
            from app.services.voice import tts_service
            with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
                tts_service.synthesize("Hello")

    def test_custom_voice(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.read.return_value = b"mp3"
        mock_client.audio.speech.create.return_value = mock_response

        with patch("app.services.voice.tts_service.get_openai_client", return_value=mock_client):
            from app.services.voice import tts_service
            tts_service.synthesize("Hello", voice="onyx")

        call_kwargs = mock_client.audio.speech.create.call_args.kwargs
        assert call_kwargs["voice"] == "onyx"


# ---------------------------------------------------------------------------
# query_service — _generate_summary
# ---------------------------------------------------------------------------

class TestGenerateSummary:
    @pytest.mark.asyncio
    async def test_summary_generated_from_llm(self):
        mock_client = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "You have 2 commitments this week for Matt."
        mock_client.chat.completions.create.return_value = MagicMock(choices=[mock_choice])

        with patch("app.services.voice.query_service.get_openai_client", return_value=mock_client):
            from app.services.voice.query_service import _generate_summary
            result = await _generate_summary(
                transcript="What's due this week for Matt?",
                commitments=[
                    {"title": "Send proposal", "counterparty": "Matt", "deadline": "Friday Apr 3", "overdue": False},
                    {"title": "Review contract", "counterparty": "Matt", "deadline": "Thursday Apr 2", "overdue": False},
                ],
                total_count=2,
            )
        assert "Matt" in result or "commitment" in result.lower()

    @pytest.mark.asyncio
    async def test_empty_commitments_no_client(self):
        with patch("app.services.voice.query_service.get_openai_client", return_value=None):
            from app.services.voice.query_service import _generate_summary
            result = await _generate_summary(
                transcript="What's overdue?",
                commitments=[],
                total_count=0,
            )
        assert "couldn't find" in result.lower() or "no" in result.lower()

    @pytest.mark.asyncio
    async def test_fallback_on_llm_error(self):
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("OpenAI down")

        with patch("app.services.voice.query_service.get_openai_client", return_value=mock_client):
            from app.services.voice.query_service import _generate_summary
            result = await _generate_summary(
                transcript="What's due?",
                commitments=[{"title": "Send docs", "counterparty": None, "deadline": "Monday", "overdue": False}],
                total_count=1,
            )
        assert "1 commitment" in result or "commitment" in result.lower()
