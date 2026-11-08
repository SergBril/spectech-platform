"""Coverage tests for salary_export."""

from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import patch

import pytest


def _make_record(**kwargs):
    defaults = {
        "employee_contractor_id": 1,
        "period_start": date(2026, 11, 1),
        "period_end": date(2026, 11, 30),
        "salary_type": "fixed_shift",
        "shifts_count": 10,
        "total_hours": 80.0,
        "total_km": 500.0,
        "gross_amount": 100000.0,
        "deductions": 13000.0,
        "net_amount": 87000.0,
        "status": "approved",
        "created_at": datetime(2026, 11, 30, 12, 0),
        "calculation_details": {"formula": "10 * 10000"},
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


class TestExportSalariesToExcel:
    """Cover export_salaries_to_excel (lines 17-139)."""

    def test_basic_export(self):
        from app.services.salary_export import export_salaries_to_excel

        records = [_make_record()]
        result = export_salaries_to_excel(records, {1: "Ivanov"})
        assert isinstance(result, bytes)
        assert len(result) > 0
        # Verify it's valid xlsx
        assert result[:2] == b"PK"  # ZIP/XLSX magic bytes

    def test_multiple_records(self):
        from app.services.salary_export import export_salaries_to_excel

        records = [
            _make_record(employee_contractor_id=1),
            _make_record(employee_contractor_id=2, salary_type="hourly", status="paid"),
            _make_record(
                employee_contractor_id=3, salary_type="per_km", status="draft"
            ),
        ]
        names = {1: "Ivanov", 2: "Petrov", 3: "Sidorov"}
        result = export_salaries_to_excel(records, names)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_no_employee_names(self):
        from app.services.salary_export import export_salaries_to_excel

        records = [_make_record()]
        result = export_salaries_to_excel(records, None)
        assert isinstance(result, bytes)

    def test_missing_name_in_dict(self):
        from app.services.salary_export import export_salaries_to_excel

        records = [_make_record(employee_contractor_id=99)]
        result = export_salaries_to_excel(records, {1: "Ivanov"})
        assert isinstance(result, bytes)

    def test_none_dates(self):
        from app.services.salary_export import export_salaries_to_excel

        records = [_make_record(period_start=None, period_end=None, created_at=None)]
        result = export_salaries_to_excel(records)
        assert isinstance(result, bytes)

    def test_none_amounts(self):
        from app.services.salary_export import export_salaries_to_excel

        records = [
            _make_record(
                total_hours=None,
                total_km=None,
                gross_amount=None,
                deductions=None,
                net_amount=None,
            )
        ]
        result = export_salaries_to_excel(records)
        assert isinstance(result, bytes)

    def test_unknown_salary_type(self):
        from app.services.salary_export import export_salaries_to_excel

        records = [_make_record(salary_type="custom_type")]
        result = export_salaries_to_excel(records)
        assert isinstance(result, bytes)

    def test_unknown_status(self):
        from app.services.salary_export import export_salaries_to_excel

        records = [_make_record(status="unknown_status")]
        result = export_salaries_to_excel(records)
        assert isinstance(result, bytes)

    def test_no_calculation_details(self):
        from app.services.salary_export import export_salaries_to_excel

        records = [_make_record(calculation_details=None)]
        result = export_salaries_to_excel(records)
        assert isinstance(result, bytes)

    def test_calculation_details_not_dict(self):
        from app.services.salary_export import export_salaries_to_excel

        records = [_make_record(calculation_details="not a dict")]
        result = export_salaries_to_excel(records)
        assert isinstance(result, bytes)

    def test_empty_records(self):
        from app.services.salary_export import export_salaries_to_excel

        result = export_salaries_to_excel([])
        assert isinstance(result, bytes)

    def test_openpyxl_import_error(self):
        from app.services.salary_export import export_salaries_to_excel

        with patch.dict("sys.modules", {"openpyxl": None}):
            with pytest.raises(ImportError, match="openpyxl"):
                export_salaries_to_excel([_make_record()])


class TestSalaryTypeLabels:
    """Cover SALARY_TYPE_LABELS constant."""

    def test_labels_exist(self):
        from app.services.salary_export import SALARY_TYPE_LABELS

        assert "fixed_shift" in SALARY_TYPE_LABELS
        assert "hourly" in SALARY_TYPE_LABELS
        assert "combo" in SALARY_TYPE_LABELS
