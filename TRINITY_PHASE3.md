# Trinity — Phase 3: Commitment Detection

## Context

You've completed:
- **Phase 1:** Database schema (migrations applied, ORM models in place)
- **Phase 2:** API scaffold (routes, Pydantic schemas, CRUD operations)

Now you're building the **detection layer** — the intelligence that identifies commitment signals from source content.

## Your Assignment

Build the commitment detection pipeline based on `briefs/Rippled - 8. Commitment Detection Brief.md`.

## Key Brief Points (Summary)

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

## Files to Read

1. `briefs/Rippled - 8. Commitment Detection Brief.md` — full spec
2. `briefs/Rippled - 4. Source Model Brief.md` — source types
3. `app/models/` — existing ORM models (especially `commitment_candidate.py`, `commitment_signal.py`)
4. `build/phases/01-schema/decisions.md` — schema decisions
5. `build/phases/02-api-scaffold/interpretation.md` — API structure

## Deliverables

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

## New Capabilities

You now have Claude Code skills installed:
- **superpowers** — Use for TDD workflow (`/test-driven-development`)
- **postgres-best-practices** — For any query optimization
- **static-analysis** — Run security checks before completing
- **modern-python** — Follow modern Python patterns (ruff, pytest)

**Leverage superpowers for this phase:** Write tests first, implement to pass, refactor.

## Build Protocol

1. Write your interpretation to `build/phases/03-detection/interpretation.md`
2. **STOP** — Wait for Kevin's approval
3. After approval: implement with TDD, document decisions
4. Run `static-analysis` before marking complete
5. Update `build/phases/03-detection/completed.md`

## Do NOT

- Reference any OpenAgency OS code
- Skip writing tests
- Make detection too aggressive (avoid noise)
- Make final commitment decisions in this layer

## Questions?

If anything in Brief 8 is unclear, write questions in your interpretation and stop. Don't guess on ambiguous requirements.
