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



class TestRemainingBranches:
    """Cover remaining uncovered lines."""

    def test_invoice_created_pdf_cleanup_error(self, service):
        """Cover lines 330-331: pdf_path.unlink() exception."""
        invoice = SimpleNamespace(id=1, document_number="INV-001")
        uploaded = SimpleNamespace(storage_path="/tmp/inv.pdf")
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = uploaded
        fake_path = MagicMock()
        fake_path.exists.return_value = True
        fake_path.unlink.side_effect = PermissionError("locked")
        with patch.object(service, "send_email", return_value=True), \
             patch("app.core.db.SessionLocal", return_value=mock_db), \
             patch("app.services.storage_service.get_file", return_value=b"%PDF-content"), \
             patch("tempfile.NamedTemporaryFile") as mock_tmp:
            mock_tmp.return_value.__enter__ = lambda s: s
            mock_tmp.return_value.__exit__ = lambda *a: False
            mock_tmp.return_value.name = "/tmp/fake.pdf"
            mock_tmp.return_value.write = MagicMock()
            mock_tmp.return_value.close = MagicMock()
            # Patch Path to return our fake_path
            with patch("app.services.email_service.Path") as MockPath:
                MockPath.return_value = fake_path
                result = service.send_invoice_created(invoice, "c@c.com", "C")
        assert result is True  # Should not raise despite unlink error

    def test_act_signed_pdf_cleanup_error(self, service):
        """Cover lines 390-391: act pdf cleanup exception."""
        act = SimpleNamespace(id=1, document_number="ACT-001")
        uploaded = SimpleNamespace(storage_path="/tmp/act.pdf")
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = uploaded
        fake_path = MagicMock()
        fake_path.exists.return_value = True
        fake_path.unlink.side_effect = OSError("busy")
        with patch.object(service, "send_email", return_value=True), \
             patch("app.core.db.SessionLocal", return_value=mock_db), \
             patch("app.services.storage_service.get_file", return_value=b"%PDF-act"), \
             patch("app.services.email_service.Path") as MockPath:
            MockPath.return_value = fake_path
            result = service.send_act_signed(act, "u@u.com", "U")
        assert result is True

    def test_payout_approved_pdf_file_path(self, service):
        """Cover lines 524-540: PDF as file path string."""
        import tempfile, os
        payout = SimpleNamespace(document_number="PAY-001", net_amount=50000, owner_id=1, vehicle_id=2)
        mock_db = MagicMock()
        mock_db.get.return_value = None
        # Create a real temp PDF file > 100 bytes
        tmpf = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        tmpf.write(b"%PDF-" + b"x" * 200)
        tmpf.close()
        try:
            with patch.object(service, "send_email", return_value=True) as mock_send, \
                 patch("app.core.db.SessionLocal", return_value=mock_db), \
                 patch("app.services.pdf_service.generate_payout_pdf", return_value=tmpf.name):
                result = service.send_payout_approved(payout, "o@o.com", "Owner")
            assert result is True
            att = mock_send.call_args[1]["attachments"]
            assert att is not None
        finally:
            try:
                os.unlink(tmpf.name)
            except FileNotFoundError:
                pass  # Already cleaned up by send_payout_approved

    def test_payout_approved_pdf_file_missing(self, service):
        """Cover lines 548-551: PDF file path but file missing."""
        payout = SimpleNamespace(document_number="PAY-001", net_amount=50000, owner_id=1, vehicle_id=2)
        mock_db = MagicMock()
        mock_db.get.return_value = None
        with patch.object(service, "send_email", return_value=True) as mock_send, \
             patch("app.core.db.SessionLocal", return_value=mock_db), \
             patch("app.services.pdf_service.generate_payout_pdf", return_value="/nonexistent/file.pdf"):
            result = service.send_payout_approved(payout, "o@o.com", "Owner")
        assert result is True
        assert mock_send.call_args[1]["attachments"] is None



class TestFinalBranches:
    """Cover last 7 uncovered lines."""

    def test_log_update_to_sent_fails(self, service):
        """Cover lines 249-250: exception inside try block during log update to sent."""
        call_count = [0]
        def make_session():
            call_count[0] += 1
            db = MagicMock()
            if call_count[0] == 1:
                # First call: create log entry - works fine
                db.add = MagicMock()
                return db
            else:
                # Second call: inside try block, get() raises -> hits except on line 249
                db.get.side_effect = Exception("DB connection lost")
                return db

        mock_server = MagicMock()
        mock_server.ehlo = MagicMock(return_value=(250, b"OK"))
        mock_server.starttls = MagicMock(return_value=(220, b"Ready"))
        mock_server.login = MagicMock(return_value=(235, b"OK"))
        mock_server.send_message = MagicMock()
        mock_server.quit = MagicMock()

        with patch("app.core.db.SessionLocal", side_effect=make_session), \
             patch("app.services.email_service.smtplib.SMTP", return_value=mock_server), \
             patch("app.services.email_service.settings") as ms:
            ms.SMTP_PORT = 587; ms.SMTP_HOST = "h"
            ms.SMTP_USER = "u"; ms.SMTP_PASSWORD = "p"
            ms.SMTP_FROM_NAME = "T"; ms.SMTP_FROM_EMAIL = "t@t.com"
            result = service.send_email(to_email="t@t.com", subject="S", body="B")
        assert result is True

    def test_log_update_to_failed_fails(self, service):
        """Cover lines 266-267: exception inside try block during log update to failed."""
        call_count = [0]
        def make_session():
            call_count[0] += 1
            db = MagicMock()
            if call_count[0] == 1:
                # First call: create log entry - works fine
                db.add = MagicMock()
                return db
            else:
                # Second call: inside except->try block, get() raises -> hits except on line 266
                db.get.side_effect = Exception("DB gone")
                return db

        with patch("app.core.db.SessionLocal", side_effect=make_session), \
             patch("app.services.email_service.smtplib.SMTP", side_effect=Exception("SMTP boom")), \
             patch("app.services.email_service.settings") as ms:
            ms.SMTP_PORT = 587; ms.SMTP_HOST = "h"
            ms.SMTP_USER = "u"; ms.SMTP_PASSWORD = "p"
            ms.SMTP_FROM_NAME = "T"; ms.SMTP_FROM_EMAIL = "t@t.com"
            with pytest.raises(Exception, match="SMTP boom"):
                service.send_email(to_email="t@t.com", subject="S", body="B")

    def test_payout_unexpected_pdf_type(self, service):
        """Cover line 540: unexpected PDF result type."""
        payout = SimpleNamespace(document_number="PAY-001", net_amount=50000, owner_id=1, vehicle_id=2)
        mock_db = MagicMock()
        mock_db.get.return_value = None
        with patch.object(service, "send_email", return_value=True) as mock_send, \
             patch("app.core.db.SessionLocal", return_value=mock_db), \
             patch("app.services.pdf_service.generate_payout_pdf", return_value=12345):
            result = service.send_payout_approved(payout, "o@o.com", "Owner")
        assert result is True
        assert mock_send.call_args[1]["attachments"] is None

    def test_payout_temp_cleanup_error(self, service):
        """Cover lines 550-551: temp_path_to_cleanup.unlink() exception."""
        import tempfile, os
        payout = SimpleNamespace(document_number="PAY-001", net_amount=50000, owner_id=1, vehicle_id=2)
        mock_db = MagicMock()
        mock_db.get.return_value = None
        # Create real file so exists() returns True
        tmpf = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        tmpf.write(b"%PDF-" + b"x" * 200)
        tmpf.close()
        # Make unlink fail by making file read-only and using a wrapper
        original_unlink = Path.unlink
        def failing_unlink(self, *a, **kw):
            raise PermissionError("locked")
        try:
            with patch.object(service, "send_email", return_value=True) as mock_send, \
                 patch("app.core.db.SessionLocal", return_value=mock_db), \
                 patch("app.services.pdf_service.generate_payout_pdf", return_value=tmpf.name), \
                 patch.object(Path, "unlink", failing_unlink):
                result = service.send_payout_approved(payout, "o@o.com", "Owner")
            assert result is True
        finally:
            try:
                os.unlink(tmpf.name)
            except Exception:
                pass
