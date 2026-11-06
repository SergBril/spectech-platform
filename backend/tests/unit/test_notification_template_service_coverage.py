"""Coverage tests for notification_template_service."""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_db():
    return MagicMock()


class TestRenderTemplate:
    """Cover render_template (lines 66-96)."""

    def test_from_db_success(self, mock_db):
        from app.services.notification_template_service import render_template
        tmpl = SimpleNamespace(
            code="role_change", channel="max",
            subject="Смена роли", body="Роль: {old_role} -> {new_role}",
        )
        mock_db.execute.return_value.scalar_one_or_none.return_value = tmpl
        result = render_template(mock_db, "role_change", "max", old_role="viewer", new_role="admin")
        assert result["subject"] == "Смена роли"
        assert "viewer" in result["body"]
        assert "admin" in result["body"]

    def test_from_db_no_subject(self, mock_db):
        from app.services.notification_template_service import render_template
        tmpl = SimpleNamespace(
            code="test", channel="max",
            subject=None, body="Body: {val}",
        )
        mock_db.execute.return_value.scalar_one_or_none.return_value = tmpl
        result = render_template(mock_db, "test", "max", val="hello")
        assert result["subject"] == ""
        assert result["body"] == "Body: hello"

    def test_from_db_missing_variable_fallback(self, mock_db):
        from app.services.notification_template_service import render_template
        tmpl = SimpleNamespace(
            code="role_change", channel="max",
            subject="Test", body="Missing: {undefined_var}",
        )
        mock_db.execute.return_value.scalar_one_or_none.return_value = tmpl
        # Falls back to DEFAULT_TEMPLATES
        result = render_template(mock_db, "role_change", "max", old_role="a", new_role="b")
        assert result is not None
        assert "a" in result["body"]

    def test_fallback_to_defaults(self, mock_db):
        from app.services.notification_template_service import render_template
        mock_db.execute.return_value.scalar_one_or_none.return_value = None
        result = render_template(mock_db, "act_signed", "email", act_number="ACT-001")
        assert result is not None
        assert "ACT-001" in result["body"]

    def test_fallback_missing_var_returns_unformatted(self, mock_db):
        from app.services.notification_template_service import render_template
        mock_db.execute.return_value.scalar_one_or_none.return_value = None
        # Call without required vars -> KeyError caught, returns raw template
        result = render_template(mock_db, "act_signed", "fcm")
        assert result is not None
        assert "{act_number}" in result["body"]

    def test_unknown_code_returns_none(self, mock_db):
        from app.services.notification_template_service import render_template
        mock_db.execute.return_value.scalar_one_or_none.return_value = None
        result = render_template(mock_db, "nonexistent_code", "email")
        assert result is None


class TestInitDefaultTemplates:
    """Cover init_default_templates (lines 98-end)."""

    def test_creates_all(self, mock_db):
        from app.services.notification_template_service import init_default_templates
        mock_db.execute.return_value.scalar_one_or_none.return_value = None
        created = init_default_templates(mock_db)
        assert created > 0
        assert mock_db.add.call_count == created
        mock_db.commit.assert_called_once()

    def test_skips_existing(self, mock_db):
        from app.services.notification_template_service import init_default_templates
        existing = SimpleNamespace(code="role_change", channel="max")
        mock_db.execute.return_value.scalar_one_or_none.return_value = existing
        created = init_default_templates(mock_db)
        assert created == 0
        mock_db.add.assert_not_called()
        mock_db.commit.assert_called_once()
