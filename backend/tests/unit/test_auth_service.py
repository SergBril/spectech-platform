import pytest
from unittest.mock import MagicMock, patch
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException

from app.services.auth_service import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    authenticate_user,
)


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def mock_user():
    user = MagicMock()
    user.id = 5
    user.email = "test@example.com"
    user.status = MagicMock()
    user.status.value = "active"
    user.failed_login_attempts = 0
    user.last_login_at = None
    return user


class TestPasswordHashing:
    """Tests for hash_password and verify_password"""

    def test_hash_and_verify_correct(self):
        hashed = hash_password("secret123")
        assert verify_password("secret123", hashed) is True

    def test_verify_wrong_password(self):
        hashed = hash_password("secret123")
        assert verify_password("wrong", hashed) is False

    def test_hash_produces_different_salts(self):
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2  # Different salts


class TestCreateAccessToken:
    """Tests for create_access_token"""

    def test_creates_valid_token(self, mock_user):
        token = create_access_token(mock_user)
        assert isinstance(token, str)
        assert len(token) > 20

    def test_token_contains_user_id(self, mock_user):
        token = create_access_token(mock_user)
        payload = decode_access_token(token)
        assert payload["sub"] == "5"
        assert payload["email"] == "test@example.com"


class TestDecodeAccessToken:
    """Tests for decode_access_token"""

    def test_decode_valid_token(self, mock_user):
        token = create_access_token(mock_user)
        payload = decode_access_token(token)
        assert payload["sub"] == "5"

    def test_decode_invalid_token(self):
        with pytest.raises(HTTPException) as exc_info:
            decode_access_token("invalid.token.here")
        assert exc_info.value.status_code == 401

    def test_decode_tampered_token(self, mock_user):
        token = create_access_token(mock_user)
        tampered = token[:-5] + "XXXXX"
        with pytest.raises(HTTPException) as exc_info:
            decode_access_token(tampered)
        assert exc_info.value.status_code == 401


class TestCreateRefreshToken:
    """Tests for create_refresh_token"""

    def test_creates_token_and_saves_session(self, mock_db, mock_user):
        mock_db.add = MagicMock()
        mock_db.flush = MagicMock()

        token = create_refresh_token(mock_db, mock_user)

        assert isinstance(token, str)
        assert len(token) > 40
        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()

    def test_tokens_are_unique(self, mock_db, mock_user):
        mock_db.add = MagicMock()
        mock_db.flush = MagicMock()

        t1 = create_refresh_token(mock_db, mock_user)
        t2 = create_refresh_token(mock_db, mock_user)
        assert t1 != t2


class TestAuthenticateUser:
    """Tests for authenticate_user"""

    def test_authenticate_success(self, mock_db, mock_user):
        from app.models.auth import UserStatus
        mock_user.status = UserStatus.active
        mock_user.password_hash = hash_password("correct")

        mock_db.scalar = MagicMock(return_value=mock_user)
        mock_db.commit = MagicMock()

        result = authenticate_user(mock_db, "test@example.com", "correct")

        assert result == mock_user
        assert mock_user.failed_login_attempts == 0
        assert mock_user.last_login_at is not None
        mock_db.commit.assert_called_once()

    def test_authenticate_user_not_found(self, mock_db):
        mock_db.scalar = MagicMock(return_value=None)

        with pytest.raises(HTTPException) as exc_info:
            authenticate_user(mock_db, "noone@test.com", "pass")
        assert exc_info.value.status_code == 401

    def test_authenticate_inactive_user(self, mock_db, mock_user):
        from app.models.auth import UserStatus
        mock_user.status = UserStatus.suspended
        mock_db.scalar = MagicMock(return_value=mock_user)

        with pytest.raises(HTTPException) as exc_info:
            authenticate_user(mock_db, "test@example.com", "pass")
        assert exc_info.value.status_code == 403

    def test_authenticate_wrong_password(self, mock_db, mock_user):
        from app.models.auth import UserStatus
        mock_user.status = UserStatus.active
        mock_user.password_hash = hash_password("correct")
        mock_user.failed_login_attempts = 0

        mock_db.scalar = MagicMock(return_value=mock_user)
        mock_db.commit = MagicMock()

        with pytest.raises(HTTPException) as exc_info:
            authenticate_user(mock_db, "test@example.com", "wrong")
        assert exc_info.value.status_code == 401
        assert mock_user.failed_login_attempts == 1
        mock_db.commit.assert_called_once()
