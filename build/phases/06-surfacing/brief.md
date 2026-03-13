# Phase 06: Surfacing & Prioritization — Engineering Brief

**Phase:** 06-surfacing  
**Cycle:** A  
**Preceding phases:** 01-schema, 02-api-scaffold, 03-detection, 04-clarification, 05-completion  
**Status:** Ready for A1 Interpretation

---

## Context

Phases 01–05 have built:
- Complete data model (commitments, sources, evidence)
- Detection engine (identifies commitment candidates)
- Clarification system (surfaces ambiguities)
- Completion detection (recognizes fulfilled commitments)
- Full test suite (178 tests passing)
- All migrations and database setup

**Phase 06 builds the surfacing and prioritization layer.** This is the system that decides what to show the user, in what order, and through which interface.

---

## Product Requirements

From the Surfacing & Prioritization brief:

### Three user-facing surfaces
1. **Main tab:** Big promises, high consequence, externally meaningful, clear ownership/deliverable
2. **Shortlist tab:** Small commitments, easy to forget, low-friction, internal
3. **Clarifications view:** Items that likely matter but need ambiguity resolved (owner, due date, deliverable)

### Surfacing layers
- **Internal:** May retain weak signals, candidates, low-confidence items (for reasoning/linking)
- **Surfaced:** Only items that meet threshold for meaningful user value

### Priority dimensions (not single score)
1. Externality (external > internal)
2. Timing strength (explicit due date > vague)
3. Business consequence (high > low)
4. Cognitive burden (hard to remember > easy)
5. Confidence (high > low, but doesn't fully determine)
6. Actionability (clear owner/next step > vague)
7. Staleness (long-unresolved > fresh)

### Observation before surfacing
- Don't surface immediately on detection
- Default observation windows by source (email internal 1 day, email external 2–3 days, etc.)
- Allow later signals to clarify ownership/timing/completion before surfacing

### Commitment classification
- **Big promises:** External, explicit due date, high consequence
- **Small commitments:** Internal, lower consequence, conversational

---

## Engineering Tasks

### Task 1: Extend commitment model

Add surfacing-related fields to the `commitment` table:

```sql
ALTER TABLE commitment ADD COLUMN (
    surfaced_as VARCHAR(20),  -- NULL | 'main' | 'shortlist' | 'clarifications'
    priority_score DECIMAL(5,2),  -- 0-100, for ranking within surface
    is_external BOOLEAN,  -- true if commitment involves external party
    timing_strength SMALLINT,  -- 0-10, explicit vs vague due date
    business_consequence SMALLINT,  -- 0-10, impact of miss
    cognitive_burden SMALLINT,  -- 0-10, mental cost if forgotten
    confidence_for_surfacing DECIMAL(5,2),  -- 0-100, distinct from detection confidence
    observation_window_start TIMESTAMP,  -- when we first detected it
    observation_window_end TIMESTAMP,  -- when we can surface it
    surfaced_at TIMESTAMP,  -- when we actually surfaced it
    surfacing_reason VARCHAR(255)  -- 'external_due_date' | 'high_consequence' | etc.
);
```

Add index on `(surfaced_as, priority_score DESC)` for efficient querying by surface.

### Task 2: Classify commitments

Create a classification service that decides:
1. Is this a big promise or small commitment?
2. Is this external or internal?
3. Score each priority dimension (0–10)

```
class CommitmentClassifier:
    def classify(commitment) -> ClassificationResult:
        # Determine externality (parse participants, check email domains, etc.)
        is_external = detect_externality(commitment)
        
        # Score timing strength (check for explicit dates/times)
        timing = score_timing(commitment.due_date, commitment.due_date_confidence)
        
        # Score business consequence (heuristic: external > internal, derived from sources)
        consequence = score_consequence(commitment.is_external, commitment.evidence_count)
        
        # Score cognitive burden (heuristic: small/conversational > big/formal)
        burden = score_cognitive_burden(commitment.language_markers, commitment.is_small)
        
        # Confidence for surfacing (distinct from detection confidence)
        conf = score_surfacing_confidence(commitment.owner_confidence, commitment.deliverable_confidence)
        
        # Classify as big or small
        is_big = is_external or (timing >= 7 and consequence >= 7)
        
        return ClassificationResult(
            is_external, timing, consequence, burden, conf, is_big
        )
```

### Task 3: Compute priority score

Create a priority scoring function that combines dimensions:

```
def compute_priority_score(
    is_external: bool,
    timing_strength: int,
    consequence: int,
    cognitive_burden: int,
    confidence: float,
    staleness_days: int
) -> float:
    """
    Combine dimensions into 0-100 score, preserving dimension semantics.
    
    Roughly:
    - Externality: 25 points if external
    - Timing: up to 20 points for explicit due date
    - Consequence: up to 15 points
    - Cognitive burden: up to 15 points
    - Confidence: up to 15 points (but asymmetric: low confidence can suppress, high can't fully boost)
    - Staleness: up to 10 points if unresolved past expected window
    
    Total: ~100 points max
    """
    score = 0.0
    
    # Externality (binary): +25 if external
    if is_external:
        score += 25
    
    # Timing strength (0-10 scale): up to 20 points
    score += (timing_strength / 10) * 20
    
    # Business consequence (0-10 scale): up to 15 points
    score += (consequence / 10) * 15
    
    # Cognitive burden (0-10 scale): up to 15 points
    score += (cognitive_burden / 10) * 15
    
    # Confidence (0-100 scale): up to 15 points, but suppress heavily if low
    if confidence >= 70:
        score += (confidence / 100) * 15
    elif confidence >= 40:
        score += ((confidence - 40) / 30) * 10  # 40-70 = 0-10 points
    else:
        score -= 10  # Low confidence suppresses surfacing
    
    # Staleness (days unresolved): up to 10 bonus if beyond expected window
    if staleness_days > 0:
        score += min(staleness_days * 1.5, 10)  # 1-7 days = 1-10 points
    
    return min(100, max(0, score))
```

### Task 4: Observation window logic

Implement observation window logic:

```
class ObservationWindow:
    WINDOWS = {
        'slack_internal': timedelta(hours=2),
        'email_internal': timedelta(days=1),
        'email_external': timedelta(days=2),
        'meeting_internal': timedelta(days=1),
        'meeting_external': timedelta(days=3),
    }
    
    @staticmethod
    def get_window(source_type: str, is_external: bool) -> timedelta:
        key = f"{source_type}_{'external' if is_external else 'internal'}"
        return ObservationWindow.WINDOWS.get(key, timedelta(days=1))
    
    @staticmethod
    def is_observable(commitment: Commitment) -> bool:
        """True if observation window has closed and item can be surfaced."""
        source_type = commitment.primary_source.source_type  # email, slack, meeting
        window = ObservationWindow.get_window(source_type, commitment.is_external)
        return (datetime.utcnow() - commitment.detected_at) >= window

    @staticmethod
    def should_surface_early(commitment: Commitment) -> bool:
        """True if high-consequence external promise should surface before window closes."""
        return (
            commitment.is_external and
            commitment.priority_score >= 70 and
            commitment.confidence_for_surfacing >= 80
        )
```

### Task 5: Assign surfaced_as and priority

Create a surfacing router that assigns commitments to surfaces:

```
class SurfacingRouter:
    MAIN_THRESHOLD = 60  # Items with priority >= 60 can go to Main
    SHORTLIST_THRESHOLD = 35  # Items >= 35 can go to Shortlist
    CLARIFICATIONS_THRESHOLD = 30  # Items needing clarification
    
    @staticmethod
    def route(commitment: Commitment) -> SurfacingDecision:
        """
        Decide: Main | Shortlist | Clarifications | None (hold internally)
        """
        # Is observation window closed?
        if not ObservationWindow.is_observable(commitment) and not ObservationWindow.should_surface_early(commitment):
            return SurfacingDecision(surfaced_as=None, reason='observation_window_not_closed')
        
        # Does it have critical ambiguity?
        has_critical_ambiguity = (
            commitment.owner_confidence < 0.5 or
            (commitment.is_external and commitment.due_date_confidence < 0.6)
        )
        
        if has_critical_ambiguity and commitment.priority_score >= CLARIFICATIONS_THRESHOLD:
            return SurfacingDecision(surfaced_as='clarifications', reason='critical_ambiguity')
        
        # Route to Main or Shortlist based on priority and classification
        if commitment.priority_score >= MAIN_THRESHOLD:
            return SurfacingDecision(
                surfaced_as='main',
                reason=f"priority_{int(commitment.priority_score)}_is_big_{commitment.is_big_promise}"
            )
        elif commitment.priority_score >= SHORTLIST_THRESHOLD:
            return SurfacingDecision(surfaced_as='shortlist', reason=f"priority_{int(commitment.priority_score)}")
        else:
            return SurfacingDecision(surfaced_as=None, reason='below_surfacing_threshold')
```

### Task 6: Create surfacing queries

Add API endpoints:

```
GET /api/commitments/main
    Query: WHERE surfaced_as = 'main' ORDER BY priority_score DESC
    Response: [Commitment] ordered by priority

GET /api/commitments/shortlist
    Query: WHERE surfaced_as = 'shortlist' ORDER BY priority_score DESC
    Response: [Commitment] ordered by priority

GET /api/commitments/clarifications
    Query: WHERE surfaced_as = 'clarifications' ORDER BY priority_score DESC
    Response: [Commitment] (with ambiguities highlighted)

GET /api/commitments/internal
    Query: WHERE surfaced_as IS NULL ORDER BY detected_at DESC
    Response: [Commitment] (internal hold set, visible only in debug/admin)
```

### Task 7: Batch surfacing service

Create a Celery task that runs regularly (e.g., every 30 min) to:
1. Find all non-surfaced commitments
2. For each: is observation window closed? Is it ready to surface?
3. If yes: classify, score, route, update `surfaced_as` and `priority_score`
4. Log surfacing decisions for auditing

```
@celery.task(name='rippled.tasks.recompute_surfacing')
def recompute_surfacing():
    """
    Scan all commitments. Re-evaluate what should be surfaced.
    
    - Check observation windows
    - Recompute priorities (in case evidence has changed)
    - Update surfaced_as if routing has changed
    - Log all decisions to surfacing_audit
    """
    commitments = Commitment.query.filter(
        Commitment.status.in_(['active', 'pending_clarification'])
    ).all()
    
    for commitment in commitments:
        old_surfaced_as = commitment.surfaced_as
        
        decision = SurfacingRouter.route(commitment)
        commitment.surfaced_as = decision.surfaced_as
        commitment.surfacing_reason = decision.reason
        commitment.priority_score = compute_priority_score(...)
        
        db.session.add(commitment)
        
        # Log audit
        if old_surfaced_as != decision.surfaced_as:
            log_surfacing_audit(commitment.id, old_surfaced_as, decision)
    
    db.session.commit()
```

### Task 8: Tests

Write comprehensive tests:
- Classification correctness (externality, timing, consequence)
- Priority scoring across all dimension combinations
- Observation window logic
- Surfacing router decisions
- Batch surfacing task
- API query correctness

Target: 200+ tests passing (adding ~30–40 new tests to the existing 178).

### Task 9: Documentation

Document:
- Classification logic and heuristics
- Priority dimensions and scoring algorithm
- Observation window defaults
- Surfacing thresholds and routing rules
- API contracts for each surface

---

## Constraints & Notes

1. **Do not change the existing commitment table without backward-compatible migrations.**
2. **Reuse existing patterns:** Detection confidence logic from Phase 03, evidence scoring from Phase 05.
3. **Confidence is distinct:** Surfacing confidence != detection confidence. This is intentional; a real external promise can have high priority even with moderate detection confidence.
4. **Observation windows are defaults:** Make them configurable in settings. Don't hard-code.
5. **Preserve evidence links:** Surfacing routing doesn't modify raw signals or evidence. It only assigns surface placement.
6. **Audit trail:** Every surfacing decision should be logged with reasons. Future phases will use this for learning.
7. **No push/notification logic in this phase.** This phase builds the "what should be visible" layer. Push notifications come in a later phase.

---

## Success Criteria

Phase 06 is complete when:

1. ✅ Commitment model extended with all surfacing fields
2. ✅ Classification service correctly categorizes big vs small, external vs internal
3. ✅ Priority scoring combines all dimensions correctly
4. ✅ Observation window logic respects defaults and allows early surfacing for high-consequence external items
5. ✅ Surfacing router assigns commitments to Main / Shortlist / Clarifications correctly
6. ✅ Batch surfacing task runs and re-evaluates all commitments
7. ✅ API queries work correctly (filter/sort by surface)
8. ✅ Tests demonstrate correctness across all logic layers
9. ✅ Code is documented and decision rationale is clear

---

## Phase 06 Output

After Claude Code completes Phase 06, expect:

- `build/phases/06-surfacing/interpretation.md` — Claude's understanding and plan
- `build/phases/06-surfacing/completed.md` — What was built, stats, test summary
- New code in `src/rippled/models/surfacing.py`, `src/rippled/services/classifier.py`, `src/rippled/tasks/surfacing.py`
- New tests in `tests/test_surfacing.py`, `tests/test_classifier.py`, etc.
- Updated migrations (e.g., `alembic/versions/b6c7d8e9f0a1_add_surfacing_fields.py`)
- All tests passing (200+)
- Git commit with phase summary
