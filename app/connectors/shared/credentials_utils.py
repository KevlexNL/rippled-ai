"""Credential encryption/decryption utilities for source connectors.

Sensitive fields stored in Source.credentials are encrypted at rest using
Fernet symmetric encryption. The encryption key is derived from ENCRYPTION_KEY
env var via SHA-256, producing a valid 32-byte URL-safe base64 key.

If ENCRYPTION_KEY is not set (empty string), encryption is skipped with a
one-time warning logged.
"""

import base64
import hashlib
import logging
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Sensitive keys that must be encrypted at rest
_SENSITIVE_KEYS = frozenset(
    {"imap_password", "bot_token", "signing_secret", "webhook_secret"}
)

# Module-level flag to log the "no encryption key" warning only once
_warned_no_key = False


@lru_cache(maxsize=1)
def _get_cipher() -> Fernet | None:
    """Return a Fernet instance derived from ENCRYPTION_KEY, or None if unset.

    Result is cached at module level — key derivation runs at most once per process.
    """
    key_str = get_settings().encryption_key
    if not key_str:
        return None
    derived = base64.urlsafe_b64encode(hashlib.sha256(key_str.encode()).digest())
    return Fernet(derived)


def encrypt_credentials(data: dict) -> dict:
    """Encrypt sensitive fields in *data*.

    Sensitive keys: imap_password, bot_token, signing_secret, webhook_secret.
    All other keys are passed through unchanged.
    If ENCRYPTION_KEY is not set, logs a warning once and returns *data* as-is.
    """
    global _warned_no_key

    cipher = _get_cipher()
    if cipher is None:
        if not _warned_no_key:
            logger.warning(
                "ENCRYPTION_KEY is not set — credentials will be stored unencrypted. "
                "Set ENCRYPTION_KEY in your environment to enable encryption at rest."
            )
            _warned_no_key = True
        return data

    result = {}
    for key, value in data.items():
        if key in _SENSITIVE_KEYS and isinstance(value, str):
            result[key] = cipher.encrypt(value.encode()).decode()
        else:
            result[key] = value
    return result


def decrypt_credentials(data: dict) -> dict:
    """Decrypt sensitive fields in *data*.

    If ENCRYPTION_KEY is not set, returns *data* as-is (assuming values are
    already plaintext, consistent with how they were stored).
    """
    cipher = _get_cipher()
    if cipher is None:
        return data

    result = {}
    for key, value in data.items():
        if key in _SENSITIVE_KEYS and isinstance(value, str):
            try:
                result[key] = cipher.decrypt(value.encode()).decode()
            except InvalidToken:
                logger.warning(
                    "Failed to decrypt field '%s' — possibly unencrypted legacy value, returning as-is.",
                    key,
                )
                result[key] = value
            except Exception as e:
                logger.error("Unexpected error decrypting field '%s': %s", key, e)
                result[key] = value
        else:
            result[key] = value
    return result
