"""Slack Events API webhook handler.

POST /webhooks/slack/events — receives Slack event payloads.
"""
import logging

from fastapi import APIRouter, Header, HTTPException, Request

from app.connectors.slack.verifier import verify_slack_signature
from app.core.config import get_settings

router = APIRouter(prefix="/webhooks/slack", tags=["webhooks"])
logger = logging.getLogger(__name__)


@router.post("/events")
async def slack_events(
    request: Request,
    x_slack_signature: str | None = Header(None),
    x_slack_request_timestamp: str | None = Header(None),
) -> dict:
    """Receive Slack Events API payloads.

    Security: HMAC-SHA256 signature verification via X-Slack-Signature.
    Acks immediately and dispatches to Celery (Slack requires <3s response).
    """
    body = await request.body()
    settings = get_settings()

    # Verify signature if signing secret is configured
    if settings.slack_signing_secret:
        if not x_slack_signature or not x_slack_request_timestamp:
            raise HTTPException(status_code=401, detail="Missing Slack signature headers")
        try:
            valid = verify_slack_signature(
                signing_secret=settings.slack_signing_secret,
                timestamp=x_slack_request_timestamp,
                body=body,
                signature=x_slack_signature,
            )
        except ValueError as e:
            raise HTTPException(status_code=401, detail=str(e))
        if not valid:
            raise HTTPException(status_code=401, detail="Invalid Slack signature")

    import json
    try:
        payload = json.loads(body)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # Handle Slack URL verification challenge
    if payload.get("type") == "url_verification":
        return {"challenge": payload.get("challenge")}

    # Ack immediately, dispatch to Celery
    event = payload.get("event", {})
    if event:
        try:
            from app.tasks import process_slack_event
            process_slack_event.delay(payload)
        except Exception:
            # Fire-and-forget: graceful degradation if Celery unavailable
            logger.warning("Could not dispatch process_slack_event task")

    return {"ok": True}
