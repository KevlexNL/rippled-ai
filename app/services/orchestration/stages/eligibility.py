"""Stage 0 — Eligibility check (deterministic, no LLM).

Prevents wasteful processing of unsupported or unusable signals.
"""

from __future__ import annotations

import re

from app.connectors.shared.normalized_signal import NormalizedSignal
from app.services.orchestration.config import get_orchestration_config
from app.services.orchestration.contracts import EligibilityReason, EligibilityResult

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

    # Content-based bulk-mail filter (email only)
    if signal.source_type == "email" and signal.latest_authored_text:
        if _count_bulk_mail_indicators(signal.latest_authored_text) >= _BULK_MAIL_THRESHOLD:
            return EligibilityResult(eligible=False, reason=EligibilityReason.bulk_mail_content)

    return EligibilityResult(eligible=True, reason=EligibilityReason.ok)
