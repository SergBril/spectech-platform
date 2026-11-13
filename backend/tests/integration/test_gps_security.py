"""Интеграционные тесты безопасности GPS-эндпоинтов (/api/v1/gps).

Шаг 1 плана фикса GPS (TDD): тесты описывают требуемое поведение —
авторизация обязательна, данные изолированы по company_id.
До фикса в app/api/routes/gps.py эти тесты падают.

Конвенция проекта для vehicle-scoped эндпоинтов (telematics.py, vehicles.py):
чужая или несуществующая техника → 404, чтобы не раскрывать факт существования.
"""

import csv
import io
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.catalog import Vehicle
from app.models.company import Company
from app.models.telematics import GpsPoint
from app.services.auth_service import create_access_token

pytestmark = [pytest.mark.integration]


# ─── Фикстуры ─────────────────────────────────────────────────────────────────


@pytest.fixture
def second_company(db_session: Session) -> Company:
    """Вторая компания — «чужой» тенант."""
    company = Company(
        name="GPS Other Company",
        legal_name="ООО Чужая Компания",
        inn="9999999999",
        timezone="Europe/Moscow",
        currency="RUB",
        is_active=True,
    )
    db_session.add(company)
    db_session.commit()
    db_session.refresh(company)
    return company


@pytest.fixture
def foreign_vehicle(db_session: Session, second_company: Company) -> Vehicle:
    """Техника чужой компании."""
    vehicle = Vehicle(
        name="Чужой экскаватор",
        company_id=second_company.id,
        status="free",
        id_type="internal",
        id_value="GPS-FOREIGN-001",
    )
    db_session.add(vehicle)
    db_session.commit()
    db_session.refresh(vehicle)
    return vehicle


@pytest.fixture
def other_user(db_session: Session, second_company: Company) -> User:
    """Обычный (не superuser) пользователь чужой компании."""
    user = User(
        email="gps-other@test.com",
        full_name="GPS Other User",
        password_hash="hashed_password",
        company_id=second_company.id,
        is_superuser=False,
        status="active",
        failed_login_attempts=0,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def other_auth_headers(other_user: User) -> dict:
    """Заголовки авторизации пользователя чужой компании."""
    token = create_access_token(user=other_user)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def own_point(db_session: Session, sample_vehicle: Vehicle) -> GpsPoint:
    """GPS-точка техники своей компании."""
    point = GpsPoint(
        vehicle_id=sample_vehicle.id,
        latitude=55.75,
        longitude=37.62,
        recorded_at=datetime.now(UTC),
    )
    db_session.add(point)
    db_session.commit()
    db_session.refresh(point)
    return point


@pytest.fixture
def foreign_point(db_session: Session, foreign_vehicle: Vehicle) -> GpsPoint:
    """GPS-точка техники чужой компании."""
    point = GpsPoint(
        vehicle_id=foreign_vehicle.id,
        latitude=59.93,
        longitude=30.31,
        recorded_at=datetime.now(UTC) - timedelta(minutes=5),
    )
    db_session.add(point)
    db_session.commit()
    db_session.refresh(point)
    return point


@pytest.fixture
def missing_vehicle_id(
    db_session: Session, sample_vehicle: Vehicle, foreign_vehicle: Vehicle
) -> int:
    """Гарантированно несуществующий id техники (без хардкода)."""
    max_id = db_session.query(func.max(Vehicle.id)).scalar() or 0
    return max_id + 1


def _import_payload(vehicle_id: int) -> list[dict]:
    """Тело запроса на импорт одной GPS-точки."""
    return [
        {
            "vehicle_id": vehicle_id,
            "latitude": 55.75,
            "longitude": 37.62,
            "recorded_at": datetime.now(UTC).isoformat(),
        }
    ]


# ─── Авторизация обязательна ──────────────────────────────────────────────────


class TestGpsAuthRequired:
    """Без токена все GPS-эндпоинты обязаны возвращать 401."""

    @pytest.mark.parametrize(
        ("method", "path"),
        [
            ("post", "/api/v1/gps/points/import"),
            ("get", "/api/v1/gps/points"),
            ("get", "/api/v1/gps/positions/latest"),
            ("get", "/api/v1/gps/points/stats"),
            ("get", "/api/v1/gps/points/export"),
            ("get", "/api/v1/gps/providers/vehicles"),
            ("patch", "/api/v1/gps/providers/vehicles/{vehicle_id}"),
        ],
    )
    def test_unauthorized_returns_401(
        self,
        client: TestClient,
        sample_vehicle: Vehicle,
        method: str,
        path: str,
    ):
        url = path.format(vehicle_id=sample_vehicle.id)
        kwargs = {"json": []} if method in ("post", "patch") else {}
        response = getattr(client, method)(url, **kwargs)
        assert response.status_code == 401


# ─── Изоляция чтения точек ────────────────────────────────────────────────────


class TestGpsPointsIsolation:
    """Точки, позиции, статистика и экспорт — только своей компании."""

    def test_list_points_returns_only_own_company(
        self,
        client: TestClient,
        auth_headers: dict,
        own_point: GpsPoint,
        foreign_point: GpsPoint,
        sample_vehicle: Vehicle,
    ):
        response = client.get("/api/v1/gps/points", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == own_point.id
        assert data[0]["vehicle_id"] == sample_vehicle.id

    def test_list_points_other_company_sees_only_its_own(
        self,
        client: TestClient,
        other_auth_headers: dict,
        own_point: GpsPoint,
        foreign_point: GpsPoint,
        foreign_vehicle: Vehicle,
    ):
        response = client.get("/api/v1/gps/points", headers=other_auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == foreign_point.id
        assert data[0]["vehicle_id"] == foreign_vehicle.id

    def test_list_points_foreign_vehicle_filter_returns_404(
        self,
        client: TestClient,
        auth_headers: dict,
        foreign_vehicle: Vehicle,
        own_point: GpsPoint,
    ):
        response = client.get(
            "/api/v1/gps/points",
            params={"vehicle_id": foreign_vehicle.id},
            headers=auth_headers,
        )
        assert response.status_code == 404

    def test_list_points_missing_vehicle_filter_returns_404(
        self,
        client: TestClient,
        auth_headers: dict,
        missing_vehicle_id: int,
    ):
        response = client.get(
            "/api/v1/gps/points",
            params={"vehicle_id": missing_vehicle_id},
            headers=auth_headers,
        )
        assert response.status_code == 404

    def test_latest_positions_scoped_to_company(
        self,
        client: TestClient,
        auth_headers: dict,
        own_point: GpsPoint,
        foreign_point: GpsPoint,
        sample_vehicle: Vehicle,
    ):
        response = client.get("/api/v1/gps/positions/latest", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert {p["vehicle_id"] for p in data} == {sample_vehicle.id}

    def test_latest_positions_other_company_sees_only_its_own(
        self,
        client: TestClient,
        other_auth_headers: dict,
        own_point: GpsPoint,
        foreign_point: GpsPoint,
        foreign_vehicle: Vehicle,
    ):
        response = client.get(
            "/api/v1/gps/positions/latest", headers=other_auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert {p["vehicle_id"] for p in data} == {foreign_vehicle.id}

    def test_stats_scoped_to_company(
        self,
        client: TestClient,
        auth_headers: dict,
        own_point: GpsPoint,
        foreign_point: GpsPoint,
    ):
        response = client.get("/api/v1/gps/points/stats", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total_points"] == 1
        assert data["vehicles_with_data"] == 1

    def test_stats_other_company_sees_only_its_own(
        self,
        client: TestClient,
        other_auth_headers: dict,
        own_point: GpsPoint,
        foreign_point: GpsPoint,
    ):
        response = client.get("/api/v1/gps/points/stats", headers=other_auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total_points"] == 1
        assert data["vehicles_with_data"] == 1

    def test_export_scoped_to_company(
        self,
        client: TestClient,
        auth_headers: dict,
        own_point: GpsPoint,
        foreign_point: GpsPoint,
        sample_vehicle: Vehicle,
    ):
        response = client.get("/api/v1/gps/points/export", headers=auth_headers)
        assert response.status_code == 200
        rows = list(csv.reader(io.StringIO(response.text)))
        exported_vehicle_ids = {int(row[0]) for row in rows[1:]}
        assert exported_vehicle_ids == {sample_vehicle.id}

    def test_export_foreign_vehicle_filter_returns_404(
        self,
        client: TestClient,
        auth_headers: dict,
        foreign_vehicle: Vehicle,
        own_point: GpsPoint,
    ):
        response = client.get(
            "/api/v1/gps/points/export",
            params={"vehicle_id": foreign_vehicle.id},
            headers=auth_headers,
        )
        assert response.status_code == 404

    def test_export_empty_company_returns_404(
        self, client: TestClient, auth_headers: dict
    ):
        response = client.get("/api/v1/gps/points/export", headers=auth_headers)
        assert response.status_code == 404


# ─── Безопасность импорта ─────────────────────────────────────────────────────


class TestGpsImportSecurity:
    """Импорт принимает точки только для техники своей компании."""

    def test_import_own_vehicle_ok(
        self,
        client: TestClient,
        auth_headers: dict,
        sample_vehicle: Vehicle,
        db_session: Session,
    ):
        response = client.post(
            "/api/v1/gps/points/import",
            json=_import_payload(sample_vehicle.id),
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["imported"] == 1
        count = (
            db_session.query(GpsPoint)
            .filter(GpsPoint.vehicle_id == sample_vehicle.id)
            .count()
        )
        assert count == 1

    def test_import_foreign_vehicle_returns_404_and_writes_nothing(
        self,
        client: TestClient,
        auth_headers: dict,
        foreign_vehicle: Vehicle,
        db_session: Session,
    ):
        response = client.post(
            "/api/v1/gps/points/import",
            json=_import_payload(foreign_vehicle.id),
            headers=auth_headers,
        )
        assert response.status_code == 404
        count = (
            db_session.query(GpsPoint)
            .filter(GpsPoint.vehicle_id == foreign_vehicle.id)
            .count()
        )
        assert count == 0

    def test_import_missing_vehicle_returns_404(
        self,
        client: TestClient,
        auth_headers: dict,
        missing_vehicle_id: int,
    ):
        response = client.post(
            "/api/v1/gps/points/import",
            json=_import_payload(missing_vehicle_id),
            headers=auth_headers,
        )
        assert response.status_code == 404

    def test_import_mixed_batch_rejected_atomically(
        self,
        client: TestClient,
        auth_headers: dict,
        sample_vehicle: Vehicle,
        foreign_vehicle: Vehicle,
        db_session: Session,
    ):
        """Пакет со своей и чужой техникой отклоняется целиком, до записи."""
        payload = _import_payload(sample_vehicle.id) + _import_payload(
            foreign_vehicle.id
        )
        response = client.post(
            "/api/v1/gps/points/import", json=payload, headers=auth_headers
        )
        assert response.status_code == 404
        assert db_session.query(GpsPoint).count() == 0

    def test_import_invalid_payload_returns_422(
        self, client: TestClient, auth_headers: dict, sample_vehicle: Vehicle
    ):
        payload = [{"vehicle_id": sample_vehicle.id, "latitude": 55.75}]
        response = client.post(
            "/api/v1/gps/points/import", json=payload, headers=auth_headers
        )
        assert response.status_code == 422


# ─── Провайдеры: список и конфигурация ────────────────────────────────────────


class TestGpsProvidersSecurity:
    """Список техники и GPS-конфигурация — только своей компании."""

    def test_providers_list_only_own_company(
        self,
        client: TestClient,
        auth_headers: dict,
        sample_vehicle: Vehicle,
        foreign_vehicle: Vehicle,
    ):
        response = client.get("/api/v1/gps/providers/vehicles", headers=auth_headers)
        assert response.status_code == 200
        assert [v["id"] for v in response.json()] == [sample_vehicle.id]

    def test_providers_list_other_company_sees_only_its_own(
        self,
        client: TestClient,
        other_auth_headers: dict,
        sample_vehicle: Vehicle,
        foreign_vehicle: Vehicle,
    ):
        response = client.get(
            "/api/v1/gps/providers/vehicles", headers=other_auth_headers
        )
        assert response.status_code == 200
        assert [v["id"] for v in response.json()] == [foreign_vehicle.id]

    def test_patch_own_vehicle_ok(
        self, client: TestClient, auth_headers: dict, sample_vehicle: Vehicle
    ):
        response = client.patch(
            f"/api/v1/gps/providers/vehicles/{sample_vehicle.id}",
            json={"gps_provider": "wialon"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["gps_provider"] == "wialon"

    def test_patch_foreign_vehicle_returns_404_and_keeps_config(
        self,
        client: TestClient,
        auth_headers: dict,
        foreign_vehicle: Vehicle,
        db_session: Session,
    ):
        response = client.patch(
            f"/api/v1/gps/providers/vehicles/{foreign_vehicle.id}",
            json={"gps_provider": "wialon"},
            headers=auth_headers,
        )
        assert response.status_code == 404
        db_session.refresh(foreign_vehicle)
        assert foreign_vehicle.gps_provider is None

    def test_patch_missing_vehicle_returns_404(
        self, client: TestClient, auth_headers: dict, missing_vehicle_id: int
    ):
        response = client.patch(
            f"/api/v1/gps/providers/vehicles/{missing_vehicle_id}",
            json={"gps_provider": "wialon"},
            headers=auth_headers,
        )
        assert response.status_code == 404

    def test_patch_other_company_own_vehicle_ok(
        self,
        client: TestClient,
        other_auth_headers: dict,
        foreign_vehicle: Vehicle,
    ):
        response = client.patch(
            f"/api/v1/gps/providers/vehicles/{foreign_vehicle.id}",
            json={"gps_provider": "mapix"},
            headers=other_auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["gps_provider"] == "mapix"


# ─── Переключение компании через X-Company-Id ─────────────────────────────────


class TestGpsCompanyHeader:
    """X-Company-Id работает только для superuser и не ломает изоляцию."""

    def test_superuser_can_switch_company_via_header(
        self,
        client: TestClient,
        auth_headers: dict,
        second_company: Company,
        own_point: GpsPoint,
        foreign_point: GpsPoint,
        foreign_vehicle: Vehicle,
    ):
        headers = {**auth_headers, "X-Company-Id": str(second_company.id)}
        response = client.get("/api/v1/gps/points", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["vehicle_id"] == foreign_vehicle.id

    def test_regular_user_cannot_switch_company_via_header(
        self,
        client: TestClient,
        other_auth_headers: dict,
        company: Company,
        own_point: GpsPoint,
        foreign_point: GpsPoint,
        foreign_vehicle: Vehicle,
    ):
        headers = {**other_auth_headers, "X-Company-Id": str(company.id)}
        response = client.get("/api/v1/gps/points", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["vehicle_id"] == foreign_vehicle.id
