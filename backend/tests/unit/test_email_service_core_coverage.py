"""Coverage tests for email_service (core methods)."""
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch, mock_open

import pytest


# Mock app.models.email before importing EmailService
_email_mod = ModuleType("app.models.email")


class _MockEmailStatus:
    pending = "pending"
    sent = "sent"
    failed = "failed"


class _MockEmailLog:
    def __init__(self, **kwargs):
        self.id = 1
        for k, v in kwargs.items():
            setattr(self, k, v)


_email_mod.EmailLog = _MockEmailLog
_email_mod.EmailStatus = _MockEmailStatus
sys.modules.setdefault("app.models.email", _email_mod)


@pytest.fixture
def service():
    with patch("app.services.email_service.settings") as mock_settings:
        mock_settings.EMAIL_ENABLED = True
        mock_settings.FRONTEND_URL = "http://localhost:3000"
        mock_settings.SMTP_FROM_NAME = "Spectech"
        mock_settings.SMTP_FROM_EMAIL = "noreply@spectech.dev"
        mock_settings.SMTP_HOST = "smtp.test.com"
        mock_settings.SMTP_PORT = 587
        mock_settings.SMTP_USER = "user"
        mock_settings.SMTP_PASSWORD = "pass"
        from app.services.email_service import EmailService
        svc = EmailService()
    return svc


class TestInit:
    """Cover __init__ (lines 24-36)."""

    def test_enabled(self, service):
        assert service.enabled is True

    def test_disabled(self):
        with patch("app.services.email_service.settings") as mock_settings:
            mock_settings.EMAIL_ENABLED = False
            from app.services.email_service import EmailService
            svc = EmailService()
        assert svc.enabled is False


class TestRenderTemplate:
    """Cover _render_template (lines 38-45)."""

    def test_renders_with_context(self, service):
        # Create a temp template
        import tempfile, os
        tmpdir = tempfile.mkdtemp()
        tpl_path = os.path.join(tmpdir, "test.html")
        with open(tpl_path, "w") as f:
            f.write("<html><body>{{ name }}</body></html>")
        service.jinja_env.loader.searchpath = [tmpdir]
        result = service._render_template("test.html", {"name": "Ivan"})
        assert "Ivan" in result
        os.unlink(tpl_path)
        os.rmdir(tmpdir)

    def test_adds_frontend_url(self, service):
        import tempfile, os
        tmpdir = tempfile.mkdtemp()
        tpl_path = os.path.join(tmpdir, "url_test.html")
        with open(tpl_path, "w") as f:
            f.write("<html>{{ frontend_url }}</html>")
        service.jinja_env.loader.searchpath = [tmpdir]
        result = service._render_template("url_test.html", {})
        assert "localhost:3000" in result
        os.unlink(tpl_path)
        os.rmdir(tmpdir)


class TestAttachFile:
    """Cover _attach_file (lines 47-73)."""

    def test_pdf_attachment(self, service):
        from email.mime.multipart import MIMEMultipart
        msg = MIMEMultipart()
        service._attach_file(msg, "report.pdf", b"pdf content")
        assert len(msg.get_payload()) == 1

    def test_generic_attachment(self, service):
        from email.mime.multipart import MIMEMultipart
        msg = MIMEMultipart()
        service._attach_file(msg, "data.csv", b"csv content")
        assert len(msg.get_payload()) == 1

    def test_empty_content_skipped(self, service):
        from email.mime.multipart import MIMEMultipart
        msg = MIMEMultipart()
        service._attach_file(msg, "empty.pdf", b"")
        assert len(msg.get_payload()) == 0

    def test_none_content_skipped(self, service):
        from email.mime.multipart import MIMEMultipart
        msg = MIMEMultipart()
        service._attach_file(msg, "none.pdf", None)
        assert len(msg.get_payload()) == 0


class TestSendEmail:
    """Cover send_email (lines 75-270)."""

    def test_no_body_raises(self, service):
        with patch("app.services.email_service.SessionLocal") as mock_sl:
            mock_db = MagicMock()
            mock_sl.return_value = mock_db
            mock_log = MagicMock()
            mock_log.id = 1
            mock_db.get.return_value = mock_log
            with pytest.raises(ValueError, match="Either"):
                service.send_email(to_email="test@test.com", subject="Test")

    def test_direct_body_success(self, service):
        with patch("app.services.email_service.SessionLocal") as mock_sl, \
             patch("app.services.email_service.smtplib.SMTP") as mock_smtp:
            mock_db = MagicMock()
            mock_sl.return_value = mock_db
            mock_log = MagicMock()
            mock_log.id = 1
            mock_db.get.return_value = mock_log
            mock_server = MagicMock()
            mock_smtp.return_value = mock_server
            result = service.send_email(
                to_email="test@test.com",
                subject="Test",
                body="Hello",
                html_body="<b>Hello</b>",
            )
        assert result is True
        mock_server.send_message.assert_called_once()
        mock_server.quit.assert_called_once()

    def test_ssl_port_465(self, service):
        service.smtp_port = 465
        with patch("app.services.email_service.SessionLocal") as mock_sl, \
             patch("app.services.email_service.smtplib.SMTP_SSL") as mock_smtp_ssl, \
             patch("app.services.email_service.settings") as mock_settings:
            mock_settings.SMTP_PORT = 465
            mock_settings.SMTP_HOST = "smtp.test.com"
            mock_settings.SMTP_USER = "u"
            mock_settings.SMTP_PASSWORD = "p"
            mock_settings.SMTP_FROM_NAME = "T"
            mock_settings.SMTP_FROM_EMAIL = "t@t.com"
            mock_db = MagicMock()
            mock_sl.return_value = mock_db
            mock_log = MagicMock()
            mock_log.id = 1
            mock_db.get.return_value = mock_log
            mock_server = MagicMock()
            mock_smtp_ssl.return_value = mock_server
            result = service.send_email(to_email="t@t.com", subject="S", body="B")
        assert result is True

    def test_send_error_updates_log(self, service):
        with patch("app.services.email_service.SessionLocal") as mock_sl, \
             patch("app.services.email_service.smtplib.SMTP") as mock_smtp:
            mock_db = MagicMock()
            mock_sl.return_value = mock_db
            mock_log = MagicMock()
            mock_log.id = 1
            mock_db.get.return_value = mock_log
            mock_smtp.side_effect = Exception("SMTP fail")
            with pytest.raises(Exception, match="SMTP fail"):
                service.send_email(to_email="t@t.com", subject="S", body="B")

    def test_dict_attachment(self, service):
        with patch("app.services.email_service.SessionLocal") as mock_sl, \
             patch("app.services.email_service.smtplib.SMTP") as mock_smtp:
            mock_db = MagicMock()
            mock_sl.return_value = mock_db
            mock_log = MagicMock()
            mock_log.id = 1
            mock_db.get.return_value = mock_log
            mock_server = MagicMock()
            mock_smtp.return_value = mock_server
            result = service.send_email(
                to_email="t@t.com", subject="S", body="B",
                attachments=[{"filename": "test.pdf", "content": b"data"}],
            )
        assert result is True

    def test_invalid_attachment_skipped(self, service):
        with patch("app.services.email_service.SessionLocal") as mock_sl, \
             patch("app.services.email_service.smtplib.SMTP") as mock_smtp:
            mock_db = MagicMock()
            mock_sl.return_value = mock_db
            mock_log = MagicMock()
            mock_log.id = 1
            mock_db.get.return_value = mock_log
            mock_server = MagicMock()
            mock_smtp.return_value = mock_server
            result = service.send_email(
                to_email="t@t.com", subject="S", body="B",
                attachments=[12345],
            )
        assert result is True

    def test_log_creation_failure_continues(self, service):
        with patch("app.services.email_service.SessionLocal") as mock_sl, \
             patch("app.services.email_service.smtplib.SMTP") as mock_smtp:
            mock_sl.side_effect = [Exception("DB fail"), MagicMock()]
            mock_server = MagicMock()
            mock_smtp.return_value = mock_server
            result = service.send_email(to_email="t@t.com", subject="S", body="B")
        assert result is True
