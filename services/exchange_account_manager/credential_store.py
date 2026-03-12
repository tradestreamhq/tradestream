"""Encrypted credential storage using Fernet (AES-128-CBC via cryptography).

The encryption key is derived from the CREDENTIAL_ENCRYPTION_KEY environment
variable.  Each credential is encrypted at rest and decrypted only when needed
for exchange API calls.
"""

import base64
import hashlib
import os

from cryptography.fernet import Fernet


def _get_fernet() -> Fernet:
    """Build a Fernet instance from the configured encryption key."""
    raw_key = os.environ.get("CREDENTIAL_ENCRYPTION_KEY", "")
    if not raw_key:
        raise RuntimeError(
            "CREDENTIAL_ENCRYPTION_KEY environment variable is not set"
        )
    # Derive a URL-safe 32-byte key via SHA-256 so callers can use any passphrase.
    derived = hashlib.sha256(raw_key.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(derived))


def encrypt(plaintext: str) -> str:
    """Encrypt *plaintext* and return the ciphertext as a UTF-8 string."""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    """Decrypt *ciphertext* and return the original plaintext."""
    return _get_fernet().decrypt(ciphertext.encode()).decode()
