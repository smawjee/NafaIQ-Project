"""Symmetric encryption for secrets stored at rest, and for short-lived
authenticated tokens.

Used for Google OAuth refresh tokens (bank-email import) and the OAuth `state`
parameter. The key lives in the backend env only (EMAIL_CRED_ENC_KEY) — never in
the database, never in a client bundle. Rotating the key invalidates existing
ciphertexts by design.
"""
from __future__ import annotations

import json
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


class CryptoError(Exception):
    """Raised when a secret cannot be encrypted/decrypted."""


def _fernet() -> Fernet:
    key = settings.email_cred_enc_key
    if not key:
        raise CryptoError("EMAIL_CRED_ENC_KEY is not configured")
    try:
        return Fernet(key.encode())
    except (ValueError, TypeError) as e:
        raise CryptoError(f"EMAIL_CRED_ENC_KEY is not a valid Fernet key: {e}")


def encrypt(plaintext: str) -> str:
    """Encrypt a secret for storage. Returns URL-safe base64 ciphertext."""
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    """Decrypt a stored secret.

    Raises CryptoError if the key changed or the value is corrupt — callers
    should treat that as "credential unusable, ask the user to reconnect"
    rather than a transient failure.
    """
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        raise CryptoError("stored credential could not be decrypted (key rotated?)")


def encrypt_state(payload: dict[str, Any]) -> str:
    """Encrypt an OAuth `state` payload.

    Fernet tokens are authenticated and carry a timestamp, so this gives us
    tamper-proofing and expiry (see decrypt_state) without a second secret —
    which matters because the OAuth callback is public, and `state` is the only
    thing binding Google's redirect back to a specific user.
    """
    return encrypt(json.dumps(payload, separators=(",", ":")))


def decrypt_state(token: str, *, ttl: int = 600) -> dict[str, Any]:
    """Decrypt and verify an OAuth `state`, rejecting anything older than ttl
    seconds. Raises CryptoError if forged, corrupt, or expired."""
    try:
        raw = _fernet().decrypt(token.encode(), ttl=ttl).decode()
    except InvalidToken:
        raise CryptoError("state is invalid or has expired")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        raise CryptoError("state payload is malformed")
    if not isinstance(payload, dict):
        raise CryptoError("state payload is malformed")
    return payload
