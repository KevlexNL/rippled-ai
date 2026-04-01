"""Auto-close configuration logic — Phase D2.

Resolves the auto-close inactivity window for a commitment based on
user configuration, with a hierarchical fallback:

    commitment-class-specific > internal/external > system default

Default system values (hours):
    internal:         48h (2 days)
    external:        120h (5 days)
    big_promise:     168h (7 days)
    small_commitment: 48h (2 days)

Public API:
    get_auto_close_hours(commitment, user_config=None) -> float
    merge_auto_close_defaults(user_config) -> dict
    validate_auto_close_config(config) -> None  (raises ValueError on invalid)
"""
from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# System defaults (hours)
# ---------------------------------------------------------------------------

_SYSTEM_DEFAULTS: dict[str, float] = {
    "internal_hours": 48,
    "external_hours": 120,
    "big_promise_hours": 168,
    "small_commitment_hours": 48,
}

# Valid keys for user config
VALID_AUTO_CLOSE_KEYS: set[str] = set(_SYSTEM_DEFAULTS.keys())

# Validation bounds
_MIN_HOURS = 1
_MAX_HOURS = 720  # 30 days


# ---------------------------------------------------------------------------
# Resolution hierarchy
# ---------------------------------------------------------------------------

# Map priority_class → config key
_CLASS_KEY_MAP: dict[str, str] = {
    "big_promise": "big_promise_hours",
    "small_commitment": "small_commitment_hours",
}


def get_auto_close_hours(
    commitment: Any,
    user_config: dict[str, float] | None = None,
) -> float:
    """Resolve auto-close window in hours for a commitment.

    Resolution order:
        1. commitment-class-specific (big_promise_hours / small_commitment_hours)
        2. internal/external (internal_hours / external_hours)
        3. system default (commitment.auto_close_after_hours)

    Args:
        commitment: Duck-typed Commitment with priority_class, context_type,
            and auto_close_after_hours attributes.
        user_config: Optional dict from user_settings.auto_close_config.

    Returns:
        Float hours for the auto-close window.
    """
    system_default = float(getattr(commitment, "auto_close_after_hours", 48))

    if not user_config:
        return system_default

    # Step 1: Try commitment-class-specific key
    priority_class = getattr(commitment, "priority_class", None)
    if priority_class:
        class_key = _CLASS_KEY_MAP.get(priority_class)
        if class_key and class_key in user_config:
            return float(user_config[class_key])

    # Step 2: Try internal/external key
    context_type = getattr(commitment, "context_type", None)
    if context_type == "external" and "external_hours" in user_config:
        return float(user_config["external_hours"])
    if context_type == "internal" and "internal_hours" in user_config:
        return float(user_config["internal_hours"])

    # Step 3: Fall back to system default
    return system_default


# ---------------------------------------------------------------------------
# Merge defaults (for API GET response)
# ---------------------------------------------------------------------------

def merge_auto_close_defaults(user_config: dict[str, float] | None) -> dict[str, float]:
    """Return full config with user overrides merged over system defaults.

    Only canonical keys appear in the result.
    """
    result = dict(_SYSTEM_DEFAULTS)
    if user_config:
        for key in VALID_AUTO_CLOSE_KEYS:
            if key in user_config:
                result[key] = float(user_config[key])
    return result


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_auto_close_config(config: dict[str, float]) -> None:
    """Validate auto-close config values. Raises ValueError on invalid input."""
    for key, value in config.items():
        if key not in VALID_AUTO_CLOSE_KEYS:
            msg = (
                f"Unknown auto-close config key: {key!r}. "
                f"Valid keys: {sorted(VALID_AUTO_CLOSE_KEYS)}"
            )
            raise ValueError(msg)
        if not isinstance(value, (int, float)) or value < _MIN_HOURS or value > _MAX_HOURS:
            msg = (
                f"Auto-close window for {key!r} must be between "
                f"{_MIN_HOURS} and {_MAX_HOURS} hours, got {value}"
            )
            raise ValueError(msg)
