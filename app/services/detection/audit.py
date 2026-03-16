"""Detection audit — log which tier handled each detection.

Tracks tier_1 / tier_2 / tier_3 / pattern usage per source item
for cost analysis and funnel optimization.

Public API:
    create_audit_entry(...) -> dict
    write_audit_entry(db, ...) -> DetectionAudit
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.orm import DetectionAudit


def create_audit_entry(
    source_item_id: str,
    user_id: str,
    tier_used: str,
    matched_phrase: str | None = None,
    matched_sender: str | None = None,
    confidence: Decimal | None = None,
    commitment_created: bool = False,
) -> dict:
    """Create an audit entry dict (for use without DB or for deferred write)."""
    return {
        "source_item_id": source_item_id,
        "user_id": user_id,
        "tier_used": tier_used,
        "matched_phrase": matched_phrase,
        "matched_sender": matched_sender,
        "confidence": confidence,
        "commitment_created": commitment_created,
    }


def write_audit_entry(
    db: Session,
    source_item_id: str,
    user_id: str,
    tier_used: str,
    matched_phrase: str | None = None,
    matched_sender: str | None = None,
    confidence: Decimal | None = None,
    commitment_created: bool = False,
) -> DetectionAudit:
    """Write an audit row to the database."""
    entry = DetectionAudit(
        source_item_id=source_item_id,
        user_id=user_id,
        tier_used=tier_used,
        matched_phrase=matched_phrase,
        matched_sender=matched_sender,
        confidence=confidence,
        commitment_created=commitment_created,
    )
    db.add(entry)
    db.flush()
    return entry
