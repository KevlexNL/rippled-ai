"""Commitment detection service.

Public API:
    run_detection(source_item_id: str, db: Session) -> list[CommitmentCandidate]

Import this from Celery tasks:
    from app.services.detection import run_detection
"""
from app.services.detection.detector import run_detection
from app.services.detection.seed_detector import run_seed_pass, build_user_profile

__all__ = ["run_detection", "run_seed_pass", "build_user_profile"]
