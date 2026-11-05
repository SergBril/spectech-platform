"""Tests for SalaryService."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_db():
    return MagicMock()


class TestCalculateForEmployee:
    """Cover calculate_for_employee (lines 19-100)."""

    def test_no_salary_type_raises(self, mock_db):
        from app.services.salary_service import SalaryService

        employee = SimpleNamespace(contractor_id=1, salary_type=None)

        with pytest.raises(ValueError, match="salary_type"):
            SalaryService.calculate_for_employee(
                mock_db, employee, date(2026, 11, 1), date(2026, 11, 30), 1
            )

    def test_existing_record_updates(self, mock_db):
        from app.services.salary_service import SalaryService

        employee = SimpleNamespace(
            contractor_id=1,
            salary_type="hourly",
            salary_rate=500,
            salary_rate_secondary=0,
            salary_commission_percent=0,
        )
        existing = SimpleNamespace(
            id=10,
            period_start=None,
            period_end=None,
            shifts_count=None,
            total_hours=None,
            total_km=None,
            gross_amount=None,
            net_amount=None,
            calculation_details=None,
        )

        mock_query = MagicMock()
        mock_query.filter.return_value.order_by.return_value.first.return_value = (
            existing
        )
        mock_db.query.return_value = mock_query

        with (
            patch.object(
                SalaryService,
                "_get_shifts_data",
                return_value={
                    "shifts_count": 5,
                    "total_hours": 40.0,
                    "total_km": 0,
                    "total_shift_cost": 0,
                },
            ),
            patch.object(
                SalaryService,
                "_calculate_gross",
                return_value=(Decimal("20000"), {"gross": 20000}),
            ),
        ):

            SalaryService.calculate_for_employee(
                mock_db, employee, date(2026, 11, 1), date(2026, 11, 30), 1
            )

        assert result == existing
        mock_db.commit.assert_called()

    def test_new_record_creates(self, mock_db):
        from app.services.salary_service import SalaryService

        employee = SimpleNamespace(
            contractor_id=1,
            salary_type="fixed_shift",
            salary_rate=3000,
            salary_rate_secondary=0,
            salary_commission_percent=0,
        )

        mock_query = MagicMock()
        mock_query.filter.return_value.order_by.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        with (
            patch.object(
                SalaryService,
                "_get_shifts_data",
                return_value={
                    "shifts_count": 10,
                    "total_hours": 80.0,
                    "total_km": 0,
                    "total_shift_cost": 0,
                },
            ),
            patch.object(
                SalaryService,
                "_calculate_gross",
                return_value=(Decimal("30000"), {"gross": 30000}),
            ),
        ):

            SalaryService.calculate_for_employee(
                mock_db,
                employee,
                date(2026, 11, 1),
                date(2026, 11, 30),
                1,
                created_by=5,
            )

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called()


class TestGetShiftsData:
    """Cover _get_shifts_data (lines 101-159)."""

    def test_returns_aggregated_data(self, mock_db):
        from app.services.salary_service import SalaryService

        report1 = SimpleNamespace(
            id=1, operator_moto_hours=8.5, operator_odometer=120, shift_task_id=1
        )
        report2 = SimpleNamespace(
            id=2, operator_moto_hours=7.0, operator_odometer=None, shift_task_id=2
        )
        task = SimpleNamespace(shift_date=date(2026, 11, 5))

        call_count = {"n": 0}

        def mock_query(model):
            call_count["n"] += 1
            mq = MagicMock()
            if call_count["n"] == 1:
                # all_reports (no join)
                mq.filter.return_value.all.return_value = [report1, report2]
            else:
                # filtered reports (with join)
                mq.join.return_value.filter.return_value.all.return_value = [
                    report1,
                    report2,
                ]
            return mq

        mock_db.query.side_effect = mock_query
        mock_db.get.return_value = task

        SalaryService._get_shifts_data(
            mock_db, 1, date(2026, 11, 1), date(2026, 11, 30), 1
        )

        assert result["shifts_count"] == 2
        assert result["total_hours"] == 15.5
        assert result["total_km"] == 120.0


class TestCalculateGross:
    """Cover _calculate_gross (lines 160-216)."""

    def test_fixed_shift(self):
        from app.services.salary_service import SalaryService

        employee = SimpleNamespace(
            salary_type="fixed_shift",
            salary_rate=3000,
            salary_rate_secondary=0,
            salary_commission_percent=0,
        )
        shifts_data = {
            "shifts_count": 10,
            "total_hours": 80,
            "total_km": 0,
            "total_shift_cost": 0,
        }

        gross, details = SalaryService._calculate_gross(employee, shifts_data)
        assert gross == Decimal("30000.00")
        assert "×" in details["formula"] or "СЃРјРµРЅ" in details["formula"]

    def test_hourly(self):
        from app.services.salary_service import SalaryService

        employee = SimpleNamespace(
            salary_type="hourly",
            salary_rate=500,
            salary_rate_secondary=0,
            salary_commission_percent=0,
        )
        shifts_data = {
            "shifts_count": 5,
            "total_hours": 40,
            "total_km": 0,
            "total_shift_cost": 0,
        }

        gross, details = SalaryService._calculate_gross(employee, shifts_data)
        assert gross == Decimal("20000.00")

    def test_per_km(self):
        from app.services.salary_service import SalaryService

        employee = SimpleNamespace(
            salary_type="per_km",
            salary_rate=15,
            salary_rate_secondary=0,
            salary_commission_percent=0,
        )
        shifts_data = {
            "shifts_count": 5,
            "total_hours": 40,
            "total_km": 500,
            "total_shift_cost": 0,
        }

        gross, details = SalaryService._calculate_gross(employee, shifts_data)
        assert gross == Decimal("7500.00")

    def test_shift_percent(self):
        from app.services.salary_service import SalaryService

        employee = SimpleNamespace(
            salary_type="shift_percent",
            salary_rate=0,
            salary_rate_secondary=0,
            salary_commission_percent=10,
        )
        shifts_data = {
            "shifts_count": 5,
            "total_hours": 40,
            "total_km": 0,
            "total_shift_cost": 100000,
        }

        gross, details = SalaryService._calculate_gross(employee, shifts_data)
        assert gross == Decimal("10000.00")

    def test_combo(self):
        from app.services.salary_service import SalaryService

        employee = SimpleNamespace(
            salary_type="combo",
            salary_rate=400,
            salary_rate_secondary=0,
            salary_commission_percent=5,
        )
        shifts_data = {
            "shifts_count": 5,
            "total_hours": 40,
            "total_km": 0,
            "total_shift_cost": 100000,
        }

        gross, details = SalaryService._calculate_gross(employee, shifts_data)
        # 400*40 + 5%*100000 = 16000 + 5000 = 21000
        assert gross == Decimal("21000.00")

    def test_unknown_type_raises(self):
        from app.services.salary_service import SalaryService

        employee = SimpleNamespace(
            salary_type="unknown",
            salary_rate=0,
            salary_rate_secondary=0,
            salary_commission_percent=0,
        )
        shifts_data = {
            "shifts_count": 0,
            "total_hours": 0,
            "total_km": 0,
            "total_shift_cost": 0,
        }

        with pytest.raises(ValueError, match="Unknown salary type"):
            SalaryService._calculate_gross(employee, shifts_data)


class TestCalculateBatch:
    """Cover calculate_batch (lines 217-256)."""

    def test_batch_success(self, mock_db):
        from app.services.salary_service import SalaryService

        emp = SimpleNamespace(contractor_id=1, salary_type="hourly")
        record = SimpleNamespace(id=1)

        mock_query = MagicMock()
        mock_query.join.return_value.filter.return_value.all.return_value = [emp]
        mock_db.query.return_value = mock_query

        with patch.object(SalaryService, "calculate_for_employee", return_value=record):
            SalaryService.calculate_batch(
                mock_db, 1, date(2026, 11, 1), date(2026, 11, 30)
            )

        assert len(result) == 1

    def test_batch_with_errors(self, mock_db):
        from app.services.salary_service import SalaryService

        emp = SimpleNamespace(contractor_id=1, salary_type="hourly")

        mock_query = MagicMock()
        mock_query.join.return_value.filter.return_value.all.return_value = [emp]
        mock_db.query.return_value = mock_query

        with patch.object(
            SalaryService, "calculate_for_employee", side_effect=ValueError("fail")
        ):
            SalaryService.calculate_batch(
                mock_db, 1, date(2026, 11, 1), date(2026, 11, 30)
            )

        assert len(result) == 0


class TestApproveRecord:
    """Cover approve_record (lines 257-end)."""

    def test_approve_success(self, mock_db):
        from app.models.salary import SalaryStatus
        from app.services.salary_service import SalaryService

        record = SimpleNamespace(
            id=1, status=SalaryStatus.draft.value, approved_at=None, approved_by=None
        )
        mock_db.get.return_value = record

        SalaryService.approve_record(mock_db, 1, approved_by=5)

        assert result.status == SalaryStatus.approved.value
        assert result.approved_by == 5
        mock_db.commit.assert_called_once()

    def test_not_found_raises(self, mock_db):
        from app.services.salary_service import SalaryService

        mock_db.get.return_value = None

        with pytest.raises(ValueError, match="not found"):
            SalaryService.approve_record(mock_db, 999, approved_by=5)

    def test_non_draft_raises(self, mock_db):
        from app.models.salary import SalaryStatus
        from app.services.salary_service import SalaryService

        record = SimpleNamespace(id=1, status=SalaryStatus.approved.value)
        mock_db.get.return_value = record

        with pytest.raises(ValueError, match="Cannot approve"):
            SalaryService.approve_record(mock_db, 1, approved_by=5)
