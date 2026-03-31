"""Tier 1 — Profile-based pattern matching for the learning loop.

Checks incoming source items against the user's commitment profile
(trigger phrases, high-signal senders, suppressed senders) before
any LLM call. Free, ~0ms.

Public API:
    should_skip_detection(profile, item) -> bool
    run_tier1(profile, item) -> dict | None
    check_trigger_phrases(profile, content) -> dict | None
    check_high_signal_sender(profile, sender_email) -> bool
    is_sender_suppressed(profile, sender_email) -> bool
    detect_newsletter_sender(sender_email) -> bool
"""
from __future__ import annotations

import re
from decimal import Decimal

_NEWSLETTER_PATTERNS = re.compile(
    r"^(?:[\w.-]*[-._])?"
    r"(?:no-?reply|noreply|donotreply|newsletters?|notifications?|"
    r"mailer-?daemon|updates?|digest|alerts?|info|marketing|promo)"
    r"@",
    re.IGNORECASE,
)

# Confidence scaling: base 0.6 + (weight / max_weight) * 0.35, capped at 0.95
_BASE_CONFIDENCE = 0.6
_CONFIDENCE_RANGE = 0.35
_MAX_CONFIDENCE = 0.95


def detect_newsletter_sender(sender_email: str) -> bool:
    """Auto-detect newsletter/automated senders by email pattern."""
    if not sender_email:
        return False
    return bool(_NEWSLETTER_PATTERNS.match(sender_email.strip()))


def is_sender_suppressed(profile, sender_email: str) -> bool:
    """Check if sender is on the suppression list or auto-detected as newsletter."""
    if detect_newsletter_sender(sender_email):
        return True
    if profile is None:
        return False
    suppressed = getattr(profile, "suppressed_senders", None) or []
    if not suppressed:
        return False
    sender_lower = sender_email.strip().lower()
    return any(s.lower() == sender_lower for s in suppressed)


def should_skip_detection(profile, item) -> bool:
    """Return True if this item should skip all detection (suppressed sender)."""
    sender_email = getattr(item, "sender_email", None) or ""
    if not sender_email:
        return False
    return is_sender_suppressed(profile, sender_email)


def check_trigger_phrases(profile, content: str) -> dict | None:
    """Check content against profile trigger phrases.

    Returns a dict with matched_phrase and confidence if matched, else None.
    """
    if profile is None:
        return None
    phrases = getattr(profile, "trigger_phrases", None) or []
    if not phrases:
        return None

    weights = getattr(profile, "phrase_weights", None) or {}
    content_lower = content.lower()

    best_match = None
    best_weight = 0

    for phrase in phrases:
        if phrase.lower() in content_lower:
            weight = weights.get(phrase.lower(), 1)
            if weight > best_weight:
                best_weight = weight
                best_match = phrase.lower()

    if best_match is None:
        return None

    # Compute confidence from weight
    max_weight = max(weights.values()) if weights else 1
    weight_ratio = best_weight / max_weight if max_weight > 0 else 0
    confidence = min(
        _MAX_CONFIDENCE,
        _BASE_CONFIDENCE + weight_ratio * _CONFIDENCE_RANGE,
    )

    return {
        "matched_phrase": best_match,
        "confidence": Decimal(str(round(confidence, 3))),
        "weight": best_weight,
    }


def check_high_signal_sender(profile, sender_email: str) -> bool:
    """Check if sender is in the high-signal senders list."""
    if profile is None:
        return False
    senders = getattr(profile, "high_signal_senders", None) or []
    if not senders:
        return False
    sender_lower = sender_email.strip().lower()
    return any(s.lower() == sender_lower for s in senders)


def run_tier1(profile, item) -> dict | None:
    """Run Tier 1 profile-based matching.

    Requires a trigger phrase match in the content. High-signal sender
    provides a confidence boost but is not sufficient alone.

    Returns:
        dict with tier, matched_phrase, matched_sender, confidence — or None.
    """
    if profile is None:
        return None

    content = getattr(item, "content_normalized", None) or getattr(item, "content", None) or ""
    if not content.strip():
        return None

    # Check trigger phrases first (required)
    phrase_result = check_trigger_phrases(profile, content)
    if phrase_result is None:
        return None

    # Check sender for confidence boost
    sender_email = getattr(item, "sender_email", None) or ""
    is_high_signal = check_high_signal_sender(profile, sender_email)

    confidence = phrase_result["confidence"]
    if is_high_signal:
        confidence = min(Decimal(str(_MAX_CONFIDENCE)), confidence + Decimal("0.05"))

    return {
        "tier": "tier_1",
        "matched_phrase": phrase_result["matched_phrase"],
        "matched_sender": sender_email if is_high_signal else None,
        "confidence": confidence,
    }
