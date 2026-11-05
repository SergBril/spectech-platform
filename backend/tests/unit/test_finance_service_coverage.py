"""Coverage tests for finance_service."""

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.commit = MagicMock()
    db.rollback = MagicMock()
    db.flush = MagicMock()
    db.add = MagicMock()
    db.refresh = MagicMock()
    return db


class TestGenerateDocumentNumber:
    """Cover generate_document_number (lines 28-54)."""

    def test_first_number(self, mock_db):
        from app.services.finance_service import generate_document_number

        mock_db.scalar.return_value = None
        result = generate_document_number(mock_db, "INV")
        assert result.startswith("INV-")
        assert result.endswith("-0001")

    def test_increment(self, mock_db):
        from app.services.finance_service import generate_document_number

        mock_db.scalar.return_value = "INV-2026-0042"
        result = generate_document_number(mock_db, "INV")
        assert result.endswith("-0043")

    def test_invalid_prefix(self, mock_db):
        from app.services.finance_service import generate_document_number

        with pytest.raises(ValueError, match="Unknown document prefix"):
            generate_document_number(mock_db, "XXX")

    def test_malformed_last_number(self, mock_db):
        from app.services.finance_service import generate_document_number

        mock_db.scalar.return_value = "INV-2026-bad"
        result = generate_document_number(mock_db, "INV")
        assert result.endswith("-0001")


class TestCalculateInvoiceTotals:
    """Cover calculate_invoice_totals (lines 56-101)."""

    def test_osno_vat_included(self):
        from app.services.finance_service import calculate_invoice_totals

        item = SimpleNamespace(
            quantity=Decimal("2"), unit_price=Decimal("1000"), amount=None
        )
        invoice = SimpleNamespace(
            items=[item],
            subtotal=None,
            tax_system="osno",
            vat_rate=Decimal("20"),
            is_vat_included=True,
            vat_amount=None,
            total=None,
        )
        calculate_invoice_totals(invoice)
        assert invoice.subtotal == Decimal("2000")
        assert invoice.total == Decimal("2000")
        assert invoice.vat_amount > 0

    def test_osno_vat_excluded(self):
        from app.services.finance_service import calculate_invoice_totals

        item = SimpleNamespace(
            quantity=Decimal("1"), unit_price=Decimal("1000"), amount=None
        )
        invoice = SimpleNamespace(
            items=[item],
            subtotal=None,
            tax_system="osno",
            vat_rate=Decimal("20"),
            is_vat_included=False,
            vat_amount=None,
            total=None,
        )
        calculate_invoice_totals(invoice)
        assert invoice.total == Decimal("1200")

    def test_usn_no_vat(self):
        from app.services.finance_service import calculate_invoice_totals

        item = SimpleNamespace(
            quantity=Decimal("1"), unit_price=Decimal("1000"), amount=None
        )
        invoice = SimpleNamespace(
            items=[item],
            subtotal=None,
            tax_system="usn_6",
            vat_rate=Decimal("20"),
            is_vat_included=False,
            vat_amount=None,
            total=None,
        )
        calculate_invoice_totals(invoice)
        # USN has no VAT - totals should be without VAT
        assert invoice.vat_amount == Decimal("0")
        assert invoice.total == Decimal("1000")


class TestGetField:
    """Cover _get_field (lines 103-109)."""

    def test_none_obj(self):
        from app.services.finance_service import _get_field

        assert _get_field(None, "key", "default") == "default"

    def test_dict_obj(self):
        from app.services.finance_service import _get_field

        assert _get_field({"key": "val"}, "key") == "val"

    def test_attr_obj(self):
        from app.services.finance_service import _get_field

        obj = SimpleNamespace(key="val")
        assert _get_field(obj, "key") == "val"


class TestCreateInvoice:
    """Cover create_invoice (lines 111-222)."""

    def test_success_with_items(self, mock_db):
        from app.services.finance_service import create_invoice

        user = SimpleNamespace(id=1, company_id=1)
        payload = {
            "subtotal": Decimal("1000"),
            "vat_rate": Decimal("20"),
            "vat_amount": Decimal("200"),
            "total": Decimal("1200"),
            "items": [{"description": "Service", "quantity": 1, "unit_price": 1000}],
            "client_id": 1,
        }
        client = SimpleNamespace(contact_email="c@c.com", name="Client")
        mock_db.get.return_value = client

        create_invoice(mock_db, payload, user)
        mock_db.add.assert_called()
        mock_db.commit.assert_called()

    def test_success_no_items_no_amounts(self, mock_db):
        from app.services.finance_service import create_invoice

        user = SimpleNamespace(id=1, company_id=1)
        payload = {}

        create_invoice(mock_db, payload, user)
        mock_db.commit.assert_called()


class TestRegisterPayment:
    """Cover register_payment (lines 224-240)."""

    def test_full_payment(self, mock_db):
        from app.services.finance_service import register_payment

        invoice = SimpleNamespace(
            total=Decimal("1000"), paid_amount=Decimal("500"), status="draft"
        )
        payment = SimpleNamespace(invoice_id=1, payout_id=None, amount=Decimal("500"))
        mock_db.get.return_value = invoice

        register_payment(mock_db, payment)
        assert invoice.status.value == "paid" or invoice.status == "paid"
        mock_db.commit.assert_called()

    def test_partial_payment(self, mock_db):
        from app.services.finance_service import register_payment

        invoice = SimpleNamespace(
            total=Decimal("1000"), paid_amount=Decimal("0"), status="draft"
        )
        payment = SimpleNamespace(invoice_id=1, payout_id=None, amount=Decimal("300"))
        mock_db.get.return_value = invoice

        register_payment(mock_db, payment)
        mock_db.commit.assert_called()

    def test_payout_payment(self, mock_db):
        from app.services.finance_service import register_payment

        payout = SimpleNamespace(status="pending")
        payment = SimpleNamespace(invoice_id=None, payout_id=1, amount=Decimal("500"))

        def mock_get(model, pk):
            return payout

        mock_db.get.side_effect = mock_get

        register_payment(mock_db, payment)
        mock_db.commit.assert_called()


class TestCalculatePayout:
    """Cover calculate_payout (lines 242-253)."""

    def test_calculation(self):
        from app.services.finance_service import calculate_payout

        result = calculate_payout(Decimal("10000"), Decimal("10"))
        assert result["gross_amount"] == Decimal("10000")
        assert result["platform_commission"] == Decimal("1000")
        assert result["net_amount"] == Decimal("9000")


class TestGetFinanceDashboard:
    """Cover get_finance_dashboard (lines 255-295)."""

    def test_with_company(self, mock_db):
        from app.services.finance_service import get_finance_dashboard

        mock_db.scalar.side_effect = [
            Decimal("50000"),
            Decimal("30000"),
            10,  # revenue, paid, count
            5,
            3,
            Decimal("5000"),  # acts, payouts, commission
        ]
        result = get_finance_dashboard(mock_db, 1)
        assert result["total_revenue"] == Decimal("50000")
        assert result["total_outstanding"] == Decimal("20000")

    def test_without_company(self, mock_db):
        from app.services.finance_service import get_finance_dashboard

        mock_db.scalar.side_effect = [
            Decimal("100000"),
            Decimal("80000"),
            20,
            10,
            5,
            Decimal("10000"),
        ]
        result = get_finance_dashboard(mock_db, None)
        assert result["invoices_count"] == 20


class TestGenerateAndSaveActPdf:
    """Cover generate_and_save_act_pdf (lines 297-358)."""

    def test_act_not_found(self, mock_db):
        from app.services.finance_service import generate_and_save_act_pdf

        mock_db.get.return_value = None
        result = generate_and_save_act_pdf(999, mock_db)
        assert result is None

    def test_success(self, mock_db):
        from app.services.finance_service import generate_and_save_act_pdf

        act = SimpleNamespace(
            id=1,
            document_number="ACT-2026-0001",
            request_id=1,
            contractor_id=1,
            created_by=1,
            company_id=1,
        )
        request = SimpleNamespace(client_id=1)
        contractor = SimpleNamespace(name="Client")

        call_count = {"n": 0}

        def mock_get(model, pk):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return act
            if call_count["n"] == 2:
                return request
            return contractor

        mock_db.get.side_effect = mock_get

        with (
            patch("app.services.finance_service.generate_act_pdf") as mock_pdf,
            patch("app.services.finance_service.storage_service") as mock_storage,
        ):
            mock_pdf.return_value = b"pdf-bytes"
            mock_storage.upload_bytes.return_value = {
                "path": "finance/acts/test.pdf",
                "size": 100,
            }
            result = generate_and_save_act_pdf(1, mock_db)

        assert result["path"] == "finance/acts/test.pdf"
        mock_db.commit.assert_called()


class TestGenerateAndSaveInvoicePdf:
    """Cover generate_and_save_invoice_pdf (lines 360-end)."""

    def test_invoice_not_found(self, mock_db):
        from app.services.finance_service import generate_and_save_invoice_pdf

        mock_db.scalar.return_value = None
        result = generate_and_save_invoice_pdf(999, mock_db)
        assert result is None

    def test_success(self, mock_db):
        from app.services.finance_service import generate_and_save_invoice_pdf

        invoice = SimpleNamespace(
            id=1,
            document_number="INV-2026-0001",
            client_id=1,
            created_by=1,
            company_id=1,
        )
        contractor = SimpleNamespace(name="Client")

        mock_db.scalar.return_value = invoice
        mock_db.get.return_value = contractor

        with (
            patch("app.services.pdf_generator.generate_invoice_pdf") as mock_pdf,
            patch("app.services.finance_service.storage_service") as mock_storage,
        ):
            mock_pdf.return_value = b"pdf-bytes"
            mock_storage.upload_bytes.return_value = {
                "path": "finance/invoices/test.pdf",
                "size": 200,
            }
            result = generate_and_save_invoice_pdf(1, mock_db)

        assert result["path"] == "finance/invoices/test.pdf"
        mock_db.commit.assert_called()
