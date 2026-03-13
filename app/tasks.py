"""Celery application and tasks — Phase 03 + Phase 04 + Phase 05 + Phase 06 + Phase C1.

Detection task: orchestrates detection service (Phase 03).
Clarification task: orchestrates clarification pipeline (Phase 04).
Completion sweep: evidence sweep + auto-close sweep (Phase 05).
Surfacing sweep: recompute surfacing state for all active commitments (Phase 06).
Model detection: model-assisted re-classification of ambiguous candidates (Phase C1).
"""

from celery import Celery
from app.core.config import get_settings
from app.db.session import get_sync_session
from app.services.detection import run_detection
from app.services.clarification import run_clarification
from app.services.completion import run_auto_close_sweep, run_completion_detection
from app.services.surfacing_runner import run_surfacing_sweep

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
        "completion-sweep": {
            "task": "app.tasks.run_completion_sweep",
            "schedule": 600.0,  # 10 minutes
        },
        "surfacing-sweep": {
            "task": "app.tasks.recompute_surfacing",
            "schedule": 1800.0,  # 30 minutes
        },
        "email-imap-poll": {
            "task": "app.tasks.poll_email_imap",
            "schedule": 300.0,  # 5 minutes
        },
        "model-detection-sweep": {
            "task": "app.tasks.run_model_detection_batch",
            "schedule": 600.0,  # 10 minutes
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


@celery_app.task(name="app.tasks.run_completion_sweep")
def run_completion_sweep() -> dict:
    """Completion detection sweep — Phase 05.

    Sweep A: Processes source_items ingested in the last 30 minutes (with overlap
    for beat jitter). Idempotency is guaranteed by the CommitmentSignal UniqueConstraint.

    Sweep B: Auto-closes delivered commitments that have exceeded their
    auto_close_after_hours threshold and meet the closure confidence requirement.

    Returns:
        Dict with 'sweep_a' (evidence sweep results) and 'sweep_b' (auto-close results).
    """
    from datetime import datetime, timezone, timedelta
    from sqlalchemy import select, and_
    from app.models.orm import SourceItem

    sweep_a_total: dict = {"transitions_made": 0, "signals_written": 0, "items_processed": 0}

    with get_sync_session() as session:
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(minutes=30)

        recent_item_ids = session.execute(
            select(SourceItem.id).where(
                and_(
                    SourceItem.ingested_at >= window_start,
                    SourceItem.is_quoted_content.is_(False),
                )
            ).order_by(SourceItem.ingested_at.desc())
        ).scalars().all()

    for item_id in recent_item_ids:
        with get_sync_session() as session:
            result = run_completion_detection(str(item_id), session)
            sweep_a_total["transitions_made"] += result.get("transitions_made", 0)
            sweep_a_total["signals_written"] += result.get("signals_written", 0)
            sweep_a_total["items_processed"] += 1

    sweep_b_result: dict = {}
    with get_sync_session() as session:
        sweep_b_result = run_auto_close_sweep(session)

    return {
        "sweep_a": sweep_a_total,
        "sweep_b": sweep_b_result,
    }


@celery_app.task(name="app.tasks.recompute_surfacing")
def recompute_surfacing() -> dict:
    """Recompute surfacing state for all active commitments — Phase 06.

    Runs the surfacing sweep which:
    - Classifies each active/proposed/needs_clarification commitment
    - Computes priority_score + dimension scores
    - Routes each to main / shortlist / clarifications / None
    - Updates commitment fields and writes SurfacingAudit rows for changes

    Scheduled every 30 minutes via Celery Beat.

    Returns:
        Summary dict with 'evaluated', 'changed', 'surfaced', 'held' counts.
    """
    with get_sync_session() as session:
        return run_surfacing_sweep(session)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30, name="app.tasks.process_slack_event")
def process_slack_event(self, payload: dict) -> dict:
    """Process a Slack event payload from the Events API.

    Looks up the Slack Source by team_id to get per-source user_id and
    slack_user_id from credentials. Falls back to global env-var config
    when no matching Source exists.
    """
    from app.connectors.slack.normalizer import normalise_slack_event
    from app.connectors.shared.credentials_utils import decrypt_credentials
    from app.connectors.shared.ingestor import get_or_create_source_sync, ingest_item
    from app.models.orm import Source
    from sqlalchemy import select

    try:
        event = payload.get("event", {})
        team_id = payload.get("team_id") or settings.slack_team_id
        user_id = None

        with get_sync_session() as db:
            source = None
            if team_id:
                source = db.execute(
                    select(Source).where(
                        Source.source_type == "slack",
                        Source.provider_account_id == team_id,
                        Source.is_active.is_(True),
                    )
                ).scalar_one_or_none()

            if source:
                user_id = source.user_id
                creds = decrypt_credentials(source.credentials or {})
                slack_user_id = creds.get("slack_user_id") or settings.slack_user_id
                source_id = source.id
            else:
                # Fallback: use global config and get/create a default source
                user_id = settings.slack_user_id
                slack_user_id = settings.slack_user_id
                if not user_id:
                    return {"status": "skipped", "reason": "no user configured for this team"}
                source = get_or_create_source_sync(
                    user_id=user_id,
                    source_type="slack",
                    provider_account_id=team_id or "slack",
                    db=db,
                )
                source_id = source.id

        if not user_id:
            return {"status": "skipped", "reason": "no user configured for this team"}

        item = normalise_slack_event(event, source_id, slack_user_id=slack_user_id or "")
        if item is None:
            return {"status": "filtered"}

        with get_sync_session() as db:
            _, created = ingest_item(item, user_id, db)

        return {"status": "ingested" if created else "duplicate"}
    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(name="app.tasks.poll_email_imap")
def poll_email_imap() -> dict:
    """Poll all active email Sources for new messages and ingest them.

    Scheduled every 5 minutes via Celery Beat.
    Per-source IMAP credentials are read from Source.credentials with
    fallback to global env vars for backward compatibility.
    """
    from app.connectors.email.imap_poller import poll_all_email_sources
    return poll_all_email_sources()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60, name="app.tasks.run_model_detection_pass")
def run_model_detection_pass(self, candidate_id: str) -> dict:
    """Run model-assisted detection for a single candidate — Phase C1.

    Calls the hybrid detection pipeline for the given candidate.
    Updates model_confidence, model_classification, model_explanation,
    model_called_at, detection_method, and was_discarded on the candidate row.

    Args:
        candidate_id: UUID of the CommitmentCandidate to classify.

    Returns:
        Status dict with candidate_id, detection_method, model_called.
    """
    from app.models.orm import CommitmentCandidate
    from app.services.model_detection import ModelDetectionService
    from app.services.hybrid_detection import HybridDetectionService

    try:
        if not settings.model_detection_enabled:
            return {"status": "skipped", "reason": "model_detection_enabled=false"}

        model_service = None
        if settings.openai_api_key:
            model_service = ModelDetectionService(
                api_key=settings.openai_api_key,
                model=settings.openai_model,
            )
        hybrid = HybridDetectionService(model_service=model_service)

        with get_sync_session() as db:
            candidate = db.get(CommitmentCandidate, candidate_id)
            if candidate is None:
                return {"status": "not_found", "candidate_id": candidate_id}

            # Skip already-processed or already-decided candidates
            if candidate.model_called_at is not None:
                return {"status": "already_processed", "candidate_id": candidate_id}
            if candidate.was_promoted or candidate.was_discarded:
                return {"status": "skipped", "reason": "already_decided"}

            result = hybrid.process(candidate)

            # Apply model detection results to candidate
            candidate.model_confidence = result["model_confidence"]
            candidate.model_classification = result["model_classification"]
            candidate.model_explanation = result["model_explanation"]
            candidate.model_called_at = result["model_called_at"]
            candidate.detection_method = result["detection_method"]
            if result["was_discarded"]:
                candidate.was_discarded = True
                candidate.discard_reason = result["discard_reason"]

        return {
            "status": "complete",
            "candidate_id": candidate_id,
            "detection_method": result["detection_method"],
            "model_called": result["model_called"],
        }
    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(name="app.tasks.run_model_detection_batch")
def run_model_detection_batch(limit: int = 50) -> dict:
    """Batch model detection sweep — Phase C1.

    Queries unclassified candidates in the ambiguous confidence zone
    (0.35 <= confidence_score < 0.75) that have not yet been model-processed,
    and enqueues run_model_detection_pass for each.

    Scheduled every 10 minutes via Celery Beat.

    Args:
        limit: Maximum number of candidates to enqueue per sweep.

    Returns:
        Dict with 'enqueued' count.
    """
    from decimal import Decimal as D
    from sqlalchemy import select, and_
    from app.models.orm import CommitmentCandidate

    if not settings.model_detection_enabled:
        return {"enqueued": 0, "reason": "model_detection_enabled=false"}

    AMBIGUOUS_LOWER = D("0.35")
    AMBIGUOUS_UPPER = D("0.75")

    enqueued = 0
    with get_sync_session() as db:
        stmt = (
            select(CommitmentCandidate.id)
            .where(
                and_(
                    CommitmentCandidate.confidence_score >= AMBIGUOUS_LOWER,
                    CommitmentCandidate.confidence_score < AMBIGUOUS_UPPER,
                    CommitmentCandidate.model_called_at.is_(None),
                    CommitmentCandidate.was_promoted.is_(False),
                    CommitmentCandidate.was_discarded.is_(False),
                )
            )
            .order_by(CommitmentCandidate.created_at.asc())
            .limit(limit)
        )
        candidate_ids = db.execute(stmt).scalars().all()

    for cid in candidate_ids:
        run_model_detection_pass.delay(str(cid))
        enqueued += 1

    return {"enqueued": enqueued}
