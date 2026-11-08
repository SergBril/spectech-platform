"""Coverage tests for auth_service."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_db():
    return MagicMock()


class TestHashPassword:
    """Cover hash_password (line 15-16)."""

    def test_returns_hash(self):
        from app.services.auth_service import hash_password

        result = hash_password("test123")
        assert result.startswith("$")
        assert len(result) > 20

    def test_different_hashes(self):
        from app.services.auth_service import hash_password

        h1 = hash_password("password1")
        h2 = hash_password("password2")
        assert h1 != h2


class TestVerifyPassword:
    """Cover verify_password (lines 19-20)."""

    def test_correct_password(self):
        from app.services.auth_service import hash_password, verify_password

        hashed = hash_password("test123")
        assert verify_password("test123", hashed) is True

    def test_wrong_password(self):
        from app.services.auth_service import hash_password, verify_password

        hashed = hash_password("test123")
        assert verify_password("wrong", hashed) is False


class TestCreateAccessToken:
    """Cover create_access_token (lines 23-34)."""

    def test_returns_token(self):
        from app.services.auth_service import create_access_token

        user = SimpleNamespace(id=1, email="test@test.com")
        token = create_access_token(user)
        assert isinstance(token, str)
        assert len(token) > 20

    def test_token_decodable(self):
        from app.services.auth_service import create_access_token, decode_access_token

        user = SimpleNamespace(id=1, email="test@test.com")
        token = create_access_token(user)
        payload = decode_access_token(token)
        assert payload["sub"] == "1"
        assert payload["email"] == "test@test.com"


class TestCreateRefreshToken:
    """Cover create_refresh_token (lines 36-50)."""

    def test_returns_token_and_saves_session(self, mock_db):
        from app.services.auth_service import create_refresh_token

        user = SimpleNamespace(id=1)
        mock_db.flush.side_effect = lambda: None
        token = create_refresh_token(mock_db, user)
        assert isinstance(token, str)
        assert len(token) > 40
        mock_db.add.assert_called_once()


class TestDecodeAccessToken:
    """Cover decode_access_token (lines 52-62)."""

    def test_invalid_token_raises(self):
        from fastapi import HTTPException

        from app.services.auth_service import decode_access_token

        with pytest.raises(HTTPException) as exc_info:
            decode_access_token("invalid.token.here")
        assert exc_info.value.status_code == 401


class TestAuthenticateUser:
    """Cover authenticate_user (lines 64-82)."""

    def test_user_not_found(self, mock_db):
        from fastapi import HTTPException

        from app.services.auth_service import authenticate_user

        mock_db.scalar.return_value = None
        with pytest.raises(HTTPException) as exc_info:
            authenticate_user(mock_db, "no@test.com", "pass")
        assert exc_info.value.status_code == 401

    def test_inactive_user(self, mock_db):
        from fastapi import HTTPException

        from app.services.auth_service import authenticate_user

        user = SimpleNamespace(status="inactive", password_hash="hash")
        mock_db.scalar.return_value = user
        with pytest.raises(HTTPException) as exc_info:
            authenticate_user(mock_db, "test@test.com", "pass")
        assert exc_info.value.status_code == 403

    def test_wrong_password(self, mock_db):
        from fastapi import HTTPException

        from app.services.auth_service import authenticate_user, hash_password

        hashed = hash_password("correct")
        user = SimpleNamespace(
            status=SimpleNamespace(value="active"),
            password_hash=hashed,
            failed_login_attempts=0,
        )
        # Need real UserStatus enum comparison
        from app.models.auth import UserStatus

        user.status = UserStatus.active
        mock_db.scalar.return_value = user
        with pytest.raises(HTTPException) as exc_info:
            authenticate_user(mock_db, "test@test.com", "wrong")
        assert exc_info.value.status_code == 401
        assert user.failed_login_attempts == 1
        mock_db.commit.assert_called()

    def test_success(self, mock_db):
        from app.models.auth import UserStatus
        from app.services.auth_service import authenticate_user, hash_password

        hashed = hash_password("correct")
        user = SimpleNamespace(
            id=1,
            email="test@test.com",
            status=UserStatus.active,
            password_hash=hashed,
            failed_login_attempts=2,
            last_login_at=None,
        )
        mock_db.scalar.return_value = user
        result = authenticate_user(mock_db, "test@test.com", "correct")
        assert result.id == 1
        assert user.failed_login_attempts == 0
        assert user.last_login_at is not None
        mock_db.commit.assert_called()
