"""Commitment detection orchestration.

Public API:
    run_detection(source_item_id: str, db: Session) -> list[CommitmentCandidate]

Steps:
1. Load SourceItem from DB
2. Normalize content (strip suppression spans, segment if meeting)
3. Run capture patterns for the source type
4. For each match: extract context window, compute metadata, create candidate
5. Insert each candidate with a savepoint (one bad insert doesn't abort others)
6. Return list of created candidates
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.models.orm import CommitmentCandidate, SourceItem, UserCommitmentProfile
from app.services.detection.audit import write_audit_entry
from app.services.detection.context import extract_context
from app.services.detection.patterns import (
    TriggerPattern,
    get_patterns_for_source,
    get_suppression_patterns_for_source,
)
from app.services.detection.profile_matcher import run_tier1, should_skip_detection
from app.services.observation_window import get_window_hours

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Observation window (delegates to observation_window.py — Phase D1)
# ---------------------------------------------------------------------------

def _compute_observe_until(
    source_type: str,
    is_external: bool,
    user_config: dict[str, float] | None = None,
) -> datetime:
    hours = get_window_hours(source_type, is_external, user_config=user_config)
    return datetime.now(timezone.utc) + timedelta(hours=hours)


# ---------------------------------------------------------------------------
# Confidence scoring
# ---------------------------------------------------------------------------

def _compute_confidence(
    pattern: TriggerPattern,
    is_external: bool,
) -> Decimal:
    score = pattern.base_confidence
    if is_external:
        score = min(1.0, score + 0.10)
    return Decimal(str(round(score, 3)))


# ---------------------------------------------------------------------------
# Priority elevation
# ---------------------------------------------------------------------------

def _compute_priority(
    pattern: TriggerPattern,
    is_external: bool,
    trigger_text: str,
) -> str:
    priority = pattern.base_priority_hint
    # Elevate to high if external context detected
    if is_external and priority == "medium":
        priority = "high"
    # Delivery signals are lower priority by default
    if pattern.trigger_class == "delivery_signal":
        priority = "low"
    return priority


# ---------------------------------------------------------------------------
# Commitment class hint
# ---------------------------------------------------------------------------

def _compute_class_hint(
    pattern: TriggerPattern,
    is_external: bool,
    trigger_text: str,
) -> str:
    """Return a rough commitment class hint based on pattern + context."""
    if pattern.trigger_class in ("delivery_signal", "filler", "hypothetical"):
        return "unknown"
    if is_external and pattern.trigger_class in (
        "explicit_self_commitment",
        "explicit_collective_commitment",
        "obligation_marker",
    ):
        return "big_promise"
    if pattern.trigger_class == "small_practical_commitment":
        return "small_commitment"
    if pattern.trigger_class in ("implicit_next_step", "implicit_unresolved_obligation"):
        return "unknown"
    return "small_commitment"


# ---------------------------------------------------------------------------
# Content normalization
# ---------------------------------------------------------------------------

def _apply_suppression(content: str, source_type: str) -> str:
    """Strip suppression spans from content before running capture patterns."""
    suppression_patterns = get_suppression_patterns_for_source(source_type)
    for sp in suppression_patterns:
        content = sp.pattern.sub(" ", content)
    return content


def _is_external(item: SourceItem) -> bool:
    if item.is_external_participant:
        return True
    recipients = item.recipients or []
    return any(
        isinstance(r, dict) and r.get("is_external")
        for r in recipients
    )


def _should_flag_reanalysis(item: SourceItem, trigger_text: str) -> bool:
    """Meeting transcripts with uncertain attribution should be flagged."""
    if item.source_type != "meeting":
        return False
    content = item.content_normalized or item.content or ""
    uncertain_pattern = re.compile(
        r"\[(?:inaudible|crosstalk|unclear|unknown speaker)\]",
        re.IGNORECASE,
    )
    # Check if uncertain marker appears within 100 chars of trigger
    idx = content.lower().find(trigger_text.lower())
    if idx == -1:
        return False
    window = content[max(0, idx - 100): idx + len(trigger_text) + 100]
    return bool(uncertain_pattern.search(window))


# ---------------------------------------------------------------------------
# Linked entity extraction (lightweight, no ML)
# ---------------------------------------------------------------------------

_DATE_PATTERN = re.compile(
    r"\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday"
    r"|tomorrow|today|next week|by (?:end of )?(?:day|week|month)"
    r"|(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?"
    r"|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
    r"\s+\d{1,2}(?:st|nd|rd|th)?(?:,?\s+\d{4})?)\b",
    re.IGNORECASE,
)

_PERSON_MENTION_PATTERN = re.compile(
    r"@\w+|(?<!\w)[A-Z][a-z]+ [A-Z][a-z]+(?!\w)",
)


def _extract_entities(text: str) -> dict[str, Any]:
    dates = _DATE_PATTERN.findall(text)
    mentions = _PERSON_MENTION_PATTERN.findall(text)
    return {
        "dates": list(dict.fromkeys(dates)),   # deduplicated, order-preserved
        "people": list(dict.fromkeys(mentions)),
    }


# ---------------------------------------------------------------------------
# Main detection function
# ---------------------------------------------------------------------------

def run_detection(
    source_item_id: str,
    db: Session,
    user_config: dict[str, float] | None = None,
) -> list[CommitmentCandidate]:
    """Detect commitment candidates from a source item.

    Creates CommitmentCandidate rows in DB using savepoints for isolation.
    Returns the list of created candidates.

    Args:
        source_item_id: ID of the SourceItem to analyse.
        db: Synchronous SQLAlchemy Session (from Celery worker context).

    Returns:
        List of CommitmentCandidate ORM objects that were written to DB.

    Raises:
        ValueError: If the SourceItem is not found.
    """
    item: SourceItem | None = db.get(SourceItem, source_item_id)
    if item is None:
        raise ValueError(f"SourceItem {source_item_id!r} not found")

    source_type: str = item.source_type
    content: str = item.content_normalized or item.content or ""

    if not content.strip():
        logger.info("SourceItem %s has no content — skipping detection", source_item_id)
        return []

    # --- Learning loop: load user profile for Tier 1 / sender suppression ---
    profile: UserCommitmentProfile | None = db.query(UserCommitmentProfile).filter(
        UserCommitmentProfile.user_id == item.user_id,
    ).first()

    # Step 0: Sender suppression — skip newsletters, no-reply, suppressed senders
    if should_skip_detection(profile, item):
        logger.info(
            "SourceItem %s skipped — sender suppressed (%s)",
            source_item_id, getattr(item, "sender_email", ""),
        )
        write_audit_entry(
            db, source_item_id=source_item_id, user_id=item.user_id,
            tier_used="suppressed",
            matched_sender=getattr(item, "sender_email", None),
            commitment_created=False,
        )
        return []

    # Step 0b: Tier 1 — profile-based pattern matching (free, ~0ms)
    tier1_result = run_tier1(profile, item)
    if tier1_result is not None:
        logger.info(
            "SourceItem %s matched Tier 1 (phrase=%s, confidence=%s)",
            source_item_id, tier1_result["matched_phrase"], tier1_result["confidence"],
        )
        is_ext = _is_external(item)
        observe_until = _compute_observe_until(source_type, is_ext, user_config)
        candidate = CommitmentCandidate(
            user_id=item.user_id,
            originating_item_id=item.id,
            source_type=source_type,
            raw_text=tier1_result["matched_phrase"],
            trigger_class="profile_match",
            is_explicit=True,
            detection_explanation=(
                f"Tier 1 profile match: phrase='{tier1_result['matched_phrase']}'"
                f", sender={'high-signal' if tier1_result.get('matched_sender') else 'normal'}"
            ),
            confidence_score=tier1_result["confidence"],
            priority_hint="medium",
            commitment_class_hint="small_commitment",
            context_window={
                "trigger_text": tier1_result["matched_phrase"],
                "source_type": source_type,
                "tier": "tier_1",
            },
            linked_entities=_extract_entities(content[:500]),
            observe_until=observe_until,
            flag_reanalysis=False,
            detection_method="tier_1",
        )
        try:
            with db.begin_nested():
                db.add(candidate)
                db.flush()
            write_audit_entry(
                db, source_item_id=source_item_id, user_id=item.user_id,
                tier_used="tier_1",
                matched_phrase=tier1_result["matched_phrase"],
                matched_sender=tier1_result.get("matched_sender"),
                confidence=tier1_result["confidence"],
                commitment_created=True,
            )
            logger.info(
                "Tier 1 candidate %s created for item %s", candidate.id, source_item_id,
            )
            return [candidate]
        except Exception as exc:
            logger.warning("Tier 1 candidate insert failed for item %s: %s — falling through to Tier 2", source_item_id, exc)

    # Step 1: Strip suppression spans
    normalized = _apply_suppression(content, source_type)

    # Step 2: Gather applicable patterns and run them (Tier 2)
    patterns = get_patterns_for_source(source_type)
    is_ext = _is_external(item)

    created: list[CommitmentCandidate] = []

    for pattern in patterns:
        for match in pattern.pattern.finditer(normalized):
            trigger_text = match.group(0).strip()
            if not trigger_text:
                continue

            trigger_start = match.start()
            trigger_end = match.end()

            # Extract context window
            try:
                ctx = extract_context(
                    item=item,
                    trigger_text=trigger_text,
                    trigger_start=trigger_start,
                    trigger_end=trigger_end,
                    normalized_content=normalized,
                )
            except Exception as exc:
                logger.warning(
                    "Context extraction failed for item %s pattern %s: %s",
                    source_item_id, pattern.name, exc,
                )
                ctx = {
                    "trigger_text": trigger_text,
                    "trigger_start": trigger_start,
                    "trigger_end": trigger_end,
                    "source_type": source_type,
                }

            confidence = _compute_confidence(pattern, is_ext)
            # [D4] Apply per-user detection adjustment
            if profile is not None:
                from app.services.feedback_adapter import apply_detection_adjustment
                sender_email = getattr(item, "sender_email", None)
                confidence = Decimal(str(round(
                    apply_detection_adjustment(float(confidence), profile, sender_email, pattern.trigger_class),
                    3,
                )))
            priority = _compute_priority(pattern, is_ext, trigger_text)
            class_hint = _compute_class_hint(pattern, is_ext, trigger_text)
            observe_until = _compute_observe_until(source_type, is_ext, user_config)
            flag_reanalysis = _should_flag_reanalysis(item, trigger_text)
            entities = _extract_entities(trigger_text + " " + ctx.get("post_context", ""))

            ext_note = " External recipient detected, raising priority." if is_ext else ""
            explanation = (
                f"Matched pattern '{pattern.name}' "
                f"(trigger_class={pattern.trigger_class})."
                f"{ext_note}"
            )

            candidate = CommitmentCandidate(
                user_id=item.user_id,
                originating_item_id=item.id,
                source_type=source_type,
                raw_text=trigger_text,
                trigger_class=pattern.trigger_class,
                is_explicit=pattern.is_explicit,
                detection_explanation=explanation,
                confidence_score=confidence,
                priority_hint=priority,
                commitment_class_hint=class_hint,
                context_window=ctx,
                linked_entities=entities,
                observe_until=observe_until,
                flag_reanalysis=flag_reanalysis,
            )

            try:
                with db.begin_nested():  # SAVEPOINT
                    db.add(candidate)
                    db.flush()
                created.append(candidate)
                write_audit_entry(
                    db, source_item_id=source_item_id, user_id=item.user_id,
                    tier_used="tier_2",
                    matched_phrase=trigger_text[:255],
                    confidence=confidence,
                    commitment_created=True,
                )
                logger.debug(
                    "Created candidate %s for item %s (pattern=%s)",
                    candidate.id, source_item_id, pattern.name,
                )
            except Exception as exc:
                logger.warning(
                    "Failed to insert candidate for item %s pattern %s: %s",
                    source_item_id, pattern.name, exc,
                )

    # Write a "no_match" audit entry when no candidates were found and the
    # item was not suppressed (suppressed items already get their own audit).
    if not created:
        write_audit_entry(
            db, source_item_id=source_item_id, user_id=item.user_id,
            tier_used="no_match",
            commitment_created=False,
        )

    logger.info(
        "Detection complete for item %s: %d candidate(s) created",
        source_item_id, len(created),
    )
    return created
