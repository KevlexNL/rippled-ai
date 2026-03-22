"""Lifecycle updater — Phase 05.

Applies scorer output to the database: updates commitment fields, writes
CommitmentSignal (insert-or-ignore pattern), writes LifecycleTransition.

No-op guards:
- lifecycle_state in {closed, completed, canceled, discarded}: complete no-op (no writes)
- lifecycle_state == "delivered": write signal if confidence >= 0.40, no transition

Threshold logic:
- delivery_confidence >= 0.65 AND evidence_strength != "weak" → active → delivered
- delivery_confidence >= 0.40 AND < 0.65 → log-only (signal, no transition)
- delivery_confidence < 0.40 → no writes

Public API:
    apply_completion_result(commitment, evidence, score, db) -> LifecycleTransition | None
    apply_auto_close(commitment, db) -> LifecycleTransition
    apply_cancellation(commitment, db, trigger_source_item_id) -> LifecycleTransition | None
    apply_user_confirmed_completion(commitment, db) -> LifecycleTransition | None
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import LifecycleState, SignalRole
from app.models.orm import CommitmentSignal, LifecycleTransition
from app.services.completion.matcher import CompletionEvidence
from app.services.completion.scorer import CompletionScore

logger = logging.getLogger(__name__)

# Minimum confidence to write any signal
_SIGNAL_THRESHOLD = 0.40

# Minimum confidence to trigger active → delivered transition
_DELIVERY_THRESHOLD = 0.65


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _signal_exists(
    commitment_id: str,
    source_item_id: str,
    signal_role: str,
    db: Session,
) -> bool:
    """Check if a CommitmentSignal already exists for this (commitment, item, role) triple."""
    result = db.execute(
        select(CommitmentSignal).where(
            CommitmentSignal.commitment_id == commitment_id,
            CommitmentSignal.source_item_id == source_item_id,
            CommitmentSignal.signal_role == signal_role,
        )
    ).scalar_one_or_none()
    return result is not None


def _write_signal(
    commitment: Any,
    evidence: CompletionEvidence,
    score: CompletionScore,
    db: Session,
) -> None:
    """Write a CommitmentSignal row (insert-or-ignore via existence check)."""
    role = SignalRole.delivery.value

    if _signal_exists(commitment.id, evidence.source_item_id, role, db):
        logger.debug(
            "Signal already exists for commitment=%s source_item=%s role=%s — skipping",
            commitment.id, evidence.source_item_id, role,
        )
        return

    signal = CommitmentSignal(
        id=str(uuid.uuid4()),
        commitment_id=commitment.id,
        source_item_id=evidence.source_item_id,
        user_id=commitment.user_id,
        signal_role=role,
        confidence=Decimal(str(round(score.delivery_confidence, 3))),
        interpretation_note="; ".join(score.notes),
    )
    db.add(signal)
    logger.debug(
        "CommitmentSignal written: commitment=%s confidence=%.2f",
        commitment.id, score.delivery_confidence,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def apply_completion_result(
    commitment: Any,
    evidence: CompletionEvidence,
    score: CompletionScore,
    db: Session,
) -> LifecycleTransition | None:
    """Apply scorer output to the database.

    Returns the LifecycleTransition if a state change was made, else None.
    Writes CommitmentSignal for any evidence with confidence >= 0.40.

    Args:
        commitment: Duck-typed Commitment ORM object.
        evidence: CompletionEvidence from the matcher.
        score: CompletionScore from the scorer.
        db: Synchronous SQLAlchemy Session.
    """
    current_state = commitment.lifecycle_state

    # Complete no-op for terminal states
    _terminal = {
        LifecycleState.closed.value,
        LifecycleState.completed.value,
        LifecycleState.canceled.value,
        LifecycleState.discarded.value,
    }
    if current_state in _terminal:
        logger.debug("Commitment %s in terminal state %s — skipping", commitment.id, current_state)
        return None

    # Below signal threshold: no writes at all
    if score.delivery_confidence < _SIGNAL_THRESHOLD:
        logger.debug(
            "Commitment %s delivery_confidence=%.2f below signal threshold — no write",
            commitment.id, score.delivery_confidence,
        )
        return None

    # Always write the signal (insert-or-ignore)
    _write_signal(commitment, evidence, score, db)

    # No transition if already delivered, or below delivery threshold, or weak evidence
    already_delivered = current_state == LifecycleState.delivered.value
    below_threshold = score.delivery_confidence < _DELIVERY_THRESHOLD
    weak_evidence = score.evidence_strength == "weak"

    if already_delivered or below_threshold or weak_evidence:
        logger.debug(
            "Commitment %s: signal written, no transition (state=%s, confidence=%.2f, strength=%s)",
            commitment.id, current_state, score.delivery_confidence, score.evidence_strength,
        )
        return None

    # Transition active → delivered
    now = datetime.now(timezone.utc)
    from_state = commitment.lifecycle_state

    commitment.lifecycle_state = LifecycleState.delivered.value
    commitment.state_changed_at = now
    commitment.delivered_at = now
    commitment.confidence_delivery = Decimal(str(round(score.delivery_confidence, 3)))
    commitment.confidence_closure = Decimal(str(round(score.closure_readiness_confidence, 3)))
    commitment.delivery_explanation = "; ".join(score.notes)

    transition = LifecycleTransition(
        id=str(uuid.uuid4()),
        commitment_id=commitment.id,
        user_id=commitment.user_id,
        from_state=from_state,
        to_state=LifecycleState.delivered.value,
        trigger_source_item_id=evidence.source_item_id,
        trigger_reason=(
            f"delivery_confidence={score.delivery_confidence:.2f}; {score.primary_pattern}"
        ),
        confidence_at_transition=Decimal(str(round(score.delivery_confidence, 3))),
    )
    db.add(transition)

    logger.info(
        "Commitment %s transitioned %s → delivered (confidence=%.2f)",
        commitment.id, from_state, score.delivery_confidence,
    )
    return transition


def apply_auto_close(
    commitment: Any,
    db: Session,
) -> LifecycleTransition:
    """Transition a delivered commitment to closed via the auto-close sweep.

    Called by run_auto_close_sweep() in detector.py after time + confidence checks.
    Writes a LifecycleTransition with trigger_reason='auto_close'.

    Args:
        commitment: Duck-typed Commitment ORM object in lifecycle_state=delivered.
        db: Synchronous SQLAlchemy Session.

    Returns:
        The written LifecycleTransition.
    """
    now = datetime.now(timezone.utc)
    from_state = commitment.lifecycle_state

    commitment.lifecycle_state = LifecycleState.closed.value
    commitment.state_changed_at = now

    transition = LifecycleTransition(
        id=str(uuid.uuid4()),
        commitment_id=commitment.id,
        user_id=commitment.user_id,
        from_state=from_state,
        to_state=LifecycleState.closed.value,
        trigger_source_item_id=None,
        trigger_reason="auto_close",
        confidence_at_transition=None,
    )
    db.add(transition)

    logger.info(
        "Commitment %s auto-closed (was delivered, threshold exceeded)",
        commitment.id,
    )
    return transition


def apply_cancellation(
    commitment: Any,
    db: Session,
    *,
    trigger_source_item_id: str | None = None,
) -> LifecycleTransition | None:
    """Transition a commitment to canceled (speech_act=cancellation signal).

    Only allowed from states where cancellation makes sense per transition rules:
    active, confirmed, in_progress.

    Args:
        commitment: Duck-typed Commitment ORM object.
        db: Synchronous SQLAlchemy Session.
        trigger_source_item_id: Source item that triggered the cancellation.

    Returns:
        LifecycleTransition if state changed, None if disallowed.
    """
    from app.services.lifecycle_transitions import is_transition_allowed

    from_state = commitment.lifecycle_state
    if not is_transition_allowed(from_state, LifecycleState.canceled.value):
        logger.debug(
            "Commitment %s: cancellation disallowed from state %s",
            commitment.id, from_state,
        )
        return None

    now = datetime.now(timezone.utc)
    commitment.lifecycle_state = LifecycleState.canceled.value
    commitment.state_changed_at = now

    transition = LifecycleTransition(
        id=str(uuid.uuid4()),
        commitment_id=commitment.id,
        user_id=commitment.user_id,
        from_state=from_state,
        to_state=LifecycleState.canceled.value,
        trigger_source_item_id=trigger_source_item_id,
        trigger_reason="cancellation_signal",
        confidence_at_transition=None,
    )
    db.add(transition)

    logger.info(
        "Commitment %s transitioned %s → canceled",
        commitment.id, from_state,
    )
    return transition


def apply_user_confirmed_completion(
    commitment: Any,
    db: Session,
) -> LifecycleTransition | None:
    """Transition a delivered commitment to completed (user confirmation).

    Only allowed from delivered state per transition rules.

    Args:
        commitment: Duck-typed Commitment ORM object.
        db: Synchronous SQLAlchemy Session.

    Returns:
        LifecycleTransition if state changed, None if disallowed.
    """
    from app.services.lifecycle_transitions import is_transition_allowed

    from_state = commitment.lifecycle_state
    if not is_transition_allowed(from_state, LifecycleState.completed.value):
        logger.debug(
            "Commitment %s: user-confirmed completion disallowed from state %s",
            commitment.id, from_state,
        )
        return None

    now = datetime.now(timezone.utc)
    commitment.lifecycle_state = LifecycleState.completed.value
    commitment.state_changed_at = now

    transition = LifecycleTransition(
        id=str(uuid.uuid4()),
        commitment_id=commitment.id,
        user_id=commitment.user_id,
        from_state=from_state,
        to_state=LifecycleState.completed.value,
        trigger_source_item_id=None,
        trigger_reason="user_confirmed_completion",
        confidence_at_transition=None,
    )
    db.add(transition)

    logger.info(
        "Commitment %s transitioned %s → completed (user confirmed)",
        commitment.id, from_state,
    )
    return transition
