"""Commitment detection service.

Public API:
    run_detection(source_item_id: str, db: Session) -> list[CommitmentCandidate]
    run_tier1(profile, item) -> dict | None
    should_skip_detection(profile, item) -> bool
    update_profile_after_llm(profile, source_item, commitment_data) -> None
    downweight_profile_on_dismissal(profile, source_item, trigger_phrase) -> None
    write_audit_entry(db, ...) -> DetectionAudit
    create_audit_entry(...) -> dict

Import this from Celery tasks:
    from app.services.detection import run_detection
"""
from app.services.detection.detector import run_detection
from app.services.detection.seed_detector import run_seed_pass, build_user_profile
from app.services.detection.profile_matcher import run_tier1, should_skip_detection
from app.services.detection.learning_loop import (
    update_profile_after_llm,
    downweight_profile_on_dismissal,
)
from app.services.detection.audit import write_audit_entry, create_audit_entry

__all__ = [
    "run_detection",
    "run_seed_pass",
    "build_user_profile",
    "run_tier1",
    "should_skip_detection",
    "update_profile_after_llm",
    "downweight_profile_on_dismissal",
    "write_audit_entry",
    "create_audit_entry",
]
