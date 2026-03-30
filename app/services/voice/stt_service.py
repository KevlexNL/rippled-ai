"""Speech-to-Text service for Rippled voice interface.

Uses OpenAI Whisper API (whisper-1) as the default transcription backend.
Accepts audio bytes + MIME type and returns a clean transcript string.
"""
from __future__ import annotations

import io
import logging
from typing import Literal

from app.core.openai_client import get_openai_client

logger = logging.getLogger(__name__)

# Supported MIME types and their file extensions for the Whisper API
_MIME_TO_EXT: dict[str, str] = {
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/mp4": "mp4",
    "audio/x-m4a": "m4a",
    "audio/m4a": "m4a",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/webm": "webm",
    "audio/ogg": "ogg",
    "application/octet-stream": "mp3",  # fallback
}

SupportedAudioFormat = Literal["mp3", "mp4", "m4a", "wav", "webm", "ogg"]


def _ext_from_mime(content_type: str | None, filename: str | None) -> str:
    """Determine file extension from MIME type or filename."""
    if filename:
        parts = filename.rsplit(".", 1)
        if len(parts) == 2 and parts[1].lower() in _MIME_TO_EXT.values():
            return parts[1].lower()
    if content_type:
        mime = content_type.split(";")[0].strip().lower()
        if mime in _MIME_TO_EXT:
            return _MIME_TO_EXT[mime]
    return "mp3"  # safe fallback for Whisper


def transcribe(
    audio_bytes: bytes,
    content_type: str | None = None,
    filename: str | None = None,
) -> str:
    """Transcribe audio bytes using OpenAI Whisper API.

    Args:
        audio_bytes: Raw audio file content.
        content_type: MIME type of the audio (e.g. "audio/mpeg").
        filename: Original filename hint (used for extension detection).

    Returns:
        Transcript string. Empty string if transcription fails.

    Raises:
        RuntimeError: If OpenAI client is not configured.
    """
    client = get_openai_client()
    if not client:
        raise RuntimeError("OPENAI_API_KEY not configured — voice transcription unavailable")

    ext = _ext_from_mime(content_type, filename)
    display_name = f"audio.{ext}"

    logger.info("STT: transcribing %d bytes as %s", len(audio_bytes), display_name)

    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = display_name  # Whisper API uses filename for format detection

    response = client.audio.transcriptions.create(
        model="whisper-1",
        file=audio_file,
        response_format="text",
    )

    transcript = response.strip() if isinstance(response, str) else str(response).strip()
    logger.info("STT: transcript='%s'", transcript[:120])
    return transcript
