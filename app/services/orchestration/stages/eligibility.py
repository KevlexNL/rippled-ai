"""Stage 0 — Eligibility check (deterministic, no LLM).

Prevents wasteful processing of unsupported or unusable signals.
"""

from __future__ import annotations

import re

from app.connectors.shared.normalized_signal import NormalizedSignal
from app.services.detection.profile_matcher import detect_newsletter_sender
from app.services.orchestration.config import get_orchestration_config
from app.services.orchestration.contracts import EligibilityReason, EligibilityResult

# Minimum text length for the authored text (matches fragment gate threshold)
_MIN_AUTHORED_TEXT_LENGTH = 10

# Bulk-mail content indicators — each pattern is one "indicator category".
# A signal is rejected when 2+ distinct categories match (single match
# could be a legitimate email with an unsubscribe link).
_BULK_MAIL_INDICATORS: list[re.Pattern[str]] = [
    # Unsubscribe / opt-out language
    re.compile(
        r"\b(?:unsubscribe|opt[\s-]?out(?:\s+of)?|manage\s+(?:your\s+)?(?:preferences|subscription)s?"
        r"|email\s+preferences|update\s+(?:your\s+)?email\s+preferences)\b",
        re.IGNORECASE,
    ),
    # "View in browser" / "View this email"
    re.compile(
        r"\bview\s+(?:this\s+)?(?:email|message|newsletter)\s+in\s+(?:your\s+)?browser\b",
        re.IGNORECASE,
    ),
    # Mailing-list footer ("You are receiving this because…", "This email was sent to…")
    re.compile(
        r"\b(?:you\s+are\s+receiving\s+this|this\s+email\s+was\s+sent\s+to)\b",
        re.IGNORECASE,
    ),
    # Digest / summary structure keywords
    re.compile(
        r"\b(?:daily\s+digest|weekly\s+(?:summary|digest|recap)|your\s+(?:daily|weekly)\s+(?:digest|recap|summary))\b",
        re.IGNORECASE,
    ),
]

_BULK_MAIL_THRESHOLD = 2  # Minimum distinct categories required


def _count_bulk_mail_indicators(text: str) -> int:
    """Count how many distinct bulk-mail indicator categories match in *text*."""
    return sum(1 for pattern in _BULK_MAIL_INDICATORS if pattern.search(text))


def check_eligibility(signal: NormalizedSignal) -> EligibilityResult:
    """Deterministic eligibility gate. Returns immediately."""
    config = get_orchestration_config()

    # Check source type is supported
    if signal.source_type not in config.supported_source_types:
        return EligibilityResult(eligible=False, reason=EligibilityReason.unsupported_source)

    # Check that at least one text field has content
    has_authored = bool(signal.latest_authored_text and signal.latest_authored_text.strip())
    has_prior = bool(signal.prior_context_text and signal.prior_context_text.strip())
    if not has_authored and not has_prior:
        return EligibilityResult(eligible=False, reason=EligibilityReason.missing_text)

    # Structural validity: must have a signal_id
    if not signal.signal_id:
        return EligibilityResult(eligible=False, reason=EligibilityReason.invalid_normalized_signal)

    # Email-specific filters
    if signal.source_type == "email":
        # Newsletter/noreply sender filter
        sender_email = ""
        if signal.sender and signal.sender.email:
            sender_email = signal.sender.email
        if sender_email and detect_newsletter_sender(sender_email):
            return EligibilityResult(eligible=False, reason=EligibilityReason.newsletter_sender)

        # List-Unsubscribe header filter
        headers = (signal.metadata or {}).get("headers", {})
        if headers:
            header_keys_lower = {k.lower() for k in headers}
            if "list-unsubscribe" in header_keys_lower:
                return EligibilityResult(eligible=False, reason=EligibilityReason.automated_sender_header)

        # Content-based bulk-mail filter
        if signal.latest_authored_text:
            if _count_bulk_mail_indicators(signal.latest_authored_text) >= _BULK_MAIL_THRESHOLD:
                return EligibilityResult(eligible=False, reason=EligibilityReason.bulk_mail_content)

    # Fragment gate: reject too-short authored text (applies to all source types)
    authored = (signal.latest_authored_text or "").strip()
    if authored and len(authored) < _MIN_AUTHORED_TEXT_LENGTH:
        # Only reject if authored text is the sole text source (short text
        # with substantial prior_context is still valid)
        has_substantial_prior = bool(
            signal.prior_context_text
            and len(signal.prior_context_text.strip()) >= _MIN_AUTHORED_TEXT_LENGTH
        )
        if not has_substantial_prior:
            return EligibilityResult(eligible=False, reason=EligibilityReason.fragment_too_short)

    return EligibilityResult(eligible=True, reason=EligibilityReason.ok)
