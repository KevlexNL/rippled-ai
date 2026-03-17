"""Trigger patterns for commitment detection.

Organized as structured data. Each TriggerPattern entry specifies:
- A compiled regex
- The commitment trigger class
- Explicit vs implicit signal
- Base priority hint
- Which source types it applies to
- Whether it is a suppression pattern (strip before matching)

Source type values: 'meeting' | 'slack' | 'email'

Pattern sets:
1. Universal explicit markers   — all sources
2. Universal delivery/status    — all sources
3. Universal clarification      — all sources
4. Universal suppression        — all sources (run first)
5. Meeting-specific implicit    — meeting only
6. Slack-specific small         — slack only
7. Email-specific explicit      — email only
8. Email suppression            — email only (strip quoted chains)
"""
import re
from dataclasses import dataclass


ALL_SOURCES = ("meeting", "slack", "email")


@dataclass(frozen=True)
class TriggerPattern:
    name: str
    pattern: re.Pattern
    trigger_class: str
    is_explicit: bool
    base_priority_hint: str  # 'high' | 'medium' | 'low'
    applies_to: tuple[str, ...]
    suppression: bool = False  # True = strip these spans before running capture patterns
    base_confidence: float = 0.70


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _p(raw: str, flags: int = re.IGNORECASE) -> re.Pattern:
    return re.compile(raw, flags)


# ---------------------------------------------------------------------------
# Universal suppression patterns — run first, strip matching spans
# ---------------------------------------------------------------------------

SUPPRESSION_PATTERNS: list[TriggerPattern] = [
    TriggerPattern(
        name="hypothetical_marker",
        pattern=_p(r"\b(?:maybe|perhaps|could be|might)\b"),
        trigger_class="hypothetical",
        is_explicit=False,
        base_priority_hint="low",
        applies_to=ALL_SOURCES,
        suppression=True,
        base_confidence=0.20,
    ),
    TriggerPattern(
        name="conversational_filler",
        pattern=_p(r"^\s*(?:let me know|sounds good|okay|thanks|received|looks good|noted|understood|got it)[.!]?\s*$"),
        trigger_class="filler",
        is_explicit=False,
        base_priority_hint="low",
        applies_to=ALL_SOURCES,
        suppression=True,
        base_confidence=0.10,
    ),
    TriggerPattern(
        name="greeting",
        pattern=re.compile(r"^\s*(?:hi|hello|hey|good morning|good afternoon|good evening|dear)\b[^.\n]{0,30}[,.]?\s*$", re.IGNORECASE | re.MULTILINE),
        trigger_class="greeting",
        is_explicit=False,
        base_priority_hint="low",
        applies_to=ALL_SOURCES,
        suppression=True,
        base_confidence=0.05,
    ),
]

# Email-specific suppression (strip quoted reply chains)
EMAIL_SUPPRESSION_PATTERNS: list[TriggerPattern] = [
    TriggerPattern(
        name="email_quoted_line",
        pattern=re.compile(r"^>.*$", re.MULTILINE),
        trigger_class="quoted_content",
        is_explicit=False,
        base_priority_hint="low",
        applies_to=("email",),
        suppression=True,
        base_confidence=0.0,
    ),
    TriggerPattern(
        name="email_attribution_line",
        pattern=_p(r"On .{10,100}wrote:"),
        trigger_class="quoted_content",
        is_explicit=False,
        base_priority_hint="low",
        applies_to=("email",),
        suppression=True,
        base_confidence=0.0,
    ),
    TriggerPattern(
        name="email_forward_header",
        pattern=re.compile(r"^From:.*\nSent:.*\nTo:.*\n", re.MULTILINE | re.IGNORECASE),
        trigger_class="quoted_content",
        is_explicit=False,
        base_priority_hint="low",
        applies_to=("email",),
        suppression=True,
        base_confidence=0.0,
    ),
]


# ---------------------------------------------------------------------------
# Universal explicit commitment markers — all sources
# ---------------------------------------------------------------------------

UNIVERSAL_EXPLICIT_PATTERNS: list[TriggerPattern] = [
    TriggerPattern(
        name="i_will_contraction",
        pattern=_p(r"\bI'?ll\b.{0,80}"),
        trigger_class="explicit_self_commitment",
        is_explicit=True,
        base_priority_hint="medium",
        applies_to=ALL_SOURCES,
        base_confidence=0.75,
    ),
    TriggerPattern(
        name="i_will_full",
        pattern=_p(r"\bI will\b.{0,80}"),
        trigger_class="explicit_self_commitment",
        is_explicit=True,
        base_priority_hint="medium",
        applies_to=ALL_SOURCES,
        base_confidence=0.80,
    ),
    TriggerPattern(
        name="we_will",
        pattern=_p(r"\bwe'?ll\b.{0,80}"),
        trigger_class="explicit_collective_commitment",
        is_explicit=True,
        base_priority_hint="medium",
        applies_to=ALL_SOURCES,
        base_confidence=0.65,  # owner unresolved → lower confidence
    ),
    TriggerPattern(
        name="can_you_request",
        pattern=_p(r"\bcan you\b.{0,80}"),
        trigger_class="request_for_action",
        is_explicit=True,
        base_priority_hint="medium",
        applies_to=ALL_SOURCES,
        base_confidence=0.70,
    ),
    TriggerPattern(
        name="will_you_request",
        pattern=_p(r"\bwill you\b.{0,80}"),
        trigger_class="request_for_action",
        is_explicit=True,
        base_priority_hint="medium",
        applies_to=ALL_SOURCES,
        base_confidence=0.75,
    ),
    TriggerPattern(
        name="let_me_handle",
        pattern=_p(r"\b(?:let me|I'll handle|I'll take care of)\b.{0,80}"),
        trigger_class="explicit_self_commitment",
        is_explicit=True,
        base_priority_hint="medium",
        applies_to=ALL_SOURCES,
        base_confidence=0.75,
    ),
    TriggerPattern(
        name="obligation_needs_to",
        pattern=_p(r"\b(?:needs? to|has to|have to|must)\b.{0,80}"),
        trigger_class="obligation_marker",
        is_explicit=True,
        base_priority_hint="medium",
        applies_to=ALL_SOURCES,
        base_confidence=0.60,
    ),
    TriggerPattern(
        name="still_needs",
        pattern=_p(r"\bstill needs? to\b.{0,80}"),
        trigger_class="pending_obligation",
        is_explicit=True,
        base_priority_hint="medium",
        applies_to=ALL_SOURCES,
        base_confidence=0.65,
    ),
    TriggerPattern(
        name="follow_up_on",
        pattern=_p(r"\bfollow[- ]?up (?:on|with|regarding|about)\b.{0,80}"),
        trigger_class="follow_up_commitment",
        is_explicit=True,
        base_priority_hint="medium",
        applies_to=ALL_SOURCES,
        base_confidence=0.70,
    ),
]


# ---------------------------------------------------------------------------
# Universal delivery / status markers — all sources
# ---------------------------------------------------------------------------

UNIVERSAL_DELIVERY_PATTERNS: list[TriggerPattern] = [
    TriggerPattern(
        name="delivery_confirmation",
        pattern=_p(r"\b(?:just sent|just emailed|just shared|just uploaded|completed|finished|done)\b.{0,60}"),
        trigger_class="delivery_signal",
        is_explicit=True,
        base_priority_hint="low",
        applies_to=ALL_SOURCES,
        base_confidence=0.70,
    ),
    TriggerPattern(
        name="blocker_waiting",
        pattern=_p(r"\bstill waiting on\b.{0,80}"),
        trigger_class="blocker_signal",
        is_explicit=False,
        base_priority_hint="medium",
        applies_to=ALL_SOURCES,
        base_confidence=0.55,
    ),
    TriggerPattern(
        name="blocker_blocked",
        pattern=_p(r"\bblocked (?:on|by)\b.{0,80}"),
        trigger_class="blocker_signal",
        is_explicit=False,
        base_priority_hint="medium",
        applies_to=ALL_SOURCES,
        base_confidence=0.55,
    ),
]


# ---------------------------------------------------------------------------
# Universal clarification / ownership change — all sources
# ---------------------------------------------------------------------------

UNIVERSAL_CLARIFICATION_PATTERNS: list[TriggerPattern] = [
    TriggerPattern(
        name="owner_clarification",
        pattern=_p(r"\b(?:actually|instead|that'?s on me|I'?ll take that)\b.{0,80}"),
        trigger_class="owner_clarification",
        is_explicit=True,
        base_priority_hint="medium",
        applies_to=ALL_SOURCES,
        base_confidence=0.65,
    ),
    TriggerPattern(
        name="deadline_change",
        pattern=_p(r"\b(?:moving (?:this|that) to|push(?:ing)? (?:this|the deadline)|reschedul(?:e|ing)|push(?:ed)? (?:back|out))\b.{0,80}"),
        trigger_class="deadline_change",
        is_explicit=True,
        base_priority_hint="medium",
        applies_to=ALL_SOURCES,
        base_confidence=0.70,
    ),
]


# ---------------------------------------------------------------------------
# Meeting-specific implicit patterns
# ---------------------------------------------------------------------------

MEETING_PATTERNS: list[TriggerPattern] = [
    TriggerPattern(
        name="next_step_marker",
        pattern=_p(r"\bnext step(?:s)?\b.{0,80}"),
        trigger_class="implicit_next_step",
        is_explicit=False,
        base_priority_hint="medium",
        applies_to=("meeting",),
        base_confidence=0.55,
    ),
    TriggerPattern(
        name="action_item_marker",
        pattern=_p(r"\baction item\b.{0,80}"),
        trigger_class="implicit_next_step",
        is_explicit=False,
        base_priority_hint="medium",
        applies_to=("meeting",),
        base_confidence=0.60,
    ),
    TriggerPattern(
        name="from_our_side",
        pattern=_p(r"\bfrom our side\b.{0,80}"),
        trigger_class="implicit_unresolved_obligation",
        is_explicit=False,
        base_priority_hint="medium",
        applies_to=("meeting",),
        base_confidence=0.50,
    ),
    TriggerPattern(
        name="someone_should",
        pattern=_p(r"\bsomeone (?:should|needs? to|has to)\b.{0,80}"),
        trigger_class="implicit_unresolved_obligation",
        is_explicit=False,
        base_priority_hint="medium",
        applies_to=("meeting",),
        base_confidence=0.45,
    ),
    TriggerPattern(
        name="who_is_going_to",
        pattern=_p(r"\bwho'?s (?:going to|gonna)\b.{0,80}"),
        trigger_class="implicit_unresolved_obligation",
        is_explicit=False,
        base_priority_hint="medium",
        applies_to=("meeting",),
        base_confidence=0.45,
    ),
    TriggerPattern(
        name="can_someone",
        pattern=_p(r"\bcan someone\b.{0,80}"),
        trigger_class="implicit_unresolved_obligation",
        is_explicit=False,
        base_priority_hint="medium",
        applies_to=("meeting",),
        base_confidence=0.45,
    ),
    TriggerPattern(
        name="we_should",
        pattern=_p(r"\bwe should\b.{0,80}"),
        trigger_class="implicit_next_step",
        is_explicit=False,
        base_priority_hint="medium",
        applies_to=("meeting",),
        base_confidence=0.45,
    ),
    TriggerPattern(
        name="lets_have_someone",
        pattern=_p(r"\blet'?s have \w+ .{0,60}"),
        trigger_class="implicit_next_step",
        is_explicit=False,
        base_priority_hint="medium",
        applies_to=("meeting",),
        base_confidence=0.50,
    ),
]


# ---------------------------------------------------------------------------
# Slack-specific small commitment patterns
# ---------------------------------------------------------------------------

SLACK_PATTERNS: list[TriggerPattern] = [
    TriggerPattern(
        name="slack_ill_check",
        pattern=_p(r"^\s*(?:I'?ll check|let me (?:look|check|confirm|look into it))\s*[.!]?\s*$"),
        trigger_class="small_practical_commitment",
        is_explicit=True,
        base_priority_hint="low",
        applies_to=("slack",),
        base_confidence=0.55,
    ),
    TriggerPattern(
        name="slack_ill_look_into",
        pattern=_p(r"\bI'?ll (?:look into|ask|check on|follow up on)\b.{0,60}"),
        trigger_class="small_practical_commitment",
        is_explicit=True,
        base_priority_hint="low",
        applies_to=("slack",),
        base_confidence=0.60,
    ),
    TriggerPattern(
        name="slack_accepted_request",
        pattern=_p(r"^\s*(?:yep|yes|sure|will do|on it|consider it done)[,.]?\s*$"),
        trigger_class="accepted_request",
        is_explicit=True,
        base_priority_hint="low",
        applies_to=("slack",),
        base_confidence=0.40,  # requires thread context; elevated if parent has request language
    ),
    TriggerPattern(
        name="slack_delivery_done",
        pattern=_p(r"^\s*(?:done|sent|handled)[.!]?\s*$"),
        trigger_class="delivery_signal",
        is_explicit=True,
        base_priority_hint="low",
        applies_to=("slack",),
        base_confidence=0.50,
    ),
]


# ---------------------------------------------------------------------------
# Email-specific explicit patterns
# ---------------------------------------------------------------------------

EMAIL_PATTERNS: list[TriggerPattern] = [
    TriggerPattern(
        name="email_ill_revise",
        pattern=_p(r"\bI'?ll (?:revise|update|amend) (?:and|the).{0,60}"),
        trigger_class="explicit_self_commitment",
        is_explicit=True,
        base_priority_hint="medium",
        applies_to=("email",),
        base_confidence=0.80,
    ),
    TriggerPattern(
        name="email_ill_introduce",
        pattern=_p(r"\bI'?ll (?:introduce|connect you|loop in|cc)\b.{0,60}"),
        trigger_class="explicit_self_commitment",
        is_explicit=True,
        base_priority_hint="medium",
        applies_to=("email",),
        base_confidence=0.80,
    ),
    TriggerPattern(
        name="email_please_find_attached",
        pattern=_p(r"\b(?:please find attached|attached (?:is|are)|I'?ve attached)\b.{0,80}"),
        trigger_class="delivery_signal",
        is_explicit=True,
        base_priority_hint="low",
        applies_to=("email",),
        base_confidence=0.75,
    ),
    TriggerPattern(
        name="email_deadline_push",
        pattern=_p(r"\b(?:I need to move|let'?s push|push this|reschedule) (?:this|the meeting|our call|the deadline).{0,60}"),
        trigger_class="deadline_change",
        is_explicit=True,
        base_priority_hint="medium",
        applies_to=("email",),
        base_confidence=0.75,
    ),
]


# ---------------------------------------------------------------------------
# Combined capture pattern set (by source type)
# ---------------------------------------------------------------------------

ALL_CAPTURE_PATTERNS: list[TriggerPattern] = (
    UNIVERSAL_EXPLICIT_PATTERNS
    + UNIVERSAL_DELIVERY_PATTERNS
    + UNIVERSAL_CLARIFICATION_PATTERNS
    + MEETING_PATTERNS
    + SLACK_PATTERNS
    + EMAIL_PATTERNS
)


def get_patterns_for_source(source_type: str) -> list[TriggerPattern]:
    """Return capture patterns applicable to the given source type."""
    return [p for p in ALL_CAPTURE_PATTERNS if source_type in p.applies_to]


def get_suppression_patterns_for_source(source_type: str) -> list[TriggerPattern]:
    """Return suppression patterns applicable to the given source type."""
    base = [p for p in SUPPRESSION_PATTERNS if source_type in p.applies_to]
    if source_type == "email":
        base = EMAIL_SUPPRESSION_PATTERNS + base
    return base
