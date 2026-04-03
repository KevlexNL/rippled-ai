"""Prompt registry — returns hardcoded default or DB override.

Centralizes access to all pipeline prompt texts. Each prompt has a catalog
entry with metadata. When a DB session is available, checks the
prompt_overrides table for admin-managed overrides.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.models.orm import PromptOverride
from app.services.orchestration.prompts import (
    candidate_gate,
    escalation,
    extraction,
    slack_overlay,
    speech_act,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Lazy imports for modules outside orchestration — avoids circular deps
_model_detection_prompt: str | None = None
_llm_judge_prompt: str | None = None


def _get_model_detection_prompt() -> str:
    global _model_detection_prompt
    if _model_detection_prompt is None:
        from app.services.model_detection import _SYSTEM_PROMPT
        _model_detection_prompt = _SYSTEM_PROMPT
    return _model_detection_prompt


def _get_llm_judge_prompt() -> str:
    global _llm_judge_prompt
    if _llm_judge_prompt is None:
        from app.services.llm_judge import JUDGE_PROMPT
        _llm_judge_prompt = JUDGE_PROMPT
    return _llm_judge_prompt


PROMPT_CATALOG: dict[str, dict] = {
    "candidate_gate": {
        "label": "Candidate Gate",
        "description": "Stage 1: Determines whether a message contains a business commitment, completion evidence, or ambiguous action language.",
        "source_file": "app/services/orchestration/prompts/candidate_gate.py",
        "get_default": lambda: candidate_gate.SYSTEM_PROMPT,
    },
    "speech_act": {
        "label": "Speech Act Classifier",
        "description": "Stage 2: Classifies the communicative intent (request, self-commitment, acceptance, delegation, etc.)",
        "source_file": "app/services/orchestration/prompts/speech_act.py",
        "get_default": lambda: speech_act.SYSTEM_PROMPT,
    },
    "extraction": {
        "label": "Commitment Extractor",
        "description": "Stage 3: Extracts structured fields — owner, deliverable, timing, target — from a classified commitment message.",
        "source_file": "app/services/orchestration/prompts/extraction.py",
        "get_default": lambda: extraction.SYSTEM_PROMPT,
    },
    "escalation": {
        "label": "Escalation Resolver",
        "description": "Stage 5: Resolves ambiguous signals that the main pipeline could not classify with high confidence.",
        "source_file": "app/services/orchestration/prompts/escalation.py",
        "get_default": lambda: escalation.SYSTEM_PROMPT,
    },
    "slack_overlay": {
        "label": "Slack Context Overlay",
        "description": "Appended to base prompts for Slack source signals to handle informal language patterns.",
        "source_file": "app/services/orchestration/prompts/slack_overlay.py",
        "get_default": lambda: slack_overlay.SYSTEM_ADDENDUM,
    },
    "model_detection": {
        "label": "Model Detection",
        "description": "Used by the hybrid model detection service to classify candidates via GPT (older detection path).",
        "source_file": "app/services/model_detection.py",
        "get_default": _get_model_detection_prompt,
    },
    "llm_judge": {
        "label": "LLM Judge",
        "description": "Used by the weekly Anthropic quality sweep to review and score detection outputs.",
        "source_file": "app/services/llm_judge.py",
        "get_default": _get_llm_judge_prompt,
    },
}


def get_prompt(prompt_id: str, default: str, db: Session | None = None) -> str:
    """Return the active prompt text: DB override if found, else default.

    Args:
        prompt_id: The prompt slug (e.g. "candidate_gate").
        default: The hardcoded default prompt text.
        db: Optional sync SQLAlchemy session. If None, returns default directly.
    """
    if db is None:
        return default

    try:
        row = db.get(PromptOverride, prompt_id)
        if row is not None:
            return row.text
    except Exception:
        logger.warning("Failed to look up prompt override for %s, using default", prompt_id, exc_info=True)

    return default


def get_all_prompts_with_overrides(db: Session) -> list[dict]:
    """Return all catalog entries merged with any DB overrides."""
    from sqlalchemy import select

    # Fetch all overrides in one query
    result = db.execute(select(PromptOverride))
    overrides = {row.id: row for row in result.scalars().all()}

    items = []
    for prompt_id, entry in PROMPT_CATALOG.items():
        default_text = entry["get_default"]()
        override = overrides.get(prompt_id)
        override_text = override.text if override else None

        items.append({
            "id": prompt_id,
            "label": entry["label"],
            "description": entry["description"],
            "source_file": entry["source_file"],
            "default_text": default_text,
            "override_text": override_text,
            "is_overridden": override_text is not None,
            "char_count": len(override_text) if override_text else len(default_text),
            "updated_at": override.updated_at.isoformat() if override else None,
        })

    return items


async def get_all_prompts_with_overrides_async(db) -> list[dict]:
    """Async variant for FastAPI routes using AsyncSession."""
    from sqlalchemy import select

    result = await db.execute(select(PromptOverride))
    overrides = {row.id: row for row in result.scalars().all()}

    items = []
    for prompt_id, entry in PROMPT_CATALOG.items():
        default_text = entry["get_default"]()
        override = overrides.get(prompt_id)
        override_text = override.text if override else None

        items.append({
            "id": prompt_id,
            "label": entry["label"],
            "description": entry["description"],
            "source_file": entry["source_file"],
            "default_text": default_text,
            "override_text": override_text,
            "is_overridden": override_text is not None,
            "char_count": len(override_text) if override_text else len(default_text),
            "updated_at": override.updated_at.isoformat() if override else None,
        })

    return items
