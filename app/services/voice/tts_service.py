"""Text-to-Speech service for Rippled voice interface.

Uses OpenAI TTS API (tts-1) with the 'nova' voice as default.
Returns raw MP3 bytes ready to be base64-encoded in the API response.
"""
from __future__ import annotations

import base64
import logging
from typing import Literal

from app.core.openai_client import get_openai_client

logger = logging.getLogger(__name__)

TtsVoice = Literal["alloy", "echo", "fable", "onyx", "nova", "shimmer"]

_DEFAULT_VOICE: TtsVoice = "nova"
_MAX_INPUT_CHARS = 4096


def synthesize(
    text: str,
    voice: TtsVoice = _DEFAULT_VOICE,
) -> bytes:
    """Convert text to speech using OpenAI TTS API.

    Args:
        text: Text to synthesize. Truncated to 4096 chars if longer.
        voice: TTS voice name (default: nova).

    Returns:
        Raw MP3 audio bytes.

    Raises:
        RuntimeError: If OpenAI client not configured.
    """
    client = get_openai_client()
    if not client:
        raise RuntimeError("OPENAI_API_KEY not configured — TTS unavailable")

    if len(text) > _MAX_INPUT_CHARS:
        text = text[:_MAX_INPUT_CHARS]
        logger.warning("TTS: input truncated to %d chars", _MAX_INPUT_CHARS)

    logger.info("TTS: synthesizing %d chars with voice=%s", len(text), voice)

    response = client.audio.speech.create(
        model="tts-1",
        voice=voice,
        input=text,
        response_format="mp3",
    )

    audio_bytes = response.read()
    logger.info("TTS: generated %d bytes", len(audio_bytes))
    return audio_bytes


def synthesize_b64(text: str, voice: TtsVoice = _DEFAULT_VOICE) -> str:
    """Convert text to speech and return base64-encoded MP3 string.

    Args:
        text: Text to synthesize.
        voice: TTS voice name (default: nova).

    Returns:
        Base64-encoded MP3 string (no data: URI prefix).
    """
    audio_bytes = synthesize(text, voice)
    return base64.b64encode(audio_bytes).decode("utf-8")
