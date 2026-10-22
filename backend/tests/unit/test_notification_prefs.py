"""Unit tests for notification_prefs_helper."""
import pytest
from unittest.mock import MagicMock, patch
from app.services.notification_prefs_helper import should_notify


class TestShouldNotify:
    """Tests for should_notify function."""

    def test_no_prefs_returns_true(self):
        """When user has no preferences, all notifications enabled."""
        db = MagicMock()
        db.execute.return_value.scalar_one_or_none.return_value = None
        assert should_notify(db, 1, "role_change", "max") is True
        assert should_notify(db, 1, "overdue", "email") is True

    def test_pref_enabled(self):
        """When preference is explicitly True."""
        db = MagicMock()
        prefs = MagicMock()
        prefs.notify_role_change_max = True
        db.execute.return_value.scalar_one_or_none.return_value = prefs
        assert should_notify(db, 1, "role_change", "max") is True

    def test_pref_disabled(self):
        """When preference is explicitly False."""
        db = MagicMock()
        prefs = MagicMock()
        prefs.notify_role_change_email = False
        db.execute.return_value.scalar_one_or_none.return_value = prefs
        assert should_notify(db, 1, "role_change", "email") is False

    def test_overdue_max_disabled(self):
        """Overdue MAX notification disabled."""
        db = MagicMock()
        prefs = MagicMock()
        prefs.notify_overdue_max = False
        db.execute.return_value.scalar_one_or_none.return_value = prefs
        assert should_notify(db, 1, "overdue", "max") is False

    def test_act_signed_email_enabled(self):
        """Act signed email enabled."""
        db = MagicMock()
        prefs = MagicMock()
        prefs.notify_act_signed_email = True
        db.execute.return_value.scalar_one_or_none.return_value = prefs
        assert should_notify(db, 1, "act_signed", "email") is True

    def test_unknown_attr_defaults_true(self):
        """Unknown attribute defaults to True via getattr."""
        db = MagicMock()
        prefs = MagicMock(spec=[])  # No attributes
        db.execute.return_value.scalar_one_or_none.return_value = prefs
        assert should_notify(db, 1, "unknown_event", "max") is True
