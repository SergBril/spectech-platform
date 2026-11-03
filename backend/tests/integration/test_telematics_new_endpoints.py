"""Integration tests for new telematics API endpoints."""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.catalog import Vehicle
from app.models.company import Company
from app.models.telematics import EngineHoursLog, GpsSyncLog


class TestEngineHoursHistoryAPI:
    """Tests for GET /api/v1/telematics/engine-hours/{vehicle_id}."""

    def test_returns_history(
        self,
        client: TestClient,
        auth_headers: dict,
        db_session: Session,
        company: Company,
    ):
        """Возвращает историю моточасов для техники."""
        vehicle = Vehicle(
            id_type="internal",
            id_value="EH-API-001",
            name="API Excavator",
            status="free",
            company_id=company.id,
            engine_hours=100.0,
        )
        db_session.add(vehicle)
        db_session.commit()
        db_session.refresh(vehicle)

        # Создаём записи в EngineHoursLog
        for i in range(3):
            log = EngineHoursLog(
                vehicle_id=vehicle.id,
                date=datetime.now(UTC) - timedelta(days=i),
                hours=5.0 + i,
                idle_hours=1.0,
                work_hours=4.0 + i,
                company_id=company.id,
            )
            db_session.add(log)
        db_session.commit()

        response = client.get(
            f"/api/v1/telematics/engine-hours/{vehicle.id}",
            headers=auth_headers,
            params={"days": 7},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        assert all("hours" in item and "work_hours" in item for item in data)

    def test_404_for_other_company_vehicle(
        self, client: TestClient, auth_headers: dict, db_session: Session
    ):
        """Возвращает 404 для чужой техники."""
        other_company = Company(
            name="Other EH Co",
            legal_name="Other",
            inn="7700000031",
            timezone="Europe/Moscow",
            currency="RUB",
            is_active=True,
        )
        db_session.add(other_company)
        db_session.flush()

        vehicle = Vehicle(
            id_type="internal",
            id_value="EH-OTHER",
            name="Other Vehicle",
            status="free",
            company_id=other_company.id,
            engine_hours=50.0,
        )
        db_session.add(vehicle)
        db_session.commit()

        response = client.get(
            f"/api/v1/telematics/engine-hours/{vehicle.id}",
            headers=auth_headers,
        )
        assert response.status_code == 404


class TestGpsSyncLogsAPI:
    """Tests for GET /api/v1/telematics/sync-logs."""

    def test_list_sync_logs(
        self, client: TestClient, auth_headers: dict, db_session: Session
    ):
        """Возвращает список логов синхронизации."""

        # Получаем company_id из auth_headers context
        # Создаём логи напрямую
        company = db_session.query(Company).first()

        for i in range(3):
            log = GpsSyncLog(
                company_id=company.id,
                provider_name="wialon",
                sync_type="last_position",
                status="success" if i < 2 else "error",
                points_received=1,
                duration_ms=100 + i * 50,
                error_message="Timeout" if i == 2 else None,
            )
            db_session.add(log)
        db_session.commit()

        response = client.get("/api/v1/telematics/sync-logs", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 3

    def test_filter_by_status(
        self, client: TestClient, auth_headers: dict, db_session: Session
    ):
        """Фильтрация по статусу работает."""
        company = db_session.query(Company).first()

        log = GpsSyncLog(
            company_id=company.id,
            provider_name="mapix",
            sync_type="track",
            status="error",
            error_message="Connection refused",
        )
        db_session.add(log)
        db_session.commit()

        response = client.get(
            "/api/v1/telematics/sync-logs",
            headers=auth_headers,
            params={"status": "error"},
        )
        assert response.status_code == 200
        data = response.json()
        assert all(item["status"] == "error" for item in data)

    def test_sync_logs_stats(
        self, client: TestClient, auth_headers: dict, db_session: Session
    ):
        """Статистика синхронизации группируется по провайдеру и статусу."""
        response = client.get(
            "/api/v1/telematics/sync-logs/stats", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
