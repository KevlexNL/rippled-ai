"""Event linker service — Phase C3.

Two classes:
    DeadlineEventLinker — links commitments to Events by deadline proximity + scoring
    CounterpartyExtractor — classifies and stores counterparty type/email on Commitment

Public API:
    DeadlineEventLinker().run(db, user_id, commitments, events, existing_link_ids=None) -> dict
    CounterpartyExtractor(settings, user_email).extract(commitment, source_item, user_email) -> None
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

logger = logging.getLogger(__name__)

# Confidence threshold: below this, don't create a link to an existing event
_LINK_CONFIDENCE_THRESHOLD = 0.70


class DeadlineEventLinker:
    """Links active commitments (with resolved_deadline) to Events.

    For each unlinked commitment:
      - Scan events within ±24h of the deadline
      - Score each candidate (attendee overlap + keyword overlap + time proximity)
      - If best score >= 0.7: create CommitmentEventLink to that event
      - Otherwise: create an implicit Event + link (confidence=1.0)
    """

    def run(
        self,
        db,
        user_id: str,
        commitments: list,
        events: list,
        existing_link_ids: set | None = None,
    ) -> dict:
        """Link commitments to events.

        Args:
            db: Synchronous SQLAlchemy session.
            user_id: User ID (for new Event rows).
            commitments: List of Commitment objects to process.
            events: List of Event objects available for matching.
            existing_link_ids: Set of commitment IDs that already have a delivery_at link.

        Returns:
            Dict with 'links_created' and 'implicit_events_created' counts.
        """
        if existing_link_ids is None:
            existing_link_ids = set()

        links_created = 0
        implicit_events_created = 0

        for commitment in commitments:
            if commitment.resolved_deadline is None:
                continue

            if commitment.id in existing_link_ids:
                continue

            deadline = commitment.resolved_deadline
            if deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=timezone.utc)

            # Scan events within ±24h of deadline
            window_start = deadline - timedelta(hours=24)
            window_end = deadline + timedelta(hours=24)

            candidates = [
                e for e in events
                if getattr(e, "status", "confirmed") != "cancelled"
                and getattr(e, "starts_at", None) is not None
                and _tz_aware(e.starts_at) >= window_start
                and _tz_aware(e.starts_at) <= window_end
            ]

            best_event = None
            best_score = 0.0

            for event in candidates:
                s = self._match_score(commitment, event, deadline)
                if s > best_score:
                    best_score = s
                    best_event = event

            if best_event is not None and best_score >= _LINK_CONFIDENCE_THRESHOLD:
                # Create link to existing event
                link = _make_link(commitment.id, best_event.id, "delivery_at", Decimal(str(round(best_score, 3))))
                db.add(link)
                links_created += 1
            else:
                # Create implicit event + link
                implicit_event = _make_implicit_event(commitment, deadline)
                db.add(implicit_event)
                link = _make_link(commitment.id, implicit_event.id, "delivery_at", Decimal("1.000"))
                db.add(link)
                implicit_events_created += 1

        if links_created + implicit_events_created > 0:
            db.flush()

        logger.info(
            "DeadlineEventLinker: links_created=%d implicit_events_created=%d",
            links_created, implicit_events_created,
        )

        return {
            "links_created": links_created,
            "implicit_events_created": implicit_events_created,
        }

    def _match_score(self, commitment, event, deadline: datetime) -> float:
        """Score a commitment-event pair for linking confidence.

        Components:
          +0.4 attendee email overlap
          +0.4 keyword overlap (Jaccard ≥ 0.3 on title tokens)
          +0.2 time proximity (within 2h) / +0.1 (within 24h)
        """
        score = 0.0

        # Attendee overlap (+0.5)
        counterparty = getattr(commitment, "counterparty_email", None)
        if counterparty:
            attendees = getattr(event, "attendees", None) or []
            attendee_emails = {
                a.get("email", "").lower() if isinstance(a, dict) else ""
                for a in attendees
            }
            if counterparty.lower() in attendee_emails:
                score += 0.5

        # Keyword overlap (Jaccard on title tokens) (+0.5 if Jaccard ≥ 0.3)
        commitment_tokens = set(_tokenize(commitment.title or ""))
        event_tokens = set(_tokenize(event.title or ""))
        if commitment_tokens and event_tokens:
            intersection = commitment_tokens & event_tokens
            union = commitment_tokens | event_tokens
            jaccard = len(intersection) / len(union)
            if jaccard >= 0.3:
                score += 0.5

        # Time proximity (+0.2 within 2h, +0.1 within 24h)
        event_start = _tz_aware(event.starts_at)
        diff_hours = abs((event_start - deadline).total_seconds()) / 3600
        if diff_hours <= 2:
            score += 0.2
        elif diff_hours <= 24:
            score += 0.1

        return score


class CounterpartyExtractor:
    """Classifies the counterparty of a commitment and writes to commitment.counterparty_type/_email.

    Classification logic:
      - sender == user_email → 'self'
      - sender in internal_managers list → 'internal_manager'
      - sender domain in internal_domains → 'internal_peer'
      - otherwise → 'external_client'
    """

    def __init__(self, settings=None, user_email: str = ""):
        self._settings = settings
        self._user_email = user_email

    def extract(self, commitment, source_item, user_email: str = "") -> None:
        """Classify counterparty and write to commitment fields.

        Args:
            commitment: Commitment ORM object (modified in-place).
            source_item: SourceItem or None.
            user_email: The authenticated user's email (used for 'self' detection).
        """
        if source_item is None:
            return

        effective_user_email = (user_email or self._user_email or "").lower()
        source_type = getattr(source_item, "source_type", "email")
        sender_email = getattr(source_item, "sender_email", None)

        # For meeting source items, fallback to first non-user recipient
        if source_type == "meeting" or not sender_email:
            recipients = getattr(source_item, "recipients", None) or []
            sender_email = self._first_non_user_recipient(recipients, effective_user_email)

        if not sender_email:
            return

        commitment.counterparty_email = sender_email
        commitment.counterparty_type = self._classify(sender_email.lower(), effective_user_email)

    def _first_non_user_recipient(self, recipients: list, user_email: str) -> str | None:
        for r in recipients:
            email = r.get("email", "").lower() if isinstance(r, dict) else ""
            if email and email != user_email:
                return email
        return None

    def _classify(self, sender_email: str, user_email: str) -> str:
        if sender_email == user_email:
            return "self"

        settings = self._settings
        internal_managers_str = getattr(settings, "internal_managers", "") or ""
        internal_managers = {
            m.strip().lower()
            for m in internal_managers_str.split(",")
            if m.strip()
        }
        if sender_email in internal_managers:
            return "internal_manager"

        internal_domains_str = getattr(settings, "internal_domains", "") or ""
        internal_domains = {
            d.strip().lower()
            for d in internal_domains_str.split(",")
            if d.strip()
        }
        if internal_domains:
            try:
                domain = sender_email.split("@")[1]
                if domain in internal_domains:
                    return "internal_peer"
            except IndexError:
                pass

        return "external_client"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> list[str]:
    """Simple whitespace + punctuation tokenizer; filters short stop words."""
    _STOP = {"the", "a", "an", "to", "for", "of", "in", "on", "at", "and", "or", "is"}
    tokens = []
    for word in text.lower().split():
        word = word.strip(".,!?;:\"'()")
        if len(word) >= 3 and word not in _STOP:
            tokens.append(word)
    return tokens


def _tz_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _make_implicit_event(commitment, deadline: datetime):
    """Create an implicit Event from a commitment deadline."""
    # Import here to avoid circular imports at module load time
    from app.models.orm import Event
    return Event(
        id=str(uuid.uuid4()),
        source_id=None,
        external_id=None,
        title=f"[implicit] {commitment.title or 'Delivery'}",
        starts_at=deadline,
        ends_at=deadline + timedelta(hours=1),
        event_type="implicit",
        status="confirmed",
        is_recurring=False,
    )


def _make_link(commitment_id: str, event_id: str, relationship: str, confidence: Decimal):
    """Create a CommitmentEventLink row."""
    from app.models.orm import CommitmentEventLink
    return CommitmentEventLink(
        id=str(uuid.uuid4()),
        commitment_id=commitment_id,
        event_id=event_id,
        relationship=relationship,
        confidence=confidence,
    )
