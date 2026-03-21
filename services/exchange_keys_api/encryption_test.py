"""Tests for encryption utilities."""

import os
from unittest.mock import patch

import pytest

from services.exchange_keys_api.encryption import decrypt, encrypt, mask


@pytest.fixture(autouse=True)
def _set_encryption_secret():
    with patch.dict(
        os.environ, {"EXCHANGE_KEY_ENCRYPTION_SECRET": "test-secret-key-12345"}
    ):
        yield


class TestEncryptDecrypt:
    def test_round_trip(self):
        plaintext = "my-api-key-abc123"
        token = encrypt(plaintext)
        assert token != plaintext
        assert decrypt(token) == plaintext

    def test_different_plaintexts_produce_different_tokens(self):
        t1 = encrypt("key-one")
        t2 = encrypt("key-two")
        assert t1 != t2

    def test_same_plaintext_produces_different_tokens(self):
        """Fernet includes a timestamp and random IV, so tokens should differ."""
        t1 = encrypt("same-key")
        t2 = encrypt("same-key")
        assert t1 != t2
        assert decrypt(t1) == decrypt(t2) == "same-key"

    def test_empty_string(self):
        token = encrypt("")
        assert decrypt(token) == ""

    def test_long_secret(self):
        long_key = "x" * 1000
        token = encrypt(long_key)
        assert decrypt(token) == long_key

    def test_decrypt_with_wrong_secret_fails(self):
        token = encrypt("my-secret")
        with patch.dict(os.environ, {"EXCHANGE_KEY_ENCRYPTION_SECRET": "wrong-secret"}):
            with pytest.raises(Exception):
                decrypt(token)

    def test_missing_env_var_raises(self):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("EXCHANGE_KEY_ENCRYPTION_SECRET", None)
            with pytest.raises(RuntimeError, match="EXCHANGE_KEY_ENCRYPTION_SECRET"):
                encrypt("test")


class TestMask:
    def test_mask_long_value(self):
        assert mask("abcdefgh1234") == "****1234"

    def test_mask_short_value(self):
        assert mask("abc") == "****"

    def test_mask_exactly_four(self):
        assert mask("abcd") == "****"

    def test_mask_five_chars(self):
        assert mask("abcde") == "****bcde"
