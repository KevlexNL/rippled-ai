"""Completion matcher — Phase 05.

Matches a source_item against active commitments to find delivery evidence.

Quoted email suppression is applied before any keyword matching. Items with
is_quoted_content=True are excluded entirely. Lines starting with ">" are
stripped from content before pattern evaluation.

Public API:
    find_matching_commitments(source_item, active_commitments) -> list[tuple[commitment, CompletionEvidence]]
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Strips quoted email lines ("> ...") before keyword matching
_QUOTED_LINE_RE = re.compile(r"^>.*$", re.MULTILINE)

# Delivery keywords indicating the actor has sent/shared/completed something
_DELIVERY_KEYWORD_RE = re.compile(
    r"\b(sent|send|shared|share|attached|attach|delivered|deliver|submitted|submit|"
    r"uploaded|upload|forwarded|forward|introduced|introduce|scheduled|schedule|"
    r"completed|complete|finished|finish|done)\b",
    re.IGNORECASE,
)

# Words excluded from deliverable keyword overlap matching
_STOPWORDS = frozenset(
    {
        "the", "a", "an", "is", "it", "in", "on", "at", "to", "for", "of",
        "and", "or", "but", "we", "i", "my", "your", "this", "that", "with",
        "by", "as", "be", "will", "ll", "have", "has", "had", "do", "did",
        "not", "no", "so", "if", "up", "out", "its",
    }
)

# Commitment types that count as "deliver" for the attachment bonus
_DELIVER_TYPES = {"send", "deliver", "introduce"}

# Commitment types with the review/investigate penalty
_REVIEW_TYPES = {"review", "investigate"}

# Maximum number of days after commitment creation to consider evidence
_MAX_EVIDENCE_DAYS = 90


# ---------------------------------------------------------------------------
# CompletionEvidence dataclass
# ---------------------------------------------------------------------------

@dataclass
class CompletionEvidence:
    """Intermediate object produced by the matcher and consumed by the scorer.

    Not persisted directly — its output is persisted via CommitmentSignal and
    confidence columns on Commitment.
    """

    source_item_id: str
    source_type: str                   # "meeting" | "slack" | "email"
    occurred_at: datetime
    raw_text: str                      # original content (not suppressed)
    normalized_text: str               # after suppression patterns applied
    matched_patterns: list             # pattern names that fired
    actor_name: str | None             # who produced this item
    actor_email: str | None
    recipients: list                   # from source_item.recipients
    has_attachment: bool
    attachment_metadata: dict | None
    thread_id: str | None
    direction: str | None              # "inbound" | "outbound" | None
    evidence_strength: str             # "strong" | "moderate" | "weak"


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _suppress_quoted_lines(text: str) -> str:
    """Remove lines starting with '>' (quoted email chains)."""
    return _QUOTED_LINE_RE.sub("", text).strip()


def _actor_matches(source_item: Any, commitment: Any) -> bool:
    """Return True if source_item sender matches commitment owner.

    Case-insensitive fuzzy (contains) match on name and exact on email.
    """
    sender_name = (source_item.sender_name or "").lower().strip()
    sender_email = (source_item.sender_email or "").lower().strip()

    candidates = [
        (commitment.resolved_owner or "").lower().strip(),
        (commitment.suggested_owner or "").lower().strip(),
    ]
    candidates = [c for c in candidates if c]

    if not candidates:
        return False

    for owner in candidates:
        if not owner:
            continue
        # Name fuzzy match (contains)
        if sender_name and (sender_name in owner or owner in sender_name):
            return True
        # Email match
        if sender_email and (sender_email in owner or owner in sender_email):
            return True

    return False


def _recipient_matches(source_item: Any, commitment: Any) -> bool:
    """Return True if source_item recipients overlap with commitment.target_entity."""
    target = (commitment.target_entity or "").lower().strip()
    if not target:
        return False

    for recipient in source_item.recipients or []:
        if isinstance(recipient, str) and target in recipient.lower():
            return True

    return False


def _deliverable_matches(normalized_text: str, commitment: Any) -> bool:
    """Return True if ≥1 significant noun from deliverable appears in normalized_text.

    Significant = 2+ characters and not in stopwords.
    """
    deliverable = (commitment.deliverable or commitment.commitment_text or "").lower()
    if not deliverable or not normalized_text:
        return False

    words = re.findall(r"\b[a-z]{2,}\b", deliverable)
    significant = [w for w in words if w not in _STOPWORDS]

    content_lower = normalized_text.lower()
    return any(word in content_lower for word in significant)


def _thread_matches(source_item: Any, commitment: Any) -> bool:
    """Return True if source_item.thread_id matches a known origin signal thread.

    The detector pre-attaches _origin_thread_ids to each commitment before
    calling this function. Defaults to empty list if not present.
    """
    thread_id = source_item.thread_id
    if not thread_id:
        return False
    origin_ids = getattr(commitment, "_origin_thread_ids", []) or []
    return thread_id in origin_ids


def _compute_evidence_strength(
    has_deliverable: bool,
    has_thread: bool,
    has_attachment: bool,
    direction: str | None,
    has_recipient: bool,
    commitment_type: str | None = None,
) -> str:
    """Classify evidence strength based on matched dimensions.

    Per §3a channel classification and §3b match decision rule:
    - strong: deliverable + (thread OR outbound-attachment with recipient)
    - moderate: deliverable OR thread OR recipient
    - weak: delivery keyword only (no secondary dimensions)

    Phase E3 type-aware adjustment:
    - create type: without attachment, downgrade moderate → weak (requires artifact)
    """
    outbound_with_attachment = has_attachment and direction == "outbound"

    if has_deliverable and (has_thread or (outbound_with_attachment and has_recipient)):
        strength = "strong"
    elif has_deliverable or has_thread or has_recipient:
        strength = "moderate"
    else:
        strength = "weak"

    # Type-aware downgrade: create/revise/prepare types require artifact proof
    ct = (commitment_type or "").lower()
    if ct == "create" and not has_attachment and strength == "moderate":
        strength = "weak"

    return strength


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def find_matching_commitments(
    source_item: Any,
    active_commitments: list[Any],
) -> list[tuple[Any, CompletionEvidence]]:
    """Find active commitments that source_item provides delivery evidence for.

    Args:
        source_item: Duck-typed SourceItem ORM object or compatible namespace.
        active_commitments: List of duck-typed Commitment rows in lifecycle_state=active.

    Returns:
        List of (commitment, CompletionEvidence) tuples. A single source_item may
        match multiple commitments (actor delivered multiple things). Empty if none match.
    """
    # Guard: quoted content items are excluded entirely
    if source_item.is_quoted_content:
        return []

    raw_text = source_item.content or ""
    # Strip quoted reply lines before keyword evaluation
    normalized_text = _suppress_quoted_lines(
        source_item.content_normalized or raw_text
    )

    now = datetime.now(timezone.utc)
    cutoff = timedelta(days=_MAX_EVIDENCE_DAYS)

    results: list[tuple[Any, CompletionEvidence]] = []

    for commitment in active_commitments:
        # Time proximity: source_item must be after commitment creation
        if source_item.occurred_at <= commitment.created_at:
            continue
        # Cap at 90 days — stale commitments handled by auto-close sweep
        if source_item.occurred_at > commitment.created_at + cutoff:
            continue

        # Observation window: skip commitments still in their silent window
        observe_until = commitment.observe_until
        if observe_until is not None and observe_until > now:
            continue

        # Actor match is mandatory
        if not _actor_matches(source_item, commitment):
            continue

        # Evaluate secondary dimensions against suppressed text
        has_recipient = _recipient_matches(source_item, commitment)
        has_deliverable = _deliverable_matches(normalized_text, commitment)
        has_thread = _thread_matches(source_item, commitment)
        has_delivery_keyword = bool(_DELIVERY_KEYWORD_RE.search(normalized_text))

        # Must have at least one substantive secondary signal (recipient, deliverable, or thread).
        # Delivery keyword alone is insufficient — it would falsely match all active commitments
        # for this actor any time they send anything unrelated. The keyword is tracked in
        # matched_patterns as supporting evidence but does not gate the match itself.
        has_secondary = has_recipient or has_deliverable or has_thread
        if not has_secondary:
            continue

        strength = _compute_evidence_strength(
            has_deliverable=has_deliverable,
            has_thread=has_thread,
            has_attachment=source_item.has_attachment,
            direction=source_item.direction,
            has_recipient=has_recipient,
            commitment_type=commitment.commitment_type,
        )

        matched_patterns: list[str] = []
        if has_deliverable:
            matched_patterns.append("deliverable_keyword")
        if has_thread:
            matched_patterns.append("thread_continuity")
        if has_recipient:
            matched_patterns.append("recipient_match")
        if has_delivery_keyword:
            matched_patterns.append("delivery_keyword")

        evidence = CompletionEvidence(
            source_item_id=source_item.id,
            source_type=source_item.source_type,
            occurred_at=source_item.occurred_at,
            raw_text=raw_text,
            normalized_text=normalized_text,
            matched_patterns=matched_patterns,
            actor_name=source_item.sender_name,
            actor_email=source_item.sender_email,
            recipients=list(source_item.recipients or []),
            has_attachment=source_item.has_attachment,
            attachment_metadata=getattr(source_item, "attachment_metadata", None),
            thread_id=source_item.thread_id,
            direction=source_item.direction,
            evidence_strength=strength,
        )
        results.append((commitment, evidence))

    return results
