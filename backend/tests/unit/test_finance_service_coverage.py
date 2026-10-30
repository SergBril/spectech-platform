"""Tests for finance_service.py (coverage boost)."""
import pytest
from decimal import Decimal
from datetime import date


class TestFinanceServicePure:
    """Unit tests for pure functions (no DB needed)."""

    def test_calculate_payout_normal(self):
        from app.services.finance_service import calculate_payout
        result = calculate_payout(Decimal("100000"), Decimal("15"))
        assert result["gross_amount"] == Decimal("100000")
        assert result["commission_rate"] == Decimal("15")
        assert "net_amount" in result
        assert "platform_commission" in result

    def test_calculate_payout_zero_commission(self):
        from app.services.finance_service import calculate_payout
        result = calculate_payout(Decimal("50000"), Decimal("0"))
        assert result["net_amount"] == Decimal("50000")
        assert result["platform_commission"] == Decimal("0")

    def test_calculate_payout_full_commission(self):
        from app.services.finance_service import calculate_payout
        result = calculate_payout(Decimal("10000"), Decimal("100"))
        assert result["net_amount"] == Decimal("0")

    def test_calculate_invoice_totals(self, db_session, sample_invoice):
        from app.services.finance_service import calculate_invoice_totals
        calculate_invoice_totals(sample_invoice)
        # Should not raise, totals already set by fixture

    def test_generate_document_number(self, db_session):
        from app.services.finance_service import generate_document_number
        num = generate_document_number(db_session, "INV")
        assert num.startswith("INV")
        assert len(num) > 3


class TestFinanceServiceDB:
    """Integration tests for DB-dependent functions."""

    def test_get_finance_dashboard(self, db_session, company, sample_vehicle):
        from app.services.finance_service import get_finance_dashboard
        result = get_finance_dashboard(db_session, company.id)
        assert isinstance(result, dict)

    def test_get_finance_dashboard_no_company(self, db_session):
        from app.services.finance_service import get_finance_dashboard
        result = get_finance_dashboard(db_session, None)
        assert isinstance(result, dict)

    def test_create_invoice(self, db_session, company, sample_user, sample_contractor):
        from app.services.finance_service import create_invoice
        from types import SimpleNamespace
        payload = SimpleNamespace(
            client_id=sample_contractor.id,
            items=[],
            subtotal=Decimal("10000"),
            vat_rate=Decimal("20"),
            invoice_date=date.today(),
            due_date=date.today(),
        )
        invoice = create_invoice(db_session, payload, sample_user)
        assert invoice is not None
        assert invoice.company_id == company.id

    def test_generate_act_pdf_not_found(self, db_session):
        from app.services.finance_service import generate_and_save_act_pdf
        result = generate_and_save_act_pdf(99999, db_session)
        assert result is None

    def test_generate_invoice_pdf_not_found(self, db_session):
        from app.services.finance_service import generate_and_save_invoice_pdf
        result = generate_and_save_invoice_pdf(99999, db_session)
        assert result is None
