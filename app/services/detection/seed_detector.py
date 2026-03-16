"""Seed pass detection — WO-RIPPLED-SEED-PASS.

Runs a full LLM pass across all existing source items, bypassing the pattern
layer entirely. Produces Commitment + CommitmentSignal rows directly.

Public API:
    run_seed_pass(user_id, db) -> SeedPassResult
    build_user_profile(user_id, db) -> dict
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal

from openai import OpenAI, RateLimitError
from sqlalchemy import and_, func, select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.orm import (
    Commitment,
    CommitmentSignal,
    SourceItem,
    UserCommitmentProfile,
)

logger = logging.getLogger(__name__)

_BATCH_SIZE = 20
_MAX_RETRIES = 3
_INITIAL_BACKOFF = 1.0

_SYSTEM_PROMPT = """You are a commitment extraction engine for a workplace intelligence system.

Analyze the following email and extract ALL commitments, follow-ups, or obligations.

A commitment is a statement where someone obligates themselves or others to a specific
future action, deliverable, or outcome. This includes:
- Explicit: "I will", "I'll", "We will", "I promise", "I commit to"
- Implicit: "Consider it done", "Leave it with me", "I'll look into that"
- Follow-ups: "Let me circle back", "I'll send this over", "Will follow up"
- Delegations: "Can you handle...", "Please take care of..."
- Scheduled actions: "Let's meet Tuesday", "I'll call you tomorrow"

NOT a commitment:
- Casual acknowledgments: "OK", "Sounds good", "Got it"
- Questions or hypotheticals: "Should we...?", "What if we..."
- Past-tense descriptions: "I already did X", "We completed Y"
- Filler phrases: "By the way", "Just checking in"
- Informational statements with no action implication

For each commitment found, extract:
- trigger_phrase: the exact words that signal the commitment
- who_committed: who made the commitment (name or role)
- directed_at: who the commitment is directed at (name, role, or null)
- urgency: "high", "medium", or "low"
- commitment_type: one of "send", "review", "follow_up", "deliver", "investigate", "introduce", "coordinate", "update", "delegate", "schedule", "confirm", "other"
- title: a concise summary (max 80 chars)
- is_external: true if this involves someone outside the organization

Respond with valid JSON only:
{
  "commitments": [
    {
      "trigger_phrase": "...",
      "who_committed": "...",
      "directed_at": "...",
      "urgency": "high|medium|low",
      "commitment_type": "...",
      "title": "...",
      "is_external": true|false,
      "confidence": 0.0-1.0
    }
  ]
}

If no commitments are found, return: {"commitments": []}"""


@dataclass
class SeedPassResult:
    """Summary of a seed pass run."""

    items_processed: int = 0
    items_skipped: int = 0
    commitments_created: int = 0
    signals_created: int = 0
    errors: int = 0
    duration_ms: int = 0
    error_details: list[str] = field(default_factory=list)


def run_seed_pass(user_id: str, db: Session) -> SeedPassResult:
    """Run LLM seed pass across all unprocessed source items for a user.

    Creates Commitment + CommitmentSignal rows directly, bypassing pattern detection.
    Idempotent: skips items where seed_processed_at is already set.

    Args:
        user_id: UUID of the user.
        db: SQLAlchemy sync session (caller manages commit/rollback).

    Returns:
        SeedPassResult with processing stats.
    """
    settings = get_settings()
    if not settings.openai_api_key:
        logger.error("Seed pass: no OPENAI_API_KEY configured")
        return SeedPassResult(error_details=["No OPENAI_API_KEY configured"])

    client = OpenAI(api_key=settings.openai_api_key)
    start = time.monotonic()
    result = SeedPassResult()

    # Load unprocessed source items with non-empty content
    items = (
        db.execute(
            select(SourceItem)
            .where(
                and_(
                    SourceItem.user_id == user_id,
                    SourceItem.content.isnot(None),
                    SourceItem.content != "",
                    SourceItem.seed_processed_at.is_(None),
                )
            )
            .order_by(SourceItem.occurred_at.asc())
        )
        .scalars()
        .all()
    )

    logger.info(
        "Seed pass: found %d unprocessed items for user %s", len(items), user_id
    )

    # Process in batches
    for batch_start in range(0, len(items), _BATCH_SIZE):
        batch = items[batch_start : batch_start + _BATCH_SIZE]
        logger.info(
            "Seed pass: processing batch %d-%d of %d",
            batch_start + 1,
            min(batch_start + _BATCH_SIZE, len(items)),
            len(items),
        )

        for item in batch:
            try:
                commitments_data = _extract_commitments(client, settings.openai_model, item)

                if not commitments_data:
                    result.items_skipped += 1
                    logger.debug("Seed pass: no commitments in item %s", item.id)
                else:
                    for c_data in commitments_data:
                        _create_commitment_and_signal(db, user_id, item, c_data)
                        result.commitments_created += 1
                        result.signals_created += 1

                # Mark as processed (even if no commitments found)
                db.execute(
                    update(SourceItem)
                    .where(SourceItem.id == item.id)
                    .values(seed_processed_at=datetime.now(timezone.utc))
                )
                db.flush()
                result.items_processed += 1

            except Exception as exc:
                result.errors += 1
                msg = f"Item {item.id}: {exc}"
                result.error_details.append(msg)
                logger.error("Seed pass error: %s", msg)

        # Commit after each batch so partial progress is saved
        db.commit()

    result.duration_ms = int((time.monotonic() - start) * 1000)
    logger.info(
        "Seed pass complete: processed=%d, skipped=%d, commitments=%d, errors=%d, duration=%dms",
        result.items_processed,
        result.items_skipped,
        result.commitments_created,
        result.errors,
        result.duration_ms,
    )
    return result


def _extract_commitments(
    client: OpenAI, model: str, item: SourceItem
) -> list[dict]:
    """Call LLM to extract commitments from a source item. Returns list of dicts."""
    content = item.content or ""
    if len(content.strip()) < 10:
        return []

    # Build context message
    parts = [f"Source type: {item.source_type}"]
    if item.sender_name or item.sender_email:
        parts.append(f"From: {item.sender_name or ''} <{item.sender_email or ''}>")
    if item.direction:
        parts.append(f"Direction: {item.direction}")
    parts.append(f"\n--- Email Content ---\n{content}")
    user_message = "\n".join(parts)

    for attempt in range(_MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
            )

            usage = response.usage
            if usage:
                logger.debug(
                    "Seed pass LLM usage — model=%s prompt=%d completion=%d item=%s",
                    model,
                    usage.prompt_tokens,
                    usage.completion_tokens,
                    item.id,
                )

            raw = response.choices[0].message.content
            data = json.loads(raw)
            return data.get("commitments", [])

        except RateLimitError as exc:
            if attempt < _MAX_RETRIES - 1:
                backoff = _INITIAL_BACKOFF * (2**attempt)
                logger.warning(
                    "Seed pass rate limit (attempt %d/%d), retrying in %.1fs",
                    attempt + 1,
                    _MAX_RETRIES,
                    backoff,
                )
                time.sleep(backoff)
            else:
                logger.error("Seed pass rate limit exhausted for item %s", item.id)
                raise

        except (json.JSONDecodeError, KeyError, IndexError) as exc:
            logger.warning("Seed pass: malformed LLM response for item %s: %s", item.id, exc)
            return []

    return []


def _create_commitment_and_signal(
    db: Session,
    user_id: str,
    item: SourceItem,
    c_data: dict,
) -> None:
    """Create a Commitment and its origin CommitmentSignal from extracted data."""
    urgency = c_data.get("urgency", "medium")
    is_external = c_data.get("is_external", False)
    confidence = min(max(float(c_data.get("confidence", 0.5)), 0.0), 1.0)

    priority_class = "big_promise" if is_external and urgency == "high" else "small_commitment"
    context_type = "external" if is_external else "internal"

    # Map commitment_type, defaulting to "other"
    raw_type = c_data.get("commitment_type", "other")
    valid_types = {
        "send", "review", "follow_up", "deliver", "investigate",
        "introduce", "coordinate", "update", "delegate", "schedule",
        "confirm", "other",
    }
    commitment_type = raw_type if raw_type in valid_types else "other"

    commitment = Commitment(
        user_id=user_id,
        title=str(c_data.get("title", "Untitled commitment"))[:255],
        description=c_data.get("trigger_phrase"),
        commitment_text=c_data.get("trigger_phrase"),
        commitment_type=commitment_type,
        priority_class=priority_class,
        context_type=context_type,
        suggested_owner=c_data.get("who_committed"),
        target_entity=c_data.get("directed_at"),
        confidence_commitment=Decimal(str(round(confidence, 3))),
        confidence_actionability=Decimal(str(round(confidence * 0.8, 3))),
        lifecycle_state="proposed",
        commitment_explanation=f"Seed pass extraction from {item.source_type} item",
    )
    db.add(commitment)
    db.flush()  # get commitment.id

    signal = CommitmentSignal(
        commitment_id=commitment.id,
        source_item_id=item.id,
        user_id=user_id,
        signal_role="origin",
        confidence=Decimal(str(round(confidence, 3))),
        interpretation_note=f"Seed pass: {c_data.get('trigger_phrase', '')}",
    )
    db.add(signal)
    db.flush()


def build_user_profile(user_id: str, db: Session) -> dict:
    """Analyze seed pass results and write/update user_commitment_profiles.

    Returns the profile dict for logging.
    """
    # Count processed items
    items_processed = db.execute(
        select(func.count())
        .select_from(SourceItem)
        .where(
            and_(
                SourceItem.user_id == user_id,
                SourceItem.seed_processed_at.isnot(None),
            )
        )
    ).scalar_one()

    # Get all seed-created commitments (those with seed pass explanation)
    commitments = (
        db.execute(
            select(Commitment)
            .where(
                and_(
                    Commitment.user_id == user_id,
                    Commitment.commitment_explanation.like("Seed pass%"),
                )
            )
        )
        .scalars()
        .all()
    )

    total_commitments = len(commitments)

    # Extract trigger phrases
    trigger_phrases: dict[str, int] = {}
    for c in commitments:
        phrase = c.commitment_text
        if phrase:
            # Normalize: lowercase, strip
            key = phrase.strip().lower()[:100]
            trigger_phrases[key] = trigger_phrases.get(key, 0) + 1

    # Sort by frequency, take top 20
    top_phrases = sorted(trigger_phrases.keys(), key=lambda k: trigger_phrases[k], reverse=True)[:20]

    # Get high-signal senders from the origin signals
    sender_counts: dict[str, int] = {}
    for c in commitments:
        signals = (
            db.execute(
                select(CommitmentSignal)
                .where(
                    and_(
                        CommitmentSignal.commitment_id == c.id,
                        CommitmentSignal.signal_role == "origin",
                    )
                )
            )
            .scalars()
            .all()
        )
        for sig in signals:
            source_item = db.execute(
                select(SourceItem).where(SourceItem.id == sig.source_item_id)
            ).scalar_one_or_none()
            if source_item and source_item.sender_email:
                email = source_item.sender_email.lower()
                sender_counts[email] = sender_counts.get(email, 0) + 1

    top_senders = sorted(sender_counts.keys(), key=lambda k: sender_counts[k], reverse=True)[:10]

    # Extract domains from commitment types
    type_counts: dict[str, int] = {}
    for c in commitments:
        ct = c.commitment_type or "other"
        type_counts[ct] = type_counts.get(ct, 0) + 1
    domains = sorted(type_counts.keys(), key=lambda k: type_counts[k], reverse=True)

    profile_data = {
        "trigger_phrases": top_phrases,
        "high_signal_senders": top_senders,
        "domains": domains,
    }

    # Upsert profile
    existing = db.execute(
        select(UserCommitmentProfile).where(UserCommitmentProfile.user_id == user_id)
    ).scalar_one_or_none()

    now = datetime.now(timezone.utc)
    if existing:
        existing.trigger_phrases = top_phrases
        existing.high_signal_senders = top_senders
        existing.domains = domains
        existing.total_items_processed = items_processed
        existing.total_commitments_found = total_commitments
        existing.last_seed_pass_at = now
        existing.updated_at = now
    else:
        profile = UserCommitmentProfile(
            user_id=user_id,
            trigger_phrases=top_phrases,
            high_signal_senders=top_senders,
            domains=domains,
            total_items_processed=items_processed,
            total_commitments_found=total_commitments,
            last_seed_pass_at=now,
        )
        db.add(profile)

    db.commit()

    logger.info(
        "User profile built: user=%s, items=%d, commitments=%d, phrases=%d, senders=%d",
        user_id,
        items_processed,
        total_commitments,
        len(top_phrases),
        len(top_senders),
    )
    return profile_data
