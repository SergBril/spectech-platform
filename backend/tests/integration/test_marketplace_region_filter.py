"""Тесты региональной фильтрации маркетплейса."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.catalog import Vehicle
from app.models.dispatch import Request as DispatchRequest
from app.models.marketplace import MarketplaceOffer


class TestMarketplaceRegionFilter:
    """Владелец техники видит только заявки своего региона."""

    def _create_marketplace_request(
        self, db: Session, company_id: int, region: str, category_id: int | None = None
    ) -> DispatchRequest:
        from datetime import datetime, timedelta, UTC
        req = DispatchRequest(
            company_id=company_id,
            source_channel="marketplace",
            is_published=True,
            status="new",
            region=region,
            vehicle_category_id=category_id,
            work_type="earthworks",
            object_address=f"{region}, ул. Тестовая",
            planned_start=datetime.now(UTC) + timedelta(days=1),
            planned_end=datetime.now(UTC) + timedelta(days=2),
            shift_duration_hours=8,
            client_rate=5000,
            rate_type="hourly",
        )
        db.add(req)
        db.commit()
        db.refresh(req)
        return req

    def test_owner_sees_only_same_region_requests(
        self,
        auth_client: TestClient,
        db_session: Session,
        sample_vehicle: Vehicle,
        auth_headers: dict,
    ):
        """Владелец техники в Москве видит только московские заявки."""
        # Устанавливаем регион техники
        sample_vehicle.region = "Москва"
        db_session.commit()

        # Создаём заявки в разных регионах от другой компании
        other_company_id = sample_vehicle.company_id + 999  # другая компания
        moscow_req = self._create_marketplace_request(db_session, other_company_id, "Москва")
        spb_req = self._create_marketplace_request(db_session, other_company_id, "Санкт-Петербург")
        lenobl_req = self._create_marketplace_request(db_session, other_company_id, "Ленинградская область")

        # Запрашиваем список заявок как владелец техники
        response = auth_client.get("/api/v1/public/marketplace/requests")
        assert response.status_code == 200
        data = response.json()

        request_ids = [r["id"] for r in data["items"]]

        # Должна быть видна только московская заявка
        assert moscow_req.id in request_ids, "Московская заявка должна быть видна"
        assert spb_req.id not in request_ids, "Питерская заявка НЕ должна быть видна"
        assert lenobl_req.id not in request_ids, "Заявка Ленобласти НЕ должна быть видна"

    def test_unauthenticated_user_sees_all_requests(
        self,
        client: TestClient,
        db_session: Session,
    ):
        """Неавторизованный пользователь видит все заявки (без фильтрации по региону)."""
        other_company_id = 9999
        self._create_marketplace_request(db_session, other_company_id, "Москва")
        self._create_marketplace_request(db_session, other_company_id, "Санкт-Петербург")

        response = client.get("/api/v1/public/marketplace/requests")
        assert response.status_code == 200
        data = response.json()

        # Без авторизации видны все заявки
        assert data["total"] >= 2

    def test_owner_without_vehicles_sees_all_requests(
        self,
        auth_client: TestClient,
        db_session: Session,
    ):
        """Авторизованный пользователь без техники видит все заявки."""
        other_company_id = 9999
        self._create_marketplace_request(db_session, other_company_id, "Москва")
        self._create_marketplace_request(db_session, other_company_id, "Санкт-Петербург")

        response = auth_client.get("/api/v1/public/marketplace/requests")
        assert response.status_code == 200
        data = response.json()

        # Пользователь без техники видит все
        assert data["total"] >= 2
