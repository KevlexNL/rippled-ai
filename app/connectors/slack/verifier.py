"""Slack Events API webhook signature verification.

Implements Slack's HMAC-SHA256 signing algorithm as documented at:
https://api.slack.com/authentication/verifying-requests-from-slack
"""
import hashlib
import hmac
import time


def verify_slack_signature(
    signing_secret: str,
    timestamp: str,
    body: bytes,
    signature: str,
) -> bool:
    """Verify a Slack webhook request signature.

    Args:
        signing_secret: The SLACK_SIGNING_SECRET env var value.
        timestamp: X-Slack-Request-Timestamp header value.
        body: Raw request body bytes.
        signature: X-Slack-Signature header value (format: "v0=<hex>").

    Returns:
        True if signature is valid and timestamp is fresh (< 5 minutes).
        False if signature is invalid or timestamp is stale.

    Raises:
        ValueError: If signing_secret is empty (misconfigured).
    """
    if not signing_secret:
        raise ValueError("SLACK_SIGNING_SECRET is not configured")

    # Validate timestamp to prevent replay attacks
    try:
        ts = int(timestamp)
    except (ValueError, TypeError):
        return False

    if abs(time.time() - ts) > 300:  # 5 minutes
        return False

    # Compute expected signature per Slack's algorithm
    sig_basestring = f"v0:{timestamp}:{body.decode('utf-8', errors='replace')}"
    expected = "v0=" + hmac.new(
        signing_secret.encode("utf-8"),
        sig_basestring.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, signature)
