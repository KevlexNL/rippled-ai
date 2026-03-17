"""Ad-hoc signal matcher — text similarity matching for Telegram signals.

Matches ad-hoc commitment text against recent commitments using:
1. Substring matching (exact phrase fragments)
2. Keyword overlap (Jaccard similarity on normalized tokens)

Combined into a single 0–1 confidence score.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.orm import AdhocSignal, Commitment, CommitmentSignal, EvalDataset, SourceItem


# ---------------------------------------------------------------------------
# Text normalization
# ---------------------------------------------------------------------------

_STOPWORDS = frozenset({
    "i", "me", "my", "we", "our", "you", "your", "he", "she", "it", "they",
    "the", "a", "an", "is", "am", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "shall", "should",
    "can", "could", "may", "might", "must", "to", "of", "in", "for", "on", "with",
    "at", "by", "from", "as", "into", "about", "that", "this", "which", "who",
    "whom", "what", "and", "but", "or", "not", "no", "so", "if", "then",
    "committed", "commit", "promised", "promise", "agreed", "agree", "going",
})


def _tokenize(text: str) -> set[str]:
    """Lowercase, strip punctuation, remove stopwords."""
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w for w in words if w not in _STOPWORDS and len(w) > 1}


# ---------------------------------------------------------------------------
# Similarity functions (exported for testing)
# ---------------------------------------------------------------------------

def compute_keyword_similarity(text_a: str, text_b: str) -> float:
    """Jaccard similarity on keyword sets."""
    tokens_a = _tokenize(text_a)
    tokens_b = _tokenize(text_b)
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)


def has_substring_match(needle: str, haystack: str) -> bool:
    """Check if any 3+ word phrase from needle appears in haystack (case-insensitive)."""
    needle_lower = needle.lower()
    haystack_lower = haystack.lower()

    # Direct substring
    if needle_lower in haystack_lower:
        return True

    # Check 3-word sliding windows from needle
    words = needle_lower.split()
    if len(words) >= 3:
        for i in range(len(words) - 2):
            phrase = " ".join(words[i:i + 3])
            if phrase in haystack_lower:
                return True

    return False


def score_match(adhoc_text: str, commitment_text: str) -> float:
    """Combined similarity score (0–1) between ad-hoc text and commitment text."""
    keyword_score = compute_keyword_similarity(adhoc_text, commitment_text)

    # Substring bonus: if a significant phrase matches, boost confidence
    substring_bonus = 0.0
    if has_substring_match(adhoc_text, commitment_text):
        substring_bonus = 0.25
    elif has_substring_match(commitment_text, adhoc_text):
        substring_bonus = 0.25

    return min(1.0, keyword_score + substring_bonus)


# ---------------------------------------------------------------------------
# Match check against DB
# ---------------------------------------------------------------------------

MATCH_THRESHOLD = 0.20  # minimum confidence to consider a match
LOOKBACK_HOURS = 24     # search commitments created in last N hours


async def check_match(
    signal_id: str,
    db: AsyncSession,
) -> dict:
    """Run match check for an adhoc_signal. Updates the record in-place.

    Returns dict with match result fields.
    """
    # Load the signal
    result = await db.execute(
        select(AdhocSignal).where(AdhocSignal.id == signal_id)
    )
    signal = result.scalar_one_or_none()
    if signal is None:
        return {"error": "not_found"}

    adhoc_text = signal.raw_text
    user_id = signal.user_id
    now = datetime.now(timezone.utc)
    lookback = now - timedelta(hours=LOOKBACK_HOURS)

    # Query recent commitments for this user
    commitments_result = await db.execute(
        select(Commitment).where(
            and_(
                Commitment.user_id == user_id,
                Commitment.created_at >= lookback,
            )
        )
    )
    commitments = commitments_result.scalars().all()

    best_match_id: str | None = None
    best_score: float = 0.0

    for c in commitments:
        # Score against title, description, and commitment_text
        texts = [t for t in [c.title, c.description, c.commitment_text] if t]
        for text in texts:
            s = score_match(adhoc_text, text)
            if s > best_score:
                best_score = s
                best_match_id = c.id

    # Also check commitment_signals (source item content)
    signals_result = await db.execute(
        select(CommitmentSignal, SourceItem).join(
            SourceItem, CommitmentSignal.source_item_id == SourceItem.id
        ).where(
            and_(
                CommitmentSignal.user_id == user_id,
                CommitmentSignal.created_at >= lookback,
            )
        )
    )
    for cs, si in signals_result.all():
        if si.content:
            s = score_match(adhoc_text, si.content)
            if s > best_score:
                best_score = s
                best_match_id = cs.commitment_id

    # Determine result
    was_found = best_score >= MATCH_THRESHOLD and best_match_id is not None

    signal.match_checked_at = now
    signal.was_found = was_found
    signal.match_confidence = Decimal(str(round(best_score, 3)))
    signal.match_status = "matched" if was_found else "not_found"

    commitment_title: str | None = None
    if was_found:
        signal.matched_commitment_id = best_match_id
        # Look up commitment title for response
        for c in commitments:
            if c.id == best_match_id:
                commitment_title = c.title
                break

    # Auto-create eval_dataset row for missed signals (false negative ground truth)
    if not was_found:
        # Find the most recent source_item for this user to anchor the eval row
        recent_si = await db.execute(
            select(SourceItem.id)
            .where(SourceItem.user_id == user_id)
            .order_by(SourceItem.ingested_at.desc())
            .limit(1)
        )
        source_item_id = recent_si.scalar_one_or_none()
        if source_item_id:
            eval_row = EvalDataset(
                user_id=user_id,
                source_item_id=source_item_id,
                expected_has_commitment=True,
                label_notes=adhoc_text,
                labeled_by="adhoc_signal",
            )
            db.add(eval_row)

    await db.flush()

    return {
        "id": signal.id,
        "match_status": signal.match_status,
        "was_found": signal.was_found,
        "matched_commitment_id": signal.matched_commitment_id,
        "match_confidence": float(signal.match_confidence) if signal.match_confidence is not None else None,
        "match_checked_at": signal.match_checked_at.isoformat() if signal.match_checked_at else None,
        "commitment_title": commitment_title,
    }


def check_match_sync(signal_id: str, db: Session) -> dict:
    """Synchronous version of check_match for Celery tasks."""
    signal = db.execute(
        select(AdhocSignal).where(AdhocSignal.id == signal_id)
    ).scalar_one_or_none()
    if signal is None:
        return {"error": "not_found"}

    adhoc_text = signal.raw_text
    user_id = signal.user_id
    now = datetime.now(timezone.utc)
    lookback = now - timedelta(hours=LOOKBACK_HOURS)

    commitments = db.execute(
        select(Commitment).where(
            and_(
                Commitment.user_id == user_id,
                Commitment.created_at >= lookback,
            )
        )
    ).scalars().all()

    best_match_id: str | None = None
    best_score: float = 0.0

    for c in commitments:
        texts = [t for t in [c.title, c.description, c.commitment_text] if t]
        for text in texts:
            s = score_match(adhoc_text, text)
            if s > best_score:
                best_score = s
                best_match_id = c.id

    signals_result = db.execute(
        select(CommitmentSignal, SourceItem).join(
            SourceItem, CommitmentSignal.source_item_id == SourceItem.id
        ).where(
            and_(
                CommitmentSignal.user_id == user_id,
                CommitmentSignal.created_at >= lookback,
            )
        )
    )
    for cs, si in signals_result.all():
        if si.content:
            s = score_match(adhoc_text, si.content)
            if s > best_score:
                best_score = s
                best_match_id = cs.commitment_id

    was_found = best_score >= MATCH_THRESHOLD and best_match_id is not None

    signal.match_checked_at = now
    signal.was_found = was_found
    signal.match_confidence = Decimal(str(round(best_score, 3)))
    signal.match_status = "matched" if was_found else "not_found"

    if was_found:
        signal.matched_commitment_id = best_match_id

    if not was_found:
        source_item_id = db.execute(
            select(SourceItem.id)
            .where(SourceItem.user_id == user_id)
            .order_by(SourceItem.ingested_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        if source_item_id:
            eval_row = EvalDataset(
                user_id=user_id,
                source_item_id=source_item_id,
                expected_has_commitment=True,
                label_notes=adhoc_text,
                labeled_by="adhoc_signal",
            )
            db.add(eval_row)

    return {
        "signal_id": signal.id,
        "match_status": signal.match_status,
        "was_found": was_found,
    }
