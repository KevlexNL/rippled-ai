"""Commitment detection service.

Public API:
    run_detection(source_item_id: str, db: Session) -> list[CommitmentCandidate]

Import this from Celery tasks:
    from app.services.detection import run_detection
"""
from app.services.detection.detector import run_detection

__all__ = ["run_detection"]
