"""Model-Assisted Detection Service — Phase C1.

Calls OpenAI (GPT-4.1-mini) to classify a CommitmentCandidate as
commitment / not-commitment with confidence and explanation.

Public API:
    service = ModelDetectionService(api_key="...", model="gpt-4.1-mini")
    result = service.classify(candidate)   # returns ModelDetectionResult | None

Error contract:
    classify() NEVER raises. Returns None on any failure (API error,
    malformed response, rate limit exhaustion, missing API key).
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any

from openai import OpenAI, RateLimitError

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are a commitment classifier for a workplace intelligence system.

A commitment is a statement where someone obligates themselves or others to a specific
future action, deliverable, or outcome. This includes:
- Explicit: "I will", "I'll", "We will", "I promise", "I commit to"
- Implicit: "Consider it done", "Leave it with me", "I'll look into that"
- Collective: "We need to get this done", "Someone should handle this"

NOT a commitment:
- Casual acknowledgments: "OK", "Sounds good", "Got it"
- Questions or hypotheticals: "Should we...?", "What if we..."
- Past-tense descriptions: "I already did X"
- Filler phrases: "By the way", "Just checking in"

Given a communication fragment and its surrounding context, classify it.

You must respond with valid JSON only, exactly this structure:
{
  "is_commitment": <boolean>,
  "confidence": <float 0.0 to 1.0>,
  "explanation": "<1-2 sentence explanation>",
  "suggested_owner": "<name of who made the commitment, or null>",
  "suggested_deadline": "<deadline as text or ISO date, or null>"
}"""

_MAX_RETRIES = 3
_INITIAL_BACKOFF = 1.0  # seconds
_PROMPT_VERSION = "ongoing-v1"


@dataclass
class ModelDetectionResult:
    """Result from model classification."""
    is_commitment: bool
    confidence: float
    explanation: str
    suggested_owner: str | None
    suggested_deadline: str | None
    # Audit metadata
    raw_prompt: str | None = None
    raw_response: str | None = None
    parsed_result: dict | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    model: str | None = None
    duration_ms: int | None = None
    prompt_version: str | None = None
    error_detail: str | None = None


class ModelDetectionService:
    """Classifies a CommitmentCandidate using OpenAI structured output.

    Args:
        api_key: OpenAI API key. Empty string disables the service.
        model: OpenAI model name. Defaults to "gpt-4.1-mini".
    """

    def __init__(self, api_key: str, model: str = "gpt-4.1-mini") -> None:
        self._model = model
        if api_key:
            self._client = OpenAI(api_key=api_key)
        else:
            self._client = None  # type: ignore[assignment]

    def classify(self, candidate: Any) -> ModelDetectionResult | None:
        """Classify a candidate as commitment / not-commitment.

        Args:
            candidate: CommitmentCandidate ORM object or compatible namespace.
                       Must have .context_window (dict or None) and .raw_text.

        Returns:
            ModelDetectionResult on success, None on any failure.
        """
        if self._client is None:
            logger.debug("ModelDetectionService: no API key, skipping")
            return None

        context_window = candidate.context_window
        if not context_window:
            logger.debug(
                "Candidate %s has no context_window — skipping model call",
                getattr(candidate, "id", "?"),
            )
            return None

        user_message = self._build_user_message(context_window)
        full_prompt = f"[system]\n{_SYSTEM_PROMPT}\n\n[user]\n{user_message}"

        call_start = time.monotonic()

        for attempt in range(_MAX_RETRIES):
            try:
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": user_message},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.1,
                )

                duration_ms = int((time.monotonic() - call_start) * 1000)

                # Log token usage
                tokens_in = None
                tokens_out = None
                usage = response.usage
                if usage:
                    tokens_in = usage.prompt_tokens
                    tokens_out = usage.completion_tokens
                    logger.debug(
                        "OpenAI usage — model=%s prompt_tokens=%d completion_tokens=%d candidate=%s",
                        self._model,
                        tokens_in,
                        tokens_out,
                        getattr(candidate, "id", "?"),
                    )

                result = self._parse_response(response)
                if result is None:
                    raw_content = ""
                    try:
                        raw_content = response.choices[0].message.content
                    except (IndexError, AttributeError):
                        pass
                    return ModelDetectionResult(
                        is_commitment=False,
                        confidence=0.0,
                        explanation="",
                        suggested_owner=None,
                        suggested_deadline=None,
                        raw_prompt=full_prompt,
                        raw_response=raw_content,
                        parsed_result=None,
                        tokens_in=tokens_in,
                        tokens_out=tokens_out,
                        model=self._model,
                        duration_ms=duration_ms,
                        prompt_version=_PROMPT_VERSION,
                        error_detail="Failed to parse response",
                    )

                # Attach audit metadata
                raw_content = response.choices[0].message.content
                result.raw_prompt = full_prompt
                result.raw_response = raw_content
                result.parsed_result = json.loads(raw_content)
                result.tokens_in = tokens_in
                result.tokens_out = tokens_out
                result.model = self._model
                result.duration_ms = duration_ms
                result.prompt_version = _PROMPT_VERSION
                return result

            except RateLimitError as exc:
                if attempt < _MAX_RETRIES - 1:
                    backoff = _INITIAL_BACKOFF * (2 ** attempt)
                    logger.warning(
                        "OpenAI rate limit (attempt %d/%d), retrying in %.1fs: %s",
                        attempt + 1, _MAX_RETRIES, backoff, exc,
                    )
                    time.sleep(backoff)
                else:
                    logger.error(
                        "OpenAI rate limit exhausted after %d retries for candidate %s",
                        _MAX_RETRIES, getattr(candidate, "id", "?"),
                    )
                    return None

            except Exception as exc:
                duration_ms = int((time.monotonic() - call_start) * 1000)
                logger.error(
                    "OpenAI API error for candidate %s: %s",
                    getattr(candidate, "id", "?"), exc,
                )
                return None

        return None  # unreachable, but satisfies type checker

    def _build_user_message(self, context_window: dict) -> str:
        trigger = context_window.get("trigger_text", "")
        pre = context_window.get("pre_context", "")
        post = context_window.get("post_context", "")
        source = context_window.get("source_type", "unknown")

        parts = []
        if pre:
            parts.append(f"[Before]: {pre}")
        parts.append(f"[Trigger]: {trigger}")
        if post:
            parts.append(f"[After]: {post}")

        return f"Source type: {source}\n\n" + "\n".join(parts)

    def _parse_response(self, response: Any) -> ModelDetectionResult | None:
        """Parse OpenAI response into ModelDetectionResult. Returns None on parse failure."""
        try:
            content = response.choices[0].message.content
            data = json.loads(content)

            # Validate required fields
            is_commitment = data["is_commitment"]
            confidence = float(data["confidence"])
            explanation = data["explanation"]

            return ModelDetectionResult(
                is_commitment=bool(is_commitment),
                confidence=confidence,
                explanation=str(explanation),
                suggested_owner=data.get("suggested_owner"),
                suggested_deadline=data.get("suggested_deadline"),
            )
        except (KeyError, ValueError, json.JSONDecodeError, IndexError) as exc:
            logger.warning("Failed to parse OpenAI response: %s", exc)
            return None
