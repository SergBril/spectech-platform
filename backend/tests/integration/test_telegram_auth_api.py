"""Интеграционные тесты Telegram-привязки пользователя."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.auth import User


class TestTelegramAuthAPI:
    """Тесты endpoints привязки Telegram."""

    def test_generate_telegram_link_code_success(
        self, auth_client, db_session, admin_user
    ):
        """✅ Генерация кода привязки работает."""
        response = auth_client.post("/api/v1/auth/me/telegram-link-code")

        assert response.status_code == 200
        data = response.json()

        assert "code" in data
        assert len(data["code"]) >= 16
        assert data["bot_command"] == "/link_account"
        assert "message" in data

        # Проверяем в БД
        db_session.refresh(admin_user)
        assert admin_user.telegram_link_code == data["code"]

    def test_generate_link_code_regenerates(
        self, auth_client, db_session, admin_user
    ):
        """✅ Повторный вызов генерирует новый код."""
        # Первый код
        resp1 = auth_client.post("/api/v1/auth/me/telegram-link-code")
        code1 = resp1.json()["code"]

        # Второй код
        resp2 = auth_client.post("/api/v1/auth/me/telegram-link-code")
        code2 = resp2.json()["code"]

        assert code1 != code2, "Коды должны быть разными"

        # В БД — последний
        db_session.refresh(admin_user)
        assert admin_user.telegram_link_code == code2

    def test_get_telegram_status_unlinked(
        self, auth_client
    ):
        """✅ Показывает статус 'не привязан' для нового пользователя."""
        response = auth_client.get("/api/v1/auth/me/telegram-status")

        assert response.status_code == 200
        data = response.json()

        assert "linked" in data
        assert data["linked"] is False

    def test_unlink_telegram_when_not_linked(
        self, auth_client
    ):
        """❌ Отвязка без привязки возвращает 400."""
        response = auth_client.delete("/api/v1/auth/me/telegram-link")
        assert response.status_code == 400
        assert "not linked" in response.json()["detail"].lower()

    def test_telegram_link_flow(
        self, auth_client, db_session, admin_user
    ):
        """✅ Полный flow: генерация → привязка → статус → отвязка."""
        # 1. Генерируем код
        resp1 = auth_client.post("/api/v1/auth/me/telegram-link-code")
        assert resp1.status_code == 200
        code = resp1.json()["code"]

        # 2. Имитируем привязку (как бот сделал бы)
        admin_user.telegram_id = 123456789
        admin_user.telegram_link_code = None
        db_session.commit()

        # 3. Проверяем статус
        resp2 = auth_client.get("/api/v1/auth/me/telegram-status")
        assert resp2.status_code == 200
        data = resp2.json()
        assert data["linked"] is True
        assert data["telegram_id"] == 123456789

        # 4. Отвязываем
        resp3 = auth_client.delete("/api/v1/auth/me/telegram-link")
        assert resp3.status_code == 200

        # 5. Проверяем снова — отвязан
        db_session.refresh(admin_user)
        assert admin_user.telegram_id is None

    def test_endpoints_require_auth(
        self, client: TestClient
    ):
        """❌ Все endpoints требуют авторизацию."""
        endpoints = [
            ("POST", "/api/v1/auth/me/telegram-link-code"),
            ("GET", "/api/v1/auth/me/telegram-status"),
            ("DELETE", "/api/v1/auth/me/telegram-link"),
        ]
        
        for method, url in endpoints:
            if method == "POST":
                resp = client.post(url)
            elif method == "GET":
                resp = client.get(url)
            else:
                resp = client.delete(url)
            
            assert resp.status_code in (401, 422), f"{method} {url} should require auth"