"""Coverage tests for audit_service."""
from unittest.mock import MagicMock, patch


class TestLogAction:
    """Cover log_action (lines 12-35)."""

    def test_success(self):
        from app.services.audit_service import log_action
        db = MagicMock()
        with patch("app.services.audit_service.AuditLog") as MockAuditLog:
            mock_entry = MagicMock()
            MockAuditLog.return_value = mock_entry
            log_action(db, user_id=1, action="login", resource_type="user",
                       resource_id=42, details="test", ip_address="127.0.0.1")
        db.add.assert_called_once_with(mock_entry)
        db.commit.assert_called_once()

    def test_truncates_details(self):
        from app.services.audit_service import log_action
        db = MagicMock()
        long_details = "x" * 2000
        with patch("app.services.audit_service.AuditLog") as MockAuditLog:
            log_action(db, user_id=1, action="test", details=long_details)
        call_kwargs = MockAuditLog.call_args[1]
        assert len(call_kwargs["details"]) == 1000

    def test_none_details(self):
        from app.services.audit_service import log_action
        db = MagicMock()
        with patch("app.services.audit_service.AuditLog") as MockAuditLog:
            log_action(db, user_id=None, action="system_event")
        call_kwargs = MockAuditLog.call_args[1]
        assert call_kwargs["details"] is None
        assert call_kwargs["user_id"] is None

    def test_exception_rollback(self):
        from app.services.audit_service import log_action
        db = MagicMock()
        db.add.side_effect = Exception("DB error")
        with patch("app.services.audit_service.AuditLog"):
            log_action(db, user_id=1, action="test")
        db.rollback.assert_called_once()
        db.commit.assert_not_called()
