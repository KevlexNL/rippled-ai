# Rippled.ai Build Protocol

## Rules for Trinity (Claude Code)

### Context Boundaries
- **READ ONLY** the files listed in your Work Order
- **NEVER** reference OpenAgency OS, Interpretation Engine, Gating API, or any archived code
- **NEVER** assume context from previous sessions — each WO is a fresh start
- The `briefs/` folder is **READ-ONLY** — never modify brief files

### Build Workflow
1. Read the files listed in your WO
2. Write your understanding to `build/phases/XX/interpretation.md`
3. **Immediately notify Kevin via Telegram** that interpretation is ready for evaluation
4. Wait for Kevin's evaluation (approval or changes) before implementing
5. After approval: implement, document decisions in `decisions.md`, list files in `completed.md`
6. Commit and report completion to Kevin via Telegram

### When to STOP and ask Kevin
- **Always:** After writing interpretation — notify Kevin immediately, wait for evaluation
- **Always:** If a decision would be irreversible and destructive (e.g. dropping tables with live user data)
- **Always:** If a scope change conflicts with agreed architecture and affects other phases
- **Always:** If you are genuinely blocked on a missing input (credential, spec gap) you cannot resolve

### No approval needed for
- Production deploys (project is not yet live)
- Test failures you can fix yourself
- Style/approach choices within an approved interpretation
- Refactoring within the agreed scope

### File Naming
- `interpretation.md` — Your understanding of what needs to be built
- `decisions.md` — Technical choices you made and why
- `completed.md` — List of files created/modified with one-line descriptions

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
