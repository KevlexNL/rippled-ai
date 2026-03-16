"""Learning loop — profile updates after LLM detection and user dismissal.

Every time Tier 3 (LLM) produces a commitment signal:
1. Extract trigger phrase(s) and add to profile
2. Update sender weights
3. Next time, Tier 1 catches similar items without LLM

Every time the user dismisses a surfaced commitment:
1. Downweight the trigger phrase/sender that caused it
2. Profile gets more precise over time

Public API:
    extract_and_update_phrases(profile, trigger_text) -> None
    update_sender_weight(profile, sender_email) -> None
    downweight_phrase(profile, trigger_text) -> None
    downweight_sender(profile, sender_email) -> None
    update_profile_after_llm(profile, source_item, commitment_data) -> None
    downweight_profile_on_dismissal(profile, source_item) -> None
"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

_MAX_PHRASES = 50

# Common commitment trigger patterns for extraction
_TRIGGER_PATTERN = re.compile(
    r"(i['\u2019]ll\s+\w+(?:\s+\w+){0,5}|"
    r"i\s+will\s+\w+(?:\s+\w+){0,5}|"
    r"let\s+me\s+\w+(?:\s+\w+){0,5}|"
    r"we['\u2019]ll\s+\w+(?:\s+\w+){0,5}|"
    r"we\s+will\s+\w+(?:\s+\w+){0,5}|"
    r"i\s+(?:promise|commit)\s+(?:to\s+)?\w+(?:\s+\w+){0,5}|"
    r"consider\s+it\s+done|"
    r"leave\s+it\s+with\s+me)",
    re.IGNORECASE,
)


def _extract_trigger_phrase(text: str) -> str | None:
    """Extract the most relevant trigger phrase from text."""
    match = _TRIGGER_PATTERN.search(text)
    if match:
        return match.group(0).strip().lower()
    return text.strip().lower()[:100] if text.strip() else None


def extract_and_update_phrases(profile, trigger_text: str) -> None:
    """Add or update trigger phrases in the profile from detected text."""
    phrase = _extract_trigger_phrase(trigger_text)
    if not phrase:
        return

    phrases = list(getattr(profile, "trigger_phrases", None) or [])
    weights = dict(getattr(profile, "phrase_weights", None) or {})

    # Check if phrase already exists (exact or substring match)
    existing = None
    for p in phrases:
        if p in phrase or phrase in p:
            existing = p
            break

    if existing:
        # Increment weight of existing phrase
        weights[existing] = weights.get(existing, 1) + 1
    else:
        # Add new phrase
        phrases.append(phrase)
        weights[phrase] = 1

    # Cap at _MAX_PHRASES by removing lowest-weight entries
    if len(phrases) > _MAX_PHRASES:
        sorted_phrases = sorted(phrases, key=lambda p: weights.get(p, 0))
        removed = sorted_phrases[:len(phrases) - _MAX_PHRASES]
        phrases = [p for p in phrases if p not in removed]
        for r in removed:
            weights.pop(r, None)

    profile.trigger_phrases = phrases
    profile.phrase_weights = weights


def update_sender_weight(profile, sender_email: str) -> None:
    """Increment sender weight and add to high_signal_senders if new."""
    if not sender_email:
        return

    sender = sender_email.strip().lower()
    weights = dict(getattr(profile, "sender_weights", None) or {})
    senders = list(getattr(profile, "high_signal_senders", None) or [])

    weights[sender] = weights.get(sender, 0) + 1
    if sender not in senders:
        senders.append(sender)

    profile.sender_weights = weights
    profile.high_signal_senders = senders


def downweight_phrase(profile, trigger_text: str) -> None:
    """Downweight a trigger phrase after user dismisses a commitment."""
    phrase = trigger_text.strip().lower()
    weights = dict(getattr(profile, "phrase_weights", None) or {})
    phrases = list(getattr(profile, "trigger_phrases", None) or [])

    if phrase in weights:
        weights[phrase] = max(0, weights[phrase] - 1)
        if weights[phrase] <= 0:
            weights.pop(phrase, None)
            phrases = [p for p in phrases if p != phrase]
    else:
        # Try substring match
        for p in list(weights.keys()):
            if p in phrase or phrase in p:
                weights[p] = max(0, weights[p] - 1)
                if weights[p] <= 0:
                    weights.pop(p, None)
                    phrases = [pp for pp in phrases if pp != p]
                break

    profile.phrase_weights = weights
    profile.trigger_phrases = phrases


def downweight_sender(profile, sender_email: str) -> None:
    """Downweight a sender after user dismisses a commitment from them."""
    sender = sender_email.strip().lower()
    weights = dict(getattr(profile, "sender_weights", None) or {})
    senders = list(getattr(profile, "high_signal_senders", None) or [])

    if sender in weights:
        weights[sender] = max(0, weights[sender] - 1)
        if weights[sender] <= 0:
            weights.pop(sender, None)
            senders = [s for s in senders if s.lower() != sender]

    profile.sender_weights = weights
    profile.high_signal_senders = senders


def update_profile_after_llm(
    profile,
    source_item,
    commitment_data: dict,
) -> None:
    """Update profile after an LLM (Tier 3) detection creates a commitment.

    Called asynchronously after signal creation.
    """
    trigger_phrase = commitment_data.get("trigger_phrase", "")
    if trigger_phrase:
        extract_and_update_phrases(profile, trigger_phrase)

    sender_email = getattr(source_item, "sender_email", None) or ""
    if sender_email:
        update_sender_weight(profile, sender_email)


def downweight_profile_on_dismissal(
    profile,
    source_item,
    trigger_phrase: str | None = None,
) -> None:
    """Downweight profile entries after user dismisses a surfaced commitment.

    Called asynchronously after dismissal.
    """
    if trigger_phrase:
        downweight_phrase(profile, trigger_phrase)

    sender_email = getattr(source_item, "sender_email", None) or ""
    if sender_email:
        downweight_sender(profile, sender_email)
