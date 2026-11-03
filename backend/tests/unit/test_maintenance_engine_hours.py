"""Unit tests for engine-hours-based maintenance scheduling."""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.catalog import Vehicle
from app.models.company import Company


def _create_test_user(db_session: Session, company_id: int) -> User:
    """Создаёт тестового пользователя для компании (требуется для auto_check)."""
    user = User(
        email=f"maint_test_{company_id}@test.com",
        full_name="Maintenance Test User",
        password_hash="test_hash",
        company_id=company_id,
        is_superuser=False,
        status="active",
    )
    db_session.add(user)
    db_session.flush()
    return user


class TestUpdateVehicleEngineHours:
    """Tests for maintenance_service.update_vehicle_engine_hours."""

    def test_updates_engine_hours(self, db_session: Session):
        """Моточасы обновляются корректно."""
        from app.services.maintenance_service import maintenance_service

        company = Company(
            name="Test Co",
            legal_name="Test",
            inn="7700000001",
            timezone="Europe/Moscow",
            currency="RUB",
            is_active=True,
        )
        db_session.add(company)
        db_session.flush()

        vehicle = Vehicle(
            id_type="internal",
            id_value="EH-001",
            name="Test Excavator",
            status="free",
            company_id=company.id,
            engine_hours=100.0,
            maintenance_interval=250,
            next_maintenance_hours=250.0,
        )
        db_session.add(vehicle)
        db_session.commit()
        db_session.refresh(vehicle)

        result = maintenance_service.update_vehicle_engine_hours(
            db=db_session,
            vehicle_id=vehicle.id,
            new_engine_hours=150.0,
            auto_check=False,
        )
        db_session.commit()

        assert result["updated"] is True
        assert result["old_hours"] == 100.0
        assert result["new_hours"] == 150.0
        db_session.refresh(vehicle)
        assert float(vehicle.engine_hours) == 150.0

    def test_rejects_rollback(self, db_session: Session):
        """Откат моточасов отклоняется."""
        from app.services.maintenance_service import maintenance_service

        company = Company(
            name="Test Co2",
            legal_name="Test2",
            inn="7700000002",
            timezone="Europe/Moscow",
            currency="RUB",
            is_active=True,
        )
        db_session.add(company)
        db_session.flush()

        vehicle = Vehicle(
            id_type="internal",
            id_value="EH-002",
            name="Test Loader",
            status="free",
            company_id=company.id,
            engine_hours=200.0,
            maintenance_interval=250,
        )
        db_session.add(vehicle)
        db_session.commit()
        db_session.refresh(vehicle)

        result = maintenance_service.update_vehicle_engine_hours(
            db=db_session,
            vehicle_id=vehicle.id,
            new_engine_hours=150.0,
            auto_check=False,
        )

        assert result["updated"] is False
        assert result["reason"] == "engine_hours_rollback"

    def test_auto_creates_maintenance_order(self, db_session: Session):
        """При достижении порога check_scheduled_maintenance создаёт наряд."""
        from app.services.maintenance_service import MaintenanceService

        company = Company(
            name="Test Co3",
            legal_name="Test3",
            inn="7700000003",
            timezone="Europe/Moscow",
            currency="RUB",
            is_active=True,
        )
        db_session.add(company)
        db_session.flush()

        vehicle = Vehicle(
            id_type="internal",
            id_value="EH-003",
            name="Test Crane",
            status="free",
            company_id=company.id,
            engine_hours=260.0,
            maintenance_interval=250,
            next_maintenance_hours=250.0,
        )
        db_session.add(vehicle)
        user = _create_test_user(db_session, company.id)
        db_session.commit()

        # Вызываем check_scheduled_maintenance напрямую (vehicle уже имеет engine_hours >= threshold)
        created = MaintenanceService.check_scheduled_maintenance(
            db=db_session,
            company_id=company.id,
            user_id=user.id,
        )
        db_session.commit()

        assert len(created) > 0
        assert created[0]["hours_overdue"] == 10.0
        assert created[0]["vehicle_id"] == vehicle.id

    def test_no_duplicate_maintenance_order(self, db_session: Session):
        """Повторный вызов не создаёт дубликат наряда."""
        from app.services.maintenance_service import MaintenanceService

        company = Company(
            name="Test Co4",
            legal_name="Test4",
            inn="7700000004",
            timezone="Europe/Moscow",
            currency="RUB",
            is_active=True,
        )
        db_session.add(company)
        db_session.flush()

        vehicle = Vehicle(
            id_type="internal",
            id_value="EH-004",
            name="Test Dozer",
            status="free",
            company_id=company.id,
            engine_hours=260.0,
            maintenance_interval=250,
            next_maintenance_hours=250.0,
        )
        db_session.add(vehicle)
        user = _create_test_user(db_session, company.id)
        db_session.commit()

        # Первый вызов — создаёт наряд
        r1 = MaintenanceService.check_scheduled_maintenance(
            db=db_session,
            company_id=company.id,
            user_id=user.id,
        )
        db_session.commit()
        assert len(r1) > 0

        # Второй вызов — не должен создавать дубликат
        r2 = MaintenanceService.check_scheduled_maintenance(
            db=db_session,
            company_id=company.id,
            user_id=user.id,
        )
        db_session.commit()
        assert len(r2) == 0

    def test_writes_engine_hours_log(self, db_session: Session):
        """Обновление записывается в EngineHoursLog."""
        from app.models.telematics import EngineHoursLog
        from app.services.maintenance_service import maintenance_service

        company = Company(
            name="Test Co5",
            legal_name="Test5",
            inn="7700000005",
            timezone="Europe/Moscow",
            currency="RUB",
            is_active=True,
        )
        db_session.add(company)
        db_session.flush()

        vehicle = Vehicle(
            id_type="internal",
            id_value="EH-005",
            name="Test Grader",
            status="free",
            company_id=company.id,
            engine_hours=100.0,
            maintenance_interval=250,
        )
        db_session.add(vehicle)
        db_session.commit()
        db_session.refresh(vehicle)

        maintenance_service.update_vehicle_engine_hours(
            db=db_session,
            vehicle_id=vehicle.id,
            new_engine_hours=110.0,
            auto_check=False,
        )
        db_session.commit()

        today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        log = (
            db_session.query(EngineHoursLog)
            .filter(
                EngineHoursLog.vehicle_id == vehicle.id,
                EngineHoursLog.date == today,
            )
            .first()
        )

        assert log is not None
        assert float(log.hours) == 10.0
        assert float(log.work_hours) == 10.0


class TestGetUpcomingMaintenance:
    """Tests for maintenance_service.get_upcoming_maintenance."""

    def test_returns_vehicles_near_threshold(self, db_session: Session):
        """Возвращает технику, приближающуюся к ТО."""
        from app.services.maintenance_service import maintenance_service

        company = Company(
            name="Test Co6",
            legal_name="Test6",
            inn="7700000006",
            timezone="Europe/Moscow",
            currency="RUB",
            is_active=True,
        )
        db_session.add(company)
        db_session.flush()

        vehicle = Vehicle(
            id_type="internal",
            id_value="EH-006",
            name="Near TO Vehicle",
            status="free",
            company_id=company.id,
            engine_hours=230.0,
            maintenance_interval=250,
            next_maintenance_hours=250.0,
        )
        db_session.add(vehicle)
        db_session.commit()

        result = maintenance_service.get_upcoming_maintenance(
            db_session, company_id=company.id, hours_threshold=50
        )

        assert len(result) >= 1
        found = [v for v in result if v["vehicle_id"] == vehicle.id]
        assert len(found) == 1
        assert found[0]["hours_until_to"] == 20.0

    def test_excludes_overdue_vehicles(self, db_session: Session):
        """Не возвращает технику, которая уже просрочила ТО."""
        from app.services.maintenance_service import maintenance_service

        company = Company(
            name="Test Co7",
            legal_name="Test7",
            inn="7700000007",
            timezone="Europe/Moscow",
            currency="RUB",
            is_active=True,
        )
        db_session.add(company)
        db_session.flush()

        vehicle = Vehicle(
            id_type="internal",
            id_value="EH-007",
            name="Overdue Vehicle",
            status="free",
            company_id=company.id,
            engine_hours=300.0,
            maintenance_interval=250,
            next_maintenance_hours=250.0,
        )
        db_session.add(vehicle)
        db_session.commit()

        result = maintenance_service.get_upcoming_maintenance(
            db_session, company_id=company.id, hours_threshold=100
        )

        found = [v for v in result if v["vehicle_id"] == vehicle.id]
        assert len(found) == 0
