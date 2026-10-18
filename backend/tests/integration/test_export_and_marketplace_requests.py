"""Интеграционные тесты: экспорт заявок и маркетплейс заявок."""

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.catalog import Category
from app.models.dispatch import Request


class TestRequestsExport:
    """Тесты экспорта заявок в PDF и Excel."""

    @pytest.fixture
    def sample_request(self, db_session: Session, company, sample_contractor):
        """Создаёт тестовую заявку."""
        cat = Category(name="Экскаваторы гусеничные", code="excavators", level=1)
        db_session.add(cat)
        db_session.flush()

        req = Request(
            client_id=sample_contractor.id,
            status="new",
            request_type="one_time",
            work_type="Земляные работы",
            object_address="Москва, ул. Тестовая, д. 1",
            planned_start=datetime.now() + timedelta(days=1),
            planned_end=datetime.now() + timedelta(days=3),
            vehicle_category_id=cat.id,
            priority="high",
            estimated_amount=150000,
            company_id=company.id,
        )
        db_session.add(req)
        db_session.commit()
        db_session.refresh(req)
        return req

    def test_export_pdf_returns_200(
        self, auth_client: TestClient, sample_request: Request
    ):
        """✅ Экспорт заявок в PDF возвращает 200 и валидный PDF."""
        response = auth_client.get("/api/v1/requests/export/pdf")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        content = response.content
        assert len(content) > 0
        assert content[:5] == b"%PDF-"

    def test_export_excel_returns_200(
        self, auth_client: TestClient, sample_request: Request
    ):
        """✅ Экспорт заявок в Excel возвращает 200 и валидный XLSX."""
        response = auth_client.get("/api/v1/requests/export/excel")
        assert response.status_code == 200
        assert "spreadsheetml" in response.headers["content-type"]
        content = response.content
        assert len(content) > 0
        assert content[:2] == b"PK"

    def test_export_pdf_with_filters(
        self, auth_client: TestClient, sample_request: Request
    ):
        """✅ Экспорт PDF с фильтрами работает."""
        response = auth_client.get(
            "/api/v1/requests/export/pdf",
            params={"status": "new", "priority": "high"},
        )
        assert response.status_code == 200
        assert len(response.content) > 0

    def test_export_excel_with_search(
        self, auth_client: TestClient, sample_request: Request
    ):
        """✅ Экспорт Excel с поиском работает."""
        response = auth_client.get(
            "/api/v1/requests/export/excel",
            params={"search": "Земляные"},
        )
        assert response.status_code == 200
        assert len(response.content) > 0

    def test_export_unauthenticated_returns_401(self, client: TestClient):
        """❌ Экспорт без авторизации возвращает 401."""
        response = client.get("/api/v1/requests/export/pdf")
        assert response.status_code == 401


class TestMarketplaceRequests:
    """Тесты получения заявок маркетплейса."""

    @pytest.fixture
    def other_company_request(self, db_session: Session):
        """Создаёт опубликованную заявку от ДРУГОЙ компании."""
        from app.models.company import Company

        other_co = Company(
            name="Other Company",
            legal_name="Other LLC",
            inn="7799999999",
            kpp="779901001",
            city="Москва",
        )
        db_session.add(other_co)
        db_session.flush()

        cat = Category(name="Автокраны", code="cranes", level=1)
        db_session.add(cat)
        db_session.flush()

        req = Request(
            status="new",
            request_type="one_time",
            work_type="Монтажные работы",
            object_address="Москва, Промышленный проезд",
            planned_start=datetime.now() + timedelta(days=1),
            planned_end=datetime.now() + timedelta(days=3),
            vehicle_category_id=cat.id,
            priority="normal",
            estimated_amount=200000,
            company_id=other_co.id,
            is_published=True,
        )
        db_session.add(req)
        db_session.commit()
        db_session.refresh(req)
        return req

    def test_marketplace_requests_returns_published(
        self, auth_client: TestClient, other_company_request: Request
    ):
        """✅ Маркетплейс возвращает опубликованные заявки других компаний."""
        response = auth_client.get("/api/v1/marketplace/requests")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        ids = [r["id"] for r in data]
        assert other_company_request.id in ids

    def test_marketplace_requests_excludes_own_company(
        self, auth_client: TestClient, db_session: Session, company
    ):
        """❌ Маркетплейс НЕ возвращает заявки своей компании."""
        own_req = Request(
            status="new",
            request_type="one_time",
            work_type="Своя заявка",
            object_address="Москва",
            planned_start=datetime.now() + timedelta(days=1),
            planned_end=datetime.now() + timedelta(days=3),
            company_id=company.id,
            is_published=True,
        )
        db_session.add(own_req)
        db_session.commit()

        response = auth_client.get("/api/v1/marketplace/requests")
        assert response.status_code == 200
        data = response.json()
        ids = [r["id"] for r in data]
        assert own_req.id not in ids

    def test_marketplace_requests_unpublished_not_returned(
        self, auth_client: TestClient, db_session: Session
    ):
        """❌ Неопубликованные заявки не видны в маркетплейсе."""
        from app.models.company import Company

        other_co = Company(
            name="Hidden Co",
            legal_name="Hidden LLC",
            inn="7788888888",
            kpp="778801001",
        )
        db_session.add(other_co)
        db_session.flush()

        req = Request(
            status="new",
            request_type="one_time",
            work_type="Скрытая заявка",
            object_address="Москва",
            planned_start=datetime.now() + timedelta(days=1),
            planned_end=datetime.now() + timedelta(days=3),
            company_id=other_co.id,
            is_published=False,
        )
        db_session.add(req)
        db_session.commit()

        response = auth_client.get("/api/v1/marketplace/requests")
        data = response.json()
        ids = [r["id"] for r in data]
        assert req.id not in ids
