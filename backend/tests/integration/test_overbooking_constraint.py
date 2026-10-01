"""Тесты для проверки constraint защиты от овербукинга на уровне БД."""

from datetime import datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.catalog import Vehicle
from app.models.contractor import Contractor
from app.models.dispatch import Request, RequestAssignment


class TestOverbookingConstraint:
    """Тесты EXCLUDE constraint для защиты от овербукинга."""

    @pytest.fixture
    def test_data(self, db_session: Session):
        """Создаёт тестовые данные."""
        # Создаём компанию
        from app.models.company import Company

        company = Company(name="Test Company", inn="1234567890")
        db_session.add(company)
        db_session.commit()
        db_session.refresh(company)

        # Создаём клиента
        client = Contractor(
            name="Test Client",
            inn="9876543210",
            type="client",
            company_id=company.id,
        )
        db_session.add(client)
        db_session.commit()
        db_session.refresh(client)

        # Создаём технику (С ОБЯЗАТЕЛЬНЫМИ ПОЛЯМИ id_type и id_value)
        vehicle = Vehicle(
            name="Test Vehicle",
            id_type="vin",
            id_value="TEST_VIN_123456789",
            category_id=1,
            company_id=company.id,
            status="free",
        )
        db_session.add(vehicle)
        db_session.commit()
        db_session.refresh(vehicle)

        return {
            "company": company,
            "client": client,
            "vehicle": vehicle,
        }

    def test_constraint_blocks_overlapping_assignments(
        self, db_session: Session, test_data
    ):
        """
        Тест: constraint блокирует создание пересекающихся назначений.

        Этот тест работает только в PostgreSQL с применённой миграцией.
        В SQLite тест пропускается.
        """
        # Проверяем, что это PostgreSQL
        if db_session.bind.dialect.name != "postgresql":
            pytest.skip("EXCLUDE constraint работает только в PostgreSQL")

        vehicle = test_data["vehicle"]
        client = test_data["client"]

        # Создаём первую заявку
        request1 = Request(
            client_id=client.id,
            status="assigned",
            planned_start=datetime.now() + timedelta(days=1),
            planned_end=datetime.now() + timedelta(days=1, hours=8),
            company_id=test_data["company"].id,
        )
        db_session.add(request1)
        db_session.commit()
        db_session.refresh(request1)

        # Создаём первое назначение
        assignment1 = RequestAssignment(
            request_id=request1.id,
            vehicle_id=vehicle.id,
            planned_start=request1.planned_start,
            planned_end=request1.planned_end,
            status="planned",
        )
        db_session.add(assignment1)
        db_session.commit()

        # Создаём вторую заявку на ТОТ ЖЕ период
        request2 = Request(
            client_id=client.id,
            status="assigned",
            planned_start=datetime.now() + timedelta(days=1),
            planned_end=datetime.now() + timedelta(days=1, hours=8),
            company_id=test_data["company"].id,
        )
        db_session.add(request2)
        db_session.commit()
        db_session.refresh(request2)

        # Пытаемся создать второе назначение — должно упасть с IntegrityError
        assignment2 = RequestAssignment(
            request_id=request2.id,
            vehicle_id=vehicle.id,
            planned_start=request2.planned_start,
            planned_end=request2.planned_end,
            status="planned",
        )
        db_session.add(assignment2)

        # Ожидаем IntegrityError из-за constraint
        with pytest.raises(IntegrityError) as exc_info:
            db_session.commit()

        # Проверяем, что ошибка связана с constraint
        assert (
            "prevent_overbooking" in str(exc_info.value).lower()
            or "conflicting key value violates exclusion constraint"
            in str(exc_info.value).lower()
        )

        # Откатываем транзакцию
        db_session.rollback()

    def test_constraint_allows_non_overlapping_assignments(
        self, db_session: Session, test_data
    ):
        """Тест: constraint разрешает непересекающиеся назначения."""
        if db_session.bind.dialect.name != "postgresql":
            pytest.skip("EXCLUDE constraint работает только в PostgreSQL")

        vehicle = test_data["vehicle"]
        client = test_data["client"]

        # Создаём первую заявку (завтра)
        request1 = Request(
            client_id=client.id,
            status="assigned",
            planned_start=datetime.now() + timedelta(days=1),
            planned_end=datetime.now() + timedelta(days=1, hours=8),
            company_id=test_data["company"].id,
        )
        db_session.add(request1)
        db_session.commit()
        db_session.refresh(request1)

        # Создаём первое назначение
        assignment1 = RequestAssignment(
            request_id=request1.id,
            vehicle_id=vehicle.id,
            planned_start=request1.planned_start,
            planned_end=request1.planned_end,
            status="planned",
        )
        db_session.add(assignment1)
        db_session.commit()

        # Создаём вторую заявку (послезавтра — НЕ пересекается)
        request2 = Request(
            client_id=client.id,
            status="assigned",
            planned_start=datetime.now() + timedelta(days=2),
            planned_end=datetime.now() + timedelta(days=2, hours=8),
            company_id=test_data["company"].id,
        )
        db_session.add(request2)
        db_session.commit()
        db_session.refresh(request2)

        # Создаём второе назначение — должно успешно создаться
        assignment2 = RequestAssignment(
            request_id=request2.id,
            vehicle_id=vehicle.id,
            planned_start=request2.planned_start,
            planned_end=request2.planned_end,
            status="planned",
        )
        db_session.add(assignment2)
        db_session.commit()  # Не должно быть ошибки

        # Проверяем, что оба назначения созданы
        assignments = (
            db_session.query(RequestAssignment)
            .filter(RequestAssignment.vehicle_id == vehicle.id)
            .all()
        )
        assert len(assignments) == 2

    def test_constraint_ignores_cancelled_assignments(
        self, db_session: Session, test_data
    ):
        """Тест: constraint игнорирует отменённые назначения."""
        if db_session.bind.dialect.name != "postgresql":
            pytest.skip("EXCLUDE constraint работает только в PostgreSQL")

        vehicle = test_data["vehicle"]
        client = test_data["client"]

        # Создаём первую заявку
        request1 = Request(
            client_id=client.id,
            status="assigned",
            planned_start=datetime.now() + timedelta(days=1),
            planned_end=datetime.now() + timedelta(days=1, hours=8),
            company_id=test_data["company"].id,
        )
        db_session.add(request1)
        db_session.commit()
        db_session.refresh(request1)

        # Создаём первое назначение со статусом CANCELLED
        assignment1 = RequestAssignment(
            request_id=request1.id,
            vehicle_id=vehicle.id,
            planned_start=request1.planned_start,
            planned_end=request1.planned_end,
            status="cancelled",  # ВАЖНО: отменённое
        )
        db_session.add(assignment1)
        db_session.commit()

        # Создаём вторую заявку на ТОТ ЖЕ период
        request2 = Request(
            client_id=client.id,
            status="assigned",
            planned_start=datetime.now() + timedelta(days=1),
            planned_end=datetime.now() + timedelta(days=1, hours=8),
            company_id=test_data["company"].id,
        )
        db_session.add(request2)
        db_session.commit()
        db_session.refresh(request2)

        # Создаём второе назначение — должно успешно создаться
        # (потому что первое отменено и constraint его игнорирует)
        assignment2 = RequestAssignment(
            request_id=request2.id,
            vehicle_id=vehicle.id,
            planned_start=request2.planned_start,
            planned_end=request2.planned_end,
            status="planned",
        )
        db_session.add(assignment2)
        db_session.commit()  # Не должно быть ошибки

        # Проверяем, что оба назначения существуют
        assignments = (
            db_session.query(RequestAssignment)
            .filter(RequestAssignment.vehicle_id == vehicle.id)
            .all()
        )
        assert len(assignments) == 2
