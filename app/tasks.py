"""Celery application and tasks — Phase 03 + Phase 04 + Phase 05 + Phase 06 + Phase C1 + Phase C2 + Phase C3.

Detection task: orchestrates detection service (Phase 03).
Clarification task: orchestrates clarification pipeline (Phase 04).
Completion sweep: evidence sweep + auto-close sweep (Phase 05).
Surfacing sweep: recompute surfacing state for all active commitments (Phase 06).
Model detection: model-assisted re-classification of ambiguous candidates (Phase C1).
Daily digest: morning summary of surfaced commitments via email (Phase C2).
"""

import logging

from celery import Celery
from celery.schedules import crontab
from app.core.config import get_settings
from app.db.session import get_sync_session
from app.services.detection import run_detection
from app.services.clarification import run_clarification
from app.services.completion import run_auto_close_sweep, run_completion_detection
from app.services.surfacing_runner import run_surfacing_sweep
from app.services.digest import DigestAggregator, DigestFormatter, DigestDelivery

logger = logging.getLogger(__name__)
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
        "detection-sweep": {
            "task": "app.tasks.run_detection_sweep",
            "schedule": 300.0,  # 5 minutes — catch items missed at ingest
        },
        "model-detection-sweep": {
            "task": "app.tasks.run_model_detection_batch",
            "schedule": 600.0,  # 10 minutes
        },
        "daily-digest": {
            "task": "app.tasks.send_daily_digest",
            "schedule": crontab(hour=8, minute=0),
        },
        # Phase C3 — Google Calendar sync every 15 minutes
        "google-calendar-sync": {
            "task": "app.tasks.sync_google_calendar",
            "schedule": crontab(minute="*/15"),
        },
        # Phase C3 — Pre-event nudge every hour on the hour
        "pre-event-nudge": {
            "task": "app.tasks.run_pre_event_nudge",
            "schedule": crontab(minute=0),
        },
        # Phase C3 — Post-event resolution every hour at :30
        "post-event-resolution": {
            "task": "app.tasks.run_post_event_resolution",
            "schedule": crontab(minute=30),
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
    logger.info(
        "Pipeline: detection started for source_item %s",
        source_item_id,
    )
    try:
        with get_sync_session() as session:
            result = run_detection(source_item_id, session)
        logger.info(
            "Pipeline: detection complete for source_item %s — %d candidate(s) created",
            source_item_id, len(result),
        )
        return {
            "source_item_id": source_item_id,
            "status": "complete",
            "candidates_created": len(result),
        }
    except Exception as exc:
        logger.warning(
            "Pipeline: detection FAILED for source_item %s — %s (retry %d/%d)",
            source_item_id, exc, self.request.retries, self.max_retries,
        )
        raise self.retry(exc=exc)


@celery_app.task(name="app.tasks.run_detection_sweep")
def run_detection_sweep(limit: int = 100) -> dict:
    """Sweep source_items that have no commitment_candidates yet.

    Catches items that were ingested while Celery was down or where
    the inline _enqueue_detection() failed silently.

    Scheduled every 5 minutes via Celery Beat.

    Args:
        limit: Maximum number of items to process per sweep.

    Returns:
        Dict with 'processed' and 'candidates_created' counts.
    """
    from sqlalchemy import select, and_, exists
    from app.models.orm import SourceItem, CommitmentCandidate

    logger.info("Pipeline: detection sweep starting")

    # Find source_items with no associated candidates
    has_candidate = (
        select(CommitmentCandidate.id)
        .where(CommitmentCandidate.originating_item_id == SourceItem.id)
        .exists()
    )

    with get_sync_session() as session:
        unprocessed_ids = session.execute(
            select(SourceItem.id)
            .where(
                and_(
                    ~has_candidate,
                    SourceItem.is_quoted_content.is_(False),
                )
            )
            .order_by(SourceItem.ingested_at.asc())
            .limit(limit)
        ).scalars().all()

    processed = 0
    total_candidates = 0

    for item_id in unprocessed_ids:
        try:
            with get_sync_session() as session:
                result = run_detection(str(item_id), session)
            total_candidates += len(result)
            processed += 1
            logger.info(
                "Pipeline: sweep detected %d candidate(s) for source_item %s",
                len(result), item_id,
            )
        except Exception:
            logger.exception(
                "Pipeline: sweep detection FAILED for source_item %s",
                item_id,
            )

    logger.info(
        "Pipeline: detection sweep complete — %d item(s) processed, %d candidate(s) created",
        processed, total_candidates,
    )
    return {
        "processed": processed,
        "candidates_created": total_candidates,
        "unprocessed_found": len(unprocessed_ids),
    }


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
    """Sweep candidates eligible for promotion and enqueue clarification.

    Eligible candidates (all must be was_promoted=False, was_discarded=False):
      A) observe_until <= now  (observation window expired)
      B) confidence_score >= 0.75  (high-confidence direct promotion)

    Enqueues run_clarification_task for each. Returns count of enqueued tasks.
    """
    from decimal import Decimal as D
    from datetime import datetime, timezone
    from sqlalchemy import select, and_, or_
    from app.models.orm import CommitmentCandidate

    enqueued = 0
    with get_sync_session() as session:
        now = datetime.now(timezone.utc)
        stmt = select(CommitmentCandidate.id).where(
            and_(
                CommitmentCandidate.was_promoted.is_(False),
                CommitmentCandidate.was_discarded.is_(False),
                or_(
                    CommitmentCandidate.observe_until <= now,
                    CommitmentCandidate.confidence_score >= D("0.75"),
                ),
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


@celery_app.task(name="app.tasks.send_daily_digest")
def send_daily_digest() -> dict:
    """Build and send the daily digest — Phase C2.

    Guard clauses (checked in order):
    1. settings.digest_enabled is False → skip
    2. settings.digest_to_email is empty → skip
    3. User not found in public users table → skip
    4. UserSettings.digest_enabled is False → skip
    5. last_digest_sent_at is today (UTC) → skip (idempotency)
    6. Digest is empty → skip

    On success: writes DigestLog row, updates last_digest_sent_at.
    On failure: writes DigestLog row with status=failed.

    Returns:
        Dict with status (sent|skipped|failed), reason (if skipped), commitment_count.
    """
    from datetime import datetime, timezone
    from sqlalchemy import select
    from app.models.orm import User, UserSettings, DigestLog

    # Guard 1: global feature flag
    if not settings.digest_enabled:
        return {"status": "skipped", "reason": "digest disabled in settings"}

    # Guard 2: no recipient configured
    if not settings.digest_to_email:
        return {"status": "skipped", "reason": "digest_to_email not configured"}

    with get_sync_session() as db:
        # Guard 3: look up user by email in the public users table
        user = db.execute(
            select(User).where(User.email == settings.digest_to_email)
        ).scalar_one_or_none()

        if user is None:
            return {"status": "skipped", "reason": "user not found for digest_to_email"}

        # Load or default UserSettings
        user_settings = db.execute(
            select(UserSettings).where(UserSettings.user_id == user.id)
        ).scalar_one_or_none()

        # Guard 4: per-user digest toggle
        if user_settings is not None and not user_settings.digest_enabled:
            return {"status": "skipped", "reason": "digest disabled in user settings"}

        # Guard 5: idempotency — already sent today
        now_utc = datetime.now(timezone.utc)
        if user_settings is not None and user_settings.last_digest_sent_at is not None:
            if user_settings.last_digest_sent_at.date() == now_utc.date():
                return {"status": "skipped", "reason": "digest already sent today"}

        # Aggregate
        agg = DigestAggregator()
        digest = agg.aggregate_sync(db, user_id=user.id)

        # Guard 6: empty digest — don't email an empty message
        if digest.is_empty:
            return {"status": "skipped", "reason": "empty digest — nothing to send"}

        # Format
        fmt = DigestFormatter()
        formatted = fmt.format(digest)

        # Build digest_content snapshot for audit
        def _snap(commitment) -> dict:
            return {
                "id": commitment.id,
                "title": commitment.title,
                "deadline": str(commitment.resolved_deadline) if commitment.resolved_deadline else None,
            }

        digest_content = {
            "main": [_snap(c) for c in digest.main],
            "shortlist": [_snap(c) for c in digest.shortlist],
            "clarifications": [_snap(c) for c in digest.clarifications],
            "subject": formatted.subject,
        }
        commitment_count = len(digest.main) + len(digest.shortlist) + len(digest.clarifications)

        # Deliver
        delivery = DigestDelivery(settings=settings)
        result = delivery.send(formatted.subject, formatted.plain_text, formatted.html)

        # Write audit log
        log_status = "sent" if result.success else "failed"
        log_row = DigestLog(
            sent_at=now_utc,
            commitment_count=commitment_count,
            delivery_method=result.method,
            status=log_status,
            error_message=result.error,
            digest_content=digest_content,
        )
        db.add(log_row)

        # Update last_digest_sent_at
        if result.success:
            if user_settings is None:
                user_settings = UserSettings(user_id=user.id)
                db.add(user_settings)
            user_settings.last_digest_sent_at = now_utc

    if not result.success:
        return {
            "status": "failed",
            "reason": result.error,
            "commitment_count": commitment_count,
        }

    return {
        "status": "sent",
        "commitment_count": commitment_count,
        "delivery_method": result.method,
    }


@celery_app.task(name="app.tasks.sync_google_calendar")
def sync_google_calendar() -> dict:
    """Sync Google Calendar events for the configured user — Phase C3.

    Guard clauses (checked in order):
    1. settings.google_calendar_enabled is False → skip
    2. settings.google_oauth_client_id is empty → skip
    3. User not found or has no refresh_token → skip

    Scheduled every 15 minutes via Celery Beat.

    Returns:
        Dict with status and sync counts.
    """
    from sqlalchemy import select
    from app.models.orm import User
    from app.connectors.google_calendar import GoogleCalendarConnector

    if not settings.google_calendar_enabled:
        return {"status": "skipped", "reason": "google_calendar_enabled=false"}

    if not settings.google_oauth_client_id:
        return {"status": "skipped", "reason": "oauth not configured"}

    user_email = settings.google_calendar_user_email or settings.digest_to_email
    if not user_email:
        return {"status": "skipped", "reason": "no user email configured"}

    with get_sync_session() as db:
        user = db.execute(
            select(User).where(User.email == user_email)
        ).scalar_one_or_none()

        if user is None:
            return {"status": "skipped", "reason": "user not found"}

        connector = GoogleCalendarConnector(settings=settings, db=db)
        return connector.sync(user.id)


@celery_app.task(name="app.tasks.run_pre_event_nudge")
def run_pre_event_nudge() -> dict:
    """Force upcoming-delivery commitments to main surface — Phase C3.

    Finds commitments with a delivery_at event in the next 25 hours,
    promotes them to 'main' if not already there, and logs SurfacingAudit rows.

    Scheduled every hour on the hour via Celery Beat.

    Returns:
        Dict with 'nudged' count.
    """
    from datetime import datetime, timezone
    from app.services.nudge import NudgeService

    with get_sync_session() as db:
        now_dt = datetime.now(timezone.utc)
        pairs = NudgeService.load_pairs(db, now_dt)
        service = NudgeService()
        return service.run(db, commitment_event_pairs=pairs)


@celery_app.task(name="app.tasks.run_post_event_resolution")
def run_post_event_resolution() -> dict:
    """Resolve commitments after their delivery events end — Phase C3.

    Scans events that ended 0-48h ago with unresolved linked commitments.
    Classifies delivery signal from recent SourceItems or escalates to main.

    Scheduled every hour at :30 via Celery Beat.

    Returns:
        Dict with 'processed' and 'escalated' counts.
    """
    from datetime import datetime, timezone
    from app.services.post_event_resolver import PostEventResolver

    with get_sync_session() as db:
        now_dt = datetime.now(timezone.utc)
        pairs, source_item_map = PostEventResolver.load_pairs(db, now_dt)
        resolver = PostEventResolver()
        return resolver.run(db, commitment_event_pairs=pairs, source_item_map=source_item_map, now=now_dt)
