"""Voice query service — fetches commitments and generates spoken summaries.

Handles the query_commitments intent by:
1. Querying the DB based on intent params (time_window, counterparty)
2. Generating a concise spoken summary via OpenAI
3. Returning structured data + text ready for TTS
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.openai_client import get_openai_client
from app.models.orm import Commitment

logger = logging.getLogger(__name__)

_MAX_COMMITMENTS_IN_RESPONSE = 3

_SUMMARY_SYSTEM_PROMPT = """\
You are a voice assistant for a commitment tracking system.
The user has asked a question about their commitments.
You have been given a list of relevant commitments (or an empty list if there are none).

Generate a natural, concise spoken response — as if answering out loud.
- Use plain language, no bullet points or markdown.
- Mention at most 3 commitments. If there are more, say "and X others".
- State deadlines naturally: "by end of this week", "overdue since Monday", etc.
- If no commitments found, say so briefly and suggest what to try.
- Keep the response under 60 words.
"""


async def query_commitments(
    transcript: str,
    intent_params: dict,
    user_id: str,
    db: AsyncSession,
) -> dict[str, Any]:
    """Query commitments based on parsed intent and generate a spoken summary.

    Args:
        transcript: Original voice transcript.
        intent_params: Parsed intent dict (intent, time_window, counterparty).
        user_id: The authenticated user's ID.
        db: Async DB session.

    Returns:
        Dict with keys: commitments (list), summary_text (str), total_count (int).
    """
    now = datetime.now(timezone.utc)
    time_window = intent_params.get("time_window", "all")
    counterparty = intent_params.get("counterparty")

    # Build base query — active/confirmed commitments for this user
    q = select(Commitment).where(
        Commitment.user_id == user_id,
        Commitment.lifecycle_state.in_(["active", "confirmed", "proposed"]),
    )

    # Apply time window filter
    if time_window == "today":
        today_end = now.replace(hour=23, minute=59, second=59)
        q = q.where(
            or_(
                Commitment.resolved_deadline <= today_end,
                Commitment.suggested_due_date <= today_end,
            )
        )
    elif time_window == "this_week":
        week_end = now + timedelta(days=7 - now.weekday())
        week_end = week_end.replace(hour=23, minute=59, second=59)
        q = q.where(
            or_(
                Commitment.resolved_deadline <= week_end,
                Commitment.suggested_due_date <= week_end,
            )
        )
    elif time_window == "overdue":
        q = q.where(
            or_(
                Commitment.resolved_deadline < now,
                Commitment.suggested_due_date < now,
            )
        )

    # Apply counterparty filter (case-insensitive match on requester/beneficiary/target)
    if counterparty:
        cp_lower = f"%{counterparty.lower()}%"
        q = q.where(
            or_(
                Commitment.requester_name.ilike(cp_lower),
                Commitment.beneficiary_name.ilike(cp_lower),
                Commitment.target_entity.ilike(cp_lower),
                Commitment.counterparty_name.ilike(cp_lower),
            )
        )

    # Order by priority, then deadline
    q = q.order_by(
        Commitment.priority_class.desc().nullslast(),
        Commitment.resolved_deadline.asc().nullslast(),
        Commitment.suggested_due_date.asc().nullslast(),
    ).limit(20)

    result = await db.execute(q)
    rows = list(result.scalars())
    total_count = len(rows)
    top_rows = rows[:_MAX_COMMITMENTS_IN_RESPONSE]

    # Serialize commitments for the LLM summary
    commitment_summaries = []
    for c in top_rows:
        deadline = c.resolved_deadline or c.suggested_due_date
        deadline_str = deadline.strftime("%A %b %d") if deadline else "no deadline"
        overdue = deadline and deadline < now

        commitment_summaries.append({
            "id": c.id,
            "title": c.title,
            "state": c.lifecycle_state,
            "deadline": deadline_str,
            "overdue": overdue,
            "counterparty": c.requester_name or c.beneficiary_name or c.target_entity or c.counterparty_name,
            "priority": c.priority_class,
        })

    # Generate spoken summary
    summary_text = await _generate_summary(
        transcript=transcript,
        commitments=commitment_summaries,
        total_count=total_count,
    )

    return {
        "commitments": commitment_summaries,
        "summary_text": summary_text,
        "total_count": total_count,
    }


async def _generate_summary(
    transcript: str,
    commitments: list[dict],
    total_count: int,
) -> str:
    """Generate a concise spoken summary of the commitment query result."""
    client = get_openai_client()
    if not client:
        if not commitments:
            return "I couldn't find any matching commitments."
        titles = ", ".join(c["title"][:40] for c in commitments[:3])
        return f"I found {total_count} commitment{'s' if total_count != 1 else ''}: {titles}."

    settings = get_settings()

    context_lines = []
    if commitments:
        for c in commitments:
            overdue_flag = " (OVERDUE)" if c.get("overdue") else ""
            cp = f" for {c['counterparty']}" if c.get("counterparty") else ""
            context_lines.append(f"- {c['title']}{cp}, due {c['deadline']}{overdue_flag}")
        if total_count > len(commitments):
            context_lines.append(f"... and {total_count - len(commitments)} more commitments")
    else:
        context_lines.append("(no matching commitments found)")

    user_message = f"User asked: \"{transcript}\"\n\nRelevant commitments:\n" + "\n".join(context_lines)

    try:
        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": _SUMMARY_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            max_tokens=100,
            temperature=0.3,
        )
        return (response.choices[0].message.content or "").strip()
    except Exception as exc:
        logger.warning("Summary generation failed: %s", exc)
        if not commitments:
            return "I couldn't find any matching commitments."
        return f"I found {total_count} commitment{'s' if total_count != 1 else ''} matching your query."
