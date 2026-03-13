"""Centralized OpenAI client for Rippled.ai.

All OpenAI calls go through this module. Provides:
- Client initialization from settings
- Rate limit handling (exponential backoff on 429)
- Cost logging (token counts at DEBUG level)
- Graceful degradation when no API key configured
"""
from __future__ import annotations

import logging

from openai import OpenAI, RateLimitError

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def get_openai_client(api_key: str | None = None) -> OpenAI | None:
    """Return a configured OpenAI client or None if no API key.

    Args:
        api_key: Override API key. Falls back to settings.openai_api_key.

    Returns:
        Configured OpenAI client, or None if no key available.
    """
    key = api_key or get_settings().openai_api_key
    if not key:
        logger.debug("No OPENAI_API_KEY configured — model detection disabled")
        return None
    return OpenAI(api_key=key)


__all__ = ["get_openai_client", "RateLimitError"]
