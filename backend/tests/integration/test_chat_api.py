"""Интеграционные тесты для чата по заявке."""

import pytest
from fastapi.testclient import TestClient

from app.models.chat import ChatMessageType, ChatParticipantRole


class TestChatAPI:
    """Тесты API чата."""

    def test_get_or_create_chat(self, client: TestClient, auth_headers: dict):
        """Тест: получение или создание чата для заявки."""
        # Создаём тестовую заявку
        response = client.post(
            "/api/v1/requests",
            json={
                "client_id": 1,
                "vehicle_category_id": 1,
                "planned_start": "2026-01-15T09:00:00",
                "planned_end": "2026-01-15T18:00:00",
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        request_id = response.json()["id"]

        # Получаем чат (должен создаться автоматически)
        response = client.get(
            f"/api/v1/chat/requests/{request_id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["request_id"] == request_id
        assert data["participants_count"] >= 1

    def test_send_text_message(self, client: TestClient, auth_headers: dict):
        """Тест: отправка текстового сообщения."""
        # Создаём заявку и чат
        response = client.post(
            "/api/v1/requests",
            json={
                "client_id": 1,
                "vehicle_category_id": 1,
                "planned_start": "2026-01-15T09:00:00",
                "planned_end": "2026-01-15T18:00:00",
            },
            headers=auth_headers,
        )
        request_id = response.json()["id"]

        # Отправляем сообщение
        response = client.post(
            f"/api/v1/chat/requests/{request_id}/messages",
            json={
                "content": "Привет, когда приедет техника?",
                "message_type": ChatMessageType.text.value,
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["content"] == "Привет, когда приедет техника?"
        assert data["message_type"] == ChatMessageType.text.value

    def test_send_message_with_attachments(
        self, client: TestClient, auth_headers: dict
    ):
        """Тест: отправка сообщения с вложениями."""
        response = client.post(
            "/api/v1/requests",
            json={
                "client_id": 1,
                "vehicle_category_id": 1,
                "planned_start": "2026-01-15T09:00:00",
                "planned_end": "2026-01-15T18:00:00",
            },
            headers=auth_headers,
        )
        request_id = response.json()["id"]

        response = client.post(
            f"/api/v1/chat/requests/{request_id}/messages",
            json={
                "content": "Вот фото объекта",
                "message_type": ChatMessageType.photo.value,
                "attachments": {
                    "files": [
                        {"url": "https://storage.example.com/photo1.jpg", "name": "photo1.jpg"}
                    ]
                },
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["message_type"] == ChatMessageType.photo.value
        assert data["attachments"] is not None

    def test_get_messages_with_cursor(
        self, client: TestClient, auth_headers: dict
    ):
        """Тест: cursor-based пагинация сообщений."""
        response = client.post(
            "/api/v1/requests",
            json={
                "client_id": 1,
                "vehicle_category_id": 1,
                "planned_start": "2026-01-15T09:00:00",
                "planned_end": "2026-01-15T18:00:00",
            },
            headers=auth_headers,
        )
        request_id = response.json()["id"]

        # Отправляем 10 сообщений
        for i in range(10):
            client.post(
                f"/api/v1/chat/requests/{request_id}/messages",
                json={
                    "content": f"Сообщение {i+1}",
                    "message_type": ChatMessageType.text.value,
                },
                headers=auth_headers,
            )

        # Получаем первую страницу (5 сообщений)
        response = client.get(
            f"/api/v1/chat/requests/{request_id}/messages?limit=5",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["messages"]) == 5
        assert data["has_more"] is True
        assert data["next_cursor"] is not None

        # Получаем вторую страницу
        response = client.get(
            f"/api/v1/chat/requests/{request_id}/messages?limit=5&cursor={data['next_cursor']}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data2 = response.json()
        assert len(data2["messages"]) == 5
        assert data2["has_more"] is False

    def test_filter_messages_by_type(
        self, client: TestClient, auth_headers: dict
    ):
        """Тест: фильтрация сообщений по типу."""
        response = client.post(
            "/api/v1/requests",
            json={
                "client_id": 1,
                "vehicle_category_id": 1,
                "planned_start": "2026-01-15T09:00:00",
                "planned_end": "2026-01-15T18:00:00",
            },
            headers=auth_headers,
        )
        request_id = response.json()["id"]

        # Отправляем разные типы сообщений
        client.post(
            f"/api/v1/chat/requests/{request_id}/messages",
            json={"content": "Текст", "message_type": ChatMessageType.text.value},
            headers=auth_headers,
        )
        client.post(
            f"/api/v1/chat/requests/{request_id}/messages",
            json={"content": "Фото", "message_type": ChatMessageType.photo.value},
            headers=auth_headers,
        )
        client.post(
            f"/api/v1/chat/requests/{request_id}/messages",
            json={"content": "Документ", "message_type": ChatMessageType.document.value},
            headers=auth_headers,
        )

        # Фильтруем только фото
        response = client.get(
            f"/api/v1/chat/requests/{request_id}/messages?message_type={ChatMessageType.photo.value}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["messages"]) == 1
        assert data["messages"][0]["message_type"] == ChatMessageType.photo.value

    def test_unauthorized_access(self, client: TestClient):
        """Тест: доступ без авторизации."""
        response = client.get("/api/v1/chat/requests/1")
        assert response.status_code == 401

    def test_chat_not_found(self, client: TestClient, auth_headers: dict):
        """Тест: чат не найден."""
        response = client.get(
            "/api/v1/chat/requests/99999",
            headers=auth_headers,
        )
        assert response.status_code == 404