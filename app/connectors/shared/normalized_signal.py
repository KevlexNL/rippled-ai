"""Shared NormalizedSignal contract — WO-RIPPLED-NORMALIZED-SIGNAL-CONTRACT.

All connectors must produce a NormalizedSignal before hitting the detection
pipeline. This is an in-memory contract, not a DB model.
"""
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Participant:
    """A person involved in a signal event."""

    name: str | None = None
    email: str | None = None
    role: str | None = None  # "speaker", "sender", "recipient", "cc", "attendee", etc.


@dataclass
class NormalizedSignal:
    """Canonical input contract for the detection pipeline.

    Every connector normalizes its platform-specific payload into this
    structure before detection runs.
    """

    signal_id: str  # maps to source_item.external_id
    source_type: str  # email | slack | meeting
    source_thread_id: str | None  # nullable for non-threaded sources
    source_message_id: str | None
    occurred_at: datetime  # when the event happened
    authored_at: datetime  # when the text was authored
    actor_participants: list[Participant]  # who authored/spoke
    addressed_participants: list[Participant]  # direct recipients / audience
    visible_participants: list[Participant]  # all participants in context
    latest_authored_text: str  # ONLY current authored block, no quoted history
    prior_context_text: str | None  # bounded quoted/thread history, for linking only
    attachments: list[dict] = field(default_factory=list)
    links: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
