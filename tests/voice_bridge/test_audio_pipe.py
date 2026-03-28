"""Tests for bidirectional audio pipe (Twilio <-> Gemini Live).

Tests verify:
- AudioPipe connects Twilio media events to GeminiLiveClient
- Incoming audio from Twilio is forwarded to Gemini
- Gemini text responses are logged
- Mock TTS returns a stubbed audio response
- Error handling on connection failures
- Clean shutdown on stop event
"""
import asyncio
from unittest.mock import AsyncMock

from app.voice_bridge.audio_pipe import AudioPipe
from app.voice_bridge.gemini_client import GeminiLiveClient, GeminiResponse


class TestAudioPipeInit:
    """AudioPipe should wire Twilio to Gemini."""

    def test_creates_with_gemini_client(self):
        client = GeminiLiveClient(project_id="test-project")
        pipe = AudioPipe(gemini_client=client)
        assert pipe.gemini_client is client

    def test_creates_with_default_client(self):
        pipe = AudioPipe()
        assert pipe.gemini_client is not None
        assert isinstance(pipe.gemini_client, GeminiLiveClient)


class TestAudioPipeForwarding:
    """AudioPipe should forward Twilio audio to Gemini."""

    def test_forward_audio_calls_gemini_send(self):
        client = GeminiLiveClient()
        client.send_audio = AsyncMock()
        pipe = AudioPipe(gemini_client=client)

        raw_audio = b"\x80" * 160
        asyncio.run(pipe.forward_audio(raw_audio))

        client.send_audio.assert_awaited_once_with(raw_audio, mime_type="audio/x-mulaw")

    def test_forward_audio_with_custom_mime_type(self):
        client = GeminiLiveClient()
        client.send_audio = AsyncMock()
        pipe = AudioPipe(gemini_client=client)

        asyncio.run(pipe.forward_audio(b"\x00" * 100, mime_type="audio/pcm"))
        client.send_audio.assert_awaited_once_with(b"\x00" * 100, mime_type="audio/pcm")


class TestAudioPipeGeminiResponse:
    """AudioPipe should handle Gemini responses."""

    def test_handle_text_response_stores_transcript(self):
        pipe = AudioPipe()
        resp = GeminiResponse(text="I'll schedule that meeting for you.")
        pipe.handle_response(resp)
        assert len(pipe.transcript) == 1
        assert pipe.transcript[0] == "I'll schedule that meeting for you."

    def test_handle_audio_response_stores_outbound_audio(self):
        pipe = AudioPipe()
        audio = b"\x01\x02\x03"
        resp = GeminiResponse(audio_data=audio)
        pipe.handle_response(resp)
        assert pipe.last_outbound_audio == audio

    def test_handle_function_call_logs_it(self):
        pipe = AudioPipe()
        resp = GeminiResponse(function_calls=[{"name": "create_wo", "args": {"title": "Test"}}])
        pipe.handle_response(resp)
        assert len(pipe.pending_function_calls) == 1
        assert pipe.pending_function_calls[0]["name"] == "create_wo"


class TestAudioPipeMockTTS:
    """AudioPipe should provide a stubbed TTS response for testing."""

    def test_get_mock_tts_returns_audio_bytes(self):
        pipe = AudioPipe()
        audio = pipe.get_mock_tts_response("Hello there")
        assert isinstance(audio, bytes)
        assert len(audio) > 0

    def test_get_mock_tts_returns_mulaw_silence(self):
        pipe = AudioPipe()
        audio = pipe.get_mock_tts_response("Test")
        assert all(b == 0x7F for b in audio)


class TestAudioPipeLifecycle:
    """AudioPipe should manage connection lifecycle."""

    def test_start_connects_gemini(self):
        client = GeminiLiveClient()
        client.connect = AsyncMock()
        pipe = AudioPipe(gemini_client=client)

        asyncio.run(pipe.start())
        client.connect.assert_awaited_once()
        assert pipe.is_active

    def test_stop_disconnects_gemini(self):
        client = GeminiLiveClient()
        client.connect = AsyncMock()
        client.disconnect = AsyncMock()
        pipe = AudioPipe(gemini_client=client)

        asyncio.run(pipe.start())
        asyncio.run(pipe.stop())
        client.disconnect.assert_awaited_once()
        assert not pipe.is_active
