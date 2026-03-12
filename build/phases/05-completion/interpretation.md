# Phase 05 — Completion Detection: Interpretation

**Stage:** STAGE 2 — INTERPRET
**Date:** 2026-03-12

---

## 1. What Phase 05 Does and Why

Phase 05 answers the question: *has this commitment been delivered?* It does not ask whether it was correctly fulfilled, or whether the recipient is happy — it asks whether the owner sent/shared/completed the thing they said they would, as evidenced by subsequent signals in the same channel.

**Core contract:**
- Phase 04 promoted candidates into `Commitment` rows. Phase 05 works exclusively on those rows.
- Phase 05 runs on commitments in `lifecycle_state = active`. It never touches `proposed`, `needs_clarification`, `discarded`, or `closed` rows.
- Completion is a **suggestion with a confidence score**, not a hard determination. The user confirms or dismisses in the surface layer (Phase 06).
- `delivered` and `closed` are **distinct and reversible** states. A delivered commitment is awaiting closure confirmation. A closed one is done. Both can be reversed.

**Signal flow:**
```
source_items (new content from ingestion)
      ↓
CompletionMatcher — which commitments does this new item relate to?
      ↓
CompletionScorer — what confidence dimensions does this evidence yield?
      ↓
LifecycleUpdater — if confidence ≥ threshold, transition state + write CommitmentSignal + LifecycleTransition
```

**Why not fold this into detection?**
Detection (Phase 03) works on fresh, uncommitted content. Phase 05 works on the retrospective relationship between a `source_item` and a specific, existing `Commitment`. The logic is fundamentally different: matching is personalized (this commitment, this owner, this deliverable), while detection is generic pattern scanning.

**Why not fold this into Phase 06 (surfacing)?**
Surfacing decides *what to show users*. Completion detection decides *what has happened*. They are separate concerns. Surfacing should receive pre-computed confidence scores, not do signal analysis.

---

## 2. Architecture

```
app/services/completion/
├── __init__.py
├── matcher.py       — match source_items → active commitments
├── scorer.py        — compute confidence dimensions from matched evidence
├── updater.py       — write state transitions, signals, explanation fields
└── detector.py      — orchestrator: matcher → scorer → updater
```

`app/tasks.py` gains a new Celery task `run_completion_sweep_task` on a beat schedule.

No new API endpoints in Phase 05. State changes are observable via `GET /commitments/{id}` (Phase 02 API).

---

## 3. Implementation Plan

### 3a. CompletionEvidence Data Model

**What it is:** A lightweight intermediate object produced by the matcher and consumed by the scorer. Not persisted directly — its output is persisted via `CommitmentSignal` and confidence columns on `Commitment`.

**Fields:**

```python
@dataclass
class CompletionEvidence:
    source_item_id: str
    source_type: str                  # "meeting" | "slack" | "email"
    occurred_at: datetime
    raw_text: str                     # original content (not suppressed)
    normalized_text: str              # after suppression patterns applied
    matched_patterns: list[str]       # pattern names that fired
    actor_name: str | None            # who produced this item
    actor_email: str | None
    recipients: list[str]             # from source_item.recipients
    has_attachment: bool
    attachment_metadata: dict | None
    thread_id: str | None
    direction: str | None             # "inbound" | "outbound" | None
    evidence_strength: str            # "strong" | "moderate" | "weak"
```

**Evidence strength per channel (pre-scorer classification):**

| Channel  | Strong                                                   | Moderate                                              | Weak                                          |
|----------|----------------------------------------------------------|-------------------------------------------------------|-----------------------------------------------|
| email    | outbound email with attachment to known recipient        | outbound email without attachment, delivery keywords  | inbound ACK ("received it, thanks")           |
| slack    | delivery keywords + @mention of recipient                | delivery keywords, no mention                         | emoji reaction only (out of Phase 05 scope)   |
| meeting  | explicit verbal delivery confirmation by owner           | "I sent / I shared" in transcript                     | "I think I sent" or "should be done"          |

**Email suppression is mandatory before pattern matching.** Apply `EMAIL_SUPPRESSION_PATTERNS` first; any match on stripped text that also appears in the quoted portion does NOT count. The `is_quoted_content` flag on `SourceItem` is the primary guard — items where `is_quoted_content=True` are excluded from evidence gathering entirely.

---

### 3b. Matcher

**Purpose:** Given a `source_item`, find the set of active `Commitment` rows it could be evidence for.

**File:** `app/services/completion/matcher.py`

**Function signature:**
```python
def find_matching_commitments(
    source_item: Any,  # duck-typed SourceItem
    active_commitments: list[Any],  # duck-typed Commitment rows
) -> list[tuple[Any, CompletionEvidence]]:
    ...
```

**Matching strategy (all dimensions must be evaluated, not all must pass):**

1. **Actor match** — `source_item.sender_name` or `source_item.sender_email` matches `commitment.resolved_owner` or `commitment.suggested_owner`. Case-insensitive. Fuzzy (contains match) is acceptable for names. This is the strongest signal — a commitment can only be delivered by its owner.

2. **Recipient match** — `source_item.recipients` overlaps `commitment.target_entity`. If `commitment.target_entity` is None, skip this dimension (no penalty). Strength: moderate.

3. **Deliverable/topic match** — keyword overlap between `source_item.content_normalized` and `commitment.deliverable` or `commitment.commitment_text`. Minimum 1 significant overlapping noun (2+ characters, not stopwords). This prevents false positives where the same actor sends anything.

4. **Thread continuity** — `source_item.thread_id` matches thread_id stored on any `CommitmentSignal` with `signal_role=origin` for this commitment. This is a strong contextual anchor when available.

5. **Time proximity** — `source_item.occurred_at` must be after `commitment.created_at`. Cap at 90 days forward; commitments older than 90 days without delivery will be handled by auto-close sweep (see §3e). This prevents matching stale content.

**Match decision rule:**
- Actor match is required (score 0 if no actor match)
- At least one of: recipient match, deliverable match, or thread continuity
- If actor match + deliverable match + thread continuity → `evidence_strength = strong`
- If actor match + deliverable match OR thread continuity → `evidence_strength = moderate`
- If actor match only with weak delivery keyword → `evidence_strength = weak`

**Return:** List of `(commitment, evidence)` tuples. A single source_item can match multiple commitments (actor sent multiple things). The scorer handles each independently.

---

### 3c. Scorer

**Purpose:** Compute confidence dimensions for a `(commitment, evidence)` pair.

**File:** `app/services/completion/scorer.py`

**Output data model** (see Q3 for model type decision):
```python
@dataclass
class CompletionScore:
    delivery_confidence: float          # P(delivery happened)
    completion_confidence: float        # P(commitment fully satisfied)
    evidence_strength: str              # "strong" | "moderate" | "weak"
    recipient_match_confidence: float   # P(right recipient got it)
    artifact_match_confidence: float    # P(right deliverable was sent)
    closure_readiness_confidence: float # P(safe to auto-close later)
    primary_pattern: str | None         # name of the pattern that most contributed
    notes: list[str]                    # human-readable evidence notes
```

**Confidence computation per dimension:**

**`delivery_confidence`** — core signal:
- Strong evidence: 0.85 base
- Moderate evidence: 0.65 base
- Weak evidence: 0.40 base
- Adjustment +0.05: `has_attachment=True` and `commitment_type` in (`send`, `deliver`, `introduce`)
- Adjustment -0.10: `commitment.commitment_type` in (`review`, `investigate`) — these are hard to confirm from delivery signals alone
- Adjustment -0.15: email with `is_external_participant=True` on commitment AND `direction != "outbound"` — external commitments need outbound confirmation

**`completion_confidence`** — higher bar than delivery, accounts for `commitment_type`:
- `send` / `share` / `introduce`: completion_confidence = delivery_confidence × 0.95 (delivery ≈ completion)
- `review` / `check` / `investigate`: completion_confidence = delivery_confidence × 0.70 (delivery ≠ done — need more)
- `follow_up` / `update` / `coordinate`: completion_confidence = delivery_confidence × 0.80
- All others: completion_confidence = delivery_confidence × 0.75

**`recipient_match_confidence`:**
- Explicit recipient match in source_item.recipients: 0.90
- Partial/fuzzy match: 0.65
- No target_entity on commitment (can't verify): 0.50 (neutral)
- No recipient field on source_item: 0.50 (neutral)

**`artifact_match_confidence`:**
- Deliverable keyword match + has_attachment: 0.90
- Deliverable keyword match only: 0.70
- No deliverable on commitment: 0.50 (neutral)
- Pattern-only (no keyword match): 0.40

**`closure_readiness_confidence`:**
```
closure_readiness = (delivery_confidence × 0.5) + (recipient_match_confidence × 0.3) + (artifact_match_confidence × 0.2)
```
This is used later by the auto-close sweep to decide whether to transition `delivered → closed` without user action.

**`evidence_strength`:** Passed through from matcher (not recomputed).

**Threshold values** (see Q4 for rationale):

| Transition                | Required condition                                                     |
|---------------------------|------------------------------------------------------------------------|
| `active → delivered`      | `delivery_confidence >= 0.65` AND `evidence_strength != "weak"`        |
| `delivered → closed`      | `closure_readiness_confidence >= 0.75` AND age since delivered >= 24h  |
| No transition (log only)  | `delivery_confidence >= 0.40` AND `delivery_confidence < 0.65`         |

---

### 3d. Lifecycle Updater

**Purpose:** Apply scorer output to the database — update commitment fields, write `CommitmentSignal`, write `LifecycleTransition`.

**File:** `app/services/completion/updater.py`

**Function signature:**
```python
def apply_completion_result(
    commitment: Any,            # duck-typed Commitment ORM object
    evidence: CompletionEvidence,
    score: CompletionScore,
    db: Session,
) -> LifecycleTransition | None:
    """
    Returns the LifecycleTransition if a state change was made, else None.
    Writes CommitmentSignal regardless of state change (for log-only cases).
    """
```

**What it writes:**

1. **`CommitmentSignal`** — always written when `delivery_confidence >= 0.40`:
   - `signal_role = SignalRole.delivery`
   - `confidence = score.delivery_confidence`
   - `interpretation_note` = joined `score.notes`
   - Uses `UniqueConstraint(commitment_id, source_item_id, signal_role)` — safe to call idempotently (insert-or-ignore pattern)

2. **`Commitment` field updates** (only when transitioning):
   - `confidence_delivery = score.delivery_confidence`
   - `confidence_closure = score.closure_readiness_confidence`
   - `delivery_explanation = "; ".join(score.notes)`
   - `lifecycle_state = LifecycleState.delivered` (or `closed` for auto-close path)
   - `state_changed_at = now()`

3. **`LifecycleTransition`** — only when state changes:
   - `from_state = commitment.lifecycle_state` (before change)
   - `to_state = LifecycleState.delivered`
   - `trigger_source_item_id = evidence.source_item_id`
   - `trigger_reason = f"delivery_confidence={score.delivery_confidence:.2f}; {score.primary_pattern}"`
   - `confidence_at_transition = score.delivery_confidence`

**Reversibility:** The updater does not prevent re-running. If a delivered commitment receives new counter-evidence (e.g., "actually I haven't sent that yet"), Phase 05 should be able to re-score. The auto-close sweep (§3e) handles `delivered → closed`; the updater here handles `active → delivered` only.

**No-op guard:** If `commitment.lifecycle_state` is already `delivered` or `closed`, the updater writes the signal (if confidence ≥ threshold) but does NOT write a new transition. This prevents duplicate transitions on re-sweep.

---

### 3e. Celery Task

**File:** `app/tasks.py` (existing file, add new task)

**Task name:** `run_completion_sweep`

**Beat schedule:** Every 10 minutes (consistent with Phase 04's `run_clarification_batch`)

**Two sub-sweeps per invocation:**

**Sweep A — New evidence sweep:**
```python
@celery_app.task(name="run_completion_sweep")
def run_completion_sweep() -> dict:
    """
    1. Query source_items ingested in last 30 minutes (ingested_at >= now() - 30m)
       that are NOT quoted content (is_quoted_content=False)
    2. For each item, call detector.run_completion_detection(source_item_id, db)
    3. Return count of transitions made
    """
```

**Query scope (Sweep A):**
```sql
SELECT si.*
FROM source_items si
WHERE si.ingested_at >= now() - INTERVAL '30 minutes'
  AND si.is_quoted_content = FALSE
ORDER BY si.ingested_at DESC
```

Rationale for 30-minute window (not 10-minute): beat jitter and processing delays mean we want overlap. Idempotency via `CommitmentSignal` UniqueConstraint prevents duplicate writes.

**Sweep B — Auto-close sweep** (see Q5 for decision on scope):
```python
# Within same task, after Sweep A:
# Query commitments where lifecycle_state='delivered'
#   AND state_changed_at <= now() - auto_close_after_hours (from schema column)
#   AND closure_readiness_confidence >= 0.75
# Transition delivered → closed, write LifecycleTransition with trigger_reason='auto_close_sweep'
```

**Query scope for active commitments (used by matcher):**
```sql
SELECT c.*
FROM commitments c
WHERE c.user_id = :user_id
  AND c.lifecycle_state = 'active'
  AND (c.observe_until IS NULL OR c.observe_until <= now())
```

The `observe_until` guard ensures we don't try to complete commitments still in their observation window (rare edge case but possible if Phase 04 sets a long window).

**`run_completion_detection(source_item_id, db)` orchestrator** in `detector.py`:
1. Load source_item
2. Load active commitments for `source_item.user_id`
3. Call `find_matching_commitments(source_item, active_commitments)` → list of (commitment, evidence)
4. For each match: call `score_evidence(commitment, evidence)` → CompletionScore
5. For each score: call `apply_completion_result(commitment, evidence, score, db)`
6. Commit, return summary dict

---

## 4. Open Questions with Recommendations

### Q1: New `completion_signals` table vs JSONB on `commitment`?

**Recommendation: Use the existing `CommitmentSignal` table (neither option).**

Both options in the question assume we need new storage. We don't. `CommitmentSignal` already exists with `signal_role` (which includes `delivery` and `closure`), `confidence`, and `interpretation_note`. It's indexed on `commitment_id` and `source_item_id`. It has a UniqueConstraint preventing duplicates.

A new `completion_signals` table would duplicate this structure with minor differences. JSONB on `commitment` would lose queryability and make it impossible to trace which specific source_item drove each signal.

**Decision:** Write completion signals to `commitment_signals` with `signal_role=delivery`. The `delivery_explanation` and `closure_explanation` text columns on `Commitment` hold the human-readable summary. No new table or JSONB blob needed.

*Exception:* If Phase 06 needs to surface "evidence list" to the user (which source_items contributed to the delivery inference), it reads `CommitmentSignal` rows with `signal_role=delivery`. This is already queryable.

---

### Q2: New migration for `delivered_at` and `auto_close_after_hours` columns?

**Recommendation: YES — add both columns.**

`delivered_at` is necessary:
- The auto-close sweep needs to know when the commitment transitioned to `delivered` (not just `state_changed_at`, which gets overwritten on any transition)
- Surfacing (Phase 06) will want to show "delivered 3 days ago, awaiting closure"
- The existing `state_changed_at` column cannot be used because it's overwritten on every state change

`auto_close_after_hours` is worth adding as a nullable column with a sensible server default:
- Allows per-commitment configuration in the future (e.g., external commitments auto-close after 48h, internal after 72h)
- For Phase 05, simply default to `48` (hours) via a server default
- Having the column in schema now prevents a future migration that requires a default value on a live table

**Migration adds:**
- `commitments.delivered_at TIMESTAMP WITH TIME ZONE NULL`
- `commitments.auto_close_after_hours INTEGER NOT NULL DEFAULT 48`
- Index on `(lifecycle_state, delivered_at)` for the auto-close sweep query

The `Commitment` ORM model also needs updating to reflect these columns.

---

### Q3: Pydantic model vs plain dict for scorer output?

**Recommendation: Use a `@dataclass`, not Pydantic, not plain dict.**

Rationale:
- Plain dict: no type safety, fragile across call sites, forces string key access everywhere
- Pydantic: validation overhead is unnecessary here — scorer produces this internally, it is not a user-facing API object and never deserializes from JSON
- `@dataclass(frozen=True)`: gives type safety, clean field access, no overhead, testable with `==`, consistent with how `CompletionEvidence` is structured

This is consistent with the `TriggerPattern` dataclass already in `patterns.py`. The pattern is established.

If Phase 06 needs to serialize the score to JSON for a response, that serialization belongs in the API layer (Phase 02 schema), not in the scorer.

---

### Q4: Threshold values for `active → delivered` and `delivered → closed`?

**Recommendation:**

```
active → delivered:   delivery_confidence >= 0.65 AND evidence_strength IN ("strong", "moderate")
delivered → closed:   closure_readiness_confidence >= 0.75 AND delivered_at <= now() - auto_close_after_hours
```

**Reasoning for `0.65` delivery threshold:**
- Below 0.65 is "weak" evidence territory (see scorer §3c). We should log these signals but not surface a state change.
- 0.65 maps to "actor sent something relevant to this commitment" — not verified but credible.
- Lower threshold risks false positives that erode user trust in surfaced completions.
- Higher threshold (e.g. 0.80) would miss many legitimate deliveries in meeting transcripts where language is informal.

**Reasoning for `0.75` closure threshold:**
- Closure is a stronger claim than delivery. The auto-close should only fire when we're highly confident.
- `closure_readiness_confidence` is a composite score (delivery × 0.5 + recipient × 0.3 + artifact × 0.2), so reaching 0.75 requires consistently strong evidence across multiple dimensions.
- The 24/48h wait is an additional buffer — if the user would have dismissed the delivery suggestion, they have time to do so before auto-close fires.

**Log-only zone:** `delivery_confidence >= 0.40 AND < 0.65` → write `CommitmentSignal` with `signal_role=delivery` but no state change. This builds a signal trail without prematurely transitioning state.

---

### Q5: Auto-close sweep in Phase 05 or Phase 06?

**Recommendation: Phase 05 owns the auto-close sweep.**

Reasons:
1. Auto-close is a completion lifecycle decision, not a surfacing decision. The question "has this been closed?" is owned by completion detection, not surfacing.
2. Phase 06 (surfacing) should receive a commitment already in `closed` state, not decide whether to close it.
3. If auto-close lives in Phase 06, it creates a hidden dependency: surfacing must run before closure can happen. This breaks separation of concerns.
4. The Celery task already exists (Sweep B in §3e). Adding it to Phase 05 keeps the complete `active → delivered → closed` lifecycle in one service boundary.

**Implementation in Phase 05:** Same `run_completion_sweep` Celery task, second sweep after evidence sweep. Query `commitments WHERE lifecycle_state='delivered' AND delivered_at <= now() - (auto_close_after_hours * interval '1 hour')`. For each, check `closure_readiness_confidence >= 0.75` (already stored on commitment). If yes, call `apply_auto_close(commitment, db)` which writes a `LifecycleTransition` with `trigger_reason='auto_close'` and sets `lifecycle_state=closed`.

---

## 5. Test Plan

**File:** `tests/services/test_completion.py`

**Test strategy:** SimpleNamespace for ORM duck-typing throughout (consistent with Phase 04). All tests are unit tests; no DB required. Scorer and matcher are pure functions.

---

### `TestCompletionMatcher`

**Setup:** Helper `make_commitment(**kwargs)` and `make_source_item(**kwargs)` using SimpleNamespace.

| Scenario | Expectation |
|----------|-------------|
| Actor match + deliverable keyword match + attachment → send commitment | Returns 1 match, evidence_strength=strong |
| Actor match only, no deliverable overlap | Returns 0 matches |
| Actor match + thread_id continuity, no deliverable | Returns 1 match, evidence_strength=moderate |
| Source item is_quoted_content=True | Returns 0 matches (skipped entirely) |
| Email attribution line in content (quoted chain) | Suppressed; if nothing remains after suppression, 0 matches |
| Multiple active commitments for same actor → different deliverables | Each returns independently; correct per-deliverable match |
| Commitment has no resolved_owner AND no suggested_owner | Returns 0 matches (can't determine owner) |
| occurred_at before commitment.created_at | Returns 0 matches |
| commitment.observe_until in the future | Returns 0 matches (still in observation window) |

---

### `TestCompletionScorer`

| Scenario | Key assertion |
|----------|---------------|
| Strong evidence + commitment_type=send | delivery_confidence >= 0.85, completion_confidence >= 0.80 |
| Moderate evidence + commitment_type=review | completion_confidence < 0.65 (hard type penalty) |
| Weak evidence | delivery_confidence < 0.65 (below transition threshold) |
| has_attachment=True + commitment_type=deliver | +0.05 artifact bonus reflected |
| External commitment + direction != outbound | -0.15 penalty reflected |
| No target_entity → recipient_match_confidence = 0.50 | Neutral/unknown, not penalized |
| closure_readiness formula correctness | Verify: (delivery×0.5 + recipient×0.3 + artifact×0.2) |
| commitment_type=investigate, strong evidence | completion_confidence = delivery_confidence × 0.70 |

---

### `TestLifecycleUpdater`

Uses mock `db.add()` and `db.commit()` (or passes a list to capture written objects).

| Scenario | Expected writes |
|----------|----------------|
| delivery_confidence=0.70 + evidence_strength=moderate | CommitmentSignal written; LifecycleTransition active→delivered; commitment.lifecycle_state=delivered |
| delivery_confidence=0.50 (log-only zone) | CommitmentSignal written; NO LifecycleTransition; lifecycle_state unchanged |
| delivery_confidence=0.70, commitment already delivered | CommitmentSignal written; NO new LifecycleTransition |
| Strong score, already closed commitment | No writes (no-op guard) |
| delivered_at set correctly on active→delivered transition | commitment.delivered_at = transition time |

---

### `TestCompletionDetector`

Integration-style unit test: wires matcher → scorer → updater with mocked DB.

| Scenario | Expectation |
|----------|-------------|
| source_item matches 2 commitments | Both processed; 2 signals written; correct transitions per score |
| source_item matches 0 commitments | No writes; returns empty summary |
| Duplicate sweep (same source_item run twice) | UniqueConstraint prevents duplicate signal; idempotent |

---

### `TestAutoCloseSweep`

| Scenario | Expectation |
|----------|-------------|
| commitment.lifecycle_state=delivered, delivered_at=72h ago, auto_close_after_hours=48, closure_readiness=0.80 | Transitions to closed |
| commitment.lifecycle_state=delivered, delivered_at=12h ago, auto_close_after_hours=48 | No transition (not old enough) |
| commitment.lifecycle_state=delivered, delivered_at=72h ago, closure_readiness=0.60 | No transition (confidence too low) |
| commitment.lifecycle_state=active (not delivered) | Not touched by auto-close sweep |

---

### `TestQuotedEmailSuppression`

Dedicated tests for the "quoted email MUST NOT count as fresh evidence" rule.

| Scenario | Expectation |
|----------|-------------|
| source_item.is_quoted_content=True | Excluded before matcher runs |
| content contains `> Original message\n> I'll send the report` | Suppressed; delivery keyword in quoted line does not match |
| Outbound email with quoted chain + new delivery confirmation in top paragraph | Only the new paragraph evidence counts |

---

## 6. No-regression Checklist

The following must remain unaffected (checked in CI after Phase 05):
- Phase 03: `pytest tests/services/test_detection.py` all green
- Phase 04: `pytest tests/services/test_clarification.py` all green
- No new imports into Phase 03 or 04 service files
- `alembic upgrade head` idempotent on a fresh schema
- `ruff check app/` clean (no new warnings introduced)
