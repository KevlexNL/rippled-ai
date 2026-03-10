# Phase 03 — Detection Pipeline: Interpretation

**Phase:** 03-detection
**Date:** 2026-03-10
**Status:** Awaiting Kevin approval before implementation

---

## 1. How I Understand the Detection Pipeline

### Core philosophy

Detection is not the place where Rippled decides what matters. It is the place where Rippled captures what _might_ matter. The brief is explicit: **preserve ambiguity, cast a broad net, produce candidates not commitments**.

This drives every design decision below:
- Err toward capture over suppression
- Never resolve ownership, deadline, or commitment strength at detection time
- Write structured signals with enough context for later stages to decide
- Be source-aware: meetings, Slack, and email have different noise profiles and signal patterns

### Two-layer detection strategy

The brief calls for **deterministic heuristics + model assistance**. For MVP, I plan to implement deterministic-only detection (regex + keyword matching) with the architecture designed to slot in model-assisted calls later.

**Deterministic heuristics handle:**
- Explicit future-action markers ("I'll", "I will", "we'll", "can you", "let me")
- Obligation markers ("needs to", "still needs", "has to", "should get sent")
- Timing markers attached to action language ("by Monday", "tomorrow", "later today")
- Delivery/status markers ("sent", "done", "handled", "waiting on")
- Clarification/change markers ("actually", "instead", "moving this to", "I'll take that")
- Suppression patterns (email quoted text, pure hypotheticals, conversational fillers)

**Model assistance (future, not MVP):**
- Implicit obligation interpretation when deterministic patterns don't match
- Short Slack replies understood in thread context
- Differentiating suggestion from commitment in ambiguous cases
- Evaluating whether a statement creates real expectation

### Broad net, controlled noise

The suppression rules keep noise controlled without being too aggressive:
- Suppress: pure hypotheticals ("maybe", "could", "might"), historical statements ("I sent it yesterday"), conversational fillers ("sounds good", "okay")
- Capture despite low confidence: "I'll try", small Slack commitments, "will do" when context object is clear
- Never suppress based on size alone — "I'll check" is always captured

### Preserve ambiguity principle

Detection never assigns `resolved_owner` or `resolved_deadline` — those live on `commitments`. What detection does assign:
- `trigger_class` — what category of commitment signal this is (e.g., `explicit_self_commitment`, `implicit_next_step`)
- `is_explicit` — grammatically explicit vs implied
- `priority_hint` — a lightweight `high/medium/low` based on external context + due date presence
- `commitment_class_hint` — `big_promise | small_commitment | unknown` based on the three-factor priority order from the brief

---

## 2. Planned Service Structure: `app/services/detection/`

```
app/services/detection/
├── __init__.py          # exports: run_detection(source_item_id, db)
├── detector.py          # orchestration layer
├── patterns.py          # trigger patterns organized by source type
└── context.py           # context window extraction per source type
```

### `detector.py` — Orchestration

**Single public function:** `run_detection(source_item_id: str, db: Session) -> list[CommitmentCandidate]`

Responsibilities:
1. Load the `SourceItem` from DB by ID
2. Determine source type (`meeting | slack | email`)
3. Normalize content: strip quoted email text, segment meeting transcript by speaker turn, preserve Slack thread references
4. Run applicable trigger patterns from `patterns.py` against the normalized content
5. For each pattern match above the noise threshold: extract context window via `context.py`
6. Create a `CommitmentCandidate` row per signal (individual savepoints — one bad insert doesn't abort all)
7. Set `observe_until` on each candidate based on source type + internal/external context
8. Return list of created candidates (for task logging)

**Design constraints:**
- Synchronous function (Celery workers are sync by default)
- Uses its own SQLAlchemy `Session` (not `AsyncSession`) — the task opens a sync session
- Failures per candidate are caught and logged; the item is not re-queued for one bad candidate
- Full failure of `run_detection` triggers Celery retry (up to 3 attempts)

### `patterns.py` — Trigger Patterns

Organized as structured data, not scattered logic. Each pattern entry has:

```python
@dataclass
class TriggerPattern:
    pattern: re.Pattern          # compiled regex
    trigger_class: str           # detection category from the brief's taxonomy
    is_explicit: bool            # explicit vs implicit signal
    base_priority_hint: str      # default priority before context elevation
    applies_to: list[str]        # source types this pattern applies to
    suppression: bool = False    # True = this is a suppression pattern (strip these spans first)
```

Pattern sets by source type:

**All sources — explicit markers:**
- `r"\bI'?ll\b.{0,80}"` → `explicit_self_commitment`, explicit=True, priority=medium
- `r"\bI will\b.{0,80}"` → `explicit_self_commitment`, explicit=True, priority=medium
- `r"\bwe'?ll\b.{0,80}"` → `explicit_collective_commitment`, explicit=True, priority=medium (unresolved owner)
- `r"\bcan you\b.{0,80}"` → `request_for_action`, explicit=True, priority=medium
- `r"\bwill you\b.{0,80}"` → `request_for_action`, explicit=True, priority=medium
- `r"\b(?:let me|I'll handle|I'll take care)\b.{0,80}"` → `explicit_self_commitment`, explicit=True

**All sources — delivery/status:**
- `r"\b(?:sent|done|handled|just sent|just emailed|completed)\b"` → `delivery_signal`, explicit=True, priority=low (needs context check)
- `r"\bstill waiting on\b.{0,80}"` → `blocker_signal`, explicit=False, priority=medium
- `r"\bblocked (?:on|by)\b.{0,80}"` → `blocker_signal`, explicit=False, priority=medium

**All sources — clarification triggers:**
- `r"\b(?:actually|instead|that's on me|I'll take that)\b.{0,80}"` → `owner_clarification`, explicit=True
- `r"\b(?:moving (?:this|that) to|push(?:ing)? (?:this|the deadline))\b.{0,80}"` → `deadline_change`, explicit=True

**Meeting-specific — implicit:**
- `r"\bnext step\b.{0,80}"` → `implicit_next_step`, explicit=False, priority=medium
- `r"\bfrom our side\b.{0,80}"` → `implicit_unresolved_obligation`, explicit=False
- `r"\bsomeone (?:should|needs to)\b.{0,80}"` → `implicit_unresolved_obligation`, explicit=False
- `r"\b(?:we should|let's have \w+ )\b.{0,80}"` → `implicit_next_step`, explicit=False

**Slack-specific — small practical:**
- `r"^\s*(?:I'?ll check|let me (?:look|check|confirm))\s*$"` → `small_practical_commitment`, low priority, still captured
- `r"^\s*(?:yep|yes|sure|will do)[,.]?\s*$"` → `accepted_request`, explicit=True (requires thread context for meaning)

**Email-specific — suppression (run first, strip these spans before detection):**
- `r"^>.*$"` (per line) → quoted chain text, suppression=True
- `r"On .+wrote:"` → email attribution line, suppression=True
- `r"^From:.*\nSent:.*\nTo:.*\n"` (multiline) → forward header, suppression=True

**Suppression patterns (all sources):**
- `r"\b(?:maybe|perhaps|could be|might)\b"` → hypothetical marker (lower confidence, not full suppress)
- `r"\b(?:let me know|sounds good|okay|thanks|received|looks good)\b"` → conversational filler, suppress standalone

### `context.py` — Context Window Extraction

**Public function:** `extract_context(item: SourceItem, trigger_span: str, trigger_start: int) -> dict`

Returns a dict stored in `context_window` JSONB:

```python
{
    "trigger_text": str,           # the exact matched span
    "trigger_start": int,          # char offset in normalized content
    "trigger_end": int,
    "pre_context": str,            # text before trigger
    "post_context": str,           # text after trigger
    "source_type": str,
    # Source-type-specific fields:
    "thread_parent": str | None,   # Slack: parent message text
    "speaker_turns": list | None,  # Meeting: surrounding speaker turns
    "email_direction": str | None, # Email: inbound | outbound
    "has_external_recipient": bool | None,  # Email/Meeting
    "sender": str | None,
}
```

**Per-source context extraction rules:**

**Meeting:** Extract 1–3 speaker turns before and after the trigger turn. Preserve speaker labels and timestamps. Flag if speaker attribution looks uncertain (e.g., transcript says "[inaudible]" or "[crosstalk]" near the trigger).

**Slack:** Extract parent message if the trigger is a thread reply. Extract 2–3 neighboring messages in the same thread. Include sender, mentions, and channel metadata.

**Email:** Extract the current message body (after quoted text is stripped). Include sender, recipients, direction, and whether any recipient is flagged as `is_external_participant`. Do NOT include prior email chain body — that's the quoted text suppression.

---

## 3. How the Celery Task Triggers Detection

### Current state (Phase 02 stub)

`app/tasks.py` already defines:
```python
@celery_app.task(name="app.tasks.detect_commitments")
def detect_commitments(source_item_id: str) -> dict:
    """Detect commitments from a source item. Implemented in Phase 03."""
    return {"source_item_id": source_item_id, "status": "queued"}
```

The Phase 02 ingestion route (`POST /source-items`) already calls:
```python
detect_commitments.delay(source_item_id)
```

### Phase 03 implementation

Phase 03 replaces the stub body with real detection. The task will:

```python
@celery_app.task(
    name="app.tasks.detect_commitments",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def detect_commitments(self, source_item_id: str) -> dict:
    from app.services.detection import run_detection
    from app.db.session import get_sync_session  # sync session for Celery

    try:
        with get_sync_session() as db:
            candidates = run_detection(source_item_id, db)
        return {
            "source_item_id": source_item_id,
            "status": "complete",
            "candidates_created": len(candidates),
        }
    except Exception as exc:
        raise self.retry(exc=exc)
```

**Session handling:** The Celery worker runs synchronously. Phase 02 set up `AsyncSessionLocal` for FastAPI routes. Phase 03 needs a parallel **sync session factory** (`get_sync_session`) using `create_engine` + `sessionmaker` (not async). This means `app/db/engine.py` gets a sync counterpart.

**Savepoints for candidate insertion:** Inside `run_detection`, each candidate insert uses a savepoint:
```python
with db.begin_nested():  # SAVEPOINT
    db.add(candidate)
    db.flush()
```
This ensures one bad candidate insert (e.g., a constraint violation) doesn't roll back all candidates from the same source item.

**Fire-and-forget contract preserved:** The ingestion route does not wait for detection. The route returns `201` as soon as the item is written; detection happens asynchronously.

---

## 4. Detection Output: CommitmentCandidate Records

### Schema gap (requires Phase 03 migration)

The current `commitment_candidates` table has minimal columns:
- `id`, `user_id`, `originating_item_id`, `raw_text`, `detection_explanation`, `confidence_score`, `was_promoted`, `was_discarded`, `discard_reason`

The brief requires candidates to carry:
- Trigger class (category from the 13-category taxonomy)
- Explicit vs implicit flag
- Priority hint (`high | medium | low`)
- Commitment class hint (`big_promise | small_commitment | unknown`)
- Context window (surrounding text)
- Observation recommendation and `observe_until` timestamp
- Re-analysis flag (primarily for meetings)
- Linked entities (people/dates mentioned near trigger)

**Proposed migration — new columns on `commitment_candidates`:**

| Column | Type | Purpose |
|--------|------|---------|
| `trigger_class` | `TEXT` | Detection category (one of the 13 classes from the brief) |
| `is_explicit` | `BOOLEAN` | True = explicit commitment language; False = implicit |
| `priority_hint` | `TEXT` CHECK IN ('high','medium','low') | Initial priority signal for downstream |
| `commitment_class_hint` | `TEXT` CHECK IN ('big_promise','small_commitment','unknown') | Big vs small hint |
| `context_window` | `JSONB` | Surrounding text, speaker turns, thread context |
| `linked_entities` | `JSONB` | People, dates, deliverables detected in the trigger span |
| `observe_until` | `TIMESTAMPTZ` | When observation window closes for this candidate |
| `flag_reanalysis` | `BOOLEAN` DEFAULT false | Transcript quality may affect interpretation |
| `source_type` | `TEXT` | Denormalized from source_item for query efficiency |

**Why denormalize `source_type`?** Detection queries will frequently need to group/filter candidates by source type without joining to source_items. The denormalization is intentional.

**`raw_text` usage:** The existing `raw_text` column holds the exact trigger span (quoted text that matched). This maps to "quoted trigger text or span" in the brief.

**`detection_explanation` usage:** Holds the human-readable reason why detection fired (e.g., "Matched explicit self-commitment pattern: 'I'll send'. External recipient detected, raising priority to high.").

**`confidence_score` usage:** Maps to the brief's "initial confidence hint". Deterministic patterns set this at 0.7–0.9 for explicit matches, 0.4–0.6 for implicit, and lower for edge cases ("I'll try", "will do" without clear object).

### What gets written per candidate

For each pattern match, the detector writes one `CommitmentCandidate` row with:

```python
CommitmentCandidate(
    user_id=source_item.user_id,
    originating_item_id=source_item.id,
    source_type=source_item.source_type,
    raw_text=trigger_span,
    trigger_class=pattern.trigger_class,
    is_explicit=pattern.is_explicit,
    detection_explanation=f"Matched pattern '{pattern.name}'. {context_notes}",
    confidence_score=computed_confidence,
    priority_hint=computed_priority,
    commitment_class_hint=computed_class_hint,
    context_window=context_dict,
    linked_entities=extracted_entities,
    observe_until=computed_observe_until,
    flag_reanalysis=is_reanalysis_flagged,
)
```

One source item can produce multiple candidates (e.g., a meeting transcript with three commitment statements → three candidates). Each candidate is independent.

---

## 5. Source-Specific Pattern Differences

### Meeting detection

**What's different:**
- Content arrives as a transcript — multiple speaker turns, often timestamped
- Attribution uncertainty is real: "[Speaker 1]", "[inaudible]", overlapping speech
- Broader implicit detection is warranted vs email — the brief explicitly says this
- Collective language ("we should", "from our side", "next step is") is especially common and should be captured

**Key behaviors:**
- Segment by speaker turn before running patterns — match against turn content, not the whole transcript blob
- Preserve speaker label in `context_window.speaker_turns`
- `flag_reanalysis = True` when: speaker label is generic ("Speaker 1"), "[inaudible]" appears within 30 chars of trigger, or "[crosstalk]" appears near trigger
- `observe_until` = now + 1–2 working days (internal) or 2–3 working days (external)
- Priority elevated if meeting includes external participants (`source_item.is_external_participant = true`)

**Patterns that apply meeting-only:**
- Next-step markers: `"next step is"`, `"action item"`, `"from our side"`
- Ownership gap markers: `"can someone"`, `"who's going to"`, `"someone needs to"`
- Group consensus markers: `"we should"`, `"let's have [name]"`

### Slack detection

**What's different:**
- Messages are short — context comes from thread, not the message itself
- Small commitments ("I'll check", "yep, I'll handle it") are first-class signals
- Thread parent is critical: a reply of "will do" is meaningless without the parent message
- `is_quoted_content` on SourceItem is never true for Slack (no quote stripping needed)
- No re-analysis flagging needed (Slack messages are self-authored, not transcribed)

**Key behaviors:**
- Always pull thread parent via `thread_id` from `source_items` and include in `context_window.thread_parent`
- Short messages (< 50 chars) should still match if they hit an explicit pattern
- "Yep", "sure", "will do", "on it" — detect as `accepted_request` if thread parent contains request language, otherwise suppress or mark very low confidence
- `observe_until` = now + 2 working hours (Slack resolves fastest)
- No priority elevation for external context (Slack is inherently internal for MVP scope)

**Patterns that apply Slack-only:**
- Short acceptance phrases: `"^yep$"`, `"^sure$"`, `"^on it$"`, `"^will do$"` (only with thread context check)
- Status updates: `"^done\.$"`, `"^sent\.$"`, `"^handled\.$"` (delivery_signal, needs thread context)
- Practical small: `"let me check"`, `"I'll look into"`, `"I'll ask them"` (even standalone)

### Email detection

**What's different:**
- Quoted chain text must be stripped before any pattern matching — failure to do this is the biggest email detection failure mode
- Direction matters: outbound email + delivery statement = strong `delivery_signal`
- `is_external_participant` on recipients → elevate priority, `commitment_class_hint` bias toward `big_promise`
- Email tends toward more formal commitment language — explicit patterns match more reliably
- Modifying signals are common: "Actually, let's move that to next week" is a `deadline_change`

**Key behaviors:**
- Run suppression patterns first (strip all quoted text from `content_normalized` before matching)
- Check `source_item.direction` — outbound email with delivery verb → `delivery_signal` with higher confidence
- Check `source_item.recipients` for `is_external` flags → elevate priority if any external recipient
- `observe_until` = now + 1 working day (internal) or 2–3 working days (external)
- `flag_reanalysis = False` always (email is written, not transcribed)

**Patterns that apply email-only:**
- Revision promises: `"I'll revise and"`, `"let me revise"`, `"I'll update and send"`
- Introduction promises: `"I'll introduce"`, `"I'll connect you"`
- Delivery completion: `"attached is"`, `"please find attached"` → `delivery_signal` when combined with prior commitment context
- Reply chain modifiers: `"I need to move this"`, `"let's push to"` → `deadline_change`

### Cross-source observation window defaults

| Source | Internal | External |
|--------|----------|----------|
| Slack | +2 working hours | N/A (all Slack is internal for MVP) |
| Email | +1 working day | +2–3 working days |
| Meeting | +1–2 working days | +2–3 working days |

"External" determined by: `source_item.is_external_participant = true` or any recipient in `source_item.recipients` with `is_external = true`.

---

## 6. Open Questions Before Building

### Q1 — Schema migration: which columns to add to `commitment_candidates`?

The brief requires candidate signals to carry trigger_class, priority_hint, commitment_class_hint, context_window, observe_until, and re-analysis flag. The current schema does not have these.

I propose a Phase 03 migration adding the 9 columns listed in Section 4. **Is this the right approach, or should some of these live in a single `detection_metadata` JSONB instead to keep the migration smaller?**

Leaning: explicit columns for `trigger_class`, `is_explicit`, `priority_hint`, `commitment_class_hint` (queried/filtered), and `flag_reanalysis` (indexed); JSONB for `context_window` and `linked_entities` (stored but not relationally queried).

### Q2 — Sync session for Celery workers

Phase 02 set up async SQLAlchemy only. Celery tasks need a sync session. I plan to add `app/db/session.py` with a sync `SessionLocal` factory (standard `create_engine` + `sessionmaker`). This means two SQLAlchemy engines: one async (FastAPI routes) and one sync (Celery workers).

**Is this acceptable, or should I instead run an async event loop inside the Celery task?** Leaning: sync session is simpler and the correct pattern for Celery workers — no event loop management.

### Q3 — Confidence score assignment at detection time

The brief calls this an "initial confidence hint," not a precise score. For deterministic pattern matching, I plan fixed heuristic values:
- Explicit pattern match + external context: 0.85
- Explicit pattern match (internal): 0.75
- Implicit pattern match: 0.50–0.60
- Edge cases ("I'll try", short acceptance without strong context): 0.35–0.45

**Is this calibration reasonable, or should MVP confidence scoring be simpler (e.g., just high/medium/low as a string field rather than a numeric)?** The schema already has `confidence_score` as `NUMERIC(4,3)` so numerics are committed, but the values above are my proposal.

### Q4 — Model-assisted detection for implicit signals: MVP scope?

The brief says detection "should combine deterministic heuristics with model assistance." For MVP, I plan deterministic-only with the `context_window` stored to enable model calls later.

**Should I include any model-assisted detection in Phase 03, or is deterministic-only correct for MVP?** My read of the brief suggests deterministic-only is the right MVP scope. If Kevin wants model calls in Phase 03, the Claude API integration approach needs to be defined.

### Q5 — Batch detection: one Celery task per item or batch task?

Currently the ingestion route enqueues one `detect_commitments` task per source item, even for batch ingestion. For a batch of 100 items, that's 100 tasks.

**Should batch ingestion trigger a single `detect_commitments_batch(source_item_ids: list[str])` task instead?** Leaning: keep one-task-per-item for now. Simpler failure isolation. Can batch later if queue pressure demands it.

### Q6 — Where does `observe_until` get written?

The `commitments` table has an `observe_until` column. The `commitment_candidates` table (as I propose above) also gets one. When a candidate is promoted to a commitment, the commitment's `observe_until` should be set from the candidate's value (unless the candidate's window has already passed).

**Confirmed understanding:** Detection writes `observe_until` to the candidate. Promotion (a later phase) copies it to the commitment. Is this correct, or should the commitment's `observe_until` be independently computed at promotion time?

---

## 7. Implementation Plan (for Kevin's review)

Once approved, implementation order:

1. **Migration** — add missing columns to `commitment_candidates` (Q1 resolution needed first)
2. **`app/db/session.py`** — sync session factory for Celery (Q2)
3. **`app/services/detection/patterns.py`** — pattern data with tests
4. **`app/services/detection/context.py`** — context window extraction with tests
5. **`app/services/detection/detector.py`** — orchestration with tests
6. **`app/tasks.py`** — replace stub with real call to `run_detection`
7. **`tests/services/test_detection.py`** — full test suite per trigger class + source type
8. **Static analysis scan** before marking complete

TDD workflow: tests written before implementation for each module.

---

*Interpretation complete. Awaiting Kevin's approval and Q1 resolution before implementation begins.*
