"""Intent parser for Rippled voice interface.

Classifies a voice transcript into one of four intents and extracts
any structured parameters (counterparty, time window) from the query.
"""
from __future__ import annotations

import json
import logging
from typing import Literal

from app.core.openai_client import get_openai_client
from app.core.config import get_settings

logger = logging.getLogger(__name__)

Intent = Literal["query_commitments", "update_status", "review_surfaced", "unknown"]

_SYSTEM_PROMPT = """\
You are an intent parser for a commitment tracking system.

Classify the user's voice query into exactly one of these intents:
- query_commitments: asking about existing commitments (overdue, this week, by person, etc.)
- update_status: trying to update or close a commitment
- review_surfaced: asking to review surfaced / flagged commitments
- unknown: does not match any of the above

Also extract optional filter parameters from the transcript:
- counterparty: person's name mentioned (e.g. "Matt", "Sarah")
- time_window: one of "today", "this_week", "overdue", "all" (default: "all")

Respond with a JSON object only. Example:
{
  "intent": "query_commitments",
  "counterparty": "Matt",
  "time_window": "this_week"
}
"""


def parse_intent(transcript: str) -> dict:
    """Parse voice transcript into structured intent + parameters.

    Args:
        transcript: Raw transcript from STT.

    Returns:
        Dict with keys: intent, counterparty (optional), time_window.
        Falls back to {"intent": "unknown"} on any error.
    """
    if not transcript.strip():
        return {"intent": "unknown", "time_window": "all"}

    client = get_openai_client()
    if not client:
        logger.warning("Intent parser: no OpenAI client — defaulting to query_commitments")
        return {"intent": "query_commitments", "time_window": "all"}

    settings = get_settings()

    try:
        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": transcript},
            ],
            response_format={"type": "json_object"},
            max_tokens=150,
            temperature=0,
        )
        raw = response.choices[0].message.content or "{}"
        result = json.loads(raw)

        # Normalise and validate
        intent = result.get("intent", "unknown")
        if intent not in ("query_commitments", "update_status", "review_surfaced", "unknown"):
            intent = "unknown"

        time_window = result.get("time_window", "all")
        if time_window not in ("today", "this_week", "overdue", "all"):
            time_window = "all"

        parsed = {"intent": intent, "time_window": time_window}
        if result.get("counterparty"):
            parsed["counterparty"] = str(result["counterparty"])

        logger.info("Intent parsed: %s", parsed)
        return parsed

    except Exception as exc:
        logger.warning("Intent parsing failed: %s — defaulting to query_commitments", exc)
        return {"intent": "query_commitments", "time_window": "all"}
