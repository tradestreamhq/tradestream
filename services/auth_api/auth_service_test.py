"""Tests for auth_service module — unit tests for password, JWT, and token utilities."""

import time
from unittest.mock import patch

import jwt as pyjwt
import pytest

from services.auth_api.auth_service import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    generate_api_key,
    get_api_key_prefix,
    hash_password,
    hash_token,
    verify_password,
)


class TestPasswordHashing:
    def test_hash_and_verify(self):
        pw = "my-secure-password"
        hashed = hash_password(pw)
        assert hashed != pw
        assert verify_password(pw, hashed)

    def test_wrong_password_fails(self):
        hashed = hash_password("correct")
        assert not verify_password("wrong", hashed)

    def test_different_hashes_for_same_password(self):
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2  # bcrypt salts differ

    def test_unicode_password(self):
        pw = "пароль-密码-🔑"
        hashed = hash_password(pw)
        assert verify_password(pw, hashed)


class TestJWT:
    def test_create_and_decode_access_token(self):
        token = create_access_token("user-123", "test@example.com")
        payload = decode_access_token(token)
        assert payload["sub"] == "user-123"
        assert payload["email"] == "test@example.com"
        assert payload["type"] == "access"

    def test_expired_token_raises(self):
        with patch("services.auth_api.auth_service.ACCESS_TOKEN_EXPIRE_MINUTES", -1):
            token = create_access_token("user-123", "test@example.com")
        with pytest.raises(pyjwt.ExpiredSignatureError):
            decode_access_token(token)

    def test_invalid_token_raises(self):
        with pytest.raises(pyjwt.InvalidTokenError):
            decode_access_token("not.a.valid.token")

    def test_tampered_token_raises(self):
        token = create_access_token("user-123", "test@example.com")
        tampered = token[:-5] + "XXXXX"
        with pytest.raises(Exception):
            decode_access_token(tampered)

    def test_wrong_type_raises(self):
        """A token with type != 'access' should be rejected."""
        payload = {
            "sub": "user-123",
            "email": "test@example.com",
            "type": "refresh",
            "iat": time.time(),
            "exp": time.time() + 3600,
        }
        from services.auth_api.auth_service import JWT_ALGORITHM, JWT_SECRET

        token = pyjwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
        with pytest.raises(pyjwt.InvalidTokenError, match="Not an access token"):
            decode_access_token(token)


class TestRefreshToken:
    def test_create_refresh_token_is_unique(self):
        t1 = create_refresh_token()
        t2 = create_refresh_token()
        assert t1 != t2

    def test_refresh_token_length(self):
        token = create_refresh_token()
        assert len(token) > 30


class TestTokenHashing:
    def test_hash_token_deterministic(self):
        assert hash_token("abc") == hash_token("abc")

    def test_hash_token_different_inputs(self):
        assert hash_token("abc") != hash_token("def")


class TestApiKey:
    def test_generate_api_key_prefix(self):
        key = generate_api_key()
        assert key.startswith("ts_")
        assert len(key) > 20

    def test_get_api_key_prefix(self):
        key = "ts_abcdef1234567890"
        assert get_api_key_prefix(key) == "ts_abcde"

    def test_generated_keys_unique(self):
        keys = {generate_api_key() for _ in range(100)}
        assert len(keys) == 100
