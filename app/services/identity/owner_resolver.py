"""Owner resolution — maps suggested_owner strings to user IDs via identity profiles.

Uses case-insensitive substring matching + difflib fuzzy matching (threshold 0.75).
"""
from __future__ import annotations

import logging
from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.orm import UserIdentityProfile

logger = logging.getLogger(__name__)

_FUZZY_THRESHOLD = 0.75


def _is_match(suggested: str, identity_value: str) -> bool:
    """Check if suggested_owner matches an identity value.

    Uses case-insensitive substring matching and fuzzy matching.
    """
    s = suggested.lower().strip()
    v = identity_value.lower().strip()

    if not s or not v:
        return False

    # Exact match
    if s == v:
        return True

    # Substring match (either direction)
    if s in v or v in s:
        return True

    # Fuzzy match
    ratio = SequenceMatcher(None, s, v).ratio()
    if ratio >= _FUZZY_THRESHOLD:
        return True

    return False


async def resolve_owner(
    suggested_owner: str, user_id: str, db: AsyncSession
) -> str | None:
    """Resolve a suggested_owner string to a user_id via confirmed identity profiles.

    Args:
        suggested_owner: The name/email string from LLM extraction.
        user_id: The user who owns these commitments (scope the lookup).
        db: Async SQLAlchemy session.

    Returns:
        The user_id string if matched, None otherwise.
    """
    if not suggested_owner or not suggested_owner.strip():
        return None

    result = await db.execute(
        select(UserIdentityProfile).where(
            UserIdentityProfile.user_id == user_id,
            UserIdentityProfile.confirmed.is_(True),
        )
    )
    profiles = result.scalars().all()

    for profile in profiles:
        if _is_match(suggested_owner, profile.identity_value):
            logger.debug(
                "Owner resolved: '%s' matched identity '%s' (type=%s) -> user %s",
                suggested_owner, profile.identity_value, profile.identity_type, user_id,
            )
            return user_id

    return None


def resolve_owner_sync(
    suggested_owner: str, user_id: str, db: Session
) -> str | None:
    """Sync version of resolve_owner for use in seed_detector and other sync contexts."""
    if not suggested_owner or not suggested_owner.strip():
        return None

    result = db.execute(
        select(UserIdentityProfile).where(
            UserIdentityProfile.user_id == user_id,
            UserIdentityProfile.confirmed.is_(True),
        )
    )
    profiles = result.scalars().all()

    for profile in profiles:
        if _is_match(suggested_owner, profile.identity_value):
            logger.debug(
                "Owner resolved (sync): '%s' matched identity '%s' (type=%s) -> user %s",
                suggested_owner, profile.identity_value, profile.identity_type, user_id,
            )
            return user_id

    return None


async def resolve_party(
    party_name: str | None, user_id: str, db: AsyncSession
) -> str | None:
    """Resolve a requester or beneficiary name against identity profiles.

    Same matching logic as resolve_owner — returns user_id if the party name
    matches a confirmed identity profile for the given user.

    Args:
        party_name: Name string from LLM extraction (requester or beneficiary).
        user_id: The user who owns these commitments (scope the lookup).
        db: Async SQLAlchemy session.

    Returns:
        The user_id string if matched, None otherwise.
    """
    if not party_name or not party_name.strip():
        return None

    result = await db.execute(
        select(UserIdentityProfile).where(
            UserIdentityProfile.user_id == user_id,
            UserIdentityProfile.confirmed.is_(True),
        )
    )
    profiles = result.scalars().all()

    for profile in profiles:
        if _is_match(party_name, profile.identity_value):
            logger.debug(
                "Party resolved: '%s' matched identity '%s' (type=%s) -> user %s",
                party_name, profile.identity_value, profile.identity_type, user_id,
            )
            return user_id

    return None


def resolve_party_sync(
    party_name: str | None, user_id: str, db: Session
) -> str | None:
    """Sync version of resolve_party."""
    if not party_name or not party_name.strip():
        return None

    result = db.execute(
        select(UserIdentityProfile).where(
            UserIdentityProfile.user_id == user_id,
            UserIdentityProfile.confirmed.is_(True),
        )
    )
    profiles = result.scalars().all()

    for profile in profiles:
        if _is_match(party_name, profile.identity_value):
            logger.debug(
                "Party resolved (sync): '%s' matched identity '%s' (type=%s) -> user %s",
                party_name, profile.identity_value, profile.identity_type, user_id,
            )
            return user_id

    return None
