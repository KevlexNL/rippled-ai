# Rippled.ai Build Protocol

## The Build Cycle

Every phase follows this exact 6-stage cycle. No skipping. No merging stages.
At the start of each stage, state explicitly which stage you are entering.

**Division of labour:** Claude Code does all the work — analysis, interpretation, coding, testing, linting, committing. Trinity orchestrates and decides — loads context, spawns Claude Code with the right brief and skills, reviews output against the directive, approves or redirects, advances stages.

---

### STAGE 1 — INTAKE
**Who:** Trinity
**What:** Read everything needed before spawning Claude Code.

Checklist:
- [ ] Read the WO in full
- [ ] Read all context files listed in the WO
- [ ] Read the relevant brief(s) from `briefs/`
- [ ] Read prior phase `decisions.md` files if referenced
- [ ] Confirm current phase in `build/current-phase.txt` and `build/state.json`

**Exit condition:** All listed files read. Full context loaded.
**Next:** Move to STAGE 2 — INTERPRET

---

### STAGE 2 — INTERPRET
**Who:** Claude Code does the work → Trinity reviews and decides
**What:** Claude Code analyses the brief and produces an interpretation. Trinity reviews it against the brief and directive, then decides whether to proceed.

Checklist:
- [ ] Spawn Claude Code with: brief, prior decisions, relevant models/routes, skills (`modern-python`, `postgres-best-practices`, `static-analysis`)
- [ ] Claude Code writes `build/phases/XX-name/interpretation.md`:
  - What the phase does and why
  - Proposed implementation (architecture, patterns, key decisions)
  - Open questions with Claude Code's recommended answers
- [ ] Trinity reviews interpretation against:
  - The relevant brief in `briefs/`
  - The phased build directive
  - Existing schema/API decisions
- [ ] If interpretation meets the standard: Trinity approves and proceeds immediately
- [ ] If interpretation has issues: Trinity steers Claude Code, regenerate, re-review
- [ ] Trinity documents the approved direction in `build/state.json` (`last_action`)

**Self-approval rule:** Trinity does not wait for Kevin. Claude Code recommends, Trinity decides. If it meets the brief and doesn't break existing work, it's approved.

**Exit condition:** interpretation.md written, reviewed by Trinity, decision made.
**Next:** Move to STAGE 3 — BUILD

---

### STAGE 3 — BUILD
**Who:** Claude Code implements and tests → Trinity reviews
**What:** Claude Code implements using TDD. Trinity reviews commits and output.

Checklist:
- [ ] Spawn Claude Code with approved interpretation + TDD instruction
- [ ] Claude Code uses skills: `superpowers` (TDD), `modern-python`, `property-based-testing`
- [ ] Write failing tests first
- [ ] Implement to pass tests
- [ ] Refactor for clarity
- [ ] Claude Code updates `build/phases/XX-name/decisions.md` — every non-obvious choice

**Exit condition:** All planned deliverables implemented. All tests passing.
**Next:** Move to STAGE 4 — VERIFY

---

### STAGE 4 — VERIFY
**Who:** Claude Code runs all checks → Trinity confirms
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
**Who:** Trinity (or Claude Code under Trinity direction)
**What:** Package the work cleanly.

Checklist:
- [ ] Write `build/phases/XX-name/completed.md` — list every file created/modified
- [ ] Write `build/phases/XX-name/completed.flag` — empty marker file
- [ ] `git add` only relevant files (never `.env`, `__pycache__`, etc.)
- [ ] Commit: `feat: phase XX — [short description]`
- [ ] Push to main
- [ ] Update `build/state.json` — advance phase, set next action

**Exit condition:** Clean commit pushed. State updated.
**Next:** Move to STAGE 6 — REPORT

---

### STAGE 6 — REPORT
**Who:** Trinity
**What:** Close the loop. Set up the next cycle.

Checklist:
- [ ] Update `build/current-phase.txt` to next phase
- [ ] Create next phase WO if not already present
- [ ] Write Morpheus completion signal (see WO template)
- [ ] Notify Kevin via Telegram with completion summary:
  - What was built
  - Key decisions made
  - What's next

**Exit condition:** Kevin notified. Next phase queued. WO closed.
**Next:** INTAKE on next phase.

---

## Hard Rules

- **Never** proceed to the next stage without completing the current checklist
- **Claude Code does all the work. Trinity orchestrates and decides.** Never bypass this — Claude Code handles analysis, coding, testing, linting, committing. Trinity loads context, spawns CC with precise prompts, reviews output against the brief, makes the call
- **Self-approval at Stage 2** — Trinity reviews against the brief. No waiting for Kevin
- **Only stop mid-build for:** destructive/irreversible actions on live data, scope conflicts with other phases, or genuine blockers with no resolution path
- **Production deploys:** no approval needed (Rippled is not yet live)
- **Document every decision** — `decisions.md` is the record that survives session resets

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
