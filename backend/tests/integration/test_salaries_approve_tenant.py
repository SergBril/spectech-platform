"""Кросс-тенант гейт POST /api/v1/salaries/{id}/approve.

Две реальные компании: чужая запись → 404 (без утечки существования),
свой draft → 200 (positive-control). После отказа — DB-facts: статус,
approved_at и approved_by не изменились.
"""

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.models.auth import User
from app.models.company import Company
from app.models.contractor import Contractor, Employee
from app.models.salary import SalaryRecord
from app.services.auth_service import create_access_token

pytestmark = [pytest.mark.integration]


def _make_salary_record(db_session, company) -> SalaryRecord:
    contractor = Contractor(
        name="Approve Tenant Employee",
        inn="7799999998",
        kpp="779901002",
        type="employee",
        company_id=company.id,
        is_active=True,
    )
    db_session.add(contractor)
    db_session.flush()

    employee = Employee(
        contractor_id=contractor.id,
        position="Driver",
        hire_date=date(2025, 1, 1),
        salary_type="hourly",
        salary_rate=Decimal("500"),
    )
    db_session.add(employee)
    db_session.flush()

    record = SalaryRecord(
        company_id=company.id,
        employee_contractor_id=employee.contractor_id,
        period_start=date(2025, 12, 1),
        period_end=date(2025, 12, 31),
        salary_type="hourly",
        status="draft",
    )
    db_session.add(record)
    db_session.commit()
    db_session.refresh(record)
    return record


@pytest.fixture
def company_b(db_session):
    c = Company(
        name="Other Company",
        legal_name="Other Company LLC",
        inn="7800000000",
        kpp="780001001",
    )
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    return c


@pytest.fixture
def admin_b_headers(db_session, company_b):
    user = User(
        email="admin-b@test.com",
        full_name="Admin B",
        password_hash="admin_b_hashed_password_12345",
        is_superuser=True,
        status="active",
        company_id=company_b.id,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    token = create_access_token(user=user)
    return {"Authorization": f"Bearer {token}"}


class TestSalariesApproveTenant:
    def test_foreign_record_returns_404(
        self, client: TestClient, db_session, company, admin_b_headers
    ):
        record = _make_salary_record(db_session, company)

        resp = client.post(
            f"/api/v1/salaries/{record.id}/approve", headers=admin_b_headers
        )
        assert resp.status_code == 404

        # DB-facts: отказ не изменил запись
        db_session.expire_all()
        fresh = db_session.get(SalaryRecord, record.id)
        assert fresh.status == "draft"
        assert fresh.approved_at is None
        assert fresh.approved_by is None

    def test_own_record_returns_200(
        self, client: TestClient, db_session, company, auth_headers
    ):
        record = _make_salary_record(db_session, company)

        resp = client.post(
            f"/api/v1/salaries/{record.id}/approve", headers=auth_headers
        )
        assert resp.status_code == 200

        db_session.expire_all()
        fresh = db_session.get(SalaryRecord, record.id)
        assert fresh.status == "approved"
        assert fresh.approved_at is not None
