"""Voice interface API routes — WO-RIPPLED-VOICE-INTERFACE.

Endpoints:
    POST /voice/query   — accept audio, return transcript + commitment data + spoken audio
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user_id
from app.db.deps import get_db
from app.services.voice import intent_parser, query_service, stt_service, tts_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice", tags=["voice"])

_SUPPORTED_CONTENT_TYPES = {
    "audio/mpeg", "audio/mp3", "audio/mp4",
    "audio/x-m4a", "audio/m4a",
    "audio/wav", "audio/x-wav",
    "audio/webm", "audio/ogg",
    "application/octet-stream",  # allow generic binary for Telegram voice notes
}

_MAX_AUDIO_BYTES = 25 * 1024 * 1024  # 25 MB — Whisper API limit


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class CommitmentSummary(BaseModel):
    id: str
    title: str
    state: str
    deadline: str | None = None
    overdue: bool = False
    counterparty: str | None = None
    priority: str | None = None


class VoiceQueryResponse(BaseModel):
    transcript: str
    intent: str
    time_window: str
    counterparty: str | None = None
    total_count: int
    commitments: list[CommitmentSummary]
    summary_text: str
    audio_b64: str | None = None  # base64 MP3; None if TTS failed or not requested


# ---------------------------------------------------------------------------
# POST /voice/query
# ---------------------------------------------------------------------------

@router.post(
    "/query",
    response_model=VoiceQueryResponse,
    summary="Voice query endpoint — STT → intent → commitments → TTS",
    description=(
        "Upload an audio file (m4a, mp3, wav). Returns the transcript, "
        "detected intent, matching commitments, and a spoken summary as base64 MP3."
    ),
)
async def voice_query(
    audio: UploadFile = File(..., description="Audio file: m4a, mp3, wav, webm, ogg"),
    tts: bool = Form(True, description="Include TTS audio in response (default: true)"),
    voice: str = Form("nova", description="TTS voice: alloy, echo, fable, onyx, nova, shimmer"),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> VoiceQueryResponse:
    """Full voice query pipeline: audio → transcript → intent → commitments → spoken answer."""

    # --- 1. Validate content type ---
    content_type = (audio.content_type or "").split(";")[0].strip().lower()
    if content_type and content_type not in _SUPPORTED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported audio type: {content_type}. Supported: mp3, m4a, wav, webm, ogg.",
        )

    # --- 2. Read audio bytes ---
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file")
    if len(audio_bytes) > _MAX_AUDIO_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Audio file too large ({len(audio_bytes)} bytes). Max 25 MB.",
        )

    logger.info(
        "voice_query: user=%s size=%d content_type=%s filename=%s",
        user_id, len(audio_bytes), content_type, audio.filename,
    )

    # --- 3. STT: transcribe ---
    try:
        transcript = stt_service.transcribe(
            audio_bytes=audio_bytes,
            content_type=content_type or None,
            filename=audio.filename,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.exception("STT failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Transcription failed: {exc}")

    if not transcript:
        raise HTTPException(
            status_code=422,
            detail="No speech detected in audio. Please try again with a clear voice note.",
        )

    # --- 4. Intent parsing ---
    intent_params = intent_parser.parse_intent(transcript)
    intent = intent_params.get("intent", "unknown")

    # --- 5. Query commitments (for query_commitments + review_surfaced) ---
    commitments_data: list[dict] = []
    summary_text = ""
    total_count = 0

    if intent in ("query_commitments", "review_surfaced", "unknown"):
        # For review_surfaced, default to overdue/surfaced items
        if intent == "review_surfaced" and intent_params.get("time_window", "all") == "all":
            intent_params["time_window"] = "overdue"

        result = await query_service.query_commitments(
            transcript=transcript,
            intent_params=intent_params,
            user_id=user_id,
            db=db,
        )
        commitments_data = result["commitments"]
        summary_text = result["summary_text"]
        total_count = result["total_count"]

    elif intent == "update_status":
        summary_text = (
            "Voice-based status updates aren't supported yet. "
            "Please use the app to update a commitment's status."
        )

    else:
        summary_text = "I didn't understand that query. Try asking about your commitments this week or what's overdue."

    # --- 6. TTS: generate spoken response ---
    audio_b64: str | None = None
    if tts and summary_text:
        valid_voices = {"alloy", "echo", "fable", "onyx", "nova", "shimmer"}
        tts_voice = voice if voice in valid_voices else "nova"
        try:
            audio_b64 = tts_service.synthesize_b64(summary_text, voice=tts_voice)  # type: ignore[arg-type]
        except RuntimeError as exc:
            logger.warning("TTS unavailable: %s", exc)
        except Exception as exc:
            logger.warning("TTS failed (non-fatal): %s", exc)

    return VoiceQueryResponse(
        transcript=transcript,
        intent=intent,
        time_window=intent_params.get("time_window", "all"),
        counterparty=intent_params.get("counterparty"),
        total_count=total_count,
        commitments=[CommitmentSummary(**c) for c in commitments_data],
        summary_text=summary_text,
        audio_b64=audio_b64,
    )
