# Trinity — Phase 3: Commitment Detection

## FIRST: Review Phases 1 & 2 with New Skills

Before building Phase 3, review the completed work using the newly installed Claude Code skills.

### Phase 1 Review (Schema)

Use these skills to audit `migrations/versions/` and `app/models/`:

1. **postgres-best-practices** — Review schema design, indexes, constraints
2. **static-analysis** — Run CodeQL/Semgrep on ORM models
3. **insecure-defaults** — Check for any hardcoded values or weak defaults

Write findings to `build/phases/01-schema/skill-review.md`:
- Issues found (critical/warning/info)
- Recommended fixes
- What's already good

### Phase 2 Review (API Scaffold)

Use these skills to audit `app/api/routes/` and `app/core/`:

1. **modern-python** — Check for modern patterns (ruff, type hints, async best practices)
2. **static-analysis** — Security scan on API routes
3. **insecure-defaults** — Check auth patterns, input validation
4. **property-based-testing** — Identify areas that would benefit from property tests

Write findings to `build/phases/02-api-scaffold/skill-review.md`:
- Issues found (critical/warning/info)
- Recommended fixes
- What's already good

### Review Gate

**STOP after completing both reviews.** 

Present findings to Kevin. If critical issues exist, fix them before proceeding to Phase 3. If only warnings/info, note them and proceed.

---

## THEN: Phase 3 — Detection Pipeline

### Context

You've completed:
- **Phase 1:** Database schema (migrations applied, ORM models in place)
- **Phase 2:** API scaffold (routes, Pydantic schemas, CRUD operations)

Now you're building the **detection layer** — the intelligence that identifies commitment signals from source content.

### Your Assignment

Build the commitment detection pipeline based on `briefs/Rippled - 8. Commitment Detection Brief.md`.

### Key Brief Points (Summary)

Detection should:
- Cast a **broad but disciplined net** — capture more than we ultimately surface
- Optimize for **high recall on real commitments** + **controlled noise**
- Preserve ambiguity — detection isn't final truth
- Produce **candidate commitment signals**, not final commitments
- Be **source-aware** (meetings vs Slack vs email have different patterns)

Detection outputs a `commitment_candidate` with:
- source reference
- detected spans (the text that triggered detection)
- trigger class (explicit promise, delegated action, implied follow-up, etc.)
- initial confidence hint
- context window (surrounding text for later analysis)

### Files to Read

1. `briefs/Rippled - 8. Commitment Detection Brief.md` — full spec
2. `briefs/Rippled - 4. Source Model Brief.md` — source types
3. `app/models/` — existing ORM models (especially `commitment_candidate.py`, `commitment_signal.py`)
4. `build/phases/01-schema/decisions.md` — schema decisions
5. `build/phases/02-api-scaffold/interpretation.md` — API structure

### Deliverables

1. **Detection service** in `app/services/detection/`
   - `detector.py` — main detection orchestration
   - `patterns.py` — trigger patterns by source type
   - `context.py` — context window extraction
   
2. **Source-specific detection** 
   - Meeting transcript detection (speaker attribution matters)
   - Slack detection (thread context, mentions)
   - Email detection (reply chains, CC implications)

3. **Celery task** for async detection
   - Trigger detection when new `source_item` is ingested
   - Create `commitment_candidate` records

4. **Tests** in `tests/services/test_detection.py`
   - Test each trigger class
   - Test source-specific patterns
   - Test context window extraction

### Skills to Use for Phase 3

- **superpowers** — TDD workflow (write tests first, implement to pass, refactor)
- **postgres-best-practices** — For any query optimization
- **static-analysis** — Run security checks before completing
- **modern-python** — Follow modern Python patterns
- **property-based-testing** — For detection edge cases

### Build Protocol

1. Complete Phase 1 & 2 reviews first (see above)
2. Write Phase 3 interpretation to `build/phases/03-detection/interpretation.md`
3. **STOP** — Wait for Kevin's approval
4. After approval: implement with TDD, document decisions
5. Run `static-analysis` before marking complete
6. Update `build/phases/03-detection/completed.md`

### Do NOT

- Reference any OpenAgency OS code
- Skip the Phase 1 & 2 reviews
- Skip writing tests
- Make detection too aggressive (avoid noise)
- Make final commitment decisions in this layer

### Questions?

If anything is unclear, write questions in your interpretation and stop. Don't guess on ambiguous requirements.
