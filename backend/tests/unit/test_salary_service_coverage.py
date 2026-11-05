"""Coverage tests for salary_service."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_db():
    db = MagicMock()
    return db


def _make_employee(salary_type="hourly", rate=500):
    return SimpleNamespace(
        contractor_id=1,
        salary_type=salary_type,
        salary_rate=rate,
        salary_rate_secondary=0,
        salary_commission_percent=10,
    )


class TestCalculateGross:
    """Cover _calculate_gross (lines 160-215)."""

    def test_fixed_shift(self):
        from app.services.salary_service import SalaryService

        emp = _make_employee("fixed_shift", 3000)
        shifts_data = {
            "shifts_count": 5,
            "total_hours": 40,
            "total_km": 0,
            "total_shift_cost": 0,
        }
        gross, details = SalaryService._calculate_gross(emp, shifts_data)
        assert gross == Decimal("15000.00")
        assert (
            "×" in details["formula"]
            or "x" in details["formula"].lower()
            or "смен" in details["formula"]
        )

    def test_hourly(self):
        from app.services.salary_service import SalaryService

        emp = _make_employee("hourly", 500)
        shifts_data = {
            "shifts_count": 3,
            "total_hours": 24,
            "total_km": 0,
            "total_shift_cost": 0,
        }
        gross, details = SalaryService._calculate_gross(emp, shifts_data)
        assert gross == Decimal("12000.00")

    def test_per_km(self):
        from app.services.salary_service import SalaryService

        emp = _make_employee("per_km", 15)
        shifts_data = {
            "shifts_count": 2,
            "total_hours": 16,
            "total_km": 800,
            "total_shift_cost": 0,
        }
        gross, details = SalaryService._calculate_gross(emp, shifts_data)
        assert gross == Decimal("12000.00")

    def test_shift_percent(self):
        from app.services.salary_service import SalaryService

        emp = _make_employee("shift_percent", 0)
        emp.salary_commission_percent = 10
        shifts_data = {
            "shifts_count": 2,
            "total_hours": 16,
            "total_km": 0,
            "total_shift_cost": 50000,
        }
        gross, details = SalaryService._calculate_gross(emp, shifts_data)
        assert gross == Decimal("5000.00")

    def test_combo(self):
        from app.services.salary_service import SalaryService

        emp = _make_employee("combo", 500)
        emp.salary_commission_percent = 10
        shifts_data = {
            "shifts_count": 2,
            "total_hours": 16,
            "total_km": 0,
            "total_shift_cost": 50000,
        }
        gross, details = SalaryService._calculate_gross(emp, shifts_data)
        # hourly_part = 500 * 16 = 8000, percent_part = 50000 * 10 / 100 = 5000
        assert gross == Decimal("13000.00")
        assert "hourly_part" in details
        assert "percent_part" in details

    def test_unknown_type_raises(self):
        from app.services.salary_service import SalaryService

        emp = _make_employee("unknown_type", 100)
        shifts_data = {
            "shifts_count": 0,
            "total_hours": 0,
            "total_km": 0,
            "total_shift_cost": 0,
        }
        with pytest.raises(ValueError, match="Unknown salary type"):
            SalaryService._calculate_gross(emp, shifts_data)


class TestGetShiftsData:
    """Cover _get_shifts_data (lines 101-158)."""

    def test_returns_dict(self, mock_db):
        from app.services.salary_service import SalaryService

        # Mock query chain for all_reports and filtered reports
        report = SimpleNamespace(
            id=1, operator_moto_hours=8.5, operator_odometer=120, shift_task_id=1
        )
        task = SimpleNamespace(shift_date=date(2026, 11, 3))

        q_all = MagicMock()
        q_all.filter.return_value.all.return_value = [report]

        q_filtered = MagicMock()
        q_filtered.join.return_value.filter.return_value.all.return_value = [report]

        call_count = {"n": 0}

        def mock_query(model):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return q_all
            return q_filtered

        mock_db.query.side_effect = mock_query
        mock_db.get.return_value = task

        result = SalaryService._get_shifts_data(
            mock_db, 1, date(2026, 11, 1), date(2026, 11, 30), 7
        )
        assert "shifts_count" in result
        assert "total_hours" in result
        assert "total_km" in result


class TestCalculateForEmployee:
    """Cover calculate_for_employee (lines 19-99)."""

    def test_no_salary_type_raises(self, mock_db):
        from app.services.salary_service import SalaryService

        emp = SimpleNamespace(contractor_id=1, salary_type=None)
        with pytest.raises(ValueError, match="salary_type"):
            SalaryService.calculate_for_employee(
                mock_db, emp, date(2026, 11, 1), date(2026, 11, 30), 7
            )

    def test_creates_new_record(self, mock_db):
        from app.services.salary_service import SalaryService

        emp = _make_employee("hourly", 500)

        # No existing record
        q_existing = MagicMock()
        q_existing.filter.return_value.order_by.return_value.first.return_value = None

        # Shifts data mock
        q_shifts_all = MagicMock()
        q_shifts_all.filter.return_value.all.return_value = []
        q_shifts_filtered = MagicMock()
        q_shifts_filtered.join.return_value.filter.return_value.all.return_value = []

        call_count = {"n": 0}

        def mock_query(model):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return q_existing
            elif call_count["n"] == 2:
                return q_shifts_all
            return q_shifts_filtered

        mock_db.query.side_effect = mock_query

        SimpleNamespace(id=1)
        mock_db.refresh.side_effect = lambda r: None

        # Capture the added record
        added = []
        mock_db.add.side_effect = lambda r: added.append(r)

        SalaryService.calculate_for_employee(
            mock_db, emp, date(2026, 11, 1), date(2026, 11, 30), 7, created_by=1
        )
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called()

    def test_updates_existing_record(self, mock_db):
        from app.services.salary_service import SalaryService

        emp = _make_employee("hourly", 500)

        existing = SimpleNamespace(id=42)

        q_existing = MagicMock()
        q_existing.filter.return_value.order_by.return_value.first.return_value = (
            existing
        )

        q_shifts_all = MagicMock()
        q_shifts_all.filter.return_value.all.return_value = []
        q_shifts_filtered = MagicMock()
        q_shifts_filtered.join.return_value.filter.return_value.all.return_value = []

        call_count = {"n": 0}

        def mock_query(model):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return q_existing
            elif call_count["n"] == 2:
                return q_shifts_all
            return q_shifts_filtered

        mock_db.query.side_effect = mock_query
        mock_db.refresh.side_effect = lambda r: None

        result = SalaryService.calculate_for_employee(
            mock_db, emp, date(2026, 11, 1), date(2026, 11, 30), 7
        )
        assert result.id == 42
        mock_db.commit.assert_called()


class TestCalculateBatch:
    """Cover calculate_batch (lines 217-255)."""

    def test_empty_employees(self, mock_db):
        from app.services.salary_service import SalaryService

        q = MagicMock()
        q.join.return_value.filter.return_value.all.return_value = []
        mock_db.query.return_value = q

        result = SalaryService.calculate_batch(
            mock_db, 7, date(2026, 11, 1), date(2026, 11, 30)
        )
        assert result == []

    def test_with_errors(self, mock_db):
        from app.services.salary_service import SalaryService

        emp = _make_employee("hourly", 500)
        q = MagicMock()
        q.join.return_value.filter.return_value.all.return_value = [emp]
        mock_db.query.return_value = q

        with patch.object(
            SalaryService,
            "calculate_for_employee",
            side_effect=ValueError("test error"),
        ):
            result = SalaryService.calculate_batch(
                mock_db, 7, date(2026, 11, 1), date(2026, 11, 30)
            )
        assert result == []

    def test_with_success_and_errors(self, mock_db):
        from app.services.salary_service import SalaryService

        emp1 = _make_employee("hourly", 500)
        emp2 = _make_employee("hourly", 500)
        q = MagicMock()
        q.join.return_value.filter.return_value.all.return_value = [emp1, emp2]
        mock_db.query.return_value = q

        fake_record = SimpleNamespace(id=1)
        call_count = {"n": 0}

        def side_effect(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return fake_record
            raise ValueError("fail")

        with patch.object(
            SalaryService, "calculate_for_employee", side_effect=side_effect
        ):
            result = SalaryService.calculate_batch(
                mock_db, 7, date(2026, 11, 1), date(2026, 11, 30)
            )
        assert len(result) == 1


class TestApproveRecord:
    """Cover approve_record (lines 257-end)."""

    def test_not_found_raises(self, mock_db):
        from app.services.salary_service import SalaryService

        mock_db.get.return_value = None
        with pytest.raises(ValueError, match="not found"):
            SalaryService.approve_record(mock_db, 999, 1)

    def test_wrong_status_raises(self, mock_db):
        from app.services.salary_service import SalaryService

        record = SimpleNamespace(status="approved")
        mock_db.get.return_value = record
        with pytest.raises(ValueError, match="Cannot approve"):
            SalaryService.approve_record(mock_db, 1, 1)

    def test_success(self, mock_db):
        from app.services.salary_service import SalaryService

        record = SimpleNamespace(status="draft")
        mock_db.get.return_value = record
        mock_db.refresh.side_effect = lambda r: None

        result = SalaryService.approve_record(mock_db, 1, 42)
        assert result.status == "approved"
        assert result.approved_by == 42
        mock_db.commit.assert_called_once()
