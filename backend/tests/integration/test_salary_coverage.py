"""Tests for salary_service coverage improvement."""

import pytest
from decimal import Decimal
from datetime import date, datetime, timezone
from types import SimpleNamespace


class TestCalculateGross:
    """Cover _calculate_gross pure function (lines 160-214)."""

    def _make_employee(self, salary_type, rate=Decimal("1000"), commission=None):
        return SimpleNamespace(
            salary_type=salary_type,
            salary_rate=rate,
            salary_rate_secondary=Decimal("0"),
            salary_commission_percent=commission or Decimal("0"),
        )

    def test_fixed_shift(self):
        from app.services.salary_service import SalaryService
        emp = self._make_employee("fixed_shift", Decimal("5000"))
        shifts_data = {"shifts_count": 10, "total_hours": 80, "total_km": 0}
        gross, details = SalaryService._calculate_gross(emp, shifts_data)
        assert gross == Decimal("50000")
        assert details["formula"] is not None

    def test_hourly(self):
        from app.services.salary_service import SalaryService
        emp = self._make_employee("hourly", Decimal("500"))
        shifts_data = {"shifts_count": 5, "total_hours": 40, "total_km": 0}
        gross, details = SalaryService._calculate_gross(emp, shifts_data)
        assert gross == Decimal("20000")

    def test_per_km(self):
        from app.services.salary_service import SalaryService
        emp = self._make_employee("per_km", Decimal("15"))
        shifts_data = {"shifts_count": 3, "total_hours": 24, "total_km": 1500}
        gross, details = SalaryService._calculate_gross(emp, shifts_data)
        assert gross == Decimal("22500")

    def test_shift_percent(self):
        from app.services.salary_service import SalaryService
        emp = self._make_employee("shift_percent", Decimal("0"), Decimal("10"))
        shifts_data = {
            "shifts_count": 5, "total_hours": 40, "total_km": 0,
            "total_shift_cost": 100000,
        }
        gross, details = SalaryService._calculate_gross(emp, shifts_data)
        assert gross == Decimal("10000")  # 10% of 100000

    def test_combo(self):
        from app.services.salary_service import SalaryService
        emp = self._make_employee("combo", Decimal("500"), Decimal("5"))
        shifts_data = {
            "shifts_count": 5, "total_hours": 40, "total_km": 0,
            "total_shift_cost": 100000,
        }
        gross, details = SalaryService._calculate_gross(emp, shifts_data)
        # hourly_part = 500 * 40 = 20000
        # percent_part = 100000 * 5 / 100 = 5000
        assert gross == Decimal("25000")

    def test_unknown_type_raises(self):
        from app.services.salary_service import SalaryService
        emp = self._make_employee("unknown_type")
        shifts_data = {"shifts_count": 0, "total_hours": 0, "total_km": 0}
        with pytest.raises(ValueError, match="Unknown salary type"):
            SalaryService._calculate_gross(emp, shifts_data)


def _create_employee(db_session, company, salary_type="hourly", rate=Decimal("500")):
    """Helper to create Contractor + Employee for salary tests."""
    from app.models.contractor import Contractor, Employee

    contractor = Contractor(
        name=f"Salary Test Employee {salary_type}",
        inn="7799999999",
        kpp="779901001",
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
        salary_type=salary_type,
        salary_rate=rate,
        salary_commission_percent=Decimal("10") if salary_type in ("shift_percent", "combo") else None,
    )
    db_session.add(employee)
    db_session.commit()
    db_session.refresh(employee)
    return employee


class TestCalculateForEmployee:
    """Cover calculate_for_employee (lines 19-98)."""

    def test_no_salary_type_raises(self, db_session, company):
        from app.services.salary_service import SalaryService
        emp = _create_employee(db_session, company, salary_type=None)
        emp.salary_type = None
        db_session.commit()
        with pytest.raises(ValueError, match="salary_type"):
            SalaryService.calculate_for_employee(
                db_session, emp, date(2025, 1, 1), date(2025, 1, 31), company.id
            )

    def test_creates_new_record(self, db_session, company):
        from app.services.salary_service import SalaryService
        emp = _create_employee(db_session, company, "hourly", Decimal("500"))
        record = SalaryService.calculate_for_employee(
            db_session, emp, date(2025, 1, 1), date(2025, 1, 31), company.id
        )
        assert record.id is not None
        assert record.gross_amount >= 0
        assert record.status == "draft"

    def test_updates_existing_record(self, db_session, company):
        from app.services.salary_service import SalaryService
        emp = _create_employee(db_session, company, "fixed_shift", Decimal("5000"))
        r1 = SalaryService.calculate_for_employee(
            db_session, emp, date(2025, 1, 1), date(2025, 1, 31), company.id
        )
        r2 = SalaryService.calculate_for_employee(
            db_session, emp, date(2025, 1, 1), date(2025, 1, 31), company.id
        )
        assert r1.id == r2.id  # Same record updated


class TestApproveRecord:
    """Cover approve_record (lines 257-270)."""

    def test_approve_draft(self, db_session, company):
        from app.services.salary_service import SalaryService
        emp = _create_employee(db_session, company, "hourly")
        record = SalaryService.calculate_for_employee(
            db_session, emp, date(2025, 1, 1), date(2025, 1, 31), company.id
        )
        approved = SalaryService.approve_record(db_session, record.id, 1)
        assert approved.status == "approved"
        assert approved.approved_by == 1

    def test_approve_nonexistent_raises(self, db_session):
        from app.services.salary_service import SalaryService
        with pytest.raises(ValueError, match="not found"):
            SalaryService.approve_record(db_session, 99999, 1)

    def test_approve_non_draft_raises(self, db_session, company):
        from app.services.salary_service import SalaryService
        emp = _create_employee(db_session, company, "hourly")
        record = SalaryService.calculate_for_employee(
            db_session, emp, date(2025, 1, 1), date(2025, 1, 31), company.id
        )
        SalaryService.approve_record(db_session, record.id, 1)
        with pytest.raises(ValueError, match="Cannot approve"):
            SalaryService.approve_record(db_session, record.id, 1)


class TestCalculateBatch:
    """Cover calculate_batch (lines 217-254)."""

    def test_batch_empty(self, db_session, company):
        from app.services.salary_service import SalaryService
        records = SalaryService.calculate_batch(
            db_session, company.id, date(2025, 1, 1), date(2025, 1, 31)
        )
        assert isinstance(records, list)

    def test_batch_with_employees(self, db_session, company):
        from app.services.salary_service import SalaryService
        _create_employee(db_session, company, "hourly", Decimal("500"))
        _create_employee(db_session, company, "fixed_shift", Decimal("5000"))
        records = SalaryService.calculate_batch(
            db_session, company.id, date(2025, 1, 1), date(2025, 1, 31)
        )
        assert len(records) >= 2
