"""
Тесты для проверки работоспособности инфраструктуры тестирования.
"""

import pytest


class TestInfrastructure:
    """Проверяем что тестовая инфраструктура работает."""

    def test_pytest_works(self):
        """Простой тест для проверки что pytest работает."""
        assert 1 + 1 == 2

    def test_imports_work(self):
        """Проверяем что импорты работают."""
        from app.core.config import settings
        from app.core.db import Base
        from app.main import app

        assert app is not None
        assert Base is not None
        assert settings is not None

    def test_app_routes(self):
        """Проверяем что маршруты приложения загружены."""
        from app.main import app

        routes = [route.path for route in app.routes]
        # Проверяем что базовые endpoints документации есть
        assert "/docs" in routes or any("/docs" in r for r in routes)
        # Проверяем что API endpoints загружены (хотя бы один)
        api_routes = [r for r in routes if r.startswith("/api/")]
        assert len(api_routes) > 0, "No API routes loaded"

    @pytest.mark.asyncio
    async def test_async_works(self):
        """Проверяем что асинхронные тесты работают."""
        import asyncio

        await asyncio.sleep(0.01)
        assert True

    @pytest.mark.asyncio
    def test_client_fixture(self, client):
        """Проверяем, что TestClient работает корректно."""
        # TestClient синхронный, await НЕ нужен
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
