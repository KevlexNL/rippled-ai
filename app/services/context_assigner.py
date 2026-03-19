"""Context auto-assignment service.

Matches commitments to existing commitment_contexts based on
counterparty_name and title keywords.

Public API:
    match_commitment_to_context(commitment, contexts) -> CommitmentContext | None
    assign_contexts_for_user(user_id, db) -> dict
"""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.orm import Commitment, CommitmentContext

logger = logging.getLogger(__name__)

# Minimum context name length to match against title (avoid spurious matches)
_MIN_CONTEXT_NAME_LENGTH = 3


def match_commitment_to_context(
    commitment, contexts: list
) -> object | None:
    """Pure function: find the best matching context for a commitment.

    Priority:
    1. counterparty_name matches context name (case-insensitive, substring)
    2. context name appears in commitment title (case-insensitive, word boundary)

    Returns the matched context object or None.
    """
    if not contexts:
        return None

    counterparty = getattr(commitment, "counterparty_name", None) or ""
    title = getattr(commitment, "title", None) or ""
    counterparty_lower = counterparty.lower().strip()
    title_lower = title.lower()

    # Pass 1: counterparty_name match (highest priority)
    if counterparty_lower:
        for ctx in contexts:
            ctx_name_lower = ctx.name.lower().strip()
            # Exact or substring match in either direction
            if ctx_name_lower == counterparty_lower:
                return ctx
            if counterparty_lower in ctx_name_lower or ctx_name_lower in counterparty_lower:
                return ctx

    # Pass 2: context name in title (lower priority)
    if title_lower:
        for ctx in contexts:
            ctx_name = ctx.name.strip()
            if len(ctx_name) < _MIN_CONTEXT_NAME_LENGTH:
                continue
            if ctx_name.lower() in title_lower:
                return ctx

    return None


def assign_contexts_for_user(user_id: str, db: Session) -> dict:
    """Assign contexts to unassigned commitments for a user.

    Only touches commitments where context_id IS NULL.

    Returns:
        dict with keys: total, assigned, skipped
    """
    # Load all contexts for user
    contexts = (
        db.execute(
            select(CommitmentContext).where(CommitmentContext.user_id == user_id)
        )
        .scalars()
        .all()
    )

    if not contexts:
        logger.debug("assign_contexts: no contexts for user %s", user_id)
        return {"total": 0, "assigned": 0, "skipped": 0}

    # Load commitments without context_id
    commitments = (
        db.execute(
            select(Commitment).where(
                Commitment.user_id == user_id,
                Commitment.context_id.is_(None),
            )
        )
        .scalars()
        .all()
    )

    assigned = 0
    skipped = 0

    for commitment in commitments:
        match = match_commitment_to_context(commitment, contexts)
        if match:
            commitment.context_id = match.id
            assigned += 1
        else:
            skipped += 1

    if assigned:
        db.flush()

    logger.info(
        "assign_contexts: user=%s total=%d assigned=%d skipped=%d",
        user_id, len(commitments), assigned, skipped,
    )

    return {
        "total": len(commitments),
        "assigned": assigned,
        "skipped": skipped,
    }
