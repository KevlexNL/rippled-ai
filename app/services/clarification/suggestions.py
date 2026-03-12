"""Suggestion generator — Phase 04.

Produces JSONB-ready suggested values from a commitment candidate.

Public API:
    generate_suggestions(candidate, issues) -> dict
"""
from __future__ import annotations

import re
from typing import Any

from app.models.enums import AmbiguityType


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SUBJECT_PREFIX_PATTERN = re.compile(
    r"^(?:I'll\s+|I will\s+|We'll\s+|We will\s+|I'm going to\s+|"
    r"I\s+(?:am\s+going\s+to\s+)|They'll\s+|She'll\s+|He'll\s+)",
    re.IGNORECASE,
)

_DELIVERY_SOURCE_TYPES = {"email", "slack"}

_DELIVERY_TRIGGER_CLASSES = {"delivery_signal", "blocker_signal"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_to_action_phrase(raw_text: str) -> str:
    """Strip first-person/subject prefix, keep verb+object phrase."""
    text = (raw_text or "").strip()
    stripped = _SUBJECT_PREFIX_PATTERN.sub("", text)
    if stripped and stripped != text:
        return stripped[0].upper() + stripped[1:]
    return text


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_suggestions(candidate: Any, issues: list[AmbiguityType]) -> dict:
    """Generate JSONB-ready suggested values from a candidate and its issues.

    Keys are only included when there is meaningful evidence.

    Args:
        candidate: CommitmentCandidate ORM object (or compatible namespace).
        issues: List of AmbiguityType values from analyze_candidate().

    Returns:
        Dict suitable for Clarification.suggested_values JSONB column.
    """
    result: dict = {}
    linked_entities = candidate.linked_entities or {}
    people: list = linked_entities.get("people", [])
    dates: list = linked_entities.get("dates", [])

    # likely_next_step — always attempt
    action_phrase = _normalize_to_action_phrase(candidate.raw_text or "")
    if action_phrase:
        result["likely_next_step"] = action_phrase

    # likely_owner — only if explicit + single named person
    if (
        candidate.is_explicit
        and len(people) == 1
        and AmbiguityType.owner_missing not in issues
        and AmbiguityType.owner_vague_collective not in issues
    ):
        result["likely_owner"] = {
            "value": people[0],
            "confidence": 0.7,
            "reason": "single named person in linked entities",
        }

    # likely_due_date — only if dates present
    if dates:
        result["likely_due_date"] = {
            "value": dates[0],
            "confidence": 0.6,
            "reason": "extracted from source",
        }

    # likely_completion — only if status_unclear + delivery source type pattern
    if (
        AmbiguityType.status_unclear in issues
        and (
            (candidate.source_type in _DELIVERY_SOURCE_TYPES)
            or (candidate.trigger_class in _DELIVERY_TRIGGER_CLASSES)
        )
    ):
        result["likely_completion"] = {
            "value": "possibly delivered",
            "confidence": 0.4,
            "reason": "delivery pattern detected in source",
        }

    return result
