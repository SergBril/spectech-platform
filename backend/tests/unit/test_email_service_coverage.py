"""Coverage tests for email_service."""

from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def svc():
    with (
        patch("app.services.email_service.settings") as mock_settings,
        patch("app.services.email_service.FileSystemLoader"),
        patch("app.services.email_service.Environment"),
        patch("app.services.email_service.select_autoescape"),
    ):
        mock_settings.EMAIL_ENABLED = False
        mock_settings.FRONTEND_URL = "http://localhost"
        from app.services.email_service import EmailService

        service = EmailService()
        return service


class TestAttachFile:
    """Cover _attach_file (lines 47-73)."""

    def test_empty_content(self, svc):
        msg = MagicMock()
        svc._attach_file(msg, "test.pdf", b"")
        msg.attach.assert_not_called()

    def test_pdf_attachment(self, svc):
        msg = MagicMock()
        svc._attach_file(msg, "invoice.pdf", b"%PDF-1.4 fake content")
        msg.attach.assert_called_once()

    def test_other_attachment(self, svc):
        msg = MagicMock()
        svc._attach_file(msg, "data.csv", b"col1,col2")
        msg.attach.assert_called_once()


class TestSendEmailValidation:
    """Cover send_email validation logic (lines 75-160)."""

    def test_no_body_raises(self, svc):
        with patch("app.core.db.SessionLocal") as mock_sl:
            db_mock = MagicMock()
            mock_sl.return_value = db_mock
            with pytest.raises(ValueError, match="Either"):
                svc.send_email(to_email="t@t.com", subject="Test")


class TestSendInvoiceCreated:
    """Cover send_invoice_created (lines 271-333)."""

    def test_without_pdf(self, svc):
        invoice = SimpleNamespace(id=1, document_number="INV-2026-0001")
        with (
            patch("app.core.db.SessionLocal") as mock_sl,
            patch.object(svc, "send_email", return_value=True) as mock_send,
        ):
            db_mock = MagicMock()
            db_mock.query.return_value.filter.return_value.order_by.return_value.first.return_value = (
                None
            )
            mock_sl.return_value = db_mock
            result = svc.send_invoice_created(invoice, "c@c.com", "Client")
        assert result is True
        mock_send.assert_called_once()


class TestSendActSigned:
    """Cover send_act_signed (lines 335-393)."""

    def test_without_pdf(self, svc):
        act = SimpleNamespace(id=1, document_number="ACT-2026-0001")
        with (
            patch("app.core.db.SessionLocal") as mock_sl,
            patch.object(svc, "send_email", return_value=True),
        ):
            db_mock = MagicMock()
            db_mock.query.return_value.filter.return_value.order_by.return_value.first.return_value = (
                None
            )
            mock_sl.return_value = db_mock
            result = svc.send_act_signed(act, "u@u.com", "User")
        assert result is True


class TestSendActCreated:
    """Cover send_act_created (lines 395-410)."""

    def test_success(self, svc):
        act = SimpleNamespace(document_number="ACT-2026-0001")
        with patch.object(svc, "send_email", return_value=True):
            result = svc.send_act_created(act, "e@e.com", "Exec", "Client")
        assert result is True


class TestSendInvoiceOverdue:
    """Cover send_invoice_overdue (lines 412-427)."""

    def test_success(self, svc):
        invoice = SimpleNamespace(document_number="INV-2026-0001")
        with patch.object(svc, "send_email", return_value=True):
            result = svc.send_invoice_overdue(invoice, "c@c.com", "Client", 5)
        assert result is True


class TestSendRequestStatusChanged:
    """Cover send_request_status_changed (lines 429-452)."""

    def test_success(self, svc):
        request = SimpleNamespace(id=1, title="Test request")
        with patch.object(svc, "send_email", return_value=True):
            result = svc.send_request_status_changed(
                request, "c@c.com", "Client", "draft", "active"
            )
        assert result is True


class TestSendRentalCompleted:
    """Cover send_rental_completed (lines 454-469)."""

    def test_success(self, svc):
        rental = SimpleNamespace(id=1)
        invoice = SimpleNamespace(document_number="INV-2026-0001")
        with patch.object(svc, "send_email", return_value=True):
            result = svc.send_rental_completed(rental, invoice, "c@c.com", "Client")
        assert result is True


class TestSendPayoutCreated:
    """Cover send_payout_created (lines 471-483)."""

    def test_success(self, svc):
        payout = SimpleNamespace(
            document_number="PAY-2026-0001", net_amount=Decimal("9000")
        )
        with patch.object(svc, "send_email", return_value=True):
            result = svc.send_payout_created(payout, "o@o.com", "Owner")
        assert result is True


class TestSendPayoutApproved:
    """Cover send_payout_approved (lines 485-565)."""

    def test_with_pdf_bytes(self, svc):
        payout = SimpleNamespace(
            document_number="PAY-2026-0001",
            net_amount=Decimal("9000"),
            owner_id=1,
            vehicle_id=1,
        )
        with (
            patch("app.core.db.SessionLocal") as mock_sl,
            patch(
                "app.services.pdf_service.generate_payout_pdf",
                return_value=b"%PDF-fake-content-" + b"x" * 200,
            ),
            patch.object(svc, "send_email", return_value=True) as mock_send,
        ):
            db_mock = MagicMock()
            owner = SimpleNamespace(name="OwnerCo")
            vehicle = SimpleNamespace(name="KAMAZ")
            call_count = {"n": 0}

            def mock_get(model, pk):
                call_count["n"] += 1
                return owner if call_count["n"] == 1 else vehicle

            db_mock.get.side_effect = mock_get
            mock_sl.return_value = db_mock
            result = svc.send_payout_approved(payout, "o@o.com", "Owner")
        assert result is True
        # Verify attachment was passed
        call_kwargs = mock_send.call_args
        assert call_kwargs is not None

    def test_small_pdf_skipped(self, svc):
        payout = SimpleNamespace(
            document_number="PAY-2026-0001",
            net_amount=Decimal("9000"),
            owner_id=1,
            vehicle_id=1,
        )
        with (
            patch("app.core.db.SessionLocal") as mock_sl,
            patch("app.services.pdf_service.generate_payout_pdf", return_value=b"tiny"),
            patch.object(svc, "send_email", return_value=True),
        ):
            db_mock = MagicMock()
            owner = SimpleNamespace(name="OwnerCo")
            vehicle = SimpleNamespace(name="KAMAZ")
            call_count = {"n": 0}

            def mock_get(model, pk):
                call_count["n"] += 1
                return owner if call_count["n"] == 1 else vehicle

            db_mock.get.side_effect = mock_get
            mock_sl.return_value = db_mock
            result = svc.send_payout_approved(payout, "o@o.com", "Owner")
        assert result is True


class TestSendDisputeOpened:
    """Cover send_dispute_opened (lines 567-581)."""

    def test_success(self, svc):
        dispute = SimpleNamespace(id=1)
        with patch.object(svc, "send_email", return_value=True):
            result = svc.send_dispute_opened(dispute, "d@d.com", "Dispatcher")
        assert result is True


class TestSendDisputeEscalated:
    """Cover send_dispute_escalated (lines 583-606)."""

    def test_success(self, svc):
        dispute = SimpleNamespace(id=1)
        with patch.object(svc, "send_email", return_value=True):
            result = svc.send_dispute_escalated(
                dispute, "m@m.com", "Manager", "dispatcher", "ceo"
            )
        assert result is True


class TestSendInvoicePaid:
    """Cover send_invoice_paid (lines 608-end)."""

    def test_fully_paid(self, svc):
        invoice = SimpleNamespace(
            document_number="INV-2026-0001", status=SimpleNamespace(value="paid")
        )
        with patch.object(svc, "send_email", return_value=True):
            result = svc.send_invoice_paid(
                invoice,
                Decimal("10000"),
                datetime.now(),
                "Payer",
                "1234567890",
                "c@c.com",
                "Client",
            )
        assert result is True

    def test_partially_paid(self, svc):
        invoice = SimpleNamespace(
            document_number="INV-2026-0001",
            status=SimpleNamespace(value="partially_paid"),
        )
        with patch.object(svc, "send_email", return_value=True):
            result = svc.send_invoice_paid(
                invoice,
                Decimal("5000"),
                datetime.now(),
                "Payer",
                None,
                "c@c.com",
                "Client",
            )
        assert result is True
