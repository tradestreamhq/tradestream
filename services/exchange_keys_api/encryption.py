"""Encryption utilities for exchange API credentials.

Uses Fernet symmetric encryption (AES-128-CBC with HMAC-SHA256)
from the cryptography library. The encryption key is derived from
the EXCHANGE_KEY_ENCRYPTION_SECRET environment variable.
"""

import base64
import os

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

_SALT = b"tradestream-exchange-keys-v1"


def _derive_key(secret: str) -> bytes:
    """Derive a Fernet-compatible key from a plaintext secret."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_SALT,
        iterations=480_000,
    )
    return base64.urlsafe_b64encode(kdf.derive(secret.encode()))


def get_fernet() -> Fernet:
    """Return a Fernet instance using the configured encryption secret."""
    secret = os.environ.get("EXCHANGE_KEY_ENCRYPTION_SECRET", "")
    if not secret:
        raise RuntimeError("EXCHANGE_KEY_ENCRYPTION_SECRET is not set")
    return Fernet(_derive_key(secret))


def encrypt(plaintext: str) -> str:
    """Encrypt a plaintext string, returning a base64 token."""
    return get_fernet().encrypt(plaintext.encode()).decode()


def decrypt(token: str) -> str:
    """Decrypt a Fernet token back to plaintext."""
    return get_fernet().decrypt(token.encode()).decode()


def mask(value: str) -> str:
    """Return a masked version of a secret, showing only the last 4 chars."""
    if len(value) <= 4:
        return "****"
    return "****" + value[-4:]
