"""API key health monitoring with email alerts — 4-hour check cadence.

Validates OpenAI and Anthropic API keys using cheap test calls.
Sends email alerts via DigestDelivery when a key fails, with
deduplication via Redis (one alert per 4-hour window per provider).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import redis

from app.core.config import get_settings
from app.services.digest import DigestDelivery

logger = logging.getLogger(__name__)
settings = get_settings()

_redis = redis.from_url(settings.redis_url)

PROVIDERS = ["openai", "anthropic"]

_HEALTH_KEY = "rippled:api_key_health:{provider}"
_ALERT_KEY = "rippled:api_key_alert_sent:{provider}"
_ALERT_WINDOW_SECONDS = 14400  # 4 hours


def _check_openai() -> tuple[bool, str | None]:
    """Validate OpenAI key by listing models."""
    try:
        import openai

        client = openai.OpenAI(api_key=settings.openai_api_key)
        client.models.list()
        return True, None
    except Exception as exc:
        return False, str(exc)


def _check_anthropic() -> tuple[bool, str | None]:
    """Validate Anthropic key with a minimal token count call."""
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        client.messages.count_tokens(
            model="claude-haiku-4-5",
            messages=[{"role": "user", "content": "test"}],
        )
        return True, None
    except Exception as exc:
        return False, str(exc)


_CHECKERS = {
    "openai": _check_openai,
    "anthropic": _check_anthropic,
}


def _send_alert(provider: str, error: str) -> None:
    """Send an email alert for a failing API key via DigestDelivery."""
    if not settings.digest_to_email:
        logger.warning("No digest_to_email configured — skipping alert for %s", provider)
        return

    subject = f"[Rippled] API key failure: {provider}"
    body = (
        f"The {provider} API key health check failed.\n\n"
        f"Error: {error}\n\n"
        f"Checked at: {datetime.now(timezone.utc).isoformat()}\n"
        f"Next check in ~4 hours."
    )

    delivery = DigestDelivery()
    result = delivery.send(
        subject=subject,
        plain_text=body,
        html=f"<pre>{body}</pre>",
    )
    if result.success:
        logger.info("Alert email sent for %s key failure", provider)
    else:
        logger.error("Failed to send alert email for %s: %s", provider, result.error)


def _check_provider(provider: str) -> dict:
    """Check a single provider, update Redis, send alert if needed."""
    now = datetime.now(timezone.utc).isoformat()
    checker = _CHECKERS[provider]
    ok, error = checker()

    health_key = _HEALTH_KEY.format(provider=provider)
    alert_key = _ALERT_KEY.format(provider=provider)

    # Build health record
    health: dict = {"status": "ok" if ok else "error", "last_checked": now}
    if ok:
        health["last_ok"] = now
        health["last_error"] = None
    else:
        health["last_error"] = error
        # Preserve last_ok from previous record
        prev_raw = _redis.get(health_key)
        if prev_raw:
            try:
                prev = json.loads(prev_raw)
                health["last_ok"] = prev.get("last_ok")
            except (json.JSONDecodeError, TypeError):
                health["last_ok"] = None
        else:
            health["last_ok"] = None

    _redis.set(health_key, json.dumps(health))

    # Alert logic: send if failing AND no alert sent this window
    if not ok and not _redis.exists(alert_key):
        _send_alert(provider, error or "Unknown error")
        _redis.set(alert_key, "1", ex=_ALERT_WINDOW_SECONDS)

    return {"provider": provider, "status": health["status"], "error": error}


def run_api_key_health_checks() -> dict:
    """Run health checks for all providers. Returns summary dict."""
    results = []
    for provider in PROVIDERS:
        try:
            result = _check_provider(provider)
            results.append(result)
        except Exception as exc:
            logger.exception("Unexpected error checking %s", provider)
            results.append({"provider": provider, "status": "error", "error": str(exc)})

    all_ok = all(r["status"] == "ok" for r in results)
    return {"overall": "ok" if all_ok else "degraded", "providers": results}
