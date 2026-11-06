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

    def test_import_error_fallback(self):
        """send_email doesn't exist as module-level function -> ImportError -> fallback."""
        from app.services.rbac_email_service import send_role_change_email
        user = SimpleNamespace(id=1, email="test@example.com", full_name="Ivan")
        db = MagicMock()
        # The real import will fail since send_email is not a module-level function
        send_role_change_email(user, "viewer", "admin", db)
        # Should not raise - falls back to logging

    def test_send_error_logged(self):
        """If send_email were available but raised -> except Exception branch."""
        from app.services.rbac_email_service import send_role_change_email
        user = SimpleNamespace(id=1, email="test@example.com", full_name=None)
        db = MagicMock()
        # Inject a mock send_email into the email_service module temporarily
        import app.services.email_service as email_mod
        original = getattr(email_mod, "send_email", None)
        email_mod.send_email = MagicMock(side_effect=Exception("SMTP fail"))
        try:
            send_role_change_email(user, "viewer", "admin", db)
        finally:
            if original is None:
                delattr(email_mod, "send_email")
            else:
                email_mod.send_email = original
        # Should not raise

    def test_success_with_injected_send_email(self):
        """Inject send_email into module to test success path."""
        from app.services.rbac_email_service import send_role_change_email
        user = SimpleNamespace(id=1, email="test@example.com", full_name="Ivan")
        db = MagicMock()
        import app.services.email_service as email_mod
        original = getattr(email_mod, "send_email", None)
        mock_send = MagicMock()
        email_mod.send_email = mock_send
        try:
            send_role_change_email(user, "viewer", "admin", db)
        finally:
            if original is None:
                delattr(email_mod, "send_email")
            else:
                email_mod.send_email = original
        mock_send.assert_called_once()
        call_args = mock_send.call_args[0]
        assert call_args[0] == "test@example.com"
        assert "admin" in call_args[1]

    def test_uses_email_as_name_fallback(self):
        """full_name is None -> uses email in greeting."""
        from app.services.rbac_email_service import send_role_change_email
        user = SimpleNamespace(id=1, email="test@example.com", full_name=None)
        db = MagicMock()
        import app.services.email_service as email_mod
        original = getattr(email_mod, "send_email", None)
        mock_send = MagicMock()
        email_mod.send_email = mock_send
        try:
            send_role_change_email(user, "viewer", "admin", db)
        finally:
            if original is None:
                delattr(email_mod, "send_email")
            else:
                email_mod.send_email = original
        body = mock_send.call_args[0][2]
        assert "test@example.com" in body
