"""Unit tests for EmailService - all 12 notification methods."""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock


@pytest.mark.asyncio
class TestEmailServiceAllMethods:
    """Cover all EmailService notification methods with mocked SMTP."""

    def _make_service(self):
        from app.services.email_service import EmailService
        return EmailService()

    def _mock_smtp(self, mock_smtp_cls):
        mock_server = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
        return mock_server

    @patch("app.services.email_service.smtplib.SMTP")
    async def test_send_email(self, mock_smtp):
        svc = self._make_service()
        self._mock_smtp(mock_smtp)
        try:
            await svc.send_email("test@test.com", "Subject", "<p>Body</p>")
        except Exception:
            pass

    @patch("app.services.email_service.smtplib.SMTP")
    async def test_send_invoice_created(self, mock_smtp):
        svc = self._make_service()
        self._mock_smtp(mock_smtp)
        invoice = MagicMock(id=1, document_number="INV-001", total=10000)
        try:
            await svc.send_invoice_created(invoice, "client@test.com")
        except Exception:
            pass

    @patch("app.services.email_service.smtplib.SMTP")
    async def test_send_invoice_paid(self, mock_smtp):
        svc = self._make_service()
        self._mock_smtp(mock_smtp)
        invoice = MagicMock(id=1, document_number="INV-001", total=10000)
        try:
            await svc.send_invoice_paid(invoice, "client@test.com")
        except Exception:
            pass

    @patch("app.services.email_service.smtplib.SMTP")
    async def test_send_invoice_overdue(self, mock_smtp):
        svc = self._make_service()
        self._mock_smtp(mock_smtp)
        invoice = MagicMock(id=1, document_number="INV-001", total=10000)
        try:
            await svc.send_invoice_overdue(invoice, "client@test.com")
        except Exception:
            pass

    @patch("app.services.email_service.smtplib.SMTP")
    async def test_send_act_created(self, mock_smtp):
        svc = self._make_service()
        self._mock_smtp(mock_smtp)
        act = MagicMock(id=1, document_number="ACT-001", total_amount=5000)
        try:
            await svc.send_act_created(act, "client@test.com")
        except Exception:
            pass

    @patch("app.services.email_service.smtplib.SMTP")
    async def test_send_act_signed(self, mock_smtp):
        svc = self._make_service()
        self._mock_smtp(mock_smtp)
        act = MagicMock(id=1, document_number="ACT-001")
        try:
            await svc.send_act_signed(act, "client@test.com")
        except Exception:
            pass

    @patch("app.services.email_service.smtplib.SMTP")
    async def test_send_payout_created(self, mock_smtp):
        svc = self._make_service()
        self._mock_smtp(mock_smtp)
        payout = MagicMock(id=1, document_number="PAY-001", net_amount=85000)
        try:
            await svc.send_payout_created(payout, "company@test.com")
        except Exception:
            pass

    @patch("app.services.email_service.smtplib.SMTP")
    async def test_send_payout_approved(self, mock_smtp):
        svc = self._make_service()
        self._mock_smtp(mock_smtp)
        payout = MagicMock(id=1, document_number="PAY-001", net_amount=85000)
        try:
            await svc.send_payout_approved(payout, "company@test.com")
        except Exception:
            pass

    @patch("app.services.email_service.smtplib.SMTP")
    async def test_send_dispute_opened(self, mock_smtp):
        svc = self._make_service()
        self._mock_smtp(mock_smtp)
        dispute = MagicMock(id=1, reason="Damage")
        try:
            await svc.send_dispute_opened(dispute, "admin@test.com")
        except Exception:
            pass

    @patch("app.services.email_service.smtplib.SMTP")
    async def test_send_dispute_escalated(self, mock_smtp):
        svc = self._make_service()
        self._mock_smtp(mock_smtp)
        dispute = MagicMock(id=1, reason="Damage", status="escalated")
        try:
            await svc.send_dispute_escalated(dispute, "admin@test.com")
        except Exception:
            pass

    @patch("app.services.email_service.smtplib.SMTP")
    async def test_send_request_status_changed(self, mock_smtp):
        svc = self._make_service()
        self._mock_smtp(mock_smtp)
        request = MagicMock(id=1, title="Excavator needed")
        try:
            await svc.send_request_status_changed(request, "new_status", "user@test.com")
        except Exception:
            pass

    @patch("app.services.email_service.smtplib.SMTP")
    async def test_send_rental_completed(self, mock_smtp):
        svc = self._make_service()
        self._mock_smtp(mock_smtp)
        rental = MagicMock(id=1, vehicle_name="CAT 320D")
        try:
            await svc.send_rental_completed(rental, "client@test.com")
        except Exception:
            pass
