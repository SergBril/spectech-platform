"""Integration тесты для API заявок."""

from datetime import UTC, datetime, timedelta

import pytest


@pytest.fixture
def auth_token(sample_user):
    """Создаёт валидный токен для тестов."""
    from app.services.auth_service import create_access_token

    return create_access_token(sample_user)


@pytest.fixture
def auth_headers(auth_token):
    """Возвращает headers с токеном."""
    return {"Authorization": f"Bearer {auth_token}"}


class TestRequestsAPI:
    """Тесты endpoints /api/v1/requests/*."""

    def test_list_requests_empty(self, client, auth_headers):
        """Список заявок доступен."""
        response = client.get("/api/v1/requests", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_request_not_found(self, client, auth_headers):
        """Запрос несуществующей заявки возвращает 404."""
        response = client.get("/api/v1/requests/99999", headers=auth_headers)
        assert response.status_code == 404

    def test_get_request_history(self, client, auth_headers, sample_user):
        """История заявки доступна по endpoint."""
        # Создаём заявку напрямую через БД
        from app.core.db import SessionLocal
        from app.models.dispatch import Request, RequestStatusLog

        db = SessionLocal()
        try:
            now = datetime.now(UTC)
            request = Request(
                client_id=1,
                work_type="Test work",
                object_address="Test address",
                planned_start=now,
                planned_end=now + timedelta(days=1),
                status="new",
                request_type="one_time",
                source_channel="phone",
                priority="normal",
                company_id=1,
                rate_type="hourly",
                created_by=sample_user.id,
            )
            db.add(request)
            db.flush()

            db.add(
                RequestStatusLog(
                    request_id=request.id,
                    from_status=None,
                    to_status="new",
                    changed_by_user_id=sample_user.id,
                    comment="Test creation",
                )
            )
            db.commit()
            req_id = request.id
        finally:
            db.close()

        response = client.get(
            f"/api/v1/requests/{req_id}/history",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["to_status"] == "new"
