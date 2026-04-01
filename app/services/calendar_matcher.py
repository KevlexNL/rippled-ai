"""Calendar matcher service — Phase D3.

Matches calendar events to active commitments by entity/topic overlap.
Creates links with relationship types: deadline_hint, completion_hint, context.

Public API:
    CalendarMatcher(now=None).match(events, commitments, existing_pairs=None) -> list[dict]
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Confidence threshold: below this, don't create a link
_LINK_CONFIDENCE_THRESHOLD = 0.50

# Scoring weights
_PERSON_WEIGHT = 0.40
_TOPIC_WEIGHT = 0.35
_DELIVERABLE_WEIGHT = 0.25

# Short title penalty
_SHORT_TITLE_PENALTY = 0.15

# Generic event blocklist — normalized lowercase
_GENERIC_TITLES = {
    "standup", "stand-up", "daily standup", "daily stand-up",
    "team standup", "team stand-up",
    "1:1", "1-on-1", "one on one", "1 on 1",
    "team sync", "team meeting", "weekly sync",
    "all hands", "all-hands", "company meeting",
    "lunch", "break", "focus time", "busy",
    "office hours", "no meetings",
}

# Stop words for tokenization (reuse pattern from event_linker.py)
_STOP = {"the", "a", "an", "to", "for", "of", "in", "on", "at", "and", "or", "is",
         "with", "about", "from", "by", "this", "that", "it", "its", "was", "are"}


def _tokenize(text: str) -> list[str]:
    """Simple whitespace + punctuation tokenizer; filters short stop words."""
    tokens = []
    for word in text.lower().split():
        word = word.strip(".,!?;:\"'()-")
        if len(word) >= 3 and word not in _STOP:
            tokens.append(word)
    return tokens


class CalendarMatcher:
    """Match calendar events to active commitments by entity/topic overlap."""

    def __init__(self, now: datetime | None = None):
        self._now = now or datetime.now(timezone.utc)

    def match(
        self,
        events: list,
        commitments: list,
        existing_pairs: set[tuple[str, str]] | None = None,
    ) -> list[dict]:
        """Match events to commitments and return link dicts.

        Args:
            events: List of Event-like objects.
            commitments: List of Commitment-like objects.
            existing_pairs: Set of (event_id, commitment_id) tuples already linked.

        Returns:
            List of dicts with keys: event_id, commitment_id, link_type,
            confidence, metadata, signal_role (for completion_hint links).
        """
        if existing_pairs is None:
            existing_pairs = set()

        links: list[dict] = []

        for event in events:
            if getattr(event, "status", "confirmed") == "cancelled":
                continue

            if self._is_generic_event(event):
                continue

            for commitment in commitments:
                pair = (event.id, commitment.id)
                if pair in existing_pairs:
                    continue

                link_type, confidence, metadata = self._score_pair(event, commitment)
                if link_type is None:
                    continue

                link = {
                    "event_id": event.id,
                    "commitment_id": commitment.id,
                    "link_type": link_type,
                    "confidence": confidence,
                    "metadata": metadata,
                }

                # completion_hint links produce a progress signal
                if link_type == "completion_hint":
                    link["signal_role"] = "progress"

                links.append(link)
                # Mark pair as seen for dedup within this batch
                existing_pairs.add(pair)

        return links

    def _score_pair(
        self, event, commitment
    ) -> tuple[str | None, float, dict]:
        """Score an event-commitment pair.

        Returns:
            (link_type, confidence, metadata) or (None, 0.0, {}) if no match.
        """
        if self._is_generic_event(event):
            return None, 0.0, {}

        person_score = self._entity_overlap(event, commitment)
        topic_score = self._topic_overlap(event, commitment)
        deliverable_score = self._deliverable_overlap(event, commitment)

        confidence = (
            person_score * _PERSON_WEIGHT
            + topic_score * _TOPIC_WEIGHT
            + deliverable_score * _DELIVERABLE_WEIGHT
        )

        # Short title penalty
        title_tokens = _tokenize(getattr(event, "title", "") or "")
        if len(title_tokens) <= 2:
            confidence -= _SHORT_TITLE_PENALTY

        confidence = max(0.0, confidence)

        if confidence < _LINK_CONFIDENCE_THRESHOLD:
            return None, confidence, {}

        # Determine link type based on event timing
        link_type = self._determine_link_type(event, commitment)

        # Build metadata
        matched_on = []
        if person_score > 0:
            matched_on.append(f"person:{person_score:.2f}")
        if topic_score > 0:
            matched_on.append(f"topic:{topic_score:.2f}")
        if deliverable_score > 0:
            matched_on.append(f"deliverable:{deliverable_score:.2f}")

        metadata = {
            "matched_on": matched_on,
            "person_score": round(person_score, 3),
            "topic_score": round(topic_score, 3),
            "deliverable_score": round(deliverable_score, 3),
        }

        return link_type, round(confidence, 3), metadata

    def _entity_overlap(self, event, commitment) -> float:
        """Score person/entity overlap between event and commitment (0-1)."""
        score = 0.0
        attendees = getattr(event, "attendees", None) or []

        attendee_emails = set()
        attendee_names = set()
        for a in attendees:
            if isinstance(a, dict):
                email = a.get("email", "").lower().strip()
                name = a.get("name", "").lower().strip()
                if email:
                    attendee_emails.add(email)
                if name:
                    attendee_names.add(name)

        # Check requester email
        req_email = (getattr(commitment, "requester_email", None) or "").lower().strip()
        if req_email and req_email in attendee_emails:
            score = max(score, 1.0)

        # Check beneficiary email
        ben_email = (getattr(commitment, "beneficiary_email", None) or "").lower().strip()
        if ben_email and ben_email in attendee_emails:
            score = max(score, 1.0)

        # Check requester name
        req_name = (getattr(commitment, "requester_name", None) or "").lower().strip()
        if req_name and req_name in attendee_names:
            score = max(score, 0.8)

        # Check beneficiary name
        ben_name = (getattr(commitment, "beneficiary_name", None) or "").lower().strip()
        if ben_name and ben_name in attendee_names:
            score = max(score, 0.8)

        # Check target entity in event title
        target = (getattr(commitment, "target_entity", None) or "").lower().strip()
        event_title = (getattr(event, "title", None) or "").lower()
        if target and target in event_title:
            score = max(score, 0.6)

        return score

    def _topic_overlap(self, event, commitment) -> float:
        """Score topic keyword overlap via Jaccard similarity (0-1)."""
        event_text = " ".join(filter(None, [
            getattr(event, "title", None),
            getattr(event, "description", None),
        ]))
        commitment_text = " ".join(filter(None, [
            getattr(commitment, "title", None),
            getattr(commitment, "description", None),
            getattr(commitment, "commitment_text", None),
        ]))

        event_tokens = set(_tokenize(event_text))
        commitment_tokens = set(_tokenize(commitment_text))

        if not event_tokens or not commitment_tokens:
            return 0.0

        intersection = event_tokens & commitment_tokens
        union = event_tokens | commitment_tokens
        return len(intersection) / len(union)

    def _deliverable_overlap(self, event, commitment) -> float:
        """Check if commitment deliverable terms appear in event text (0 or 1)."""
        deliverable = getattr(commitment, "deliverable", None)
        if not deliverable:
            return 0.0

        event_text = " ".join(filter(None, [
            getattr(event, "title", None),
            getattr(event, "description", None),
        ])).lower()

        deliverable_tokens = set(_tokenize(deliverable))
        if not deliverable_tokens:
            return 0.0

        event_tokens = set(_tokenize(event_text))
        matches = deliverable_tokens & event_tokens

        if not matches:
            return 0.0

        return len(matches) / len(deliverable_tokens)

    def _is_generic_event(self, event) -> bool:
        """Return True if event is generic (standup, 1:1, etc.)."""
        title = (getattr(event, "title", None) or "").lower().strip()
        if not title:
            return True

        # Exact match against blocklist
        if title in _GENERIC_TITLES:
            return True

        # Check if title starts with a generic prefix but has substantive content after
        # "1:1 with Sarah about pricing" → NOT generic
        for generic in _GENERIC_TITLES:
            if title.startswith(generic):
                remainder = title[len(generic):].strip()
                # If there's substantive content after the generic prefix, it's NOT generic
                remainder_tokens = _tokenize(remainder)
                if len(remainder_tokens) >= 2:
                    return False
                elif len(remainder_tokens) == 0:
                    return True
                # 1 token remainder — still generic-ish
                # unless it's a proper name or topic

        return False

    def _determine_link_type(self, event, commitment) -> str:
        """Determine link type based on event timing relative to now."""
        ends_at = getattr(event, "ends_at", None)
        starts_at = getattr(event, "starts_at", None)

        # Use ends_at if available, otherwise starts_at
        event_end = ends_at or starts_at
        if event_end is None:
            return "context"

        if event_end.tzinfo is None:
            event_end = event_end.replace(tzinfo=timezone.utc)

        if event_end < self._now:
            return "completion_hint"

        # Event is in the future
        has_deadline = getattr(commitment, "resolved_deadline", None) is not None
        if has_deadline:
            return "context"
        return "deadline_hint"
