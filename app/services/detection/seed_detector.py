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
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal

import anthropic
from sqlalchemy import and_, func, select, update
from sqlalchemy.orm import Session

from app.connectors.shared.credentials_utils import decrypt_value
from app.models.orm import (
    Commitment,
    CommitmentSignal,
    SourceItem,
    UserCommitmentProfile,
    UserSettings,
)
from app.services.detection.audit import estimate_cost, write_audit_entry
from app.services.identity.owner_resolver import resolve_owner_sync

logger = logging.getLogger(__name__)

_BATCH_SIZE = 20
_MAX_RETRIES = 3
_INITIAL_BACKOFF = 1.0
_DEFAULT_MODEL = "claude-sonnet-4-6"
_PROMPT_VERSION = "seed-v7"

_SYSTEM_PROMPT = """You are a commitment extraction engine for a workplace intelligence system.

Analyze the following email and extract ALL commitments, follow-ups, or obligations.

A commitment is a statement where someone obligates themselves or others to a specific
future action, deliverable, or outcome. Cast a WIDE net — it is better to surface a
probable commitment and let the user dismiss it than to miss it entirely.

This includes:
- Explicit: "I will", "I'll", "We will", "I promise", "I commit to"
- Implicit: "Consider it done", "Leave it with me", "I'll look into that"
- Tentative: "I'll try to", "Let me check", "I'll get back to you", "I should be able to"
- Follow-ups: "Let me circle back", "I'll send this over", "Will follow up", "Follow up on [topic]", "Need to follow up with [person]", "follow up on budget", "follow up on the proposal", "follow up on headcount", "follow up on the timeline"
- Bare follow-ups (ALWAYS a commitment): "need to follow up", "will follow up", "should follow up" — even without a preposition or topic, these are commitments
- Check-ins on a topic: "Checking in on the budget", "checking in on the project" — these imply a follow-up obligation
- Delegations: "Can you handle...", "Please take care of...", "Could you look into..."
- Scheduled actions: "Let's meet Tuesday", "I'll call you tomorrow"
- Soft promises: "I'll see what I can do", "Let me look into it", "I'll ping them"

NOT a commitment (NEVER extract these):
- Greetings and salutations: "Hi", "Hello", "Hey", "Good morning", "Good afternoon", "Good evening", "Dear team", "Dear all"
- Pleasantries and well-wishes: "Hope you're doing well", "Hope this finds you well", "Hope all is well", "Trust you are well", "Happy Friday", "Happy Monday"
- Sign-offs and closings: "Best regards", "Thanks", "Cheers", "Talk soon", "Warm regards", "Kind regards", "Best", "Regards"
- Social niceties: "Looking forward to connecting", "Thank you for your time", "Thanks for getting back to me"
- Casual acknowledgments with NO implied action: "OK", "Sounds good", "Got it"
- Pure questions with no self-assignment: "Should we...?", "What if we..."
- Past-tense descriptions: "I already did X", "We completed Y"
- Filler phrases: "By the way", "Just checking in" (but NOT "checking in on [topic]" — that IS a follow-up)
- Informational statements with no action implication
- Classification labels or meta-references: "greeting", "pleasantry", "filler" — these are labels, not commitments

IMPORTANT: The word "greeting" itself is NEVER a commitment. Social pleasantries are NOT commitments regardless of phrasing. Do NOT extract classification labels (e.g. "greeting", "acknowledgment") as commitments.

CRITICAL RULE — FOLLOW-UPS: ANY form of "follow up" is ALWAYS a commitment. This includes "follow up on [topic]", "need to follow up", "will follow up", "should follow up", "follow up on budget", "follow up on headcount", etc. Never skip these.

When in doubt, INCLUDE it as a commitment with lower confidence (0.4-0.6).

For each commitment found, extract:
- trigger_phrase: the exact words that signal the commitment
- who_committed: who made the commitment (name or role)
- directed_at: who the commitment is directed at (name, role, or null)
- urgency: "high", "medium", or "low"
- commitment_type: one of "send", "review", "follow_up", "deliver", "investigate", "introduce", "coordinate", "update", "delegate", "schedule", "confirm", "other"
- title: a concise summary (max 80 chars)
- is_external: true if this involves someone outside the organization

## Email input format

The input may include two sections:
[CURRENT MESSAGE]: The author's new content. Detect commitment candidates from this.
[PRIOR CONTEXT]: Quoted history from earlier in the thread. Do NOT create new commitment candidates from this section. Use it only to understand context, resolve references, or identify completion of existing commitments.

BEFORE YOU RESPOND — self-check each extracted commitment:
1. Remove any that are greetings, pleasantries, sign-offs, or classification labels
2. Verify you have not missed any "follow up" phrases — scan the text one more time
3. Confirm each remaining item describes a future action, not a past event or social nicety
4. Verify NONE of your extracted commitments come solely from [PRIOR CONTEXT] — only [CURRENT MESSAGE] content generates new commitments

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

# Regex to strip markdown code fences (```json ... ``` or ``` ... ```)
_CODE_FENCE_RE = re.compile(r"```(?:json)?\s*\n?(.*?)\n?\s*```", re.DOTALL | re.IGNORECASE)


def _strip_markdown_json(raw: str) -> str:
    """Extract JSON from a response that may be wrapped in markdown code fences."""
    m = _CODE_FENCE_RE.search(raw)
    return m.group(1).strip() if m else raw.strip()


@dataclass
class _LLMResult:
    """Internal: captures everything from an LLM call for auditing."""

    commitments: list[dict] | None  # None = skipped (content too short)
    raw_prompt: str | None = None
    raw_response: str | None = None
    parsed_result: list[dict] | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    model: str | None = None
    duration_ms: int | None = None
    error_detail: str | None = None


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
    # Load Anthropic API key from user_settings
    user_settings = db.execute(
        select(UserSettings).where(UserSettings.user_id == user_id)
    ).scalar_one_or_none()

    if not user_settings or not user_settings.anthropic_api_key_encrypted:
        logger.error("Seed pass: no Anthropic API key stored for user %s", user_id)
        return SeedPassResult(
            error_details=[
                "No Anthropic API key configured. "
                "Go to Settings and add your Anthropic API key."
            ]
        )

    api_key = decrypt_value(user_settings.anthropic_api_key_encrypted)
    if not api_key:
        logger.error("Seed pass: failed to decrypt Anthropic API key for user %s", user_id)
        return SeedPassResult(error_details=["Failed to decrypt Anthropic API key"])

    client = anthropic.Anthropic(api_key=api_key)
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
                llm_result = _extract_commitments(client, _DEFAULT_MODEL, item)

                if llm_result.commitments is None:
                    # No content / too short — no LLM call was made.
                    result.items_skipped += 1
                    logger.debug("Seed pass: skipped item %s (no content)", item.id)
                    continue

                # Write audit row for every LLM call
                commitment_created = bool(llm_result.commitments)
                cost = estimate_cost(
                    _DEFAULT_MODEL, llm_result.tokens_in, llm_result.tokens_out
                )
                write_audit_entry(
                    db,
                    source_item_id=item.id,
                    user_id=user_id,
                    tier_used="tier_3",
                    commitment_created=commitment_created,
                    prompt_version=_PROMPT_VERSION,
                    raw_prompt=llm_result.raw_prompt,
                    raw_response=llm_result.raw_response,
                    parsed_result=llm_result.parsed_result,
                    tokens_in=llm_result.tokens_in,
                    tokens_out=llm_result.tokens_out,
                    cost_estimate=cost,
                    model=llm_result.model,
                    duration_ms=llm_result.duration_ms,
                    error_detail=llm_result.error_detail,
                )

                # LLM was called successfully
                if llm_result.commitments:
                    for c_data in llm_result.commitments:
                        _create_commitment_and_signal(db, user_id, item, c_data)
                        result.commitments_created += 1
                        result.signals_created += 1
                else:
                    logger.debug("Seed pass: no commitments in item %s", item.id)

                # Mark as processed ONLY after successful LLM call
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
    client: anthropic.Anthropic, model: str, item: SourceItem
) -> _LLMResult:
    """Call Anthropic LLM to extract commitments from a source item.

    Returns:
        _LLMResult with commitments=None if item was skipped (content too short).
    """
    # Use content_normalized (latest authored text) if available, else full content
    latest_text = item.content_normalized or item.content or ""
    if len(latest_text.strip()) < 10:
        return _LLMResult(commitments=None)

    # Extract prior context from metadata if available
    metadata = item.metadata_ or {}
    prior_context = metadata.get("prior_context") if isinstance(metadata, dict) else None

    # Build context message with labeled sections
    parts = [f"Source type: {item.source_type}"]
    if item.sender_name or item.sender_email:
        parts.append(f"From: {item.sender_name or ''} <{item.sender_email or ''}>")
    if item.direction:
        parts.append(f"Direction: {item.direction}")
    parts.append(f"\n[CURRENT MESSAGE]\n{latest_text}")
    if prior_context:
        parts.append(f"\n[PRIOR CONTEXT]\n{prior_context}")
    user_message = "\n".join(parts)

    # Full prompt for audit logging
    full_prompt = f"[system]\n{_SYSTEM_PROMPT}\n\n[user]\n{user_message}"

    call_start = time.monotonic()

    for attempt in range(_MAX_RETRIES):
        try:
            response = client.messages.create(
                model=model,
                max_tokens=4096,
                system=_SYSTEM_PROMPT,
                messages=[
                    {"role": "user", "content": user_message},
                ],
                temperature=0.1,
            )

            duration_ms = int((time.monotonic() - call_start) * 1000)
            tokens_in = None
            tokens_out = None
            usage = response.usage
            if usage:
                tokens_in = usage.input_tokens
                tokens_out = usage.output_tokens
                logger.debug(
                    "Seed pass LLM usage — model=%s input=%d output=%d item=%s",
                    model,
                    tokens_in,
                    tokens_out,
                    item.id,
                )

            raw = response.content[0].text
            logger.info(
                "Seed pass raw LLM response for item %s (first 500 chars): %s",
                item.id,
                raw[:500],
            )
            cleaned = _strip_markdown_json(raw)
            data = json.loads(cleaned)
            commitments = data.get("commitments", [])
            logger.info(
                "Seed pass parsed %d commitment(s) from item %s",
                len(commitments),
                item.id,
            )
            return _LLMResult(
                commitments=commitments,
                raw_prompt=full_prompt,
                raw_response=raw,
                parsed_result=commitments,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                model=model,
                duration_ms=duration_ms,
            )

        except anthropic.RateLimitError:
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
            duration_ms = int((time.monotonic() - call_start) * 1000)
            raw_snippet = (raw[:200] if "raw" in dir() else "N/A")
            logger.warning(
                "Seed pass: malformed LLM response for item %s: %s — raw snippet: %s",
                item.id, exc, raw_snippet,
            )
            return _LLMResult(
                commitments=[],
                raw_prompt=full_prompt,
                raw_response=raw if "raw" in dir() else None,
                parsed_result=None,
                tokens_in=tokens_in if "tokens_in" in dir() else None,
                tokens_out=tokens_out if "tokens_out" in dir() else None,
                model=model,
                duration_ms=duration_ms,
                error_detail=f"Parse error: {exc}",
            )

    return _LLMResult(commitments=[], raw_prompt=full_prompt, model=model)


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

    # Resolve owner if suggested_owner was extracted
    if commitment.suggested_owner:
        resolved = resolve_owner_sync(commitment.suggested_owner, user_id, db)
        if resolved:
            commitment.resolved_owner = resolved
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
