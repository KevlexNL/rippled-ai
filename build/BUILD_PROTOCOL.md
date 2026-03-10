# Rippled.ai Build Protocol

## The Build Cycle

Every phase follows this exact cycle. No skipping. No merging stages.
At the start of each stage, state explicitly which stage you are in.

---

### STAGE 1 — INTAKE
**What:** Read everything needed before writing a single line of code or interpretation.

Checklist:
- [ ] Read the WO in full
- [ ] Read all context files listed in the WO
- [ ] Read the relevant brief(s) from `briefs/`
- [ ] Read prior phase `decisions.md` files if referenced
- [ ] Read existing models/routes relevant to this phase

**Exit condition:** All listed files read. Nothing left to load.
**Next:** Move to STAGE 2 — INTERPRET

---

### STAGE 2 — INTERPRET
**What:** Write your understanding of what needs to be built.

Checklist:
- [ ] Write `build/phases/XX-name/interpretation.md`
  - What the phase does and why
  - How you plan to implement it (architecture, patterns, key decisions)
  - Open questions or ambiguities
- [ ] **Immediately notify Kevin via Telegram** that interpretation is ready
  - Message: "Phase XX interpretation ready for evaluation — [one-line summary]. Awaiting your go-ahead."

**Exit condition:** interpretation.md written. Kevin notified. Response received.
**Next:** If approved → STAGE 3. If changes requested → revise and re-notify.

---

### STAGE 3 — BUILD
**What:** Implement. Use TDD — write failing tests first, implement to pass, refactor.

Checklist:
- [ ] Write failing tests first (`tests/`)
- [ ] Implement to pass tests
- [ ] Refactor for clarity and correctness
- [ ] Update `build/phases/XX-name/decisions.md` with every non-obvious choice and why

**Exit condition:** All planned deliverables implemented. All tests passing.
**Next:** Move to STAGE 4 — VERIFY

---

### STAGE 4 — VERIFY
**What:** Prove it works before calling it done.

Checklist:
- [ ] All tests pass (`pytest`)
- [ ] Run `ruff check app/` — fix any issues
- [ ] Manual smoke test or curl check if applicable
- [ ] No regressions in prior phase tests

**Exit condition:** Tests green. Linter clean. Behaviour confirmed.
**Next:** Move to STAGE 5 — COMMIT

---

### STAGE 5 — COMMIT
**What:** Package the work cleanly.

Checklist:
- [ ] Write `build/phases/XX-name/completed.md` — list every file created/modified with one-line descriptions
- [ ] `git add` only relevant files (never commit `.env`, `__pycache__`, etc.)
- [ ] Commit with message: `feat: phase XX — [short description]`
- [ ] Push to main

**Exit condition:** Clean commit pushed.
**Next:** Move to STAGE 6 — REPORT

---

### STAGE 6 — REPORT
**What:** Close the loop with Kevin. Set up the next cycle.

Checklist:
- [ ] Send Kevin a completion summary via Telegram:
  - What was built
  - Key decisions made
  - Any follow-up items or watch-outs
  - What phase is next
- [ ] Update `build/current-phase.txt` to next phase
- [ ] Create or update the next phase WO if needed
- [ ] Write Morpheus completion signal (see WO)

**Exit condition:** Kevin notified. Next phase WO ready. Current WO marked complete.
**Next:** INTAKE on next phase.

---

## Hard Rules

- **Never** proceed to the next stage without completing the current stage's checklist
- **Intake before interpret.** Interpret before build. Always.
- **Kevin evaluates interpretation** — this is not optional and is not negotiable
- After writing interpretation, **notify Kevin immediately** — do not wait passively
- Production deploys: no approval needed (project not yet live)
- Mid-build stops: only for destructive/irreversible actions, scope conflicts, or genuine blockers

## Context Boundaries

- **READ ONLY** files listed in your WO
- **NEVER** reference OpenAgency OS, Interpretation Engine, Gating API, or any archived code
- **NEVER** assume context from previous sessions — each WO is a fresh start
- The `briefs/` folder is **READ-ONLY** — never modify brief files

## Phase Overview

| Phase | Focus | Primary Briefs |
|-------|-------|----------------|
| 01-schema | Database tables + Alembic migrations | Brief 3 (Domain Model), Brief 5 (Lifecycle) |
| 02-api-scaffold | Route structure + Pydantic models | Brief 7 (MVP Scope) |
| 03-detection | Commitment extraction from sources | Brief 8 (Detection) |
| 04-clarification | Ambiguity resolution workflow | Brief 9 (Clarification) |
| 05-completion | Completion detection logic | Brief 10 (Completion) |
| 06-surfacing | Priority scoring + surface selection | Brief 6 (Surfacing) |

## Current Phase
See `build/current-phase.txt`
