"""Shared LLM call helper — handles JSON parsing, retries, markdown stripping.

All LLM-backed stages use this to call models and parse structured output.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import TypeVar

from openai import OpenAI, RateLimitError
from pydantic import BaseModel, ValidationError

from app.core.config import get_settings
from app.services.orchestration.config import get_orchestration_config

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMCallResult:
    """Result of an LLM call including metadata."""

    __slots__ = ("parsed", "raw_response", "model_name", "model_provider",
                 "tokens_in", "tokens_out", "duration_ms", "error")

    def __init__(
        self,
        parsed: BaseModel | None = None,
        raw_response: str = "",
        model_name: str = "",
        model_provider: str = "openai",
        tokens_in: int = 0,
        tokens_out: int = 0,
        duration_ms: int = 0,
        error: str | None = None,
    ):
        self.parsed = parsed
        self.raw_response = raw_response
        self.model_name = model_name
        self.model_provider = model_provider
        self.tokens_in = tokens_in
        self.tokens_out = tokens_out
        self.duration_ms = duration_ms
        self.error = error

    @property
    def success(self) -> bool:
        return self.parsed is not None and self.error is None


_MARKDOWN_FENCE_RE = re.compile(r"^```(?:json)?\s*\n?(.*?)\n?```$", re.DOTALL)


def _strip_markdown_json(text: str) -> str:
    """Strip markdown code fences from LLM response (lesson 2026-03-17)."""
    text = text.strip()
    m = _MARKDOWN_FENCE_RE.match(text)
    if m:
        return m.group(1).strip()
    return text


def call_llm_structured(
    system_prompt: str,
    user_prompt: str,
    output_type: type[T],
    model_name: str | None = None,
    fallback_model: str | None = None,
    client: OpenAI | None = None,
) -> LLMCallResult:
    """Call an LLM and parse structured JSON output into a Pydantic model.

    Handles markdown stripping, validation, and one retry on parse failure.
    """
    settings = get_settings()
    config = get_orchestration_config()

    if client is None:
        key = settings.openai_api_key
        if not key:
            return LLMCallResult(error="No OpenAI API key configured")
        client = OpenAI(api_key=key)

    model = model_name or settings.openai_model
    start = time.monotonic()

    for attempt in range(1 + config.max_llm_retries):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
                max_tokens=800,
            )

            raw = response.choices[0].message.content or ""
            duration = int((time.monotonic() - start) * 1000)
            tokens_in = response.usage.prompt_tokens if response.usage else 0
            tokens_out = response.usage.completion_tokens if response.usage else 0

            cleaned = _strip_markdown_json(raw)

            try:
                data = json.loads(cleaned)
            except json.JSONDecodeError as e:
                if attempt < config.max_llm_retries:
                    logger.warning("JSON parse failed (attempt %d), retrying: %s", attempt + 1, str(e)[:100])
                    continue
                return LLMCallResult(
                    raw_response=raw,
                    model_name=model,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    duration_ms=duration,
                    error=f"JSON parse error: {e}",
                )

            try:
                parsed = output_type.model_validate(data)
            except ValidationError as e:
                if attempt < config.max_llm_retries:
                    logger.warning("Schema validation failed (attempt %d), retrying: %s", attempt + 1, str(e)[:200])
                    continue
                return LLMCallResult(
                    raw_response=raw,
                    model_name=model,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    duration_ms=duration,
                    error=f"Schema validation error: {e}",
                )

            return LLMCallResult(
                parsed=parsed,
                raw_response=raw,
                model_name=model,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                duration_ms=duration,
            )

        except RateLimitError:
            if fallback_model and model != fallback_model:
                logger.warning("Rate limited on %s, falling back to %s", model, fallback_model)
                model = fallback_model
                continue
            duration = int((time.monotonic() - start) * 1000)
            return LLMCallResult(
                model_name=model,
                duration_ms=duration,
                error="Rate limited, no fallback available",
            )

        except Exception as exc:
            duration = int((time.monotonic() - start) * 1000)
            return LLMCallResult(
                model_name=model,
                duration_ms=duration,
                error=f"LLM call error: {exc}",
            )

    # Should not reach here, but safety net
    duration = int((time.monotonic() - start) * 1000)
    return LLMCallResult(model_name=model, duration_ms=duration, error="Max retries exhausted")
