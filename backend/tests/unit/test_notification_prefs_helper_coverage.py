"""Coverage tests for notification_prefs_helper."""

from types import SimpleNamespace
from unittest.mock import MagicMock


class TestShouldNotify:
    """Cover should_notify (lines 9-28)."""

    def test_no_prefs_returns_true(self):
        from app.services.notification_prefs_helper import should_notify

        db = MagicMock()
        db.execute.return_value.scalar_one_or_none.return_value = None
        assert should_notify(db, 1, "role_change", "max") is True

    def test_pref_enabled(self):
        from app.services.notification_prefs_helper import should_notify

        prefs = SimpleNamespace(notify_role_change_max=True)
        db = MagicMock()
        db.execute.return_value.scalar_one_or_none.return_value = prefs
        assert should_notify(db, 1, "role_change", "max") is True

    def test_pref_disabled(self):
        from app.services.notification_prefs_helper import should_notify

        prefs = SimpleNamespace(notify_overdue_email=False)
        db = MagicMock()
        db.execute.return_value.scalar_one_or_none.return_value = prefs
        assert should_notify(db, 1, "overdue", "email") is False

    def test_missing_attr_defaults_true(self):
        from app.services.notification_prefs_helper import should_notify

        prefs = SimpleNamespace()  # No notify_* attributes
        db = MagicMock()
        db.execute.return_value.scalar_one_or_none.return_value = prefs
        assert should_notify(db, 1, "act_signed", "fcm") is True
