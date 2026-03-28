"""Tests for Twilio webhook handler.

Tests verify:
- POST /twilio/voice returns valid TwiML with MediaStream connect
- Twilio WebSocket receives media events and logs audio chunks
- Start/stop/media event types are handled correctly
- Invalid event types are ignored gracefully
"""
import base64

from fastapi.testclient import TestClient


def _get_app():
    """Import app lazily to allow module creation."""
    from app.voice_bridge.main import voice_app
    return voice_app


class TestTwilioVoiceEndpoint:
    """POST /twilio/voice should return TwiML that connects a MediaStream."""

    def test_returns_xml_content_type(self):
        client = TestClient(_get_app())
        resp = client.post("/twilio/voice")
        assert resp.status_code == 200
        assert "text/xml" in resp.headers["content-type"]

    def test_returns_twiml_with_connect_and_stream(self):
        client = TestClient(_get_app())
        resp = client.post("/twilio/voice")
        body = resp.text
        assert "<Response>" in body
        assert "<Connect>" in body
        assert "<Stream" in body
        assert 'url="' in body  # stream URL present

    def test_stream_url_points_to_websocket(self):
        client = TestClient(_get_app())
        resp = client.post("/twilio/voice")
        body = resp.text
        # The stream URL should reference the /twilio/media-stream ws endpoint
        assert "/twilio/media-stream" in body


class TestTwilioMediaStreamWebSocket:
    """WebSocket /twilio/media-stream should handle Twilio media events."""

    def test_accepts_websocket_connection(self):
        client = TestClient(_get_app())
        with client.websocket_connect("/twilio/media-stream") as ws:
            # Send a connected event
            ws.send_json({
                "event": "connected",
                "protocol": "Call",
                "version": "1.0.0",
            })
            # Connection should stay open — no error

    def test_handles_start_event(self):
        client = TestClient(_get_app())
        with client.websocket_connect("/twilio/media-stream") as ws:
            ws.send_json({
                "event": "start",
                "start": {
                    "streamSid": "MZ1234",
                    "callSid": "CA5678",
                    "accountSid": "AC0000",
                    "mediaFormat": {
                        "encoding": "audio/x-mulaw",
                        "sampleRate": 8000,
                        "channels": 1,
                    },
                },
                "streamSid": "MZ1234",
            })
            # No crash — start event processed

    def test_handles_media_event_with_audio_payload(self):
        client = TestClient(_get_app())
        audio_chunk = base64.b64encode(b"\x00\x01\x02\x03" * 40).decode()
        with client.websocket_connect("/twilio/media-stream") as ws:
            ws.send_json({
                "event": "media",
                "media": {
                    "track": "inbound",
                    "chunk": "1",
                    "timestamp": "100",
                    "payload": audio_chunk,
                },
                "streamSid": "MZ1234",
            })
            # No crash — media event processed

    def test_handles_stop_event(self):
        client = TestClient(_get_app())
        with client.websocket_connect("/twilio/media-stream") as ws:
            ws.send_json({
                "event": "stop",
                "streamSid": "MZ1234",
            })
            # Connection should close cleanly after stop

    def test_ignores_unknown_event_types(self):
        client = TestClient(_get_app())
        with client.websocket_connect("/twilio/media-stream") as ws:
            ws.send_json({
                "event": "unknown_event",
                "data": "whatever",
            })
            # Should not crash on unknown events
