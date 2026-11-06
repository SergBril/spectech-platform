"""Coverage tests for rbac_email_service."""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


class TestSendRoleChangeEmail:
    """Cover send_role_change_email (lines 10-41)."""

    def test_no_email_skips(self):
        from app.services.rbac_email_service import send_role_change_email
        user = SimpleNamespace(id=1, email=None, full_name="Test")
        db = MagicMock()
        send_role_change_email(user, "viewer", "admin", db)
        # Should not raise, just log warning

    def test_success_sends_email(self):
        from app.services.rbac_email_service import send_role_change_email
        user = SimpleNamespace(id=1, email="test@example.com", full_name="Ivan")
        db = MagicMock()
        with patch("app.services.email_service.send_email") as mock_send:
            send_role_change_email(user, "viewer", "admin", db)
        mock_send.assert_called_once()
        call_args = mock_send.call_args[0]
        assert call_args[0] == "test@example.com"
        assert "admin" in call_args[1]

    def test_import_error_fallback(self):
        from app.services.rbac_email_service import send_role_change_email
        user = SimpleNamespace(id=1, email="test@example.com", full_name="Ivan")
        db = MagicMock()
        # Simulate ImportError by making send_email unavailable
        with patch.dict("sys.modules", {"app.services.email_service": None}):
            send_role_change_email(user, "viewer", "admin", db)
        # Should not raise

    def test_send_error_logged(self):
        from app.services.rbac_email_service import send_role_change_email
        user = SimpleNamespace(id=1, email="test@example.com", full_name=None)
        db = MagicMock()
        with patch("app.services.email_service.send_email", side_effect=Exception("SMTP fail")):
            send_role_change_email(user, "viewer", "admin", db)
        # Should not raise, error is logged

    def test_uses_email_as_name_fallback(self):
        from app.services.rbac_email_service import send_role_change_email
        user = SimpleNamespace(id=1, email="test@example.com", full_name=None)
        db = MagicMock()
        with patch("app.services.email_service.send_email") as mock_send:
            send_role_change_email(user, "viewer", "admin", db)
        body = mock_send.call_args[0][2]
        assert "test@example.com" in body
