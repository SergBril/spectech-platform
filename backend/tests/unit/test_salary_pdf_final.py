"""Comprehensive tests for salary_pdf -> 100%."""

from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.salary_pdf import (
    SALARY_TYPE_LABELS,
    _get_font,
    generate_salary_payslip,
    generate_salary_register_pdf,
)


def _record(**kw):
    d = dict(
        id=1, employee_contractor_id=10,
        period_start=date(2026, 10, 1), period_end=date(2026, 10, 31),
        net_amount="50000.00", gross_amount="60000.00",
        deductions="10000.00", shifts_count=20,
        total_hours=160.0, total_km=1500.0,
        salary_type="fixed_shift", status="approved",
        created_at=datetime(2026, 10, 31, 18, 0),
        calculation_details=None,
    )
    d.update(kw)
    return SimpleNamespace(**d)


class TestGetFont:
    def test_returns_string(self):
        f = _get_font(bold=False)
        assert isinstance(f, str)
        fb = _get_font(bold=True)
        assert isinstance(fb, str)


class TestGenerateSalaryPayslip:
    def test_basic_pdf(self):
        rec = _record()
        pdf = generate_salary_payslip(rec, "Ivanov I.I.")
        assert isinstance(pdf, bytes)
        assert len(pdf) > 100
        assert pdf[:4] == b"%PDF"

    def test_no_employee_name(self):
        rec = _record()
        pdf = generate_salary_payslip(rec, "")
        assert isinstance(pdf, bytes)
        assert pdf[:4] == b"%PDF"

    def test_with_calculation_details(self):
        rec = _record(calculation_details={"formula": "shifts * rate"})
        pdf = generate_salary_payslip(rec, "Test")
        assert isinstance(pdf, bytes)
        assert pdf[:4] == b"%PDF"

    def test_with_empty_calculation_details(self):
        rec = _record(calculation_details={})
        pdf = generate_salary_payslip(rec, "Test")
        assert isinstance(pdf, bytes)

    def test_none_fields(self):
        rec = _record(
            net_amount=None, gross_amount=None, deductions=None,
            total_hours=None, total_km=None, created_at=None,
            salary_type="unknown_type",
        )
        pdf = generate_salary_payslip(rec, "Test")
        assert isinstance(pdf, bytes)

    def test_all_salary_types(self):
        for stype in SALARY_TYPE_LABELS:
            rec = _record(salary_type=stype)
            pdf = generate_salary_payslip(rec, "Test")
            assert isinstance(pdf, bytes)


class TestFontRegistrationPaths:
    """Cover module-level except/else blocks (lines 29-32)."""

    def test_font_registration_exception(self):
        """Simulate TTFont raising exception during registration."""
        import importlib
        from unittest.mock import patch, MagicMock
        with patch("app.services.salary_pdf.pdfmetrics.registerFont", side_effect=RuntimeError("font error")):
            with patch("app.services.salary_pdf._REGULAR_FONT") as rf:
                with patch("app.services.salary_pdf._BOLD_FONT") as bf:
                    rf.exists.return_value = True
                    bf.exists.return_value = True
                    import app.services.salary_pdf as mod
                    importlib.reload(mod)
                    assert mod._FONT_REGISTERED is False
        # Restore
        importlib.reload(mod)

    def test_font_files_not_found(self):
        """Simulate font files not existing by patching Path.exists."""
        import importlib
        from unittest.mock import patch
        import app.services.salary_pdf as mod
        orig_regular = mod._REGULAR_FONT
        orig_bold = mod._BOLD_FONT
        try:
            mod._REGULAR_FONT = MagicMock()
            mod._BOLD_FONT = MagicMock()
            mod._REGULAR_FONT.exists.return_value = False
            mod._BOLD_FONT.exists.return_value = False
            importlib.reload(mod)
            assert mod._FONT_REGISTERED is False
        finally:
            mod._REGULAR_FONT = orig_regular
            mod._BOLD_FONT = orig_bold
            importlib.reload(mod)


class TestFontFallback:
    def test_get_font_no_registered(self):
        import app.services.salary_pdf as mod
        original = mod._FONT_REGISTERED
        try:
            mod._FONT_REGISTERED = False
            assert _get_font(bold=False) == "Helvetica"
            assert _get_font(bold=True) == "Helvetica-Bold"
        finally:
            mod._FONT_REGISTERED = original

    def test_payslip_without_fonts(self):
        import app.services.salary_pdf as mod
        original = mod._FONT_REGISTERED
        try:
            mod._FONT_REGISTERED = False
            rec = _record()
            pdf = generate_salary_payslip(rec, "Test")
            assert isinstance(pdf, bytes)
            assert pdf[:4] == b"%PDF"
        finally:
            mod._FONT_REGISTERED = original

    def test_register_without_fonts(self):
        import app.services.salary_pdf as mod
        original = mod._FONT_REGISTERED
        try:
            mod._FONT_REGISTERED = False
            rec = _record()
            pdf = generate_salary_register_pdf([rec], "TestCo")
            assert isinstance(pdf, bytes)
            assert pdf[:4] == b"%PDF"
        finally:
            mod._FONT_REGISTERED = original


class TestGenerateSalaryRegisterPdf:
    def test_empty_records(self):
        pdf = generate_salary_register_pdf([], "TestCo")
        assert isinstance(pdf, bytes)
        assert pdf[:4] == b"%PDF"

    def test_single_record(self):
        rec = _record()
        pdf = generate_salary_register_pdf([rec], "TestCo")
        assert isinstance(pdf, bytes)
        assert pdf[:4] == b"%PDF"

    def test_multiple_records(self):
        records = [_record(id=i, employee_contractor_id=i) for i in range(1, 4)]
        pdf = generate_salary_register_pdf(records, "MultiCo")
        assert isinstance(pdf, bytes)
        assert pdf[:4] == b"%PDF"

    def test_various_statuses(self):
        records = [
            _record(id=1, status="draft"),
            _record(id=2, status="approved"),
            _record(id=3, status="paid"),
            _record(id=4, status="unknown"),
        ]
        pdf = generate_salary_register_pdf(records, "StatusCo")
        assert isinstance(pdf, bytes)

    def test_none_amounts(self):
        rec = _record(net_amount=None, gross_amount=None, deductions=None, total_hours=None)
        pdf = generate_salary_register_pdf([rec], "NoneCo")
        assert isinstance(pdf, bytes)
