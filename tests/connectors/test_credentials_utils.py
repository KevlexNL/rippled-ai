"""Tests for app.connectors.shared.credentials_utils.

Covers encrypt_credentials and decrypt_credentials with:
- Full sensitive key roundtrip
- Non-sensitive key passthrough
- Encrypt changes values
- No ENCRYPTION_KEY → plaintext passthrough
- Empty dict edge cases
- Partial sensitive keys roundtrip
"""
import app.connectors.shared.credentials_utils as cu


def _reset(monkeypatch, key_value: str = "") -> None:
    """Set ENCRYPTION_KEY env var and clear the lru_cache on _get_cipher."""
    monkeypatch.setenv("ENCRYPTION_KEY", key_value)
    # Also patch get_settings so the cached settings object picks up the new value
    from app.core.config import get_settings
    settings = get_settings()
    monkeypatch.setattr(settings, "encryption_key", key_value)
    cu._get_cipher.cache_clear()
    cu._warned_no_key = False


def test_encrypt_decrypt_roundtrip_all_sensitive_fields(monkeypatch):
    """All 4 sensitive keys survive encrypt → decrypt unchanged."""
    _reset(monkeypatch, "test-key-value")
    try:
        original = {
            "imap_password": "super-secret",
            "bot_token": "xoxb-12345",
            "signing_secret": "signing-abc",
            "webhook_secret": "whsec-xyz",
        }
        encrypted = cu.encrypt_credentials(original)
        decrypted = cu.decrypt_credentials(encrypted)
        assert decrypted == original
    finally:
        cu._get_cipher.cache_clear()


def test_non_sensitive_keys_pass_through(monkeypatch):
    """Non-sensitive keys are not encrypted and remain identical."""
    _reset(monkeypatch, "test-key-value")
    try:
        data = {"imap_host": "imap.example.com", "imap_port": 993}
        result = cu.encrypt_credentials(data)
        assert result["imap_host"] == "imap.example.com"
        assert result["imap_port"] == 993
    finally:
        cu._get_cipher.cache_clear()


def test_encrypt_changes_sensitive_values(monkeypatch):
    """Encrypted imap_password differs from plaintext."""
    _reset(monkeypatch, "test-key-value")
    try:
        result = cu.encrypt_credentials({"imap_password": "plaintext"})
        assert result["imap_password"] != "plaintext"
        # Should be a non-empty string (Fernet token)
        assert isinstance(result["imap_password"], str)
        assert len(result["imap_password"]) > 10
    finally:
        cu._get_cipher.cache_clear()


def test_no_key_encrypt_returns_plaintext(monkeypatch):
    """When ENCRYPTION_KEY is empty, encrypt returns data as-is with a warning."""
    _reset(monkeypatch, "")
    data = {"imap_password": "plaintext", "imap_host": "mail.example.com"}
    result = cu.encrypt_credentials(data)
    assert result == data


def test_no_key_decrypt_returns_plaintext(monkeypatch):
    """When ENCRYPTION_KEY is empty, decrypt returns data as-is."""
    _reset(monkeypatch, "")
    data = {"imap_password": "plaintext", "bot_token": "some-token"}
    result = cu.decrypt_credentials(data)
    assert result == data


def test_decrypt_handles_empty_dict(monkeypatch):
    """decrypt_credentials({}) returns {}."""
    _reset(monkeypatch, "test-key-value")
    try:
        result = cu.decrypt_credentials({})
        assert result == {}
    finally:
        cu._get_cipher.cache_clear()


def test_encrypt_empty_dict(monkeypatch):
    """encrypt_credentials({}) returns {}."""
    _reset(monkeypatch, "test-key-value")
    try:
        result = cu.encrypt_credentials({})
        assert result == {}
    finally:
        cu._get_cipher.cache_clear()


def test_roundtrip_partial_sensitive_keys(monkeypatch):
    """Only some sensitive keys present — roundtrip still works for those present."""
    _reset(monkeypatch, "test-key-value")
    try:
        original = {
            "imap_password": "my-pass",
            "imap_host": "mail.example.com",
            # bot_token, signing_secret, webhook_secret absent intentionally
        }
        encrypted = cu.encrypt_credentials(original)
        # imap_host passes through unchanged
        assert encrypted["imap_host"] == "mail.example.com"
        # imap_password is encrypted
        assert encrypted["imap_password"] != "my-pass"
        decrypted = cu.decrypt_credentials(encrypted)
        assert decrypted == original
    finally:
        cu._get_cipher.cache_clear()
