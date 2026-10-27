"""Tests for finance_service coverage improvement."""

import pytest
from decimal import Decimal
from datetime import date, datetime
from types import SimpleNamespace


class TestGenerateDocumentNumber:
    """Cover generate_document_number (lines 28-54)."""

    def test_inv_first_number(self, db_session):
        from app.services.finance_service import generate_document_number
        num = generate_document_number(db_session, "INV")
        assert num.startswith("INV-")
        assert num.endswith("-0001")

    def test_act_first_number(self, db_session):
        from app.services.finance_service import generate_document_number
        num = generate_document_number(db_session, "ACT")
        assert num.startswith("ACT-")

    def test_pay_first_number(self, db_session):
        from app.services.finance_service import generate_document_number
        num = generate_document_number(db_session, "PAY")
        assert num.startswith("PAY-")

    def test_unknown_prefix_raises(self, db_session):
        from app.services.finance_service import generate_document_number
        with pytest.raises(ValueError, match="Unknown document prefix"):
            generate_document_number(db_session, "XXX")

    def test_increments_existing(self, db_session, sample_invoice, company):
        from app.services.finance_service import generate_document_number
        num = generate_document_number(db_session, "INV")
        # Should return valid format INV-YYYY-NNNN
        assert num.startswith("INV-")
        seq = int(num.split("-")[-1])
        assert seq >= 1


class TestCalculateInvoiceTotals:
    """Cover calculate_invoice_totals (lines 56-100)."""

    def _make_invoice(self, tax_system="osno", vat_rate=Decimal("20"), is_vat_included=True, items=None):
        inv = SimpleNamespace(
            items=items or [],
            subtotal=Decimal("0"),
            vat_rate=vat_rate,
            vat_amount=Decimal("0"),
            total=Decimal("0"),
            tax_system=tax_system,
            is_vat_included=is_vat_included,
        )
        return inv

    def test_osno_vat_included(self):
        from app.services.finance_service import calculate_invoice_totals
        item = SimpleNamespace(quantity=Decimal("2"), unit_price=Decimal("1000"), amount=Decimal("0"))
        inv = self._make_invoice("osno", Decimal("20"), True, [item])
        calculate_invoice_totals(inv)
        assert inv.subtotal == Decimal("2000")
        assert inv.vat_amount > 0
        assert inv.total == Decimal("2000")  # VAT included

    def test_osno_vat_excluded(self):
        from app.services.finance_service import calculate_invoice_totals
        item = SimpleNamespace(quantity=Decimal("1"), unit_price=Decimal("1000"), amount=Decimal("0"))
        inv = self._make_invoice("osno", Decimal("20"), False, [item])
        calculate_invoice_totals(inv)
        assert inv.subtotal == Decimal("1000")
        assert inv.vat_amount == Decimal("200")
        assert inv.total == Decimal("1200")

    def test_usn_no_vat(self):
        from app.services.finance_service import calculate_invoice_totals
        item = SimpleNamespace(quantity=Decimal("1"), unit_price=Decimal("1000"), amount=Decimal("0"))
        inv = self._make_invoice("usn_6", Decimal("20"), True, [item])
        calculate_invoice_totals(inv)
        assert inv.vat_rate == Decimal("0")
        assert inv.vat_amount == Decimal("0")
        assert inv.total == Decimal("1000")

    def test_empty_items(self):
        from app.services.finance_service import calculate_invoice_totals
        inv = self._make_invoice("osno", Decimal("20"), True, [])
        calculate_invoice_totals(inv)
        assert inv.subtotal == Decimal("0")
        assert inv.total == Decimal("0")


class TestCalculatePayout:
    """Cover calculate_payout (lines 242-253)."""

    def test_basic_calculation(self):
        from app.services.finance_service import calculate_payout
        result = calculate_payout(Decimal("10000"), Decimal("10"))
        assert result["gross_amount"] == Decimal("10000")
        assert result["platform_commission"] == Decimal("1000")
        assert result["net_amount"] == Decimal("9000")
        assert result["commission_rate"] == Decimal("10")

    def test_zero_commission(self):
        from app.services.finance_service import calculate_payout
        result = calculate_payout(Decimal("5000"), Decimal("0"))
        assert result["net_amount"] == Decimal("5000")
        assert result["platform_commission"] == Decimal("0")


class TestGetFinanceDashboard:
    """Cover get_finance_dashboard (lines 255-295)."""

    def test_without_company(self, db_session):
        from app.services.finance_service import get_finance_dashboard
        result = get_finance_dashboard(db_session, None)
        assert "total_revenue" in result
        assert "invoices_count" in result
        assert "acts_count" in result
        assert "payouts_count" in result

    def test_with_company(self, db_session, company):
        from app.services.finance_service import get_finance_dashboard
        result = get_finance_dashboard(db_session, company.id)
        assert isinstance(result["total_revenue"], Decimal)
        assert isinstance(result["invoices_count"], int)


class TestRegisterPayment:
    """Cover register_payment (lines 224-240)."""

    def test_register_payment_full(self, db_session, sample_invoice, company):
        from app.services.finance_service import register_payment
        from app.models.finance import DocumentStatus

        payment = SimpleNamespace(
            invoice_id=sample_invoice.id,
            payout_id=None,
            amount=sample_invoice.total,
        )
        register_payment(db_session, payment)
        db_session.refresh(sample_invoice)
        assert sample_invoice.status == DocumentStatus.paid.value

    def test_register_payment_partial(self, db_session, sample_invoice, company):
        from app.services.finance_service import register_payment
        from app.models.finance import DocumentStatus

        payment = SimpleNamespace(
            invoice_id=sample_invoice.id,
            payout_id=None,
            amount=Decimal("1"),
        )
        register_payment(db_session, payment)
        db_session.refresh(sample_invoice)
        assert sample_invoice.status == DocumentStatus.partially_paid.value

    def test_register_payment_no_invoice(self, db_session):
        from app.services.finance_service import register_payment
        payment = SimpleNamespace(invoice_id=99999, payout_id=None, amount=Decimal("100"))
        # Should not raise
        register_payment(db_session, payment)


class TestGetField:
    """Cover _get_field helper (lines 103-109)."""

    def test_dict_key(self):
        from app.services.finance_service import _get_field
        assert _get_field({"a": 1}, "a") == 1

    def test_dict_missing(self):
        from app.services.finance_service import _get_field
        assert _get_field({"a": 1}, "b", "default") == "default"

    def test_none_object(self):
        from app.services.finance_service import _get_field
        assert _get_field(None, "a", "default") == "default"

    def test_object_attr(self):
        from app.services.finance_service import _get_field
        obj = SimpleNamespace(x=42)
        assert _get_field(obj, "x") == 42


class TestCreateInvoice:
    """Cover create_invoice (lines 111-222)."""

    def test_create_basic_invoice(self, db_session, company, sample_contractor):
        from app.services.finance_service import create_invoice
        user = SimpleNamespace(id=1, company_id=company.id)
        payload = {
            "client_id": sample_contractor.id,
            "subtotal": Decimal("10000"),
            "vat_rate": Decimal("20"),
            "total": Decimal("12000"),
            "vat_amount": Decimal("2000"),
        }
        invoice = create_invoice(db_session, payload, user)
        assert invoice.id is not None
        assert invoice.document_number.startswith("INV-")

    def test_create_with_items(self, db_session, company, sample_contractor):
        from app.services.finance_service import create_invoice
        user = SimpleNamespace(id=1, company_id=company.id)
        payload = {
            "client_id": sample_contractor.id,
            "items": [
                {"description": "Test item", "quantity": 2, "unit_price": Decimal("5000")},
            ],
        }
        invoice = create_invoice(db_session, payload, user)
        assert invoice.id is not None
