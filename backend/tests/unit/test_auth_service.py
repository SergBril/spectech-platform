"""Unit tests for auth_service."""

import hashlib
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from app.services.auth_service import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    hash_password,
    verify_password,
)


class TestPasswordHashing:
    """Tests for hash_password and verify_password."""

    def test_hash_produces_bcrypt_hash(self):
        hashed = hash_password("secret123")
        assert hashed.startswith("$2b$") or hashed.startswith("$2y$")

    def test_hash_is_unique_each_call(self):
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2  # bcrypt uses random salt

    def test_verify_correct_password(self):
        hashed = hash_password("correct")
        assert verify_password("correct", hashed) is True

    def test_verify_wrong_password(self):
        hashed = hash_password("correct")
        assert verify_password("wrong", hashed) is False

    def test_verify_empty_password(self):
        hashed = hash_password("")
        assert verify_password("", hashed) is True
        assert verify_password("notempty", hashed) is False


class TestJWT0:
    """Tests for create_access_token and decode_access_token."""

    @pytest.fixture
    def mock_user(self):
        user = MagicMock()
        user.id = 42
        user.email = "test@example.com"
        return user

    def test_create_decode_roundtrip(self, mock_user):
        token = create_access_token(mock_user)
        payload = decode_access_token(token)
        assert payload["sub"] == "42"
        assert payload["email"] == "test@example.com"
        assert "exp" in payload
        assert "iat" in payload

    def test_decode_invalid_token_raises_401(self):
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            decode_access_token("invalid.token.string")
        assert exc_info.value.status_code == 401

    def test_decode_expired_token_raises_401(self, mock_user):
        from fastapi import HTTPException
        from jose import jwt

        from app.core.config import settings

        expired_payload = {
            "sub": "42",
            "email": "test@example.com",
            "exp": datetime.now(UTC) - timedelta(hours=1),
            "iat": datetime.now(UTC) - timedelta(hours=2),
        }
        token = jwt.encode(
            expired_payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
        )
        with pytest.raises(HTTPException) as exc_info:
            decode_access_token(token)
        assert exc_info.value.status_code == 401


class TestRefreshToken:
    """Tests for create_refresh_token."""

    @pytest.fixture
    def mock_db_and_user(self):
        db = MagicMock()
        user = MagicMock()
        user.id = 99
        return db, user

    def test_returns_urlsafe_token(self, mock_db_and_user):
        db, user = mock_db_and_user
        token = create_refresh_token(db, user)
        assert isinstance(token, str)
        assert len(token) > 50

    def test_saves_session_with_hash(self, mock_db_and_user):
        db, user = mock_db_and_user
        token = create_refresh_token(db, user)
        db.add.assert_called()
        db.flush.assert_called()
        # Verify the session has a SHA-256 hash
        call_args = db.add.call_args
        session = call_args[0][0]
        expected_hash = hashlib.sha256(token.encode()).hexdigest()
        assert session.refresh_token_hash == expected_hash
