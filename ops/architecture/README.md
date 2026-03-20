# Architecture Diagram — ops/architecture/

Single source of truth for the Rippled architecture map, rendered at `/admin/architecture`.

## Data Source

`rippled-arch.json` — static JSON describing every system node and edge.

## Node Schema

```json
{
  "id": "signal-detection",
  "label": "Candidate Detection",
  "layer": "signal_pipeline",
  "status": "stable | in_progress | broken | planned | decision_needed",
  "description": "What this component does",
  "code_path": "app/services/model_detection.py",
  "git_sha": "abc123",
  "prompt_version": "ongoing-v4",
  "prompt_file": "ops/prompts/detection-prompt-v4.md",
  "wos": ["WO-RIPPLED-COMMITMENT-STRUCTURE-DETECTION"],
  "open_questions": ["Open design question?"]
}
```

### Fields

| Field | Required | Description |
|-------|----------|-------------|
| `id` | yes | Unique identifier |
| `label` | yes | Display name |
| `layer` | yes | One of: `user_flow`, `signal_pipeline`, `commitment_lifecycle`, `evaluation`, `integrations` |
| `status` | yes | `stable` / `in_progress` / `broken` / `planned` / `decision_needed` |
| `description` | yes | One-liner describing what this component does |
| `code_path` | no | Path to primary source file/directory |
| `git_sha` | no | Last known commit SHA touching this node |
| `prompt_version` | no | Active prompt version label |
| `prompt_file` | no | Path to prompt file under `ops/prompts/` |
| `wos` | no | Related work order IDs |
| `open_questions` | no | Unresolved design questions |

## Edge Schema

```json
{
  "id": "e1",
  "source": "signal-detection",
  "target": "signal-classification",
  "label": "candidate signal"
}
```

## Status Colors

| Status | Color |
|--------|-------|
| `stable` | Green |
| `in_progress` | Blue |
| `planned` | Grey (dashed border) |
| `broken` | Red |
| `decision_needed` | Amber |

## Layers

- **user_flow** — User-facing screens and onboarding
- **signal_pipeline** — Detection → extraction → surfacing pipeline
- **commitment_lifecycle** — Lifecycle state machine (proposed → closed)
- **evaluation** — Audit, judge, eval harness, prompt registry
- **integrations** — External connectors (email, Slack, Read.ai, calendar)

## Dev Cycle Rule

Every work order must include:

1. **Update `rippled-arch.json`** — change status of affected nodes (e.g. `planned` → `stable`)
2. **Add new nodes** created by the WO
3. **Commit in the same PR** as the feature

Mero reviews the diagram diff as part of WO sign-off.
