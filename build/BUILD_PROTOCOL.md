# Rippled.ai Build Protocol

## Rules for Trinity (Claude Code)

### Context Boundaries
- **READ ONLY** the files listed in your Work Order
- **NEVER** reference OpenAgency OS, Interpretation Engine, Gating API, or any archived code
- **NEVER** assume context from previous sessions — each WO is a fresh start
- The `briefs/` folder is **READ-ONLY** — never modify brief files

### Interpretation-First Workflow
1. Read the files listed in your WO
2. Write your understanding to `build/phases/XX/interpretation.md`
3. **STOP** — wait for Kevin's approval before building
4. After approval, implement and document decisions in `build/phases/XX/decisions.md`
5. List all created/modified files in `build/phases/XX/completed.md`

### File Naming
- `interpretation.md` — Your understanding of what needs to be built
- `decisions.md` — Technical choices you made and why
- `completed.md` — List of files created/modified with one-line descriptions

### Quality Gates
- No phase proceeds without Kevin's explicit "continue" or "approved"
- If unclear about anything, write questions in `interpretation.md` and stop

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
