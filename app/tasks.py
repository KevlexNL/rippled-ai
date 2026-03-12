"""Celery application and tasks — Phase 03 + Phase 04.

Detection task: orchestrates detection service (Phase 03).
Clarification task: orchestrates clarification pipeline (Phase 04).
"""

from celery import Celery
from app.core.config import get_settings
from app.db.session import get_sync_session
from app.services.detection import run_detection
from app.services.clarification import run_clarification

settings = get_settings()

celery_app = Celery(
    "rippled",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "clarification-sweep": {
            "task": "app.tasks.run_clarification_batch",
            "schedule": 300.0,  # 5 minutes
        },
    },
)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30, name="app.tasks.detect_commitments")
def detect_commitments(self, source_item_id: str) -> dict:
    """Detect commitments from a source item.

    Spawns detection service to analyze the source item and produce
    commitment candidates with structured detection signals.

    Args:
        source_item_id: UUID of the source_item to process

    Returns:
        Status dict with source_item_id and detection result summary
    """
    try:
        with get_sync_session() as session:
            result = run_detection(source_item_id, session)
        return {
            "source_item_id": source_item_id,
            "status": "complete",
            "candidates_created": result.get("candidates_created", 0),
            "summary": result.get("summary"),
        }
    except Exception as exc:
        # Retry up to max_retries with exponential backoff
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30, name="app.tasks.run_clarification")
def run_clarification_task(self, candidate_id: str) -> dict:
    """Run the clarification pipeline for a single candidate.

    Analyzes the candidate, promotes if warranted, creates Clarification row.

    Args:
        candidate_id: UUID of the CommitmentCandidate to process.

    Returns:
        Status dict with status and commitment_id (if clarified).
    """
    try:
        with get_sync_session() as session:
            result = run_clarification(candidate_id, session)
        return result
    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(name="app.tasks.run_clarification_batch")
def run_clarification_batch() -> dict:
    """Sweep candidates whose observation window has expired and enqueue clarification.

    Queries commitment_candidates where:
      - observe_until <= now()
      - was_promoted = False
      - was_discarded = False

    Enqueues run_clarification_task for each. Returns count of enqueued tasks.
    """
    from datetime import datetime, timezone
    from sqlalchemy import select, and_
    from app.models.orm import CommitmentCandidate

    enqueued = 0
    with get_sync_session() as session:
        now = datetime.now(timezone.utc)
        stmt = select(CommitmentCandidate.id).where(
            and_(
                CommitmentCandidate.observe_until <= now,
                CommitmentCandidate.was_promoted.is_(False),
                CommitmentCandidate.was_discarded.is_(False),
            )
        )
        candidate_ids = session.execute(stmt).scalars().all()

    for cid in candidate_ids:
        run_clarification_task.delay(str(cid))
        enqueued += 1

    return {"enqueued": enqueued}
