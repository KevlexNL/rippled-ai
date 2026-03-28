"""Bidirectional audio pipe connecting Twilio to Gemini Live.

Routes incoming Twilio audio to Gemini Live for processing,
handles Gemini responses (text, audio, function calls), and
provides mock TTS for pre-credential testing.
"""
from __future__ import annotations

import logging

from app.voice_bridge.gemini_client import GeminiLiveClient, GeminiResponse

logger = logging.getLogger(__name__)

# mulaw silence byte — used for mock TTS response
_MULAW_SILENCE = 0x7F
# Duration of mock TTS in samples (8000 Hz * 0.5s = 4000 samples)
_MOCK_TTS_SAMPLES = 4000


class AudioPipe:
    """Bidirectional audio pipe: Twilio <-> Gemini Live.

    Forwards incoming audio from Twilio to Gemini, collects responses,
    and manages the connection lifecycle.
    """

    def __init__(self, gemini_client: GeminiLiveClient | None = None) -> None:
        self.gemini_client = gemini_client or GeminiLiveClient()
        self.transcript: list[str] = []
        self.last_outbound_audio: bytes | None = None
        self.pending_function_calls: list[dict] = []
        self.is_active = False

    async def start(self) -> None:
        """Start the audio pipe — connect to Gemini Live."""
        logger.info("Starting audio pipe")
        await self.gemini_client.connect()
        self.is_active = True

    async def stop(self) -> None:
        """Stop the audio pipe — disconnect from Gemini Live."""
        logger.info("Stopping audio pipe")
        await self.gemini_client.disconnect()
        self.is_active = False

    async def forward_audio(
        self,
        audio_bytes: bytes,
        mime_type: str = "audio/x-mulaw",
    ) -> None:
        """Forward an audio chunk from Twilio to Gemini Live.

        Args:
            audio_bytes: Raw audio data from Twilio MediaStream.
            mime_type: Audio encoding (default: audio/x-mulaw from Twilio).
        """
        await self.gemini_client.send_audio(audio_bytes, mime_type=mime_type)

    def handle_response(self, response: GeminiResponse) -> None:
        """Process a response from Gemini Live.

        Stores text in transcript, audio for playback, and function calls
        for later execution.
        """
        if response.text:
            logger.info("Gemini text response: %s", response.text)
            self.transcript.append(response.text)

        if response.audio_data:
            logger.debug("Gemini audio response: %d bytes", len(response.audio_data))
            self.last_outbound_audio = response.audio_data

        for fc in response.function_calls:
            logger.info("Gemini function call: %s(%s)", fc["name"], fc.get("args", {}))
            self.pending_function_calls.append(fc)

    def get_mock_tts_response(self, text: str) -> bytes:
        """Generate a mock TTS audio response (mulaw silence).

        Used for testing before real Gemini Live credentials are available.
        Returns 0.5s of mulaw silence at 8kHz.

        Args:
            text: The text that would be spoken (logged, not synthesized).

        Returns:
            Bytes of mulaw silence.
        """
        logger.info("Mock TTS for: %s", text)
        return bytes([_MULAW_SILENCE] * _MOCK_TTS_SAMPLES)
