"""Observation window logic — Phase 06.

Determines whether a commitment has exited its silent observation window
and whether it should surface early (high-consequence external exception).

Default observation windows (per brief):
    - slack_internal:   2  working hours
    - email_internal:   24 working hours (1 working day)
    - email_external:   48 working hours (2 working days)
    - meeting_internal: 24 working hours (1 working day)
    - meeting_external: 48 working hours (2 working days)

"Working hours" approximation: we multiply by 1.4 to convert working hours
to calendar hours (assuming ~8 working hours / ~11.2 calendar hours per day).
This keeps the math simple and configurable.

Public API:
    default_window_hours(source_type) -> float
    is_observable(commitment) -> bool
    should_surface_early(commitment) -> bool
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.services.commitment_classifier import is_external


# ---------------------------------------------------------------------------
# Default window hours (calendar hours, not working hours)
# ---------------------------------------------------------------------------

# Working-to-calendar conversion factor (~8 working hrs per ~11.2 calendar hrs)
_WORK_TO_CALENDAR = 1.4

_DEFAULT_WINDOWS: dict[str, float] = {
    "slack":             2.0 * _WORK_TO_CALENDAR,   # ~2.8h
    "slack_internal":    2.0 * _WORK_TO_CALENDAR,
    "email":             24.0 * _WORK_TO_CALENDAR,  # ~33.6h
    "email_internal":    24.0 * _WORK_TO_CALENDAR,
    "email_external":    48.0 * _WORK_TO_CALENDAR,  # ~67.2h
    "meeting":           24.0 * _WORK_TO_CALENDAR,
    "meeting_internal":  24.0 * _WORK_TO_CALENDAR,
    "meeting_external":  48.0 * _WORK_TO_CALENDAR,
}

_FALLBACK_WINDOW_HOURS = 24.0 * _WORK_TO_CALENDAR  # email_internal default

# The 5 canonical keys users can configure (matches brief spec).
VALID_WINDOW_KEYS: set[str] = {
    "slack",
    "email_internal",
    "email_external",
    "meeting_internal",
    "meeting_external",
}

# Canonical defaults keyed by VALID_WINDOW_KEYS (for merge_with_defaults).
_CANONICAL_DEFAULTS: dict[str, float] = {
    "slack":             2.0 * _WORK_TO_CALENDAR,
    "email_internal":    24.0 * _WORK_TO_CALENDAR,
    "email_external":    48.0 * _WORK_TO_CALENDAR,
    "meeting_internal":  24.0 * _WORK_TO_CALENDAR,
    "meeting_external":  48.0 * _WORK_TO_CALENDAR,
}


def default_window_hours(source_type: str, external: bool = False) -> float:
    """Return the default observation window in calendar hours.

    Args:
        source_type: Source type string (e.g., 'email', 'slack', 'meeting').
        external: If True, prefer the external variant of the window.

    Returns:
        Float calendar hours for the default observation window.
    """
    # Normalise to lowercase and strip extra noise
    st = (source_type or "").lower().strip()

    # Try exact match first (e.g., 'email_external')
    if external:
        external_key = f"{st}_external"
        if external_key in _DEFAULT_WINDOWS:
            return _DEFAULT_WINDOWS[external_key]

    if st in _DEFAULT_WINDOWS:
        return _DEFAULT_WINDOWS[st]

    # Try partial match (e.g., 'slack_workspace' → 'slack')
    for key in _DEFAULT_WINDOWS:
        if key in st or st in key:
            return _DEFAULT_WINDOWS[key]

    return _FALLBACK_WINDOW_HOURS


def get_window_hours(
    source_type: str,
    external: bool = False,
    user_config: dict[str, float] | None = None,
) -> float:
    """Return observation window in calendar hours, checking user config first.

    Args:
        source_type: Source type string (e.g., 'email', 'slack', 'meeting').
        external: If True, prefer the external variant of the window.
        user_config: Optional dict from user_settings.observation_window_config.
            Keys are canonical names (slack, email_internal, etc.). Values are
            calendar hours. Missing keys fall back to system defaults.

    Returns:
        Float calendar hours for the observation window.
    """
    if user_config:
        # Build the canonical key the user would have set
        st = (source_type or "").lower().strip()
        if external:
            key = f"{st}_external"
        else:
            # Bare source type (e.g., "slack") or internal variant
            internal_key = f"{st}_internal"
            key = internal_key if internal_key in user_config else st

        if key in user_config:
            return float(user_config[key])

    # Fall back to system defaults
    return default_window_hours(source_type, external)


def merge_with_defaults(user_config: dict[str, float] | None) -> dict[str, float]:
    """Return a full config dict with user overrides merged over system defaults.

    Only canonical keys (VALID_WINDOW_KEYS) appear in the result.
    """
    result = dict(_CANONICAL_DEFAULTS)
    if user_config:
        for key in VALID_WINDOW_KEYS:
            if key in user_config:
                result[key] = float(user_config[key])
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def is_observable(commitment) -> bool:
    """Return True if the commitment is still in its observation window.

    An observable commitment should NOT be surfaced yet — it is still in the
    silent observation period waiting for later signals.

    Logic:
    - If observe_until is set: window is open while now < observe_until.
    - If observe_until is not set: window is considered closed (ready to surface).
    """
    observe_until = getattr(commitment, "observe_until", None)
    if observe_until is None:
        return False  # No window set → ready to surface

    now = datetime.now(timezone.utc)

    # Handle naive datetimes in tests
    if observe_until.tzinfo is None:
        observe_until = observe_until.replace(tzinfo=timezone.utc)

    return now < observe_until


def should_surface_early(commitment) -> bool:
    """Return True if the commitment should bypass the observation window.

    Exceptions per the brief: highly consequential external promises may surface
    earlier even before the observation window completes.

    Criteria for early surfacing:
    - commitment is external (context_type == 'external' or source inference)
    - commitment has an explicit resolved_deadline
    - confidence_commitment ≥ 0.75 (high confidence this is a real commitment)

    All three must be true to trigger early surfacing.
    """
    if not is_observable(commitment):
        return False  # Already past window — no need for early exception

    external = is_external(commitment)
    if not external:
        return False

    # Must have an explicit deadline
    if getattr(commitment, "resolved_deadline", None) is None:
        return False

    # Must have high commitment confidence
    conf = float(getattr(commitment, "confidence_commitment", None) or 0)
    return conf >= 0.75
