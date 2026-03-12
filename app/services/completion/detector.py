"""Completion detection orchestrator — Phase 05.

Ties together the matcher, scorer, and updater.

Flow (per source_item):
    1. Load source_item
    2. Load active commitments for source_item.user_id
    3. find_matching_commitments(source_item, active_commitments)
    4. For each match: score_evidence(commitment, evidence)
    5. For each score: apply_completion_result(commitment, evidence, score, db)
    6. Flush, return summary

Auto-close sweep (Sweep B):
    Queries delivered commitments, checks time + confidence thresholds,
    calls apply_auto_close() for eligible ones.

Public API:
    run_completion_detection(source_item_id: str, db: Session) -> dict
    run_auto_close_sweep(db: Session) -> dict
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import LifecycleState
from app.models.orm import Commitment, CommitmentSignal, SourceItem
from app.services.completion.matcher import find_matching_commitments
from app.services.completion.scorer import score_evidence
from app.services.completion.updater import apply_auto_close, apply_completion_result

logger = logging.getLogger(__name__)

# Minimum closure_readiness_confidence for auto-close
_AUTO_CLOSE_CONFIDENCE_THRESHOLD = 0.75


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _load_origin_thread_ids(commitment_ids: list[str], db: Session) -> dict[str, list[str]]:
    """Load thread_ids from origin CommitmentSignal rows for each commitment.

    Attaches them so the matcher can check thread continuity without a DB call.

    Returns:
        Mapping commitment_id -> list of thread_ids from origin signals.
    """
    if not commitment_ids:
        return {}

    from app.models.enums import SignalRole

    rows = db.execute(
        select(CommitmentSignal.commitment_id, SourceItem.thread_id)
        .join(SourceItem, CommitmentSignal.source_item_id == SourceItem.id)
        .where(
            CommitmentSignal.commitment_id.in_(commitment_ids),
            CommitmentSignal.signal_role == SignalRole.origin.value,
            SourceItem.thread_id.isnot(None),
        )
    ).all()

    result: dict[str, list[str]] = {cid: [] for cid in commitment_ids}
    for commitment_id, thread_id in rows:
        if thread_id:
            result[commitment_id].append(thread_id)
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_completion_detection(source_item_id: str, db: Session) -> dict:
    """Detect completion evidence in a single source_item and update commitments.

    Args:
        source_item_id: UUID of the SourceItem to process.
        db: Synchronous SQLAlchemy Session.

    Returns:
        Summary dict with 'transitions_made' and 'signals_written' counts.
    """
    source_item = db.get(SourceItem, source_item_id)
    if source_item is None:
        logger.warning("SourceItem %s not found — skipping", source_item_id)
        return {"transitions_made": 0, "signals_written": 0, "status": "not_found"}

    # Load active commitments for this user that are past their observation window
    active_commitments = db.execute(
        select(Commitment).where(
            Commitment.user_id == source_item.user_id,
            Commitment.lifecycle_state == LifecycleState.active.value,
        )
    ).scalars().all()

    if not active_commitments:
        return {"transitions_made": 0, "signals_written": 0, "status": "no_active_commitments"}

    # Pre-load origin thread_ids and attach to each commitment for thread matching
    commitment_ids = [c.id for c in active_commitments]
    thread_id_map = _load_origin_thread_ids(commitment_ids, db)
    for commitment in active_commitments:
        commitment._origin_thread_ids = thread_id_map.get(commitment.id, [])

    # Match → score → update
    matches = find_matching_commitments(source_item, active_commitments)

    transitions_made = 0
    signals_written = 0

    for commitment, evidence in matches:
        score = score_evidence(commitment, evidence)
        transition = apply_completion_result(commitment, evidence, score, db)
        if transition is not None:
            transitions_made += 1
        if score.delivery_confidence >= 0.40:
            signals_written += 1

    db.flush()

    logger.info(
        "run_completion_detection: source_item=%s matches=%d transitions=%d signals=%d",
        source_item_id, len(matches), transitions_made, signals_written,
    )

    return {
        "transitions_made": transitions_made,
        "signals_written": signals_written,
        "matches_found": len(matches),
        "status": "complete",
    }


def run_auto_close_sweep(db: Session) -> dict:
    """Close delivered commitments that have exceeded their auto-close threshold.

    Queries commitments where:
    - lifecycle_state = 'delivered'
    - delivered_at is not None

    Then applies Python-side checks:
    - confidence_closure >= 0.75
    - delivered_at <= now() - auto_close_after_hours

    Args:
        db: Synchronous SQLAlchemy Session.

    Returns:
        Summary dict with 'auto_closed' count.
    """
    now = datetime.now(timezone.utc)

    delivered_commitments = db.execute(
        select(Commitment).where(
            Commitment.lifecycle_state == LifecycleState.delivered.value,
            Commitment.delivered_at.isnot(None),
        )
    ).scalars().all()

    auto_closed = 0

    for commitment in delivered_commitments:
        closure_confidence = float(commitment.confidence_closure or 0)
        if closure_confidence < _AUTO_CLOSE_CONFIDENCE_THRESHOLD:
            continue

        threshold = commitment.delivered_at + timedelta(hours=commitment.auto_close_after_hours)
        if now < threshold:
            continue

        apply_auto_close(commitment, db)
        auto_closed += 1

    if auto_closed:
        db.flush()

    logger.info("run_auto_close_sweep: auto_closed=%d", auto_closed)
    return {"auto_closed": auto_closed}
