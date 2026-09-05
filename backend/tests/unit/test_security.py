"""
Unit tests для модуля безопасности (auth_service).
"""
import pytest
from unittest.mock import Mock, MagicMock
from fastapi import HTTPException
from app.services.auth_service import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    authenticate_user,
)
from app.models.auth import User


class TestPasswordHashing:
    """Тесты хеширования паролей."""
    
    def test_hash_password_creates_hash(self):
        """Проверяем что хеш создаётся."""
        password = "secure_password_123"
        hashed = hash_password(password)
        
        assert hashed is not None
        assert hashed != password
        assert len(hashed) > 50  # bcrypt hash длина
    
    def test_hash_password_different_each_time(self):
        """Проверяем что хеш разный каждый раз (salt)."""
        password = "same_password"
        hash1 = hash_password(password)
        hash2 = hash_password(password)
        
        assert hash1 != hash2
    
    def test_verify_password_correct(self):
        """Проверяем что правильный пароль проходит верификацию."""
        password = "correct_password"
        hashed = hash_password(password)
        
        assert verify_password(password, hashed) is True
    
    def test_verify_password_incorrect(self):
        """Проверяем что неправильный пароль не проходит."""
        password = "correct_password"
        wrong_password = "wrong_password"
        hashed = hash_password(password)
        
        assert verify_password(wrong_password, hashed) is False
    
    def test_verify_password_empty(self):
        """Проверяем обработку пустых паролей."""
        hashed = hash_password("password")
        
        assert verify_password("", hashed) is False
    
    def test_hash_password_with_special_chars(self):
        """Проверяем пароли со спецсимволами."""
        password = "P@$$w0rd!#%&*()"
        hashed = hash_password(password)
        
        assert verify_password(password, hashed) is True
    
    def test_hash_password_unicode(self):
        """Проверяем пароли с unicode символами."""
        password = "пароль123"
        hashed = hash_password(password)
        
        assert verify_password(password, hashed) is True


class TestJWT:
    """Тесты JWT токенов."""
    
    def test_create_access_token(self):
        """Проверяем создание access token."""
        # Создаём mock пользователя
        user = Mock(spec=User)
        user.id = 1
        user.email = "test@example.com"
        user.company_id = 1
        user.is_superuser = False
        
        token = create_access_token(user)
        
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 50
    
    def test_create_refresh_token(self):
        """Проверяем создание refresh token."""
        # Mock DB session
        db = Mock()
        db.add = Mock()
        db.commit = Mock()
        
        user = Mock(spec=User)
        user.id = 1
        user.email = "test@example.com"
        
        token = create_refresh_token(db, user)
        
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 50
        # Проверяем что token был добавлен в БД
        # (commit может вызываться вызывающим кодом, а не внутри функции)
        db.add.assert_called_once()
    
    def test_decode_access_token_valid(self):
        """Проверяем декодирование валидного токена."""
        user = Mock(spec=User)
        user.id = 1
        user.email = "test@example.com"
        user.company_id = 1
        user.is_superuser = False
        
        token = create_access_token(user)
        decoded = decode_access_token(token)
        
        assert decoded is not None
        assert "sub" in decoded
        assert "exp" in decoded
    
    def test_decode_access_token_invalid(self):
        """Проверяем декодирование невалидного токена."""
        invalid_token = "invalid.token.here"
        
        # decode_access_token выбрасывает HTTPException 401 для невалидных токенов
        with pytest.raises(HTTPException) as exc_info:
            decode_access_token(invalid_token)
        assert exc_info.value.status_code == 401
    
    def test_decode_access_token_tampered(self):
        """Проверяем что подделанный токен не декодируется."""
        user = Mock(spec=User)
        user.id = 1
        user.email = "test@example.com"
        user.company_id = 1
        user.is_superuser = False
        
        token = create_access_token(user)
        # Подделываем токен
        tampered_token = token[:-5] + "XXXXX"
        
        # decode_access_token выбрасывает HTTPException 401
        with pytest.raises(HTTPException) as exc_info:
            decode_access_token(tampered_token)
        assert exc_info.value.status_code == 401


class TestAuthenticateUser:
    """Тесты аутентификации пользователя."""
    
    def test_authenticate_user_success(self):
        """Проверяем успешную аутентификацию."""
        from app.models.auth import UserStatus
        
        # Setup
        password = "test_password"
        hashed = hash_password(password)
        
        user = Mock(spec=User)
        user.id = 1
        user.email = "test@example.com"
        user.password_hash = hashed
        user.status = UserStatus.active
        
        db = Mock()
        db.scalar = Mock(return_value=user)
        
        # Test
        result = authenticate_user(db, "test@example.com", password)
        
        # Assert
        assert result is not None
        assert result.email == "test@example.com"
        db.scalar.assert_called_once()
    
    def test_authenticate_user_wrong_password(self):
        """Проверяем аутентификацию с неправильным паролем."""
        from app.models.auth import UserStatus
        
        password = "correct_password"
        hashed = hash_password(password)
        
        user = Mock(spec=User)
        user.id = 1
        user.email = "test@example.com"
        user.password_hash = hashed
        user.status = UserStatus.active
        user.failed_login_attempts = 0  # Обязательно как int для +=
        
        db = Mock()
        db.scalar = Mock(return_value=user)
        
        # authenticate_user выбрасывает HTTPException 401 для неправильного пароля
        with pytest.raises(HTTPException) as exc_info:
            authenticate_user(db, "test@example.com", "wrong_password")
        assert exc_info.value.status_code == 401
        # Проверяем что счётчик попыток увеличился
        assert user.failed_login_attempts == 1
    
    def test_authenticate_user_not_found(self):
        """Проверяем аутентификацию несуществующего пользователя."""
        db = Mock()
        db.scalar = Mock(return_value=None)
        
        # authenticate_user выбрасывает HTTPException 401 если пользователь не найден
        with pytest.raises(HTTPException) as exc_info:
            authenticate_user(db, "nonexistent@example.com", "password")
        assert exc_info.value.status_code == 401
    
    def test_authenticate_user_inactive(self):
        """Проверяем аутентификацию неактивного пользователя."""
        from app.models.auth import UserStatus
        
        password = "test_password"
        hashed = hash_password(password)
        
        user = Mock(spec=User)
        user.id = 1
        user.email = "test@example.com"
        user.password_hash = hashed
        user.status = UserStatus.suspended  # Используем правильное enum значение
        
        db = Mock()
        db.scalar = Mock(return_value=user)
        
        # authenticate_user выбрасывает HTTPException 403 для неактивного пользователя
        with pytest.raises(HTTPException) as exc_info:
            authenticate_user(db, "test@example.com", password)
        assert exc_info.value.status_code == 403


class TestEdgeCases:
    """Тесты граничных случаев."""
    
    def test_hash_password_very_long(self):
        """Проверяем очень длинный пароль."""
        password = "a" * 1000
        hashed = hash_password(password)
        
        assert verify_password(password, hashed) is True
    
    def test_hash_password_empty_string(self):
        """Проверяем пустой пароль."""
        password = ""
        hashed = hash_password(password)
        
        assert verify_password("", hashed) is True
    
    def test_verify_password_with_none_hash(self):
        """Проверяем обработку None в качестве хеша."""
        try:
            result = verify_password("password", None)
            assert result is False
        except (AttributeError, TypeError):
            # Допустимо выбросить исключение
            pass
    
    def test_create_multiple_access_tokens(self):
        """Проверяем что токены создаются каждый раз новые."""
        import time
        
        user = Mock(spec=User)
        user.id = 1
        user.email = "test@example.com"
        user.company_id = 1
        user.is_superuser = False
        
        token1 = create_access_token(user)
        time.sleep(1.1)  # Ждём >1 секунды чтобы exp был разным
        token2 = create_access_token(user)
        
        # Токены должны быть разными (из-за exp timestamp)
        assert token1 != token2
