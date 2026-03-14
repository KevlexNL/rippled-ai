"""Post-event resolver — Phase C3.

Scans SourceItems after a delivery event ends and classifies the delivery signal.
Updates commitment.delivery_state or escalates to main surface if no signal.

Public API:
    PostEventResolver().run(db, commitment_event_pairs, source_item_map) -> dict
    PostEventResolver().process_pair(commitment, event, source_items, db, now=None) -> dict
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
logger = logging.getLogger(__name__)

# Terminal delivery states — skip if already set
_TERMINAL_STATES = frozenset({"delivered", "closed_no_delivery", "draft_sent", "acknowledged"})

# How long after the event ends before we escalate (no signal within this window → hold)
_ESCALATION_GRACE_HOURS = 2

# Keywords for signal detection
# Draft and ack are checked first — they take priority over generic delivery signals
_DRAFT_KEYWORDS = frozenset({
    "draft", "rough draft", "initial version", "first pass", "work in progress",
    "wip", "for review", "for your review", "preliminary",
})
_ACK_KEYWORDS = frozenset({
    "got it", "received", "thanks for sending", "thank you for", "acknowledged",
    "saw it", "saw your", "looked at",
})
# Full delivery: unambiguous completed-delivery language (no "sending" — ambiguous)
_DELIVERY_KEYWORDS = frozenset({
    "attached", "find attached", "please find", "here is", "here's",
    "as requested", "as promised", "completed", "done", "finished",
    "submitted", "uploaded", "delivered",
})


class PostEventResolver:
    """Processes commitment-event pairs after an event ends."""

    def run(
        self,
        db,
        commitment_event_pairs: list | None = None,
        source_item_map: dict | None = None,
        now: datetime | None = None,
    ) -> dict:
        """Run post-event resolution for a list of pairs.

        Args:
            db: Synchronous SQLAlchemy session.
            commitment_event_pairs: List of (commitment, event) tuples.
            source_item_map: Dict mapping commitment_id → list[SourceItem].
            now: Override for current time (for testing).

        Returns:
            Dict with 'processed' and 'escalated' counts.
        """
        if commitment_event_pairs is None:
            commitment_event_pairs = []
        if source_item_map is None:
            source_item_map = {}

        processed = 0
        escalated = 0

        for commitment, event in commitment_event_pairs:
            source_items = source_item_map.get(commitment.id, [])
            result = self.process_pair(commitment, event, source_items, db, now=now)
            if result.get("skipped"):
                continue
            processed += 1
            if result.get("escalated"):
                escalated += 1

        if processed:
            db.flush()

        logger.info("PostEventResolver.run: processed=%d escalated=%d", processed, escalated)
        return {"processed": processed, "escalated": escalated}

    def process_pair(
        self,
        commitment,
        event,
        source_items: list,
        db,
        now: datetime | None = None,
    ) -> dict:
        """Resolve a single commitment-event pair after the event ends.

        Args:
            commitment: Commitment object (modified in-place).
            event: The delivery Event that has ended.
            source_items: SourceItems since the event ended (from same counterparty).
            db: Synchronous SQLAlchemy session.
            now: Override for current time.

        Returns:
            Dict with result keys.
        """
        if commitment.post_event_reviewed:
            return {"skipped": True, "reason": "already_reviewed"}

        if now is None:
            now = datetime.now(timezone.utc)

        ends_at = event.ends_at
        if ends_at is None:
            ends_at = event.starts_at
        if ends_at is not None and ends_at.tzinfo is None:
            ends_at = ends_at.replace(tzinfo=timezone.utc)

        time_since_event = (now - ends_at).total_seconds() / 3600 if ends_at else 0

        # Detect delivery signal from source items
        signal_type = self._detect_delivery_signal(source_items, commitment)

        if signal_type == "full":
            commitment.delivery_state = "delivered"
            commitment.post_event_reviewed = True
            return {"signal": "full", "escalated": False}

        if signal_type == "draft":
            commitment.delivery_state = "draft_sent"
            commitment.post_event_reviewed = True
            return {"signal": "draft", "escalated": False}

        if signal_type == "ack":
            commitment.delivery_state = "acknowledged"
            commitment.post_event_reviewed = True
            return {"signal": "ack", "escalated": False}

        # No signal
        if time_since_event < _ESCALATION_GRACE_HOURS:
            # Too soon to escalate — hold
            return {"signal": None, "escalated": False, "held": True}

        # Escalate: force main surface + audit row
        old_surface = commitment.surfaced_as
        commitment.surfaced_as = "main"
        commitment.post_event_reviewed = True

        audit = _make_audit(
            commitment_id=commitment.id,
            old_surfaced_as=old_surface,
            new_surfaced_as="main",
            priority_score=getattr(commitment, "priority_score", None),
            reason="post-event: no delivery signal detected",
        )
        db.add(audit)

        return {"signal": None, "escalated": True}

    def _detect_delivery_signal(self, source_items: list, commitment) -> str | None:
        """Classify delivery evidence from source items.

        Priority: draft > ack > full (to avoid misclassifying partial signals as full delivery)

        Returns: 'full' | 'draft' | 'ack' | None
        """
        for item in source_items:
            content = (getattr(item, "content", "") or "").lower()
            if any(kw in content for kw in _DRAFT_KEYWORDS):
                return "draft"

        for item in source_items:
            content = (getattr(item, "content", "") or "").lower()
            if any(kw in content for kw in _ACK_KEYWORDS):
                return "ack"

        for item in source_items:
            content = (getattr(item, "content", "") or "").lower()
            if any(kw in content for kw in _DELIVERY_KEYWORDS):
                return "full"

        return None


def _make_audit(commitment_id: str, old_surfaced_as, new_surfaced_as, priority_score, reason: str):
    from app.models.orm import SurfacingAudit
    return SurfacingAudit(
        commitment_id=commitment_id,
        old_surfaced_as=old_surfaced_as,
        new_surfaced_as=new_surfaced_as,
        priority_score=priority_score,
        reason=reason[:255] if reason else None,
    )
