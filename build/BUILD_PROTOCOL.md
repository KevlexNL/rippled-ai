# Rippled.ai Build Protocol

## Rules for Trinity (Claude Code)

### Context Boundaries
- **READ ONLY** the files listed in your Work Order
- **NEVER** reference OpenAgency OS, Interpretation Engine, Gating API, or any archived code
- **NEVER** assume context from previous sessions — each WO is a fresh start
- The `briefs/` folder is **READ-ONLY** — never modify brief files

### Continuous Build Workflow
1. Read the files listed in your WO
2. Write your understanding to `build/phases/XX/interpretation.md`
3. **Proceed immediately to implementation** — do not wait for approval
4. Document decisions in `build/phases/XX/decisions.md`
5. List all created/modified files in `build/phases/XX/completed.md`
6. Report completion to Kevin via Telegram

### When to STOP and ask Kevin
Only stop if:
- A decision would be **irreversible and destructive** (e.g. dropping tables with live data)
- A change **conflicts with agreed architecture** in ways that affect other phases
- You are **genuinely blocked** and cannot proceed without a missing input (credential, spec gap, etc.)
- You hit a **scope change** that belongs to another agent's domain

Do NOT stop for: interpretation steps, production deploys, test failures you can fix, style/approach choices.

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
