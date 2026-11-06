"""Coverage tests for email_service business methods."""
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


# Ensure mocks exist
_email_mod = sys.modules.get("app.models.email")
if not _email_mod:
    _email_mod = ModuleType("app.models.email")
    class _ES:
        pending = "pending"; sent = "sent"; failed = "failed"
    class _EL:
        def __init__(self, **kw):
            self.id = 1; self.status = None; self.sent_at = None; self.error_message = None
            for k, v in kw.items(): setattr(self, k, v)
    _email_mod.EmailLog = _EL
    _email_mod.EmailStatus = _ES
    sys.modules["app.models.email"] = _email_mod


@pytest.fixture
def service():
    with patch("app.services.email_service.settings") as ms, \
         patch("app.services.email_service.premailer_transform", side_effect=lambda h: h):
        ms.EMAIL_ENABLED = True
        ms.FRONTEND_URL = "http://localhost"
        ms.SMTP_FROM_NAME = "T"; ms.SMTP_FROM_EMAIL = "t@t.com"
        ms.SMTP_HOST = "h"; ms.SMTP_PORT = 587
        ms.SMTP_USER = "u"; ms.SMTP_PASSWORD = "p"
        from app.services.email_service import EmailService
        svc = EmailService()
    return svc


class TestSendInvoiceCreated:
    """Cover send_invoice_created (lines 271-333)."""

    def test_without_pdf(self, service):
        invoice = SimpleNamespace(id=1, document_number="INV-001")
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
        with patch.object(service, "send_email", return_value=True) as mock_send, \
             patch("app.core.db.SessionLocal", return_value=mock_db):
            result = service.send_invoice_created(invoice, "c@c.com", "Client")
        assert result is True
        mock_send.assert_called_once()
        assert mock_send.call_args[1]["attachments"] is None

    def test_with_pdf(self, service):
        invoice = SimpleNamespace(id=1, document_number="INV-001")
        uploaded = SimpleNamespace(storage_path="/tmp/inv.pdf")
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = uploaded
        with patch.object(service, "send_email", return_value=True) as mock_send, \
             patch("app.core.db.SessionLocal", return_value=mock_db), \
             patch("app.services.storage_service.get_file", return_value=b"%PDF-fake-content"):
            result = service.send_invoice_created(invoice, "c@c.com", "Client")
        assert result is True
        att = mock_send.call_args[1]["attachments"]
        assert att is not None and len(att) == 1

    def test_pdf_fetch_error(self, service):
        invoice = SimpleNamespace(id=1, document_number="INV-001")
        with patch.object(service, "send_email", return_value=True) as mock_send, \
             patch("app.core.db.SessionLocal", side_effect=Exception("DB fail")):
            result = service.send_invoice_created(invoice, "c@c.com", "Client")
        assert result is True
        assert mock_send.call_args[1]["attachments"] is None


class TestSendActSigned:
    """Cover send_act_signed (lines 335-393)."""

    def test_without_pdf(self, service):
        act = SimpleNamespace(id=1, document_number="ACT-001")
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
        with patch.object(service, "send_email", return_value=True) as mock_send, \
             patch("app.core.db.SessionLocal", return_value=mock_db):
            result = service.send_act_signed(act, "u@u.com", "User")
        assert result is True

    def test_with_pdf(self, service):
        act = SimpleNamespace(id=1, document_number="ACT-001")
        uploaded = SimpleNamespace(storage_path="/tmp/act.pdf")
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = uploaded
        with patch.object(service, "send_email", return_value=True) as mock_send, \
             patch("app.core.db.SessionLocal", return_value=mock_db), \
             patch("app.services.storage_service.get_file", return_value=b"%PDF-act"):
            result = service.send_act_signed(act, "u@u.com", "User")
        assert result is True

    def test_error_continues(self, service):
        act = SimpleNamespace(id=1, document_number="ACT-001")
        with patch.object(service, "send_email", return_value=True) as mock_send, \
             patch("app.core.db.SessionLocal", side_effect=Exception("fail")):
            result = service.send_act_signed(act, "u@u.com", "User")
        assert result is True


class TestSimpleDelegates:
    """Cover simple delegate methods."""

    def test_send_act_created(self, service):
        act = SimpleNamespace(id=1, document_number="ACT-001")
        with patch.object(service, "send_email", return_value=True) as m:
            assert service.send_act_created(act, "e@e.com", "Exec", "Client") is True
        m.assert_called_once()

    def test_send_invoice_overdue(self, service):
        inv = SimpleNamespace(id=1, document_number="INV-001")
        with patch.object(service, "send_email", return_value=True) as m:
            assert service.send_invoice_overdue(inv, "c@c.com", "C", 5) is True
        ctx = m.call_args[1]["context"]
        assert ctx["overdue_days"] == 5

    def test_send_request_status_changed(self, service):
        req = SimpleNamespace(id=42)
        with patch.object(service, "send_email", return_value=True) as m:
            assert service.send_request_status_changed(req, "u@u.com", "U", "new", "accepted", "ok") is True
        ctx = m.call_args[1]["context"]
        assert ctx["new_status"] == "accepted"

    def test_send_rental_completed(self, service):
        rental = SimpleNamespace(id=1)
        inv = SimpleNamespace(document_number="INV-002")
        with patch.object(service, "send_email", return_value=True) as m:
            assert service.send_rental_completed(rental, inv, "c@c.com", "C") is True
        m.assert_called_once()

    def test_send_payout_created(self, service):
        payout = SimpleNamespace(document_number="PAY-001", net_amount=50000)
        with patch.object(service, "send_email", return_value=True) as m:
            assert service.send_payout_created(payout, "o@o.com", "Owner") is True
        m.assert_called_once()

    def test_send_dispute_opened(self, service):
        dispute = SimpleNamespace(id=10)
        with patch.object(service, "send_email", return_value=True) as m:
            assert service.send_dispute_opened(dispute, "d@d.com", "Disp") is True
        m.assert_called_once()

    def test_send_dispute_escalated(self, service):
        dispute = SimpleNamespace(id=10)
        with patch.object(service, "send_email", return_value=True) as m:
            assert service.send_dispute_escalated(dispute, "m@m.com", "Mgr", "disp", "ceo") is True
        ctx = m.call_args[1]["context"]
        assert ctx["from_role"] == "disp"

    def test_send_invoice_paid_full(self, service):
        inv = SimpleNamespace(document_number="INV-001", status=SimpleNamespace(value="paid"))
        with patch.object(service, "send_email", return_value=True) as m:
            assert service.send_invoice_paid(inv, 50000, "2026-11-06", "Payer", "7701", "c@c.com", "C") is True
        assert "полностью оплачен" in m.call_args[1]["subject"]

    def test_send_invoice_paid_partial(self, service):
        inv = SimpleNamespace(document_number="INV-001", status=SimpleNamespace(value="partial"))
        with patch.object(service, "send_email", return_value=True) as m:
            assert service.send_invoice_paid(inv, 30000, "2026-11-06", "Payer", None, "c@c.com", "C") is True
        assert "Получена оплата" in m.call_args[1]["subject"]


class TestSendPayoutApproved:
    """Cover send_payout_approved (lines 487-555)."""

    def test_pdf_bytes_attached(self, service):
        payout = SimpleNamespace(document_number="PAY-001", net_amount=50000, owner_id=1, vehicle_id=2)
        owner = SimpleNamespace(name="OOO Test")
        vehicle = SimpleNamespace(name="KAMAZ")
        mock_db = MagicMock()
        mock_db.get.side_effect = lambda cls, id_: owner if cls.__name__ != "Vehicle" else vehicle
        pdf_bytes = b"%PDF-" + b"x" * 200
        with patch.object(service, "send_email", return_value=True) as mock_send, \
             patch("app.core.db.SessionLocal", return_value=mock_db), \
             patch("app.services.pdf_service.generate_payout_pdf", return_value=pdf_bytes):
            result = service.send_payout_approved(payout, "o@o.com", "Owner")
        assert result is True
        att = mock_send.call_args[1]["attachments"]
        assert att is not None

    def test_pdf_too_small_skipped(self, service):
        payout = SimpleNamespace(document_number="PAY-001", net_amount=50000, owner_id=1, vehicle_id=2)
        mock_db = MagicMock()
        mock_db.get.return_value = None
        with patch.object(service, "send_email", return_value=True) as mock_send, \
             patch("app.core.db.SessionLocal", return_value=mock_db), \
             patch("app.services.pdf_service.generate_payout_pdf", return_value=b"tiny"):
            result = service.send_payout_approved(payout, "o@o.com", "Owner")
        assert result is True
        assert mock_send.call_args[1]["attachments"] is None

    def test_pdf_error_continues(self, service):
        payout = SimpleNamespace(document_number="PAY-001", net_amount=50000, owner_id=1, vehicle_id=2)
        with patch.object(service, "send_email", return_value=True) as mock_send, \
             patch("app.core.db.SessionLocal", side_effect=Exception("fail")):
            result = service.send_payout_approved(payout, "o@o.com", "Owner")
        assert result is True
        assert mock_send.call_args[1]["attachments"] is None


class TestGlobalSingleton:
    def test_exists(self):
        from app.services.email_service import email_service
        assert email_service is not None
