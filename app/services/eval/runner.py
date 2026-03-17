"""Eval harness runner — WO-RIPPLED-EVAL-HARNESS.

Runs a prompt version against labeled eval datasets and computes
precision / recall / F1 scores. Reuses the same LLM call path as
the seed pass but writes results to eval-specific tables only.

Public API:
    classify_result(expected, actual) -> str
    compute_scores(tp, fp, tn, fn) -> EvalScores
    run_eval(user_id, prompt_version, model, dataset_size, db) -> EvalRunResult
"""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP

import anthropic
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.connectors.shared.credentials_utils import decrypt_value
from app.models.orm import EvalDataset, EvalRun, EvalRunItem, SourceItem, UserSettings
from app.services.detection.audit import estimate_cost

logger = logging.getLogger(__name__)

# Regex to strip markdown code fences (```json ... ``` or ``` ... ```)
_CODE_FENCE_RE = re.compile(r"```(?:json)?\s*\n?(.*?)\n?\s*```", re.DOTALL)

_QUANTIZE_4 = Decimal("0.0001")


@dataclass
class EvalScores:
    """Precision / recall / F1 scores rounded to 4 decimal places."""

    precision: Decimal
    recall: Decimal
    f1: Decimal


@dataclass
class EvalRunResult:
    """Summary returned after an eval run completes."""

    eval_run_id: str = ""
    items_tested: int = 0
    true_positives: int = 0
    false_positives: int = 0
    true_negatives: int = 0
    false_negatives: int = 0
    precision: Decimal = Decimal("0")
    recall: Decimal = Decimal("0")
    f1: Decimal = Decimal("0")
    total_cost: Decimal = Decimal("0")
    duration_ms: int = 0
    errors: list[str] = field(default_factory=list)


def classify_result(expected_has_commitment: bool, actual_has_commitment: bool) -> str:
    """Classify a single eval result as tp/fp/tn/fn."""
    if expected_has_commitment and actual_has_commitment:
        return "tp"
    if not expected_has_commitment and actual_has_commitment:
        return "fp"
    if not expected_has_commitment and not actual_has_commitment:
        return "tn"
    return "fn"


def compute_scores(tp: int, fp: int, tn: int, fn: int) -> EvalScores:
    """Compute precision, recall, F1 from confusion matrix counts."""
    total_predicted_positive = tp + fp
    total_actual_positive = tp + fn

    if total_predicted_positive == 0:
        precision = Decimal("0")
    else:
        precision = Decimal(tp) / Decimal(total_predicted_positive)

    if total_actual_positive == 0:
        recall = Decimal("0")
    else:
        recall = Decimal(tp) / Decimal(total_actual_positive)

    if precision + recall == 0:
        f1 = Decimal("0")
    else:
        f1 = 2 * precision * recall / (precision + recall)

    return EvalScores(
        precision=precision.quantize(_QUANTIZE_4, rounding=ROUND_HALF_UP),
        recall=recall.quantize(_QUANTIZE_4, rounding=ROUND_HALF_UP),
        f1=f1.quantize(_QUANTIZE_4, rounding=ROUND_HALF_UP),
    )


def _strip_markdown_json(raw: str) -> str:
    """Extract JSON from a response that may be wrapped in markdown code fences."""
    m = _CODE_FENCE_RE.search(raw)
    return m.group(1).strip() if m else raw.strip()


# The system prompt used for eval — same as seed-v1 by default.
# Prompt templates are selected by prompt_version string.
def _get_system_prompt(prompt_version: str) -> str:
    """Return the system prompt for the given version.

    For now, all versions use the seed-v1 prompt. Future versions
    will load from app/services/detection/prompts/<version>.txt.
    """
    return _SEED_V1_PROMPT


_SEED_V1_PROMPT = """You are a commitment extraction engine for a workplace intelligence system.

Analyze the following email and extract ALL commitments, follow-ups, or obligations.

A commitment is a statement where someone obligates themselves or others to a specific
future action, deliverable, or outcome. This includes:
- Explicit: "I will", "I'll", "We will", "I promise", "I commit to"
- Implicit: "Consider it done", "Leave it with me", "I'll look into that"
- Follow-ups: "Let me circle back", "I'll send this over", "Will follow up"
- Delegations: "Can you handle...", "Please take care of..."
- Scheduled actions: "Let's meet Tuesday", "I'll call you tomorrow"

NOT a commitment:
- Casual acknowledgments: "OK", "Sounds good", "Got it"
- Questions or hypotheticals: "Should we...?", "What if we..."
- Past-tense descriptions: "I already did X", "We completed Y"
- Filler phrases: "By the way", "Just checking in"
- Informational statements with no action implication

For each commitment found, extract:
- trigger_phrase: the exact words that signal the commitment
- who_committed: who made the commitment (name or role)
- directed_at: who the commitment is directed at (name, role, or null)
- urgency: "high", "medium", or "low"
- commitment_type: one of "send", "review", "follow_up", "deliver", "investigate", "introduce", "coordinate", "update", "delegate", "schedule", "confirm", "other"
- title: a concise summary (max 80 chars)
- is_external: true if this involves someone outside the organization

Respond with valid JSON only:
{
  "commitments": [
    {
      "trigger_phrase": "...",
      "who_committed": "...",
      "directed_at": "...",
      "urgency": "high|medium|low",
      "commitment_type": "...",
      "title": "...",
      "is_external": true|false,
      "confidence": 0.0-1.0
    }
  ]
}

If no commitments are found, return: {"commitments": []}"""


def run_eval(
    user_id: str,
    prompt_version: str,
    model: str,
    dataset_size: int | None,
    db: Session,
) -> EvalRunResult:
    """Run an eval pass against the labeled dataset for a user.

    This is the main entry point called from the Celery task.
    It does NOT write to commitment_signals or commitments — eval is isolated.

    Args:
        user_id: UUID of the user.
        prompt_version: Prompt template version (e.g. "seed-v1", "seed-v2").
        model: Anthropic model ID (e.g. "claude-haiku-4-5").
        dataset_size: Max items to test (None = all).
        db: SQLAlchemy sync session.

    Returns:
        EvalRunResult with scores and run metadata.
    """
    result = EvalRunResult()
    start = time.monotonic()

    # Load API key
    user_settings = db.execute(
        select(UserSettings).where(UserSettings.user_id == user_id)
    ).scalar_one_or_none()

    if not user_settings or not user_settings.anthropic_api_key_encrypted:
        result.errors.append("No Anthropic API key configured")
        return result

    api_key = decrypt_value(user_settings.anthropic_api_key_encrypted)
    if not api_key:
        result.errors.append("Failed to decrypt Anthropic API key")
        return result

    client = anthropic.Anthropic(api_key=api_key)
    system_prompt = _get_system_prompt(prompt_version)

    # Load labeled dataset
    query = (
        select(EvalDataset)
        .where(EvalDataset.user_id == user_id)
        .order_by(EvalDataset.labeled_at.asc())
    )
    if dataset_size:
        query = query.limit(dataset_size)

    dataset_items = db.execute(query).scalars().all()

    if not dataset_items:
        result.errors.append("No labeled eval dataset items found")
        return result

    # Create the eval_run row
    eval_run = EvalRun(
        user_id=user_id,
        prompt_version=prompt_version,
        model=model,
    )
    db.add(eval_run)
    db.flush()
    result.eval_run_id = eval_run.id

    total_cost = Decimal("0")

    for ds_item in dataset_items:
        # Load the source item
        source_item = db.execute(
            select(SourceItem).where(SourceItem.id == ds_item.source_item_id)
        ).scalar_one_or_none()

        if not source_item:
            logger.warning("Eval: source_item %s not found, skipping", ds_item.source_item_id)
            continue

        content = source_item.content or ""
        if len(content.strip()) < 10:
            # Too short — treat as no commitment found
            actual_has = False
            raw_prompt = None
            raw_response = None
            parsed = []
            tokens_in = None
            tokens_out = None
            cost = None
        else:
            # Build user message (same as seed pass)
            parts = [f"Source type: {source_item.source_type}"]
            if source_item.sender_name or source_item.sender_email:
                parts.append(
                    f"From: {source_item.sender_name or ''} "
                    f"<{source_item.sender_email or ''}>"
                )
            if source_item.direction:
                parts.append(f"Direction: {source_item.direction}")
            parts.append(f"\n--- Email Content ---\n{content}")
            user_message = "\n".join(parts)

            raw_prompt = f"[system]\n{system_prompt}\n\n[user]\n{user_message}"

            try:
                response = client.messages.create(
                    model=model,
                    max_tokens=4096,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_message}],
                    temperature=0.1,
                )
                tokens_in = response.usage.input_tokens if response.usage else None
                tokens_out = response.usage.output_tokens if response.usage else None

                raw_response = response.content[0].text
                cleaned = _strip_markdown_json(raw_response)
                data = json.loads(cleaned)
                parsed = data.get("commitments", [])
                actual_has = len(parsed) > 0
                cost = estimate_cost(model, tokens_in, tokens_out)
                if cost:
                    total_cost += cost

            except (json.JSONDecodeError, KeyError, IndexError) as exc:
                logger.warning("Eval: parse error for item %s: %s", source_item.id, exc)
                actual_has = False
                parsed = None
                cost = None
                tokens_in = None
                tokens_out = None

            except Exception as exc:
                logger.error("Eval: LLM error for item %s: %s", source_item.id, exc)
                result.errors.append(f"Item {source_item.id}: {exc}")
                continue

        # Classify
        classification = classify_result(ds_item.expected_has_commitment, actual_has)
        passed = classification in ("tp", "tn")

        if classification == "tp":
            result.true_positives += 1
        elif classification == "fp":
            result.false_positives += 1
        elif classification == "tn":
            result.true_negatives += 1
        elif classification == "fn":
            result.false_negatives += 1

        result.items_tested += 1

        # Write eval_run_item
        run_item = EvalRunItem(
            eval_run_id=eval_run.id,
            source_item_id=ds_item.source_item_id,
            expected_has_commitment=ds_item.expected_has_commitment,
            actual_has_commitment=actual_has,
            passed=passed,
            raw_prompt=raw_prompt,
            raw_response=raw_response if "raw_response" in dir() else None,
            parsed_commitments=parsed,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_estimate=cost,
        )
        db.add(run_item)

    # Compute scores
    scores = compute_scores(
        result.true_positives,
        result.false_positives,
        result.true_negatives,
        result.false_negatives,
    )
    result.precision = scores.precision
    result.recall = scores.recall
    result.f1 = scores.f1
    result.total_cost = total_cost
    result.duration_ms = int((time.monotonic() - start) * 1000)

    # Update the eval_run row with scores
    eval_run.items_tested = result.items_tested
    eval_run.true_positives = result.true_positives
    eval_run.false_positives = result.false_positives
    eval_run.true_negatives = result.true_negatives
    eval_run.false_negatives = result.false_negatives
    eval_run.precision_score = scores.precision
    eval_run.recall_score = scores.recall
    eval_run.f1_score = scores.f1
    eval_run.total_cost_estimate = total_cost
    eval_run.duration_ms = result.duration_ms

    db.flush()
    db.commit()

    logger.info(
        "Eval run complete: run_id=%s items=%d precision=%.4f recall=%.4f f1=%.4f cost=$%.6f",
        eval_run.id,
        result.items_tested,
        scores.precision,
        scores.recall,
        scores.f1,
        total_cost,
    )
    return result
