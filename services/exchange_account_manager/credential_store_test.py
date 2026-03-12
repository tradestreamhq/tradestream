"""Tests for credential encryption/decryption."""

import os
from unittest.mock import patch

import pytest

from services.exchange_account_manager.credential_store import decrypt, encrypt


@pytest.fixture(autouse=True)
def _set_key():
    with patch.dict(os.environ, {"CREDENTIAL_ENCRYPTION_KEY": "my-test-key"}):
        yield


class TestCredentialStore:
    def test_round_trip(self):
        plaintext = "super-secret-api-key-12345"
        ciphertext = encrypt(plaintext)
        assert ciphertext != plaintext
        assert decrypt(ciphertext) == plaintext

    def test_different_plaintexts_differ(self):
        a = encrypt("key-a")
        b = encrypt("key-b")
        assert a != b

    def test_missing_key_raises(self):
        with patch.dict(os.environ, {"CREDENTIAL_ENCRYPTION_KEY": ""}):
            with pytest.raises(RuntimeError, match="CREDENTIAL_ENCRYPTION_KEY"):
                encrypt("anything")
