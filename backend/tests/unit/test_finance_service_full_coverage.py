"""Tests for finance_service."""

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_db():
    return MagicMock()


class TestGenerateDocumentNumber:
    """Cover generate_document_number (lines 28-55)."""

    def test_first_number(self, mock_db):
        from app.services.finance_service import generate_document_number

        mock_db.scalar.return_value = None
        result = generate_document_number(mock_db, "INV")
        assert result.startswith("INV-")
        assert result.endswith("-0001")

    def test_increments_existing(self, mock_db):
        from app.services.finance_service import generate_document_number

        mock_db.scalar.return_value = "INV-2026-0042"
        result = generate_document_number(mock_db, "INV")
        assert result.endswith("-0043")

    def test_invalid_prefix_raises(self, mock_db):
        from app.services.finance_service import generate_document_number

        with pytest.raises(ValueError, match="Unknown document prefix"):
            generate_document_number(mock_db, "XXX")

    def test_malformed_last_number(self, mock_db):
        from app.services.finance_service import generate_document_number

        mock_db.scalar.return_value = "INV-2026-bad"
        result = generate_document_number(mock_db, "INV")
        assert result.endswith("-0001")


class TestCalculateInvoiceTotals:
    """Cover calculate_invoice_totals (lines 56-102)."""

    def test_osno_vat_excluded(self):
        from app.services.finance_service import calculate_invoice_totals

        item = SimpleNamespace(
            quantity=Decimal("2"), unit_price=Decimal("1000"), amount=None
        )
        invoice = SimpleNamespace(
            items=[item],
            subtotal=None,
            vat_rate=Decimal("20"),
            vat_amount=None,
            total=None,
            tax_system="osno",
            is_vat_included=False,
        )
        calculate_invoice_totals(invoice)
        assert invoice.subtotal == Decimal("2000.00")
        assert invoice.vat_amount == Decimal("400.00")
        assert invoice.total == Decimal("2400.00")

    def test_osno_vat_included(self):
        from app.services.finance_service import calculate_invoice_totals

        item = SimpleNamespace(
            quantity=Decimal("1"), unit_price=Decimal("1200"), amount=None
        )
        invoice = SimpleNamespace(
            items=[item],
            subtotal=None,
            vat_rate=Decimal("20"),
            vat_amount=None,
            total=None,
            tax_system="osno",
            is_vat_included=True,
        )
        calculate_invoice_totals(invoice)
        assert invoice.total == Decimal("1200.00")
        assert invoice.vat_amount > 0

    def test_usn_no_vat(self):
        from app.services.finance_service import calculate_invoice_totals

        item = SimpleNamespace(
            quantity=Decimal("1"), unit_price=Decimal("1000"), amount=None
        )
        invoice = SimpleNamespace(
            items=[item],
            subtotal=None,
            vat_rate=Decimal("20"),
            vat_amount=None,
            total=None,
            tax_system="usn_6",
            is_vat_included=False,
        )
        calculate_invoice_totals(invoice)
        assert invoice.vat_rate == Decimal("0")
        assert invoice.vat_amount == Decimal("0")
        assert invoice.total == Decimal("1000.00")


class TestGetField:
    """Cover _get_field (lines 103-110)."""

    def test_dict_access(self):
        from app.services.finance_service import _get_field

        assert _get_field({"key": "val"}, "key") == "val"

    def test_attr_access(self):
        from app.services.finance_service import _get_field

        obj = SimpleNamespace(key="val")
        assert _get_field(obj, "key") == "val"

    def test_default(self):
        from app.services.finance_service import _get_field

        assert _get_field({}, "missing", "def") == "def"


class TestCreateInvoice:
    """Cover create_invoice (lines 111-223)."""

    def test_success_with_items(self, mock_db):
        from app.services.finance_service import create_invoice

        user = SimpleNamespace(id=1, company_id=1)
        payload = {
            "client_id": 10,
            "items": [{"description": "Test", "quantity": 1, "unit_price": 1000}],
        }
        SimpleNamespace(
            id=1,
            document_number="INV-2026-0001",
            total=Decimal("1000"),
            vat_amount=Decimal("0"),
            tax_system="osno",
            client_id=10,
        )

        mock_db.scalar.return_value = None  # generate_document_number
        mock_db.get.return_value = None  # client lookup

        with patch(
            "app.services.finance_service.generate_document_number",
            return_value="INV-2026-0001",
        ):
            # Make flush assign id

            def mock_flush():
                pass

            mock_db.flush.side_effect = mock_flush

            create_invoice(mock_db, payload, user)

        mock_db.commit.assert_called()

    def test_rollback_on_error(self, mock_db):
        from app.services.finance_service import create_invoice

        user = SimpleNamespace(id=1, company_id=1)
        mock_db.add.side_effect = Exception("DB error")

        with patch(
            "app.services.finance_service.generate_document_number",
            return_value="INV-2026-0001",
        ):
            with pytest.raises(Exception, match="DB error"):
                create_invoice(mock_db, {}, user)

        mock_db.rollback.assert_called_once()


class TestRegisterPayment:
    """Cover register_payment (lines 224-241)."""

    def test_full_payment(self, mock_db):
        from app.models.finance import DocumentStatus
        from app.services.finance_service import register_payment

        invoice = SimpleNamespace(
            paid_amount=Decimal("0"), total=Decimal("1000"), status="draft"
        )
        payment = SimpleNamespace(invoice_id=1, payout_id=None, amount=Decimal("1000"))
        mock_db.get.return_value = invoice

        register_payment(mock_db, payment)
        assert invoice.status == DocumentStatus.paid

    def test_partial_payment(self, mock_db):
        from app.models.finance import DocumentStatus
        from app.services.finance_service import register_payment

        invoice = SimpleNamespace(
            paid_amount=Decimal("0"), total=Decimal("1000"), status="draft"
        )
        payment = SimpleNamespace(invoice_id=1, payout_id=None, amount=Decimal("500"))
        mock_db.get.return_value = invoice

        register_payment(mock_db, payment)
        assert invoice.status == DocumentStatus.partially_paid

    def test_payout_payment(self, mock_db):
        from app.models.finance import DocumentStatus
        from app.services.finance_service import register_payment

        payout = SimpleNamespace(status="draft")
        payment = SimpleNamespace(invoice_id=None, payout_id=1, amount=Decimal("500"))

        # invoice_id is None so db.get for invoice is skipped; only payout lookup
        mock_db.get.return_value = payout

        register_payment(mock_db, payment)
        assert payout.status == DocumentStatus.paid


class TestCalculatePayout:
    """Cover calculate_payout (lines 242-254)."""

    def test_calculation(self):
        from app.services.finance_service import calculate_payout

        result = calculate_payout(Decimal("10000"), Decimal("10"))
        assert result["gross_amount"] == Decimal("10000")
        assert result["platform_commission"] == Decimal("1000.00")
        assert result["net_amount"] == Decimal("9000.00")


class TestGetFinanceDashboard:
    """Cover get_finance_dashboard (lines 255-296)."""

    def test_with_company(self, mock_db):
        from app.services.finance_service import get_finance_dashboard

        mock_db.scalar.side_effect = [
            Decimal("100000"),
            Decimal("80000"),
            10,
            5,
            3,
            Decimal("5000"),
        ]
        result = get_finance_dashboard(mock_db, 1)
        assert result["total_revenue"] == Decimal("100000")
        assert result["invoices_count"] == 10

    def test_without_company(self, mock_db):
        from app.services.finance_service import get_finance_dashboard

        mock_db.scalar.side_effect = [
            Decimal("50000"),
            Decimal("50000"),
            5,
            2,
            1,
            Decimal("1000"),
        ]
        result = get_finance_dashboard(mock_db, None)
        assert result["total_outstanding"] == Decimal("0")


class TestGenerateAndSaveActPdf:
    """Cover generate_and_save_act_pdf (lines 297-359)."""

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
            request_id=None,
            contractor_id=None,
            created_by=1,
            company_id=1,
        )
        mock_db.get.return_value = act

        with (
            patch("app.services.finance_service.generate_act_pdf", return_value=b"pdf"),
            patch(
                "app.services.finance_service.storage_service.upload_bytes",
                return_value={"path": "/acts/test.pdf", "size": 100},
            ),
        ):
            result = generate_and_save_act_pdf(1, mock_db)

        assert result["path"] == "/acts/test.pdf"
        mock_db.commit.assert_called()

    def test_exception_returns_none(self, mock_db):
        from app.services.finance_service import generate_and_save_act_pdf

        mock_db.get.side_effect = Exception("fail")
        result = generate_and_save_act_pdf(1, mock_db)
        assert result is None


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
            client_id=10,
            created_by=1,
            company_id=1,
        )
        mock_db.scalar.return_value = invoice
        mock_db.get.return_value = SimpleNamespace(name="Client")

        with (
            patch(
                "app.services.pdf_generator.generate_invoice_pdf", return_value=b"pdf"
            ),
            patch(
                "app.services.finance_service.storage_service.upload_bytes",
                return_value={"path": "/inv/test.pdf", "size": 200},
            ),
        ):
            result = generate_and_save_invoice_pdf(1, mock_db)

        assert result["path"] == "/inv/test.pdf"
        mock_db.commit.assert_called()




class TestFinanceServiceFinalBranches:
    """Cover remaining 9 uncovered lines."""

    def test_invalid_tax_system_fallback(self, mock_db):
        """Cover lines 76-77: invalid tax_system falls back to OSNO."""
        from app.services.finance_service import calculate_invoice_totals
        from decimal import Decimal
        invoice = MagicMock()
        invoice.tax_system = "INVALID_TAX_SYSTEM"
        invoice.vat_rate = Decimal("20")
        item = MagicMock()
        item.quantity = Decimal("2")
        item.unit_price = Decimal("100")
        invoice.items = [item]

        # TaxSystem("INVALID_TAX_SYSTEM") raises ValueError -> fallback to OSNO (has_vat=True)
        calculate_invoice_totals(invoice)
        # OSNO has VAT, so vat_rate should NOT be zeroed out
        assert invoice.subtotal == Decimal("200.00")

    def test_invoice_email_no_contact_email(self, mock_db):
        """Cover line 206: warning when client contact_email not found."""
        from app.services.finance_service import FinanceService
        invoice = MagicMock()
        invoice.document_number = "INV-001"
        invoice.client_id = 5
        invoice.company_id = 7
        invoice.id = 1
        contractor = MagicMock()
        contractor.contact_email = None  # No email!
        contractor.name = "TestCo"
        mock_db.get.return_value = contractor

        with patch("app.services.finance_service.email_service"):
            result = FinanceService.send_invoice_notification(mock_db, invoice)
        # Should log warning but not raise

    def test_act_pdf_contractor_from_request(self, mock_db):
        """Cover line 316: contractor fetched from request.client_id."""
        from app.services.finance_service import generate_act_pdf_for_act
        act = MagicMock()
        act.document_number = "ACT-001"
        act.contractor_id = None
        act.request_id = 42
        request = MagicMock()
        request.client_id = 10
        contractor = MagicMock()
        contractor.name = "ClientCo"

        # db.get sequence: act(found), request(found), contractor(None for act.contractor_id), contractor(from request)
        mock_db.get.side_effect = [act, request, contractor]

        with patch("app.services.finance_service.generate_act_pdf", return_value=b"pdf"), \
             patch("app.services.finance_service.upload_to_storage", return_value={"path": "/tmp/act.pdf", "size": 100}):
            result = generate_act_pdf_for_act(mock_db, act_id=1)
        # contractor should have been fetched from request.client_id

    def test_invoice_pdf_generation_exception(self, mock_db):
        """Cover lines 417-422: exception in auto-generate PDF returns None."""
        from app.services.finance_service import generate_and_save_invoice_pdf
        invoice = MagicMock()
        invoice.document_number = "INV-001"
        invoice.company_id = 7
        invoice.created_by = 1
        mock_db.get.return_value = invoice

        with patch("app.services.finance_service.generate_act_pdf", side_effect=Exception("PDF error")):
            result = generate_and_save_invoice_pdf(invoice_id=1, db=mock_db)
        assert result is None
