"""User settings API routes — Phase C5 + LLM key storage + D1 observation windows + D2 auto-close config."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.shared.credentials_utils import encrypt_value
from app.core.dependencies import get_current_user_id
from app.db.deps import get_db
from app.models.orm import UserCommitmentProfile, UserFeedback, UserSettings
from app.services.auto_close_config import (
    merge_auto_close_defaults,
    validate_auto_close_config,
)
from app.services.observation_window import VALID_WINDOW_KEYS, merge_with_defaults

router = APIRouter(prefix="/user", tags=["user-settings"])


class UserSettingsRead(BaseModel):
    digest_enabled: bool
    digest_to_email: str | None
    google_connected: bool
    anthropic_key_connected: bool
    openai_key_connected: bool
    observation_window_config: dict[str, float]
    auto_close_config: dict[str, float]


class UserSettingsPatch(BaseModel):
    digest_enabled: bool | None = None
    digest_to_email: str | None = None
    anthropic_api_key: str | None = None  # write-only: encrypted before storage
    openai_api_key: str | None = None  # write-only: encrypted before storage
    observation_window_config: dict[str, float] | None = None
    auto_close_config: dict[str, float] | None = None

    @field_validator("observation_window_config")
    @classmethod
    def validate_observation_window_config(
        cls, v: dict[str, float] | None,
    ) -> dict[str, float] | None:
        if v is None:
            return None
        for key, value in v.items():
            if key not in VALID_WINDOW_KEYS:
                raise ValueError(
                    f"Unknown observation window key: {key!r}. "
                    f"Valid keys: {sorted(VALID_WINDOW_KEYS)}"
                )
            if not isinstance(value, (int, float)) or value < 0.5 or value > 168:
                raise ValueError(
                    f"Observation window for {key!r} must be between 0.5 and 168 hours, got {value}"
                )
        return v

    @field_validator("auto_close_config")
    @classmethod
    def validate_auto_close_config(
        cls, v: dict[str, float] | None,
    ) -> dict[str, float] | None:
        if v is None:
            return None
        validate_auto_close_config(v)
        return v


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
        observation_window_config=merge_with_defaults(us.observation_window_config),
        auto_close_config=merge_auto_close_defaults(us.auto_close_config),
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
    # Phase D1: observation window config
    if "observation_window_config" in body.model_fields_set:
        us.observation_window_config = body.observation_window_config
    # Phase D2: auto-close config
    if "auto_close_config" in body.model_fields_set:
        us.auto_close_config = body.auto_close_config
    us.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(us)
    return _to_read(us)


# ---------------------------------------------------------------------------
# [D4] Feedback stats
# ---------------------------------------------------------------------------

class FeedbackStatsRead(BaseModel):
    total_feedback_count: int
    threshold_adjustments: dict | None
    feedback_summary: dict


@router.get("/feedback-stats", response_model=FeedbackStatsRead)
async def get_feedback_stats(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> FeedbackStatsRead:
    """Return per-user feedback stats and current threshold adjustments."""
    from sqlalchemy import func as sqlfunc

    # Load profile
    profile_result = await db.execute(
        select(UserCommitmentProfile).where(UserCommitmentProfile.user_id == user_id)
    )
    profile = profile_result.scalar_one_or_none()
    threshold_adjustments = profile.threshold_adjustments if profile else None

    # Count feedback by category
    dismiss_result = await db.execute(
        select(sqlfunc.count()).select_from(UserFeedback).where(
            UserFeedback.user_id == user_id,
            UserFeedback.action.in_(["dismiss", "mark_not_commitment"]),
        )
    )
    dismiss_count = dismiss_result.scalar() or 0

    confirm_result = await db.execute(
        select(sqlfunc.count()).select_from(UserFeedback).where(
            UserFeedback.user_id == user_id,
            UserFeedback.action == "confirm",
        )
    )
    confirm_count = confirm_result.scalar() or 0

    correct_result = await db.execute(
        select(sqlfunc.count()).select_from(UserFeedback).where(
            UserFeedback.user_id == user_id,
            UserFeedback.action.in_(["correct_owner", "correct_deadline", "correct_description"]),
        )
    )
    correct_count = correct_result.scalar() or 0

    total = dismiss_count + confirm_count + correct_count

    return FeedbackStatsRead(
        total_feedback_count=total,
        threshold_adjustments=threshold_adjustments,
        feedback_summary={
            "dismiss_count": dismiss_count,
            "confirm_count": confirm_count,
            "correct_count": correct_count,
        },
    )
