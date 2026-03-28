"""Twilio webhook handler for incoming voice calls and media streams.

Handles:
- POST /twilio/voice — returns TwiML instructing Twilio to open a MediaStream
- WS /twilio/media-stream — receives real-time audio from Twilio via WebSocket
"""
import base64
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import Response

logger = logging.getLogger(__name__)

router = APIRouter()

# TwiML response that tells Twilio to connect a bidirectional media stream.
# The stream URL is relative — Twilio resolves it against the webhook host.
_TWIML_RESPONSE = """\
<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="/twilio/media-stream" />
    </Connect>
</Response>"""


@router.post("/twilio/voice")
async def twilio_voice_webhook() -> Response:
    """Handle incoming Twilio voice call.

    Returns TwiML instructing Twilio to open a bidirectional media stream
    back to our /twilio/media-stream WebSocket endpoint.
    """
    logger.info("Incoming Twilio voice call — returning TwiML with MediaStream connect")
    return Response(content=_TWIML_RESPONSE, media_type="text/xml")


@router.websocket("/twilio/media-stream")
async def twilio_media_stream(websocket: WebSocket) -> None:
    """Handle Twilio Media Stream WebSocket connection.

    Receives real-time audio chunks from Twilio and logs them for debugging.
    Events: connected, start, media, stop.
    """
    await websocket.accept()
    stream_sid: str | None = None

    try:
        while True:
            data = await websocket.receive_json()
            event_type = data.get("event")

            if event_type == "connected":
                logger.info("Twilio media stream connected (protocol=%s)", data.get("protocol"))

            elif event_type == "start":
                start_info = data.get("start", {})
                stream_sid = data.get("streamSid")
                logger.info(
                    "Media stream started: streamSid=%s callSid=%s encoding=%s",
                    stream_sid,
                    start_info.get("callSid"),
                    start_info.get("mediaFormat", {}).get("encoding"),
                )

            elif event_type == "media":
                media = data.get("media", {})
                payload = media.get("payload", "")
                audio_bytes = base64.b64decode(payload)
                logger.debug(
                    "Audio chunk: streamSid=%s track=%s chunk=%s bytes=%d",
                    data.get("streamSid"),
                    media.get("track"),
                    media.get("chunk"),
                    len(audio_bytes),
                )

            elif event_type == "stop":
                logger.info("Media stream stopped: streamSid=%s", data.get("streamSid"))
                break

            else:
                logger.debug("Ignoring unknown Twilio event: %s", event_type)

    except WebSocketDisconnect:
        logger.info("Twilio media stream disconnected: streamSid=%s", stream_sid)
