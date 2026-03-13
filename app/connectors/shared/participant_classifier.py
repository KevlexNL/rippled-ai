"""Classify email participants as internal or external based on domain.

Uses INTERNAL_DOMAINS config setting (comma-separated list of domains).
"""
from app.core.config import get_settings


def is_external_participant(email: str | None) -> bool:
    """Return True if the email belongs to an external (non-internal) participant.

    Returns True if email is None or domain is not in INTERNAL_DOMAINS.
    Returns False if domain is in INTERNAL_DOMAINS.
    """
    if not email:
        return True

    settings = get_settings()
    internal_domains_str = settings.internal_domains.strip()

    if not internal_domains_str:
        # No domains configured — treat everyone as external
        return True

    internal_domains = {d.strip().lower() for d in internal_domains_str.split(',') if d.strip()}

    try:
        domain = email.split('@')[1].lower()
    except IndexError:
        return True

    return domain not in internal_domains


def classify_participants(emails: list[str]) -> list[bool]:
    """Return is_external classification for a list of email addresses."""
    return [is_external_participant(e) for e in emails]
