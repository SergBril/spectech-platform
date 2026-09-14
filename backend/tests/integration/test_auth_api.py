"""Integration тесты для API аутентификации."""


class TestAuthAPI:
    """Тесты endpoints /api/v1/auth/*."""

    def test_login_invalid_credentials(self, client):
        """Логин с несуществующим email возвращает 401."""
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "nonexistent@example.com",
                "password": "password123",
            },
        )
        assert response.status_code == 401

    def test_login_missing_fields(self, client):
        """Логин без полей возвращает 422 (validation error)."""
        response = client.post("/api/v1/auth/login", json={})
        assert response.status_code == 422


class TestProtectedEndpoints:
    """Тесты доступа к защищённым endpoints."""

    def test_access_without_token(self, client):
        """Запрос без токена возвращает 401."""
        response = client.get("/api/v1/requests")
        assert response.status_code in (401, 403)

    def test_access_with_invalid_token(self, client):
        """Запрос с невалидным токеном возвращает 401."""
        response = client.get(
            "/api/v1/requests",
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert response.status_code in (401, 403)

    def test_me_endpoint(self, client, sample_user):
        """Endpoint /me возвращает данные текущего пользователя."""
        from app.services.auth_service import create_access_token

        token = create_access_token(sample_user)

        response = client.get(
            "/api/v1/me",  # ← ИСПРАВЛЕНО: убран двойной /me
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == sample_user.email
