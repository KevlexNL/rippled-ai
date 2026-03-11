# Phase 03 — Detection Pipeline: Approved Build Brief

**Phase:** 03-detection  
**Date:** 2026-03-10  
**Status:** APPROVED — Build now  
**Approved by:** Trinity (autonomous — all decisions within delegated authority)

---

## Context

Phases 01 (Schema) and 02 (API Scaffold) are complete. This is Phase 03: implement the detection pipeline that processes source items into candidate commitment signals.

**What exists:**
- `app/tasks.py` — `detect_commitments()` task stub (returns `{"status": "queued"}`)
- `app/models/commitment_candidate.py` — ORM model, currently missing detection-specific columns
- `app/api/routes/source_items.py` — POST `/source-items` already calls `detect_commitments.delay(source_item_id)` after inserting
- `app/db/engine.py` — async engine for FastAPI only

**What Phase 03 must deliver:**
1. Database migration adding detection columns to `commitment_candidates`
2. Sync session factory for Celery workers
3. Detection service (`app/services/detection/`)
4. Real Celery task implementation (replace stub)
5. Full test suite

---

## All Decisions Made — Build Exactly This

### 1. Migration — new columns on `commitment_candidates`

Add these columns to the existing `commitment_candidates` table:

| Column | Type | Constraint | Purpose |
|--------|------|------------|---------|
| `trigger_class` | `TEXT` | nullable | Detection category (see taxonomy below) |
| `is_explicit` | `BOOLEAN` | nullable | True = explicit language; False = implicit |
| `priority_hint` | `TEXT` | CHECK IN ('high','medium','low'), nullable | Surfacing priority signal |
| `commitment_class_hint` | `TEXT` | CHECK IN ('big_promise','small_commitment','unknown'), nullable | Big vs small hint |
| `context_window` | `JSONB` | nullable | Surrounding text, speaker turns, thread context |
| `linked_entities` | `JSONB` | nullable | People, dates, deliverables near trigger span |
| `observe_until` | `TIMESTAMPTZ` | nullable | When observation window closes |
| `flag_reanalysis` | `BOOLEAN` | DEFAULT false, not null | Flag for re-analysis (meetings mainly) |
| `source_type` | `TEXT` | nullable | Denormalized from source_item for join-free queries |

Also add indexes:
- `ix_commitment_candidates_flag_reanalysis` on `flag_reanalysis` (WHERE flag_reanalysis = true)
- `ix_commitment_candidates_observe_until` on `observe_until`
- `ix_commitment_candidates_source_type` on `source_type`

Do NOT remove any existing columns.

---

### 2. Sync Session Factory

Create `app/db/session.py` with a sync SQLAlchemy session factory:

```python
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import get_settings

# Sync engine — for Celery workers only
# FastAPI routes use the async engine in app/db/engine.py
settings = get_settings()
_sync_engine = create_engine(settings.database_url_sync)  # add this config key
_SyncSessionLocal = sessionmaker(bind=_sync_engine, autoflush=False, autocommit=False)

@contextmanager
def get_sync_session() -> Session:
    session = _SyncSessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
```

Add `database_url_sync` to `app/core/config.py` — it's the same DB URL as async but without `+asyncpg`. The sync driver is `psycopg2` or the standard postgres driver. Check `requirements.txt` for what's available — use whatever sync driver is already installed.

---

### 3. Detection Service Structure

Create `app/services/detection/` with:

```
app/services/detection/
├── __init__.py          # exports: run_detection(source_item_id, db)
├── detector.py          # orchestration
├── patterns.py          # trigger patterns as structured data
└── context.py           # context window extraction
```

#### `__init__.py`
```python
from app.services.detection.detector import run_detection
__all__ = ["run_detection"]
```

#### `patterns.py` — Pattern Data

Use a dataclass to represent patterns:

```python
from dataclasses import dataclass, field
import re
from typing import Optional

@dataclass
class TriggerPattern:
    name: str
    pattern: re.Pattern
    trigger_class: str
    is_explicit: bool
    base_priority_hint: str  # 'high' | 'medium' | 'low'
    applies_to: list[str]    # ['meeting', 'slack', 'email'] or subsets
    suppression: bool = False
    base_confidence: float = 0.75
```

**Trigger classes (use exactly these strings):**
- `explicit_self_commitment`
- `explicit_assigned_commitment`
- `explicit_collective_commitment`
- `request_for_action`
- `accepted_request`
- `implicit_next_step`
- `implicit_unresolved_obligation`
- `small_practical_commitment`
- `deadline_change`
- `owner_clarification`
- `status_update`
- `delivery_signal`
- `blocker_signal`
- `reopen_signal`

**Pattern sets — implement all of the following:**

Suppression patterns (run first, strip these spans):
```python
# Email quoted chain suppression
TriggerPattern(name="email_quoted_line", pattern=re.compile(r"^>.*$", re.MULTILINE), suppression=True, applies_to=["email"], ...),
TriggerPattern(name="email_attribution", pattern=re.compile(r"On .+wrote:", re.DOTALL), suppression=True, applies_to=["email"], ...),
TriggerPattern(name="email_forward_header", pattern=re.compile(r"^From:.*\nSent:.*\nTo:", re.MULTILINE), suppression=True, applies_to=["email"], ...),

# Cross-source fillers (reduce confidence, don't fully suppress)
TriggerPattern(name="conversational_filler", pattern=re.compile(r"\b(?:sounds good|okay|thanks|received|looks good)\b", re.IGNORECASE), suppression=True, applies_to=["meeting", "slack", "email"], ...),
```

Explicit commitment patterns:
```python
TriggerPattern(name="i_will_explicit", pattern=re.compile(r"\bI'?ll\b.{0,80}", re.IGNORECASE), trigger_class="explicit_self_commitment", is_explicit=True, base_priority_hint="medium", base_confidence=0.75, applies_to=["meeting", "slack", "email"]),
TriggerPattern(name="i_will_full", pattern=re.compile(r"\bI will\b.{0,80}", re.IGNORECASE), trigger_class="explicit_self_commitment", is_explicit=True, base_priority_hint="medium", base_confidence=0.75, applies_to=["meeting", "slack", "email"]),
TriggerPattern(name="we_will", pattern=re.compile(r"\bwe'?ll\b.{0,80}", re.IGNORECASE), trigger_class="explicit_collective_commitment", is_explicit=True, base_priority_hint="medium", base_confidence=0.75, applies_to=["meeting", "slack", "email"]),
TriggerPattern(name="can_you", pattern=re.compile(r"\bcan you\b.{0,80}", re.IGNORECASE), trigger_class="request_for_action", is_explicit=True, base_priority_hint="medium", base_confidence=0.70, applies_to=["meeting", "slack", "email"]),
TriggerPattern(name="will_you", pattern=re.compile(r"\bwill you\b.{0,80}", re.IGNORECASE), trigger_class="request_for_action", is_explicit=True, base_priority_hint="medium", base_confidence=0.70, applies_to=["meeting", "slack", "email"]),
TriggerPattern(name="let_me_take", pattern=re.compile(r"\b(?:let me|I'?ll handle|I'?ll take care)\b.{0,80}", re.IGNORECASE), trigger_class="explicit_self_commitment", is_explicit=True, base_priority_hint="medium", base_confidence=0.75, applies_to=["meeting", "slack", "email"]),
```

Delivery/status patterns:
```python
TriggerPattern(name="delivery_complete", pattern=re.compile(r"\b(?:sent|done|handled|just sent|just emailed|completed)\b", re.IGNORECASE), trigger_class="delivery_signal", is_explicit=True, base_priority_hint="low", base_confidence=0.65, applies_to=["meeting", "slack", "email"]),
TriggerPattern(name="blocker_waiting", pattern=re.compile(r"\bstill waiting on\b.{0,80}", re.IGNORECASE), trigger_class="blocker_signal", is_explicit=False, base_priority_hint="medium", base_confidence=0.60, applies_to=["meeting", "slack", "email"]),
TriggerPattern(name="blocker_on", pattern=re.compile(r"\bblocked (?:on|by)\b.{0,80}", re.IGNORECASE), trigger_class="blocker_signal", is_explicit=False, base_priority_hint="medium", base_confidence=0.60, applies_to=["meeting", "slack", "email"]),
```

Clarification/change patterns:
```python
TriggerPattern(name="owner_clarify", pattern=re.compile(r"\b(?:actually|instead|that'?s on me|I'?ll take that)\b.{0,80}", re.IGNORECASE), trigger_class="owner_clarification", is_explicit=True, base_priority_hint="medium", base_confidence=0.70, applies_to=["meeting", "slack", "email"]),
TriggerPattern(name="deadline_change", pattern=re.compile(r"\b(?:moving (?:this|that) to|push(?:ing)? (?:this|the deadline))\b.{0,80}", re.IGNORECASE), trigger_class="deadline_change", is_explicit=True, base_priority_hint="medium", base_confidence=0.70, applies_to=["meeting", "slack", "email"]),
```

Meeting-specific implicit patterns:
```python
TriggerPattern(name="next_step", pattern=re.compile(r"\bnext step\b.{0,80}", re.IGNORECASE), trigger_class="implicit_next_step", is_explicit=False, base_priority_hint="medium", base_confidence=0.55, applies_to=["meeting"]),
TriggerPattern(name="from_our_side", pattern=re.compile(r"\bfrom our side\b.{0,80}", re.IGNORECASE), trigger_class="implicit_unresolved_obligation", is_explicit=False, base_priority_hint="medium", base_confidence=0.55, applies_to=["meeting"]),
TriggerPattern(name="someone_should", pattern=re.compile(r"\bsomeone (?:should|needs to)\b.{0,80}", re.IGNORECASE), trigger_class="implicit_unresolved_obligation", is_explicit=False, base_priority_hint="medium", base_confidence=0.50, applies_to=["meeting"]),
TriggerPattern(name="we_should", pattern=re.compile(r"\bwe should\b.{0,80}", re.IGNORECASE), trigger_class="implicit_next_step", is_explicit=False, base_priority_hint="low", base_confidence=0.45, applies_to=["meeting"]),
```

Slack-specific small commitment patterns:
```python
TriggerPattern(name="slack_check", pattern=re.compile(r"^\s*(?:I'?ll check|let me (?:look|check|confirm))\s*$", re.IGNORECASE | re.MULTILINE), trigger_class="small_practical_commitment", is_explicit=True, base_priority_hint="low", base_confidence=0.70, applies_to=["slack"]),
TriggerPattern(name="slack_acceptance", pattern=re.compile(r"^\s*(?:yep|yes|sure|will do)[,.]?\s*$", re.IGNORECASE | re.MULTILINE), trigger_class="accepted_request", is_explicit=True, base_priority_hint="low", base_confidence=0.50, applies_to=["slack"]),
```

Email-specific patterns:
```python
TriggerPattern(name="email_revise", pattern=re.compile(r"\bI'?ll (?:revise|update) and\b.{0,80}", re.IGNORECASE), trigger_class="explicit_self_commitment", is_explicit=True, base_priority_hint="medium", base_confidence=0.80, applies_to=["email"]),
TriggerPattern(name="email_intro", pattern=re.compile(r"\bI'?ll (?:introduce|connect you)\b.{0,80}", re.IGNORECASE), trigger_class="explicit_self_commitment", is_explicit=True, base_priority_hint="medium", base_confidence=0.80, applies_to=["email"]),
TriggerPattern(name="email_attached", pattern=re.compile(r"\b(?:attached is|please find attached)\b", re.IGNORECASE), trigger_class="delivery_signal", is_explicit=True, base_priority_hint="low", base_confidence=0.75, applies_to=["email"]),
```

Also include a `get_patterns_for_source(source_type: str) -> list[TriggerPattern]` function that returns all non-suppression patterns applicable to a given source type, plus all suppression patterns for that source type separately.

#### `context.py` — Context Window Extraction

```python
def extract_context(
    item: SourceItem,
    trigger_span: str,
    trigger_start: int,
    trigger_end: int,
    normalized_content: str,
) -> dict:
```

Returns a dict for `context_window` JSONB:

```python
{
    "trigger_text": str,
    "trigger_start": int,
    "trigger_end": int,
    "pre_context": str,      # 200 chars before trigger
    "post_context": str,     # 200 chars after trigger
    "source_type": str,
    # Meeting-specific:
    "speaker_turns": list | None,  # list of {speaker, text, timestamp}
    # Slack-specific:
    "thread_parent": str | None,
    # Email-specific:
    "email_direction": str | None,   # "inbound" | "outbound"
    "has_external_recipient": bool | None,
    "sender": str | None,
}
```

Source-specific extraction:
- **Meeting:** Extract raw pre/post context from `content_normalized`. Speaker turns: parse the transcript for `[Speaker Name]:` patterns, extract 2 turns before and after.
- **Slack:** Pull `thread_parent` from `source_item.raw_payload.get("thread")` if available. Pre/post context from `content_normalized`.
- **Email:** Pre/post context from normalized content (after suppression stripping). Pull `direction`, `has_external_recipient` from source item fields/metadata.

Keep this simple for MVP. The context just needs to be stored, not deeply parsed.

#### `detector.py` — Orchestration

Single public function:

```python
def run_detection(source_item_id: str, db: Session) -> list[CommitmentCandidate]:
```

Algorithm:

1. Load `SourceItem` by `source_item_id`. Raise if not found.
2. Determine `source_type` from `source_item.source_type`.
3. Get suppression patterns and content patterns from `patterns.py`.
4. Normalize content: `content_normalized = source_item.content_normalized or source_item.raw_text or ""`
5. Apply suppression patterns: strip those spans from `content_normalized` before matching.
6. For each non-suppression pattern applicable to this source type:
   - Run `re.finditer(pattern.pattern, normalized_content)`
   - For each match:
     - Compute `confidence_score` using the calibration below
     - Compute `priority_hint` (elevate if external context detected)
     - Compute `commitment_class_hint`
     - Extract `context_window` via `context.py`
     - Compute `observe_until` based on source type + external flag
     - Create `CommitmentCandidate` with savepoint
7. Return list of created candidates

**Confidence calibration:**
```python
def compute_confidence(pattern: TriggerPattern, item: SourceItem, match) -> float:
    score = pattern.base_confidence
    # Elevate for external context
    if getattr(item, 'is_external_participant', False):
        score = min(score + 0.10, 0.90)
    # Edge cases — lower if hedging words in match text
    match_text = match.group(0).lower()
    if any(w in match_text for w in ["try", "maybe", "might", "could"]):
        score = max(score - 0.30, 0.35)
    return round(score, 3)
```

**Priority hint elevation:**
```python
def compute_priority(pattern: TriggerPattern, item: SourceItem, match) -> str:
    hint = pattern.base_priority_hint
    # Elevate to high if external and medium or high pattern
    if getattr(item, 'is_external_participant', False) and hint in ('medium', 'high'):
        return 'high'
    return hint
```

**commitment_class_hint:**
```python
def compute_class_hint(priority_hint: str, is_explicit: bool, item: SourceItem) -> str:
    is_external = getattr(item, 'is_external_participant', False)
    if is_external and is_explicit:
        return 'big_promise'
    if priority_hint == 'low' or not is_explicit:
        return 'small_commitment'
    return 'unknown'
```

**observe_until calculation:**
```python
from datetime import datetime, timezone, timedelta

def compute_observe_until(source_type: str, is_external: bool) -> datetime:
    now = datetime.now(timezone.utc)
    if source_type == 'slack':
        return now + timedelta(hours=2)
    elif source_type == 'email':
        days = 3 if is_external else 1
        return now + timedelta(days=days)
    else:  # meeting
        days = 3 if is_external else 2
        return now + timedelta(days=days)
```

**Savepoint pattern for candidate insert:**
```python
with db.begin_nested():
    db.add(candidate)
    db.flush()
```

**flag_reanalysis logic:**
```python
# For meetings only: set True if attribution is uncertain
def should_flag_reanalysis(source_type: str, match_text: str) -> bool:
    if source_type != 'meeting':
        return False
    uncertain_markers = ['[inaudible]', '[crosstalk]', 'speaker 1', 'speaker 2', '[speaker']
    return any(m in match_text.lower() for m in uncertain_markers)
```

---

### 4. Celery Task (Replace Stub)

Replace the stub in `app/tasks.py`:

```python
@celery_app.task(
    name="app.tasks.detect_commitments",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def detect_commitments(self, source_item_id: str) -> dict:
    from app.services.detection import run_detection
    from app.db.session import get_sync_session

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

Keep the existing `celery_app` setup. Only replace the task body.

---

### 5. ORM Model Updates

Update `app/models/commitment_candidate.py` to add the new columns after the existing ones:

```python
# Detection columns (Phase 03)
trigger_class: Mapped[str | None] = mapped_column(Text, nullable=True)
is_explicit: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
priority_hint: Mapped[str | None] = mapped_column(
    Text,
    CheckConstraint("priority_hint IN ('high', 'medium', 'low')", name="priority_hint_values"),
    nullable=True,
)
commitment_class_hint: Mapped[str | None] = mapped_column(
    Text,
    CheckConstraint("commitment_class_hint IN ('big_promise', 'small_commitment', 'unknown')", name="commitment_class_hint_values"),
    nullable=True,
)
context_window: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
linked_entities: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
observe_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
flag_reanalysis: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
source_type: Mapped[str | None] = mapped_column(Text, nullable=True)
```

Import `JSONB` from `sqlalchemy.dialects.postgresql`.

Also update `__table_args__` to add the new CheckConstraints and indexes. The `CheckConstraint` for `priority_hint_values` and `commitment_class_hint_values` must use unique names.

---

### 6. Tests

Create `tests/services/test_detection.py`. Use pytest + pytest-asyncio where needed.

**Test coverage required:**

1. `test_explicit_self_commitment_meeting` — "I'll send the revised deck tomorrow" in a meeting source item → creates candidate with `trigger_class="explicit_self_commitment"`, `is_explicit=True`, `priority_hint="medium"`
2. `test_implicit_next_step_meeting` — "Next step is pricing from us" → `trigger_class="implicit_next_step"`, `is_explicit=False`
3. `test_small_practical_slack` — "I'll check." → `trigger_class="small_practical_commitment"`, `priority_hint="low"`
4. `test_external_elevates_priority` — same pattern + `is_external_participant=True` → `priority_hint="high"`
5. `test_email_quoted_text_suppressed` — email content with quoted `> I'll send it` → no candidate created for the quoted line
6. `test_delivery_signal` — "Done, just sent it." → `trigger_class="delivery_signal"`
7. `test_blocker_signal` — "Still waiting on legal." → `trigger_class="blocker_signal"`
8. `test_hypothetical_not_detected` — "Maybe we could look into that." → 0 candidates
9. `test_multiple_candidates_one_item` — source item with 3 different commitment statements → 3 candidates created
10. `test_savepoint_isolation` — if one candidate insert fails (mock a constraint violation), other candidates still succeed
11. `test_observe_until_slack_internal` — slack source item → `observe_until` = ~2 hours from now
12. `test_observe_until_email_external` — external email → `observe_until` = ~3 days from now
13. `test_reanalysis_flag_meeting` — meeting content with `[inaudible]` near trigger → `flag_reanalysis=True`
14. `test_context_window_stored` — any candidate → `context_window` is a non-null dict with `trigger_text` and `pre_context` keys

Use a test database (or mock the DB session) — follow whatever test pattern is established in the repo (check `tests/` if it exists).

---

### 7. Build Order

Execute in this order:

1. Alembic migration — add detection columns
2. ORM model update — add mapped columns
3. `app/core/config.py` — add `database_url_sync`
4. `app/db/session.py` — sync session factory
5. `app/services/detection/patterns.py` — pattern data (TDD: write tests first)
6. `app/services/detection/context.py` — context extraction (TDD)
7. `app/services/detection/detector.py` — orchestration (TDD)
8. `app/services/detection/__init__.py` — exports
9. `app/tasks.py` — replace stub
10. Run full test suite — all green before marking complete
11. Static analysis scan
12. Write `build/phases/03-detection/completed.md`
13. Create `build/phases/03-detection/completed.flag`

---

### 8. Definition of Done

- [ ] Migration applied cleanly (`alembic upgrade head` with no errors)
- [ ] All 14 required tests passing
- [ ] `detect_commitments` task replaces stub and returns real candidate count
- [ ] At least one end-to-end test: POST a source item → task queues → candidates created
- [ ] Static analysis: no critical issues
- [ ] `completed.flag` exists at `build/phases/03-detection/completed.flag`

---

### Important Constraints

- **No model API calls in Phase 03.** Deterministic regex only.
- **No OpenAgency OS references.** This is a clean project.
- **Preserve ambiguity.** Never assert certainty you don't have.
- **One Celery task per source item.** No batch task.
- **Sync session for Celery.** Never run async event loops inside tasks.
- **TDD.** Tests before implementation for `patterns.py`, `context.py`, and `detector.py`.
- Read `build/lessons.md` before starting — it contains patterns from prior phases.
