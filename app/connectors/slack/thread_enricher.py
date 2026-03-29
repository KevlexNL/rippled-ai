"""Fetch full Slack thread context for reply messages.

WO-RIPPLED-SLACK-THREAD-ENRICHMENT
"""

import logging

import httpx

logger = logging.getLogger(__name__)

SLACK_REPLIES_URL = "https://slack.com/api/conversations.replies"


class ThreadEnricher:
    """Fetches and caches Slack thread messages for a single task invocation."""

    def __init__(self, bot_token: str) -> None:
        self._bot_token = bot_token
        self._cache: dict[str, list[dict[str, str]]] = {}

    def fetch_thread(self, channel: str, thread_ts: str) -> list[dict[str, str]]:
        """Fetch all messages in a thread, oldest first.

        Returns list of ``{"ts": ..., "user": ..., "text": ...}`` dicts.
        Returns ``[]`` on any error (API failure, rate-limit, network).
        """
        if thread_ts in self._cache:
            return self._cache[thread_ts]

        try:
            resp = httpx.get(
                SLACK_REPLIES_URL,
                params={"channel": channel, "ts": thread_ts},
                headers={"Authorization": f"Bearer {self._bot_token}"},
                timeout=10,
            )

            if resp.status_code == 429:
                logger.warning(
                    "Slack rate-limited on conversations.replies (channel=%s, thread_ts=%s)",
                    channel,
                    thread_ts,
                )
                return []

            data = resp.json()
            if not data.get("ok"):
                logger.warning(
                    "Slack API error on conversations.replies: %s (channel=%s, thread_ts=%s)",
                    data.get("error", "unknown"),
                    channel,
                    thread_ts,
                )
                return []

            messages: list[dict[str, str]] = [
                {
                    "ts": m.get("ts", ""),
                    "user": m.get("user", ""),
                    "text": m.get("text", ""),
                }
                for m in data.get("messages", [])
            ]

            self._cache[thread_ts] = messages
            return messages

        except Exception:
            logger.exception(
                "Failed to fetch Slack thread (channel=%s, thread_ts=%s)",
                channel,
                thread_ts,
            )
            return []
