"""Интеграционные тесты на multi-tenant изоляцию."""

import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.company import Company
from app.models.shift import ShiftTask
from app.models.catalog import Vehicle


class TestMultiTenantSecurity:
    """Тесты изоляции данных между компаниями."""

    @pytest.fixture
    def second_company(self, db_session: Session):
        """Создаем вторую компанию."""
        company = Company(
            name="Other Company LLC",
            legal_name="ООО Другая Компания",
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
    def other_user(self, db_session: Session, second_company: Company):
        """Создаем пользователя из другой компании."""
        user = User(
            email="other@test.com",
            full_name="Other User",
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

    def test_auto_generate_acts_isolation(
        self,
        client: TestClient,
        db_session: Session,
        company: Company,
        second_company: Company,
        other_user: User,
        auth_headers: dict,
    ):
        """❌ Пользователь НЕ может сгенерировать акты для чужой компании."""
        # 1. Создаем завершенную смену для ВТОРОЙ компании
        vehicle = Vehicle(
            name="Чужой трактор",
            company_id=second_company.id,
            status="free",
            id_type="STS",
            id_value="AA000000",
        )
        db_session.add(vehicle)
        db_session.commit()
        db_session.refresh(vehicle)

        # Create a request first (ShiftTask requires request_id)
        from app.models.dispatch import Request as DispatchRequest
        req = DispatchRequest(
            company_id=second_company.id,
            client_id=second_company.id,
            status="completed",
            work_type="earthworks",
            object_address="Test",
            vehicle_category_id=1,
            planned_start=date.today() - timedelta(days=1),
            planned_end=date.today(),
        )
        db_session.add(req)
        db_session.commit()
        db_session.refresh(req)

        shift = ShiftTask(
            company_id=second_company.id,
            vehicle_id=vehicle.id,
            request_id=req.id,
            shift_date=date.today() - timedelta(days=1),
            shift_number=1,
            status="completed",
        )
        db_session.add(shift)
        db_session.commit()

        # 2. Используем auth_headers из фикстуры (admin_user первой компании)
        headers = auth_headers

        # 3. Пытаемся сгенерировать акты (должны быть отфильтрованы по company_id)
        response = client.post(
            "/api/v1/shifts/acts/auto-generate",
            json={
                "date_from": (date.today() - timedelta(days=7)).isoformat(),
                "date_to": date.today().isoformat(),
            },
            headers=headers,
        )

        # 4. Проверяем, что акт НЕ был создан для чужой смены
        assert response.status_code == 200
        data = response.json()
        
        # Должно быть created=0, потому что у первой компании нет завершенных смен
        assert data["created"] == 0
        assert data["skipped"] == 0