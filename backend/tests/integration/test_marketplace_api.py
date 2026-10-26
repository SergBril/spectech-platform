"""Интеграционные тесты Marketplace API: публикация техники и публичная витрина."""

from datetime import datetime, timedelta, date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.catalog import Vehicle
from app.models.dispatch import Request


class TestMarketplaceListings:
    """Тесты управления публикациями (приватный API собственника)."""

    def test_publish_vehicle_success(
        self,
        auth_client: TestClient,
        db_session: Session,
        sample_vehicle: Vehicle,
    ):
        """✅ Собственник может опубликовать свою технику."""
        # Убеждаемся, что изначально не опубликована
        assert sample_vehicle.is_available_for_rent is False
        
        response = auth_client.post(
            "/api/v1/marketplace/listings",
            json={
                "vehicle_id": sample_vehicle.id,
                "hourly_rate": 2500,
                "shift_rate": 20000,
                "description": "Экскаватор CAT 320D в отличном состоянии",
                "base_location_lat": 55.7558,
                "base_location_lon": 37.6173,
            },
        )
        
        assert response.status_code == 201
        data = response.json()
        
        assert data["vehicle_id"] == sample_vehicle.id
        assert data["is_available_for_rent"] is True
        assert float(data["hourly_rate"]) == 2500.0
        assert float(data["shift_rate"]) == 20000.0
        assert data["description"] == "Экскаватор CAT 320D в отличном состоянии"
        
        # Проверяем в БД
        db_session.refresh(sample_vehicle)
        assert sample_vehicle.is_available_for_rent is True
        assert sample_vehicle.hourly_rate == Decimal("2500.00")

    def test_publish_vehicle_without_rate_fails(
        self, auth_client: TestClient, sample_vehicle: Vehicle
    ):
        """❌ Публикация без указания ставки отклоняется."""
        response = auth_client.post(
            "/api/v1/marketplace/listings",
            json={
                "vehicle_id": sample_vehicle.id,
                "description": "Без ставок",
            },
        )
        
        assert response.status_code == 400
        assert "rate" in response.json()["detail"].lower()

    def test_publish_another_company_vehicle_fails(
        self,
        auth_client: TestClient,
        db_session: Session,
    ):
        """❌ Нельзя публиковать технику другой компании."""
        from app.models.catalog import Vehicle
        
        # Создаём чужую технику
        other_vehicle = Vehicle(
            id_type="internal",
            id_value="OTHER-001",
            name="Чужой экскаватор",
            status="free",
            company_id=9999,  # Другая компания
        )
        db_session.add(other_vehicle)
        db_session.commit()
        
        response = auth_client.post(
            "/api/v1/marketplace/listings",
            json={
                "vehicle_id": other_vehicle.id,
                "hourly_rate": 1000,
            },
        )
        
        assert response.status_code == 400

    def test_get_my_listings(
        self,
        auth_client: TestClient,
        db_session: Session,
        sample_vehicle: Vehicle,
    ):
        """✅ Собственник видит список своих публикаций со статистикой."""
        # Публикуем технику
        auth_client.post(
            "/api/v1/marketplace/listings",
            json={
                "vehicle_id": sample_vehicle.id,
                "hourly_rate": 2500,
            },
        )
        
        response = auth_client.get("/api/v1/marketplace/listings/my")
        assert response.status_code == 200
        
        data = response.json()
        assert "items" in data
        assert "stats" in data
        assert data["total"] >= 1
        assert data["stats"]["published_vehicles"] >= 1
        
        # Находим нашу технику в списке
        vehicle_ids = [item["vehicle_id"] for item in data["items"]]
        assert sample_vehicle.id in vehicle_ids

    def test_update_listing(
        self,
        auth_client: TestClient,
        db_session: Session,
        sample_vehicle: Vehicle,
    ):
        """✅ Собственник может обновить параметры публикации."""
        # Публикуем
        auth_client.post(
            "/api/v1/marketplace/listings",
            json={"vehicle_id": sample_vehicle.id, "hourly_rate": 2500},
        )
        
        # Обновляем
        response = auth_client.patch(
            f"/api/v1/marketplace/listings/{sample_vehicle.id}",
            json={
                "hourly_rate": 3000,
                "description": "Обновлённое описание",
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        assert float(data["hourly_rate"]) == 3000.0
        assert data["description"] == "Обновлённое описание"

    def test_unpublish_listing(
        self,
        auth_client: TestClient,
        db_session: Session,
        sample_vehicle: Vehicle,
    ):
        """✅ Собственник может снять технику с публикации."""
        # Публикуем
        auth_client.post(
            "/api/v1/marketplace/listings",
            json={"vehicle_id": sample_vehicle.id, "hourly_rate": 2500},
        )
        
        db_session.refresh(sample_vehicle)
        assert sample_vehicle.is_available_for_rent is True
        
        # Снимаем с публикации
        response = auth_client.delete(
            f"/api/v1/marketplace/listings/{sample_vehicle.id}"
        )
        assert response.status_code == 204
        
        db_session.refresh(sample_vehicle)
        assert sample_vehicle.is_available_for_rent is False


class TestPublicMarketplace:
    """Тесты публичной витрины (без авторизации)."""

    @pytest.fixture
    def published_vehicle(
        self, auth_client: TestClient, sample_vehicle: Vehicle, db_session: Session
    ) -> Vehicle:
        """Публикует технику для публичных тестов."""
        # Убедиться, что компания активна (публичный API фильтрует по Company.is_active)
        from app.models.company import Company
        company = db_session.get(Company, sample_vehicle.company_id)
        if company and not company.is_active:
            company.is_active = True
            db_session.commit()

        auth_client.post(
            "/api/v1/marketplace/listings",
            json={
                "vehicle_id": sample_vehicle.id,
                "hourly_rate": 2500,
                "shift_rate": 20000,
                "description": "Тестовый экскаватор",
                "base_location_lat": 55.7558,
                "base_location_lon": 37.6173,
            },
        )
        return sample_vehicle

    def test_list_public_vehicles(
        self, client: TestClient, published_vehicle: Vehicle
    ):
        """✅ Публичный каталог возвращает только опубликованную технику."""
        response = client.get("/api/v1/public/vehicles")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        
        # Наша опубликованная техника должна быть в списке
        vehicle_ids = [v["id"] for v in data]
        assert published_vehicle.id in vehicle_ids
        
        # Проверяем структуру ответа
        for vehicle in data:
            assert "id" in vehicle
            assert "name" in vehicle
            assert "is_available_for_rent" in vehicle
            assert vehicle["is_available_for_rent"] is True

    def test_public_vehicles_filter_by_price(
        self, client: TestClient, published_vehicle: Vehicle
    ):
        """✅ Публичный каталог фильтрует по цене."""
        # Ищем в диапазоне, куда попадает наша техника
        response = client.get(
            "/api/v1/public/vehicles",
            params={"min_hourly_rate": 2000, "max_hourly_rate": 3000},
        )
        assert response.status_code == 200
        data = response.json()
        vehicle_ids = [v["id"] for v in data]
        assert published_vehicle.id in vehicle_ids
        
        # Ищем вне диапазона
        response = client.get(
            "/api/v1/public/vehicles",
            params={"min_hourly_rate": 5000, "max_hourly_rate": 10000},
        )
        assert response.status_code == 200
        data = response.json()
        vehicle_ids = [v["id"] for v in data]
        assert published_vehicle.id not in vehicle_ids

    def test_get_public_vehicle_details(
        self, client: TestClient, published_vehicle: Vehicle
    ):
        """✅ Детальная страница техники работает."""
        response = client.get(f"/api/v1/public/vehicles/{published_vehicle.id}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["id"] == published_vehicle.id
        assert data["name"] == published_vehicle.name
        assert data["is_available_for_rent"] is True

    def test_get_unpublished_vehicle_returns_404(
        self, client: TestClient, sample_vehicle: Vehicle
    ):
        """❌ Неопубликованная техника возвращает 404 в публичном API."""
        response = client.get(f"/api/v1/public/vehicles/{sample_vehicle.id}")
        assert response.status_code == 404

    def test_get_vehicle_availability(
        self, client: TestClient, published_vehicle: Vehicle
    ):
        """✅ Календарь доступности возвращает список дат."""
        today = date.today()
        to_date = today + timedelta(days=7)
        
        response = client.get(
            f"/api/v1/public/vehicles/{published_vehicle.id}/availability",
            params={
                "from_date": today.isoformat(),
                "to_date": to_date.isoformat(),
            },
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["vehicle_id"] == published_vehicle.id
        assert "calendar" in data
        assert len(data["calendar"]) == 8  # 7 дней + сегодня
        
        # Все даты должны быть доступны (нет активных Rental)
        for day in data["calendar"]:
            assert "date" in day
            assert "available" in day
            assert "rental_id" in day

    def test_create_request_from_listing(
        self, client: TestClient, published_vehicle: Vehicle, db_session: Session
    ):
        """✅ Создание заявки из витрины создаёт Request в базе."""
        planned_start = datetime.now() + timedelta(days=5)
        planned_end = planned_start + timedelta(days=2)
        
        response = client.post(
            f"/api/v1/public/vehicles/{published_vehicle.id}/request",
            json={
                "work_type": "Земляные работы",
                "planned_start": planned_start.isoformat(),
                "planned_end": planned_end.isoformat(),
                "comment": "Нужен экскаватор для котлована",
                "contact_name": "Иван Заказчиков",
                "contact_phone": "+79991234567",
                "contact_email": "client@example.com",
            },
        )
        
        assert response.status_code == 201
        data = response.json()
        
        assert data["vehicle_id"] == published_vehicle.id
        assert data["vehicle_name"] == published_vehicle.name
        assert data["status"] == "new"
        assert data["request_id"] > 0
        assert "Заявка" in data["message"]
        
        # Проверяем в БД
        request = db_session.get(Request, data["request_id"])
        assert request is not None
        assert request.work_type == "Земляные работы"
        assert request.planned_start == planned_start
        assert request.planned_end == planned_end

    def test_create_request_invalid_dates(
        self, client: TestClient, published_vehicle: Vehicle
    ):
        """❌ Заявка с некорректными датами отклоняется."""
        now = datetime.now()
        response = client.post(
            f"/api/v1/public/vehicles/{published_vehicle.id}/request",
            json={
                "work_type": "Тест",
                "planned_start": (now + timedelta(days=5)).isoformat(),
                "planned_end": (now + timedelta(days=3)).isoformat(),  # Раньше старта
                "contact_name": "Тест",
                "contact_phone": "+79991234567",
            },
        )
        
        assert response.status_code == 400
        assert "after" in response.json()["detail"].lower()

    def test_create_request_unpublished_vehicle(
        self, client: TestClient, sample_vehicle: Vehicle
    ):
        """❌ Заявка на неопубликованную технику отклоняется."""
        now = datetime.now()
        response = client.post(
            f"/api/v1/public/vehicles/{sample_vehicle.id}/request",
            json={
                "work_type": "Тест",
                "planned_start": (now + timedelta(days=5)).isoformat(),
                "planned_end": (now + timedelta(days=7)).isoformat(),
                "contact_name": "Тест",
                "contact_phone": "+79991234567",
            },
        )
        
        assert response.status_code == 404