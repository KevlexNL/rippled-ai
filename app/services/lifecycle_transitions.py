"""Lifecycle transition rules — WO-RIPPLED-LIFECYCLE-STATE-ALIGNMENT.

Defines and enforces allowed state transitions for commitments.

Transition map:
    proposed → needs_clarification | active | confirmed | discarded
    needs_clarification → active | discarded | dormant
    active | confirmed → in_progress | delivered | dormant | discarded
    in_progress → delivered | canceled | dormant
    delivered → completed | closed | active (reopened)
    completed → closed
    canceled → closed
    closed → active (reopened)
    dormant → active | discarded
    discarded → (terminal — no transitions out)
"""
from __future__ import annotations

# Allowed transitions: from_state → set of valid to_states
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "proposed": {"needs_clarification", "active", "confirmed", "discarded"},
    "needs_clarification": {"active", "discarded", "dormant"},
    "active": {"in_progress", "delivered", "dormant", "discarded"},
    "confirmed": {"in_progress", "delivered", "dormant", "discarded"},
    "in_progress": {"delivered", "canceled", "dormant"},
    "delivered": {"completed", "closed", "active"},
    "completed": {"closed"},
    "canceled": {"closed"},
    "closed": {"active"},
    "dormant": {"active", "discarded"},
    "discarded": set(),  # terminal
}


def is_transition_allowed(from_state: str, to_state: str) -> bool:
    """Check whether a lifecycle transition is allowed.

    Args:
        from_state: Current lifecycle state value.
        to_state: Desired lifecycle state value.

    Returns:
        True if the transition is allowed, False otherwise.
    """
    allowed = ALLOWED_TRANSITIONS.get(from_state, set())
    return to_state in allowed
