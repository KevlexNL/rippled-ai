"""Clarification service — Phase 04.

Public API:
    run_clarification(candidate_id: str, db: Session) -> dict
"""
from app.services.clarification.clarifier import run_clarification

__all__ = ["run_clarification"]
