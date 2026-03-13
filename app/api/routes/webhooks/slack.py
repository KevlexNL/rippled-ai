"""Slack Events API webhook handler.

POST /webhooks/slack/events — receives Slack event payloads.
"""
import json as json_lib
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.shared.credentials_utils import decrypt_credentials
from app.connectors.slack.verifier import verify_slack_signature
from app.core.config import get_settings
from app.db.deps import get_db
from app.models.orm import Source

router = APIRouter(prefix="/webhooks/slack", tags=["webhooks"])
logger = logging.getLogger(__name__)


@router.post("/events")
async def slack_events(
    request: Request,
    x_slack_signature: str | None = Header(None),
    x_slack_request_timestamp: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Receive Slack Events API payloads.

    Security: HMAC-SHA256 signature verification via X-Slack-Signature.
    Per-source signing secret is looked up from the matching Slack Source
    (by team_id) with fallback to the global SLACK_SIGNING_SECRET env var.
    Acks immediately and dispatches to Celery (Slack requires <3s response).
    """
    body = await request.body()
    settings = get_settings()

    # Peek at team_id from body to resolve per-source signing secret
    team_id: str | None = None
    try:
        peek = json_lib.loads(body)
        team_id = peek.get("team_id")
    except Exception:
        pass

    signing_secret = settings.slack_signing_secret  # global fallback

    if team_id:
        try:
            result = await db.execute(
                select(Source).where(
                    Source.source_type == "slack",
                    Source.provider_account_id == team_id,
                    Source.is_active.is_(True),
                )
            )
            slack_source = result.scalar_one_or_none()
            if slack_source and slack_source.credentials:
                creds = decrypt_credentials(slack_source.credentials)
                signing_secret = creds.get("signing_secret") or settings.slack_signing_secret
        except Exception:
            # DB unavailable — fall back to global signing secret for verification
            logger.warning("Could not look up Slack Source for team_id=%s — using global signing secret", team_id)

    # Verify signature using resolved signing secret
    if signing_secret:
        if not x_slack_signature or not x_slack_request_timestamp:
            raise HTTPException(status_code=401, detail="Missing Slack signature headers")
        try:
            valid = verify_slack_signature(
                signing_secret=signing_secret,
                timestamp=x_slack_request_timestamp,
                body=body,
                signature=x_slack_signature,
            )
        except ValueError as e:
            raise HTTPException(status_code=401, detail=str(e))
        if not valid:
            raise HTTPException(status_code=401, detail="Invalid Slack signature")

    try:
        payload = json_lib.loads(body)
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
