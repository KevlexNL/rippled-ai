"""User settings API routes — Phase C5 + LLM key storage."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.shared.credentials_utils import encrypt_value
from app.core.dependencies import get_current_user_id
from app.db.deps import get_db
from app.models.orm import UserSettings

router = APIRouter(prefix="/user", tags=["user-settings"])


class UserSettingsRead(BaseModel):
    digest_enabled: bool
    digest_to_email: str | None
    google_connected: bool
    anthropic_key_connected: bool
    openai_key_connected: bool


class UserSettingsPatch(BaseModel):
    digest_enabled: bool | None = None
    digest_to_email: str | None = None
    anthropic_api_key: str | None = None  # write-only: encrypted before storage
    openai_api_key: str | None = None  # write-only: encrypted before storage


async def _get_or_create_user_settings(user_id: str, db: AsyncSession) -> UserSettings:
    result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == user_id)
    )
    us = result.scalar_one_or_none()
    if us is None:
        us = UserSettings(user_id=user_id)
        db.add(us)
        await db.flush()
        await db.refresh(us)
    return us


def _to_read(us: UserSettings) -> UserSettingsRead:
    return UserSettingsRead(
        digest_enabled=us.digest_enabled,
        digest_to_email=us.digest_to_email,
        google_connected=bool(us.google_refresh_token),
        anthropic_key_connected=bool(us.anthropic_api_key_encrypted),
        openai_key_connected=bool(us.openai_api_key_encrypted),
    )


@router.get("/settings", response_model=UserSettingsRead)
async def get_user_settings(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> UserSettingsRead:
    """Get user settings, creating defaults if not exists."""
    us = await _get_or_create_user_settings(user_id, db)
    return _to_read(us)


@router.patch("/settings", response_model=UserSettingsRead)
async def patch_user_settings(
    body: UserSettingsPatch,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> UserSettingsRead:
    """Update user settings (partial update)."""
    us = await _get_or_create_user_settings(user_id, db)
    if body.digest_enabled is not None:
        us.digest_enabled = body.digest_enabled
    if body.digest_to_email is not None:
        us.digest_to_email = body.digest_to_email
    if body.anthropic_api_key is not None:
        if body.anthropic_api_key == "":
            us.anthropic_api_key_encrypted = None
        else:
            us.anthropic_api_key_encrypted = encrypt_value(body.anthropic_api_key)
    if body.openai_api_key is not None:
        if body.openai_api_key == "":
            us.openai_api_key_encrypted = None
        else:
            us.openai_api_key_encrypted = encrypt_value(body.openai_api_key)
    us.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(us)
    return _to_read(us)
