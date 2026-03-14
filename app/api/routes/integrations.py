"""Integrations API router — Phase C3.

Google OAuth endpoints:
    GET    /integrations/google/auth          → redirect to Google OAuth consent
    GET    /integrations/google/callback      → exchange code, store tokens
    GET    /integrations/google/status        → {connected: bool, expiry: datetime | None}
    DELETE /integrations/google/disconnect    → revoke and clear tokens
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.dependencies import get_current_user_id
from app.db.deps import get_db
from app.models.orm import UserSettings

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
    user_id: str = Depends(get_current_user_id),
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
) -> dict:
    """Handle Google OAuth callback, exchange code for tokens, store them."""
    _require_google_enabled()

    if error:
        raise HTTPException(status_code=400, detail=f"OAuth error: {error}")

    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")

    try:
        from app.connectors.google_calendar import exchange_code
        from app.connectors.shared.credentials_utils import encrypt_value
        tokens = exchange_code(code, settings)
    except Exception as exc:
        logger.error("Google OAuth code exchange failed: %s", exc)
        raise HTTPException(status_code=400, detail="Failed to exchange authorization code")

    us = await _get_or_create_user_settings(user_id, db)
    us.google_access_token = encrypt_value(tokens.get("access_token"))
    us.google_refresh_token = encrypt_value(tokens.get("refresh_token"))
    us.google_token_expiry = tokens.get("expiry")
    us.updated_at = datetime.now(timezone.utc)

    await db.flush()

    return {"status": "connected"}


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
