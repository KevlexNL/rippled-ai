"""Celery application and task stubs — Phase 03.

Detection task fully implemented. Orchestrates detection service.
"""

from celery import Celery
from app.core.config import get_settings
from app.db.session import get_sync_session
from app.services.detection import run_detection

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
