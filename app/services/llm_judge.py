"""LLM Judge — Sonnet reviews Haiku's detection output (WO-RIPPLED-LLM-JUDGE).

Weekly automated run: pulls detection_audit rows, sends each to Sonnet for
quality evaluation, accumulates results into llm_judge_runs, and triggers
a prompt improvement WO if quality thresholds are breached.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import anthropic
from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from app.connectors.shared.credentials_utils import decrypt_value
from app.models.orm import DetectionAudit, LlmJudgeRun, SignalFeedback, UserSettings

logger = logging.getLogger(__name__)

TARGET_USER_ID = "441f9c1f-9428-477e-a04f-fb8d5e654ec2"
JUDGE_MODEL = "claude-sonnet-4-6"
COST_PER_INPUT_TOKEN = 0.000003
COST_PER_OUTPUT_TOKEN = 0.000015

_CODE_FENCE_RE = re.compile(r"```(?:json)?\s*\n?(.*?)\n?\s*```", re.DOTALL)

JUDGE_PROMPT = """\
You are reviewing the output of a commitment detection model.

Source email:
{source_content}

Model extracted:
{parsed_result}

Evaluate:
1. Were all commitments in this email correctly identified? List any that were missed.
   - "Follow up on [topic]", "need to follow up", "checking in on [topic]" ARE commitments — always.
   - ANY form of "follow up" is a commitment. Missing one is a significant error.
2. Were any extracted items NOT actually commitments? List false positives.
   - Classification labels or meta-references (e.g. "greeting", "pleasantry", "filler") are NOT commitments, but they are also NOT false positives — they are artifacts of the model's internal labeling. Do not list them as false positives.
   - Greetings, sign-offs, and pleasantries are NOT commitments.
3. Rate extraction quality using this rubric:
   - 5: All commitments found, no false positives, correct metadata
   - 4: All commitments found, minor metadata issues or one borderline false positive
   - 3: One missed commitment OR one clear false positive
   - 2: Multiple missed commitments or multiple false positives
   - 1: Fundamentally broken — most commitments missed or mostly false positives
4. If quality < 4: suggest one specific change to the detection prompt that would improve this case.
   - Your suggestion must be actionable — e.g. "Add 'follow up on [business topic]' as an explicit example in the follow-up section" or "Move the greeting exclusion rule higher in the prompt for better adherence".
   - Do NOT leave prompt_suggestion empty when quality < 4.

Respond in JSON: {{"missed": [], "false_positives": [], "quality_rating": N, "prompt_suggestion": "..."}}"""


def _parse_judge_response(text: str) -> dict:
    """Extract JSON from judge response, handling markdown fences."""
    fence_match = _CODE_FENCE_RE.search(text)
    if fence_match:
        text = fence_match.group(1)
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        return {
            "missed": [],
            "false_positives": [],
            "quality_rating": 3,
            "prompt_suggestion": "",
            "parse_error": text[:500],
        }


def _get_api_key(db: Session) -> str | None:
    """Get Anthropic API key from UserSettings for target user."""
    user_settings = db.execute(
        select(UserSettings).where(UserSettings.user_id == TARGET_USER_ID)
    ).scalar_one_or_none()
    if not user_settings or not user_settings.anthropic_api_key_encrypted:
        return None
    return decrypt_value(user_settings.anthropic_api_key_encrypted)


def run_llm_judge(db: Session) -> dict:
    """Execute the weekly LLM judge sweep.

    Returns dict with run summary.
    """
    api_key = _get_api_key(db)
    if not api_key:
        return {"status": "skipped", "reason": "no Anthropic API key configured"}

    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)

    # Pull last 7 days of detection_audit rows with raw_response
    audits = db.execute(
        select(DetectionAudit).where(
            and_(
                DetectionAudit.user_id == TARGET_USER_ID,
                DetectionAudit.raw_response.isnot(None),
                DetectionAudit.created_at >= week_ago,
            )
        )
        .order_by(DetectionAudit.created_at.desc())
        .limit(50)
    ).scalars().all()

    if not audits:
        return {"status": "skipped", "reason": "no detection_audit rows with raw_response"}

    client = anthropic.Anthropic(api_key=api_key)
    judge_outputs: list[dict] = []
    total_false_positives = 0
    total_false_negatives = 0
    total_quality = 0
    total_cost = 0.0

    for audit in audits:
        source_content = audit.raw_prompt or "(no source content)"
        parsed_result = json.dumps(audit.parsed_result) if audit.parsed_result else audit.raw_response or ""

        from app.services.orchestration.prompts.registry import get_prompt
        active_judge_prompt = get_prompt("llm_judge", JUDGE_PROMPT, db=db)
        prompt = active_judge_prompt.format(
            source_content=source_content,
            parsed_result=parsed_result,
        )

        try:
            response = client.messages.create(
                model=JUDGE_MODEL,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )

            tokens_in = response.usage.input_tokens
            tokens_out = response.usage.output_tokens
            cost = (tokens_in * COST_PER_INPUT_TOKEN) + (tokens_out * COST_PER_OUTPUT_TOKEN)
            total_cost += cost

            logger.info(
                "LLM judge: audit %s — tokens_in=%d, tokens_out=%d, cost=$%.6f",
                audit.id, tokens_in, tokens_out, cost,
            )

            raw_text = response.content[0].text
            parsed = _parse_judge_response(raw_text)
            parsed["audit_id"] = audit.id
            parsed["tokens_in"] = tokens_in
            parsed["tokens_out"] = tokens_out
            parsed["cost"] = cost
            judge_outputs.append(parsed)

            total_false_positives += len(parsed.get("false_positives", []))
            total_false_negatives += len(parsed.get("missed", []))
            total_quality += parsed.get("quality_rating", 3)

            # Write per-item SignalFeedback row
            missed_text = json.dumps(parsed.get("missed", [])) if parsed.get("missed") else None
            fp_text = json.dumps(parsed.get("false_positives", [])) if parsed.get("false_positives") else None
            feedback = SignalFeedback(
                user_id=TARGET_USER_ID,
                detection_audit_id=audit.id,
                source_item_id=audit.source_item_id,
                reviewer_user_id=TARGET_USER_ID,
                extraction_correct=not parsed.get("missed") and not parsed.get("false_positives"),
                rating=parsed.get("quality_rating"),
                missed_commitments=missed_text,
                false_positives=fp_text,
                notes=parsed.get("prompt_suggestion") or None,
            )
            db.add(feedback)

        except Exception as exc:
            logger.warning("LLM judge: failed for audit %s — %s", audit.id, exc)
            judge_outputs.append({
                "audit_id": audit.id,
                "error": str(exc),
            })

    items_reviewed = len([j for j in judge_outputs if "error" not in j])
    avg_quality = total_quality / items_reviewed if items_reviewed > 0 else 0

    # Collect prompt suggestions
    suggestions = [
        j["prompt_suggestion"]
        for j in judge_outputs
        if j.get("prompt_suggestion") and not j.get("parse_error")
    ]

    # Write llm_judge_runs row
    judge_run = LlmJudgeRun(
        user_id=TARGET_USER_ID,
        judge_model=JUDGE_MODEL,
        student_model="claude-haiku-4-5",
        items_reviewed=items_reviewed,
        false_positives_found=total_false_positives,
        false_negatives_found=total_false_negatives,
        raw_judge_output=json.dumps(judge_outputs),
        prompt_improvement_suggestions={
            "avg_quality_rating": round(avg_quality, 2),
            "suggestions": suggestions[:10],
            "total_cost": round(total_cost, 6),
        },
    )
    db.add(judge_run)
    db.flush()

    # Check thresholds for auto-WO creation (skip when no items were successfully reviewed)
    if items_reviewed > 0 and (avg_quality < 3.5 or total_false_negatives > 5 or total_false_positives > 5):
        _create_prompt_improvement_wo(
            judge_run_id=judge_run.id,
            items_reviewed=items_reviewed,
            avg_quality=avg_quality,
            false_positives=total_false_positives,
            false_negatives=total_false_negatives,
            suggestions=suggestions,
            judge_outputs=judge_outputs,
        )

    return {
        "status": "complete",
        "judge_run_id": judge_run.id,
        "items_reviewed": items_reviewed,
        "false_positives_found": total_false_positives,
        "false_negatives_found": total_false_negatives,
        "avg_quality_rating": round(avg_quality, 2),
        "total_cost": round(total_cost, 6),
    }


def _create_prompt_improvement_wo(
    judge_run_id: str,
    items_reviewed: int,
    avg_quality: float,
    false_positives: int,
    false_negatives: int,
    suggestions: list[str],
    judge_outputs: list[dict],
) -> None:
    """Write a WO file when quality thresholds are breached.

    Skips creation if a PENDING or INPROGRESS WO already exists to avoid
    overwriting an in-flight work order.
    """
    wo_dir = Path("/home/kevinbeeftink/.openclaw/workspace/workorders")
    wo_path = wo_dir / "WO-RIPPLED-PROMPT-IMPROVEMENT_PENDING.md"
    inprogress_path = wo_dir / "WO-RIPPLED-PROMPT-IMPROVEMENT_INPROGRESS.md"

    if wo_path.exists():
        logger.info("LLM judge: skipping WO creation — PENDING WO already exists at %s", wo_path)
        return
    if inprogress_path.exists():
        logger.info("LLM judge: skipping WO creation — INPROGRESS WO already exists at %s", inprogress_path)
        return

    # Find top failure patterns
    missed_items = []
    fp_items = []
    for j in judge_outputs:
        if j.get("missed"):
            missed_items.append(j)
        if j.get("false_positives"):
            fp_items.append(j)

    content = f"""# WO-RIPPLED-PROMPT-IMPROVEMENT — Auto-generated by LLM Judge

**Priority:** HIGH
**Type:** Prompt Engineering
**Generated:** {datetime.now(timezone.utc).isoformat()}
**Judge Run ID:** {judge_run_id}

---

## Summary
- Items reviewed: {items_reviewed}
- Average quality rating: {avg_quality:.2f}/5
- False negatives (missed commitments): {false_negatives}
- False positives (non-commitments extracted): {false_positives}

## Threshold Breaches
"""
    if avg_quality < 3.5:
        content += f"- Average quality {avg_quality:.2f} < 3.5 threshold\n"
    if false_negatives > 5:
        content += f"- {false_negatives} false negatives > 5 threshold\n"
    if false_positives > 5:
        content += f"- {false_positives} false positives > 5 threshold\n"

    content += "\n## Top Prompt Improvement Suggestions\n"
    for i, suggestion in enumerate(suggestions[:5], 1):
        content += f"{i}. {suggestion}\n"

    content += "\n## Sample Failures\n"
    # Deduplicate: an audit with both missed and FP should appear once
    seen_audit_ids: set[str] = set()
    deduplicated: list[dict] = []
    for j in missed_items + fp_items:
        aid = j.get("audit_id", "unknown")
        if aid not in seen_audit_ids:
            seen_audit_ids.add(aid)
            deduplicated.append(j)
    for j in deduplicated[:5]:
        audit_id = j.get("audit_id", "unknown")
        content += f"\n### Audit {audit_id}\n"
        if j.get("missed"):
            content += f"- Missed: {j['missed']}\n"
        if j.get("false_positives"):
            content += f"- False positives: {j['false_positives']}\n"
        content += f"- Quality: {j.get('quality_rating', '?')}/5\n"

    content += "\n## Action Required\nReview detection prompt and adjust based on patterns above.\n"

    wo_path.write_text(content)
    logger.info("LLM judge: created prompt improvement WO at %s", wo_path)
