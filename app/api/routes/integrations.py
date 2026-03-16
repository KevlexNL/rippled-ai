"""Integrations API router — Phase C3 + Slack OAuth.

Google OAuth endpoints:
    GET    /integrations/google/auth          → redirect to Google OAuth consent
    GET    /integrations/google/callback      → exchange code, store tokens
    GET    /integrations/google/status        → {connected: bool, expiry: datetime | None}
    DELETE /integrations/google/disconnect    → revoke and clear tokens

Slack OAuth endpoints:
    GET    /integrations/slack/oauth/start    → redirect to Slack authorization URL
    GET    /integrations/slack/oauth/callback → exchange code for token, store via encrypted credentials
"""
from __future__ import annotations

import logging
import urllib.parse
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.shared.credentials_utils import encrypt_credentials
from app.core.config import get_settings
from app.core.dependencies import get_current_user_id, get_user_id_for_redirect
from app.db.deps import get_db
from app.models.orm import Source, UserSettings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/integrations", tags=["integrations"])
settings = get_settings()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class GoogleStatusResponse(BaseModel):
    connected: bool
    expiry: datetime | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _require_google_enabled():
    if not settings.google_calendar_enabled:
        raise HTTPException(
            status_code=503,
            detail="Google Calendar integration is not enabled. Set GOOGLE_CALENDAR_ENABLED=true.",
        )


async def _get_or_create_user_settings(user_id: str, db: AsyncSession) -> UserSettings:
    result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == user_id)
    )
    us = result.scalar_one_or_none()
    if us is None:
        us = UserSettings(user_id=user_id)
        db.add(us)
        await db.flush()
    return us


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/google/auth")
async def google_auth(
    user_id: str = Depends(get_user_id_for_redirect),
) -> RedirectResponse:
    """Redirect to Google OAuth consent screen."""
    _require_google_enabled()

    from app.connectors.google_calendar import get_auth_url
    auth_url = get_auth_url(settings)
    return RedirectResponse(url=auth_url)


@router.get("/google/callback")
async def google_callback(
    code: str | None = None,
    error: str | None = None,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Handle Google OAuth callback, exchange code for tokens, store them."""
    _require_google_enabled()

    if error or not code:
        return RedirectResponse(url="/settings/integrations?calendar=error")

    try:
        from app.connectors.google_calendar import exchange_code
        from app.connectors.shared.credentials_utils import encrypt_value
        tokens = exchange_code(code, settings)
    except Exception as exc:
        logger.error("Google OAuth code exchange failed: %s", exc)
        return RedirectResponse(url="/settings/integrations?calendar=error")

    us = await _get_or_create_user_settings(user_id, db)
    us.google_access_token = encrypt_value(tokens.get("access_token"))
    us.google_refresh_token = encrypt_value(tokens.get("refresh_token"))
    us.google_token_expiry = tokens.get("expiry")
    us.updated_at = datetime.now(timezone.utc)

    await db.flush()

    return RedirectResponse(url="/settings/integrations?calendar=connected")


@router.get("/google/status", response_model=GoogleStatusResponse)
async def google_status(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> GoogleStatusResponse:
    """Return Google Calendar connection status for the current user."""
    result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == user_id)
    )
    us = result.scalar_one_or_none()

    if us is None or not us.google_refresh_token:
        return GoogleStatusResponse(connected=False, expiry=None)

    return GoogleStatusResponse(connected=True, expiry=us.google_token_expiry)


@router.delete("/google/disconnect", status_code=204)
async def google_disconnect(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Revoke Google tokens and clear them from UserSettings."""
    _require_google_enabled()

    result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == user_id)
    )
    us = result.scalar_one_or_none()

    if us is None:
        return

    # Revoke the access token (best-effort)
    if us.google_access_token:
        try:
            from app.connectors.google_calendar import revoke_token
            from app.connectors.shared.credentials_utils import decrypt_value
            access_token = decrypt_value(us.google_access_token)
            if access_token:
                revoke_token(access_token)
        except Exception as exc:
            logger.warning("Token revocation failed (non-fatal): %s", exc)

    us.google_access_token = None
    us.google_refresh_token = None
    us.google_token_expiry = None
    us.updated_at = datetime.now(timezone.utc)
    await db.flush()


# ---------------------------------------------------------------------------
# Slack OAuth
# ---------------------------------------------------------------------------

SLACK_OAUTH_SCOPES = [
    "channels:history",
    "channels:read",
    "im:history",
    "im:read",
    "users:read",
]


def _require_slack_oauth_enabled():
    if not settings.slack_client_id or not settings.slack_client_secret:
        raise HTTPException(
            status_code=503,
            detail="Slack OAuth is not configured. Set SLACK_CLIENT_ID and SLACK_CLIENT_SECRET.",
        )


@router.get("/slack/oauth/start")
async def slack_oauth_start(
    user_id: str = Depends(get_user_id_for_redirect),
) -> RedirectResponse:
    """Redirect to Slack's OAuth authorization page."""
    _require_slack_oauth_enabled()

    redirect_uri = settings.slack_oauth_redirect_uri
    if not redirect_uri:
        redirect_uri = f"{settings.base_url}{settings.api_prefix}/integrations/slack/oauth/callback"

    params = urllib.parse.urlencode({
        "client_id": settings.slack_client_id,
        "scope": ",".join(SLACK_OAUTH_SCOPES),
        "redirect_uri": redirect_uri,
        "state": user_id,
    })
    return RedirectResponse(url=f"https://slack.com/oauth/v2/authorize?{params}")


@router.get("/slack/oauth/callback")
async def slack_oauth_callback(
    code: str | None = None,
    error: str | None = None,
    state: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Handle Slack OAuth callback — exchange code for bot token, store as Source."""
    _require_slack_oauth_enabled()

    if error or not code:
        logger.warning("Slack OAuth error: %s", error)
        return RedirectResponse(url="/settings/integrations?slack=error")

    user_id = state
    if not user_id:
        return RedirectResponse(url="/settings/integrations?slack=error")

    redirect_uri = settings.slack_oauth_redirect_uri
    if not redirect_uri:
        redirect_uri = f"{settings.base_url}{settings.api_prefix}/integrations/slack/oauth/callback"

    # Exchange authorization code for access token
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://slack.com/api/oauth.v2.access",
                data={
                    "client_id": settings.slack_client_id,
                    "client_secret": settings.slack_client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
            )
        data = resp.json()
    except Exception as exc:
        logger.error("Slack OAuth token exchange failed: %s", exc)
        return RedirectResponse(url="/settings/integrations?slack=error")

    if not data.get("ok"):
        logger.error("Slack OAuth error response: %s", data.get("error"))
        return RedirectResponse(url="/settings/integrations?slack=error")

    bot_token = data.get("access_token", "")
    team_info = data.get("team", {})
    team_id = team_info.get("id", "")
    team_name = team_info.get("name", "")
    authed_user = data.get("authed_user", {})
    slack_user_id = authed_user.get("id", "")

    credentials = encrypt_credentials({
        "bot_token": bot_token,
        "signing_secret": settings.slack_signing_secret,
        "slack_user_id": slack_user_id,
        "team_id": team_id,
    })

    # Ensure user row exists
    from app.api.routes.sources import _ensure_user_exists
    await _ensure_user_exists(user_id, db)

    # Upsert Slack source for this user
    result = await db.execute(
        select(Source).where(
            Source.user_id == user_id,
            Source.source_type == "slack",
        )
    )
    source = result.scalar_one_or_none()

    if source is None:
        source = Source(user_id=user_id, source_type="slack")
        db.add(source)

    source.provider_account_id = team_id
    source.display_name = team_name
    source.is_active = True
    source.credentials = credentials
    source.updated_at = datetime.now(timezone.utc)

    await db.flush()

    return RedirectResponse(url="/settings/integrations?slack=connected")
