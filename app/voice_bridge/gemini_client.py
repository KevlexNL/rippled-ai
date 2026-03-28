"""Gemini Live API WebSocket client.

Handles bidirectional audio streaming with Google's Gemini Live API
for real-time STT + LLM + TTS in a single unified pipeline.

Uses placeholder credentials by default — real credentials to be
configured via environment variables once provisioned.
"""
from __future__ import annotations

import base64
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

_DEFAULT_PROJECT_ID = "PLACEHOLDER_PROJECT_ID"
_DEFAULT_LOCATION = "us-central1"
_DEFAULT_MODEL = "gemini-2.5-flash-native-audio"

_WS_URL_TEMPLATE = (
    "wss://generativelanguage.googleapis.com/v1beta"
    "/projects/{project_id}/locations/{location}"
    "/publishers/google/models/{model}:streamGenerateContent"
)


@dataclass
class GeminiResponse:
    """Parsed response from Gemini Live API."""

    text: str | None = None
    audio_data: bytes | None = None
    function_calls: list[dict] = field(default_factory=list)

    @classmethod
    def from_raw(cls, raw: dict) -> GeminiResponse:
        """Parse a GenerateContentResponse message from Gemini Live."""
        candidates = raw.get("candidates", [])
        if not candidates:
            return cls()

        parts = candidates[0].get("content", {}).get("parts", [])

        text: str | None = None
        audio_data: bytes | None = None
        function_calls: list[dict] = []

        for part in parts:
            if "text" in part:
                text = part["text"]
            elif "inlineData" in part:
                inline = part["inlineData"]
                audio_data = base64.b64decode(inline.get("data", ""))
            elif "functionCall" in part:
                fc = part["functionCall"]
                function_calls.append({
                    "name": fc.get("name"),
                    "args": fc.get("args", {}),
                })

        return cls(text=text, audio_data=audio_data, function_calls=function_calls)


class GeminiLiveClient:
    """WebSocket client for Gemini Live API.

    Manages connection lifecycle and message formatting for bidirectional
    audio streaming with Gemini's native audio model.
    """

    def __init__(
        self,
        project_id: str = _DEFAULT_PROJECT_ID,
        location: str = _DEFAULT_LOCATION,
        model: str = _DEFAULT_MODEL,
    ) -> None:
        self.project_id = project_id
        self.location = location
        self.model = model

    @property
    def websocket_url(self) -> str:
        """Build the Gemini Live WebSocket URL."""
        return _WS_URL_TEMPLATE.format(
            project_id=self.project_id,
            location=self.location,
            model=self.model,
        )

    def build_audio_message(
        self,
        audio_bytes: bytes,
        mime_type: str = "audio/pcm",
    ) -> dict:
        """Build a wire-format message for sending audio to Gemini Live.

        Args:
            audio_bytes: Raw audio data.
            mime_type: Audio MIME type (default: audio/pcm, Twilio uses audio/x-mulaw).

        Returns:
            Dict ready to be JSON-serialized and sent over WebSocket.
        """
        return {
            "realtimeInput": {
                "mediaChunks": [
                    {
                        "mimeType": mime_type,
                        "data": base64.b64encode(audio_bytes).decode(),
                    }
                ],
            },
        }

    async def connect(self) -> None:
        """Establish WebSocket connection to Gemini Live API.

        NOTE: Requires real credentials. Currently a stub for mock testing.
        Real implementation will use websockets library with Google auth headers.
        """
        logger.info(
            "Connecting to Gemini Live: project=%s location=%s model=%s",
            self.project_id,
            self.location,
            self.model,
        )
        # Real connection will be established here once credentials are available.
        # For now, log the intent.
        logger.warning(
            "Using placeholder credentials — connection will fail until "
            "GOOGLE_VERTEX_AI_PROJECT_ID is configured"
        )

    async def send_audio(self, audio_bytes: bytes, mime_type: str = "audio/x-mulaw") -> None:
        """Send an audio chunk to Gemini Live.

        Args:
            audio_bytes: Raw audio data from Twilio.
            mime_type: Audio encoding (Twilio default: audio/x-mulaw).
        """
        self.build_audio_message(audio_bytes, mime_type=mime_type)
        logger.debug("Sending audio chunk: %d bytes", len(audio_bytes))
        # Will send via websocket once connected
        # await self._ws.send(json.dumps(msg))

    async def disconnect(self) -> None:
        """Close the WebSocket connection."""
        logger.info("Disconnecting from Gemini Live")
        # Will close websocket once connected
        # await self._ws.close()
