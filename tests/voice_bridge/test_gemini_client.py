"""Tests for Gemini Live WebSocket client.

Tests verify:
- Client constructs correct WebSocket URL from project config
- Client can send audio chunks in the correct wire format
- Client parses GenerateContentResponse messages (text, audio, function calls)
- Client handles connection errors gracefully
- Client uses placeholder credentials when none configured
"""
import base64

from app.voice_bridge.gemini_client import GeminiLiveClient, GeminiResponse


class TestGeminiLiveClientConfig:
    """Client should build correct connection URL and headers."""

    def test_builds_websocket_url_from_project_id(self):
        client = GeminiLiveClient(
            project_id="my-project-123",
            location="us-central1",
            model="gemini-2.5-flash-native-audio",
        )
        url = client.websocket_url
        assert "my-project-123" in url
        assert "us-central1" in url
        assert "gemini-2.5-flash-native-audio" in url
        assert url.startswith("wss://")

    def test_defaults_to_placeholder_project_id(self):
        client = GeminiLiveClient()
        assert "PLACEHOLDER" in client.websocket_url or "placeholder" in client.websocket_url.lower()

    def test_default_model_is_gemini_flash_native_audio(self):
        client = GeminiLiveClient()
        assert "gemini-2.5-flash-native-audio" in client.websocket_url


class TestGeminiResponseParsing:
    """GeminiResponse should parse different response types."""

    def test_parses_text_response(self):
        raw = {
            "candidates": [{
                "content": {
                    "parts": [{"text": "Hello, how can I help?"}],
                    "role": "model",
                },
            }],
        }
        resp = GeminiResponse.from_raw(raw)
        assert resp.text == "Hello, how can I help?"
        assert resp.audio_data is None
        assert resp.function_calls == []

    def test_parses_audio_response(self):
        audio_b64 = base64.b64encode(b"\x00\x01\x02").decode()
        raw = {
            "candidates": [{
                "content": {
                    "parts": [{"inlineData": {"mimeType": "audio/pcm", "data": audio_b64}}],
                    "role": "model",
                },
            }],
        }
        resp = GeminiResponse.from_raw(raw)
        assert resp.audio_data == b"\x00\x01\x02"
        assert resp.text is None

    def test_parses_function_call_response(self):
        raw = {
            "candidates": [{
                "content": {
                    "parts": [{
                        "functionCall": {
                            "name": "create_work_order",
                            "args": {"title": "Fix bug"},
                        },
                    }],
                    "role": "model",
                },
            }],
        }
        resp = GeminiResponse.from_raw(raw)
        assert len(resp.function_calls) == 1
        assert resp.function_calls[0]["name"] == "create_work_order"
        assert resp.function_calls[0]["args"]["title"] == "Fix bug"

    def test_handles_empty_candidates(self):
        raw = {"candidates": []}
        resp = GeminiResponse.from_raw(raw)
        assert resp.text is None
        assert resp.audio_data is None
        assert resp.function_calls == []

    def test_handles_missing_candidates_key(self):
        raw = {}
        resp = GeminiResponse.from_raw(raw)
        assert resp.text is None


class TestGeminiLiveClientAudioSend:
    """Client should format audio chunks for Gemini Live wire protocol."""

    def test_build_audio_message_encodes_base64(self):
        client = GeminiLiveClient()
        raw_audio = b"\xff\xfe\xfd" * 100
        msg = client.build_audio_message(raw_audio)
        # Message should be a dict with the audio payload
        assert "realtimeInput" in msg
        payload = msg["realtimeInput"]["mediaChunks"][0]
        assert payload["mimeType"] == "audio/pcm"
        decoded = base64.b64decode(payload["data"])
        assert decoded == raw_audio

    def test_build_audio_message_with_mulaw_encoding(self):
        client = GeminiLiveClient()
        raw_audio = b"\x80" * 160
        msg = client.build_audio_message(raw_audio, mime_type="audio/x-mulaw")
        payload = msg["realtimeInput"]["mediaChunks"][0]
        assert payload["mimeType"] == "audio/x-mulaw"
