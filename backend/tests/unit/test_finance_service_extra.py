from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.services.finance_service import register_payment


@pytest.fixture
def mock_db():
    return MagicMock()


class TestRegisterPayment:
    """Tests for register_payment"""

    def test_register_payment_invoice_full_paid(self, mock_db):
        mock_invoice = MagicMock()
        mock_invoice.paid_amount = Decimal("80")
        mock_invoice.total = Decimal("100")
        mock_invoice.status = "sent"

        mock_payment = MagicMock()
        mock_payment.invoice_id = 1
        mock_payment.payout_id = None
        mock_payment.amount = Decimal("20")

        mock_db.get = MagicMock(return_value=mock_invoice)
        mock_db.commit = MagicMock()

        register_payment(mock_db, mock_payment)

        assert mock_invoice.paid_amount == Decimal("100")
        assert mock_invoice.status.value == "paid" or mock_invoice.status == "paid"
        mock_db.commit.assert_called_once()

    def test_register_payment_invoice_partial(self, mock_db):
        mock_invoice = MagicMock()
        mock_invoice.paid_amount = Decimal("0")
        mock_invoice.total = Decimal("100")

        mock_payment = MagicMock()
        mock_payment.invoice_id = 1
        mock_payment.payout_id = None
        mock_payment.amount = Decimal("50")

        mock_db.get = MagicMock(return_value=mock_invoice)
        mock_db.commit = MagicMock()

        register_payment(mock_db, mock_payment)

        assert mock_invoice.paid_amount == Decimal("50")
        mock_db.commit.assert_called_once()

    def test_register_payment_payout(self, mock_db):
        mock_payout = MagicMock()

        mock_payment = MagicMock()
        mock_payment.invoice_id = None
        mock_payment.payout_id = 5
        mock_payment.amount = Decimal("100")

        def side_effect(model, id):
            if (
                hasattr(model, "__tablename__")
                and "payout" in str(model.__tablename__).lower()
            ):
                return mock_payout
            return None

        mock_db.get = MagicMock(
            side_effect=lambda m, i: mock_payout if i == 5 else None
        )
        mock_db.commit = MagicMock()

        register_payment(mock_db, mock_payment)

        mock_db.commit.assert_called_once()

    def test_register_payment_no_invoice_or_payout(self, mock_db):
        mock_payment = MagicMock()
        mock_payment.invoice_id = None
        mock_payment.payout_id = None

        mock_db.commit = MagicMock()

        register_payment(mock_db, mock_payment)

        mock_db.commit.assert_called_once()

    def test_register_payment_invoice_not_found(self, mock_db):
        mock_payment = MagicMock()
        mock_payment.invoice_id = 999
        mock_payment.payout_id = None

        mock_db.get = MagicMock(return_value=None)
        mock_db.commit = MagicMock()

        # Should not raise, just skip
        register_payment(mock_db, mock_payment)
        mock_db.commit.assert_called_once()


class TestGenerateAndSaveInvoicePdf:
    """Tests for generate_and_save_invoice_pdf"""

    @patch("app.services.finance_service.storage_service")
    @patch("app.services.pdf_generator.generate_invoice_pdf")
    def test_generate_success(self, mock_gen_pdf, mock_storage, mock_db):
        from app.services.finance_service import generate_and_save_invoice_pdf

        mock_invoice = MagicMock()
        mock_invoice.id = 1
        mock_invoice.document_number = "INV-001"
        mock_invoice.client_id = 10
        mock_invoice.created_by = 5
        mock_invoice.company_id = 7

        mock_db.scalar = MagicMock(return_value=mock_invoice)
        mock_db.get = MagicMock(return_value=MagicMock())
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()

        mock_gen_pdf.return_value = b"pdf_content"
        mock_storage.upload_bytes = MagicMock(
            return_value={"path": "finance/invoices/INV-001.pdf", "size": 1234}
        )

        result = generate_and_save_invoice_pdf(1, mock_db)

        assert result is not None
        assert result["path"] == "finance/invoices/INV-001.pdf"
        mock_gen_pdf.assert_called_once()
        mock_storage.upload_bytes.assert_called_once()
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_generate_invoice_not_found(self, mock_db):
        from app.services.finance_service import generate_and_save_invoice_pdf

        mock_db.scalar = MagicMock(return_value=None)

        result = generate_and_save_invoice_pdf(999, mock_db)
        assert result is None


class TestGenerateAndSaveActPdf:
    """Tests for generate_and_save_act_pdf"""

    @patch("app.services.finance_service.storage_service")
    @patch("app.services.finance_service.generate_act_pdf")
    def test_generate_act_success(self, mock_gen_pdf, mock_storage, mock_db):
        from app.services.finance_service import generate_and_save_act_pdf

        mock_act = MagicMock()
        mock_act.id = 1
        mock_act.document_number = "ACT-001"
        mock_act.client_id = 10
        mock_act.created_by = 5
        mock_act.company_id = 7

        mock_db.get = MagicMock(
            side_effect=lambda model, id: mock_act if id == 1 else MagicMock()
        )
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()

        mock_gen_pdf.return_value = b"pdf_content"
        mock_storage.upload_bytes = MagicMock(
            return_value={"path": "finance/acts/ACT-001.pdf", "size": 2345}
        )

        result = generate_and_save_act_pdf(1, mock_db)

        assert result is not None
        assert result["path"] == "finance/acts/ACT-001.pdf"
        mock_gen_pdf.assert_called_once()
        mock_storage.upload_bytes.assert_called_once()

    def test_generate_act_not_found(self, mock_db):
        from app.services.finance_service import generate_and_save_act_pdf

        mock_db.get = MagicMock(return_value=None)

        result = generate_and_save_act_pdf(999, mock_db)
        assert result is None
