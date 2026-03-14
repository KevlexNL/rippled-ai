"""Nudge service — Phase C3.

Forces commitments with an upcoming delivery_at event (within 25h) to the
'main' surface and recomputes their priority score.

Public API:
    NudgeService().run(db) -> dict
    NudgeService().process_commitment(commitment, event, db) -> dict
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal

logger = logging.getLogger(__name__)

# Delivery states that indicate work is already done or in-flight — skip nudge
_SKIP_STATES = frozenset({"delivered", "closed_no_delivery", "draft_sent"})

# How far ahead to look for upcoming events
_NUDGE_WINDOW_HOURS = 25


class NudgeService:
    """Surfaces commitments whose delivery event is within the nudge window."""

    def run(self, db, user_id: str | None = None, commitment_event_pairs: list | None = None) -> dict:
        """Run nudge sweep over provided commitment+event pairs.

        Args:
            db: Synchronous SQLAlchemy session.
            user_id: Optional user_id filter (not used in batch mode).
            commitment_event_pairs: List of (commitment, event) tuples to process.

        Returns:
            Dict with 'nudged' count.
        """
        if commitment_event_pairs is None:
            commitment_event_pairs = []

        nudged = 0
        for commitment, event in commitment_event_pairs:
            result = self.process_commitment(commitment, event, db)
            if result.get("promoted"):
                nudged += 1

        if nudged:
            db.flush()

        logger.info("NudgeService.run: nudged=%d", nudged)
        return {"nudged": nudged}

    def process_commitment(self, commitment, event, db) -> dict:
        """Process a single commitment-event pair for nudging.

        Args:
            commitment: Commitment object.
            event: The upcoming delivery Event.
            db: Synchronous SQLAlchemy session.

        Returns:
            Dict with 'promoted' (bool), 'skipped' (bool).
        """
        delivery_state = getattr(commitment, "delivery_state", None)
        if delivery_state in _SKIP_STATES:
            return {"promoted": False, "skipped": True}

        old_surface = commitment.surfaced_as

        if old_surface == "main":
            # Already on main — just recompute score (no audit needed)
            self._recompute_score(commitment, event)
            return {"promoted": False, "skipped": False}

        # Force to main and log audit
        commitment.surfaced_as = "main"
        self._recompute_score(commitment, event)

        audit = _make_audit(
            commitment_id=commitment.id,
            old_surfaced_as=old_surface,
            new_surfaced_as="main",
            priority_score=commitment.priority_score,
            reason="nudge: delivery event within 25h",
        )
        db.add(audit)

        return {"promoted": True, "skipped": False}

    def _recompute_score(self, commitment, event) -> None:
        """Recompute priority_score using proximity to the delivery event."""
        from app.services.commitment_classifier import classify
        from app.services.priority_scorer import score

        now = datetime.now(timezone.utc)
        starts_at = event.starts_at
        if starts_at.tzinfo is None:
            starts_at = starts_at.replace(tzinfo=timezone.utc)
        proximity_hours = (starts_at - now).total_seconds() / 3600

        classifier_result = classify(commitment)
        new_score = score(classifier_result, commitment, proximity_hours=proximity_hours)
        commitment.priority_score = Decimal(str(new_score))


def _make_audit(commitment_id: str, old_surfaced_as, new_surfaced_as, priority_score, reason: str):
    from app.models.orm import SurfacingAudit
    return SurfacingAudit(
        commitment_id=commitment_id,
        old_surfaced_as=old_surfaced_as,
        new_surfaced_as=new_surfaced_as,
        priority_score=priority_score,
        reason=reason[:255] if reason else None,
    )
