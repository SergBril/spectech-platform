"""Тесты driver_name в списке шаблонов смен (фикс F821 в shifts/templates.py).

Цепочка имени: ShiftTemplate.driver_id -> DriverProfile -> Employee -> Contractor.name.
"""

from datetime import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.catalog import Vehicle
from app.models.contractor import Contractor, DriverProfile, Employee
from app.models.shift import ShiftTemplate

pytestmark = [pytest.mark.integration]


class TestShiftTemplateDriverName:
    def test_template_without_driver_returns_empty_name(
        self,
        client: TestClient,
        auth_headers: dict,
        db_session: Session,
        sample_vehicle: Vehicle,
    ):
        """Шаблон без driver_id: driver_name == '' и эндпоинт не падает."""
        template = ShiftTemplate(
            vehicle_id=sample_vehicle.id,
            weekday=0,
            start_time=time(8, 0),
            end_time=time(17, 0),
        )
        db_session.add(template)
        db_session.commit()

        resp = client.get("/api/v1/shifts/templates", headers=auth_headers)
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 1
        assert items[0]["driver_id"] is None
        assert items[0]["driver_name"] == ""

    def test_template_with_driver_resolves_name(
        self,
        client: TestClient,
        auth_headers: dict,
        db_session: Session,
        sample_vehicle: Vehicle,
        company,
    ):
        """Шаблон с driver_id: имя резолвится через employee -> contractor."""
        contractor = Contractor(
            name="Иванов Иван Иванович",
            type="employee",
            company_id=company.id,
        )
        db_session.add(contractor)
        db_session.flush()

        employee = Employee(
            contractor_id=contractor.id,
            position="Водитель",
            role_in_system="driver",
        )
        db_session.add(employee)
        db_session.flush()

        driver = DriverProfile(employee_contractor_id=employee.contractor_id)
        db_session.add(driver)
        db_session.flush()

        template = ShiftTemplate(
            vehicle_id=sample_vehicle.id,
            driver_id=driver.employee_contractor_id,
            weekday=1,
            start_time=time(9, 0),
            end_time=time(18, 0),
        )
        db_session.add(template)
        db_session.commit()

        resp = client.get("/api/v1/shifts/templates", headers=auth_headers)
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 1
        assert items[0]["driver_id"] == driver.employee_contractor_id
        assert items[0]["driver_name"] == "Иванов Иван Иванович"
