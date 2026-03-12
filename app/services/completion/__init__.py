"""Completion detection service — Phase 05.

Public API:
    run_completion_detection(source_item_id: str, db: Session) -> dict
    run_auto_close_sweep(db: Session) -> dict
"""
from app.services.completion.detector import run_auto_close_sweep, run_completion_detection

__all__ = ["run_completion_detection", "run_auto_close_sweep"]
