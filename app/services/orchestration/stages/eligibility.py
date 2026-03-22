"""Stage 0 — Eligibility check (deterministic, no LLM).

Prevents wasteful processing of unsupported or unusable signals.
"""

from __future__ import annotations

from app.connectors.shared.normalized_signal import NormalizedSignal
from app.services.orchestration.config import get_orchestration_config
from app.services.orchestration.contracts import EligibilityReason, EligibilityResult


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

    return EligibilityResult(eligible=True, reason=EligibilityReason.ok)
