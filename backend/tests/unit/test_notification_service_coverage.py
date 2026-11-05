"""Coverage tests for notification_service."""
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_db():
    return MagicMock()


class TestCreateNotification:
    """Cover create_notification (lines 11-69)."""

    @pytest.mark.asyncio
    async def test_success_with_company(self, mock_db):
        from app.services.notification_service import create_notification
        notif = SimpleNamespace(id=1, title="Test", body="Body", channel="in_app", is_read=False, sent_at=datetime.now(UTC))
        user = SimpleNamespace(id=1, company_id=7)
        mock_db.refresh.side_effect = lambda n: setattr(n, "id", 1) if not getattr(n, "id", None) else None
        q = MagicMock()
        q.filter.return_value.first.return_value = user
        mock_db.query.return_value = q
        mock_ws = MagicMock()
        mock_ws.broadcast_to_company = AsyncMock()
        with patch("app.services.notification_service.manager", mock_ws):
            result = await create_notification(mock_db, 1, "Test", "Body")
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called()
        mock_ws.broadcast_to_company.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_user_company(self, mock_db):
        from app.services.notification_service import create_notification
        mock_db.refresh.side_effect = lambda n: setattr(n, "id", 1) if not getattr(n, "id", None) else None
        q = MagicMock()
        q.filter.return_value.first.return_value = None
        mock_db.query.return_value = q
        result = await create_notification(mock_db, 1, "Test", "Body")
        assert result is not None

    @pytest.mark.asyncio
    async def test_with_alert_id(self, mock_db):
        from app.services.notification_service import create_notification
        mock_db.refresh.side_effect = lambda n: setattr(n, "id", 1) if not getattr(n, "id", None) else None
        q = MagicMock()
        q.filter.return_value.first.return_value = SimpleNamespace(id=1, company_id=None)
        mock_db.query.return_value = q
        result = await create_notification(mock_db, 1, "Alert", "Body", alert_id=5)
        assert result is not None


class TestGetUnreadCount:
    """Cover get_unread_count (lines 71-78)."""

    @pytest.mark.asyncio
    async def test_returns_count(self, mock_db):
        from app.services.notification_service import get_unread_count
        q = MagicMock()
        q.filter.return_value.count.return_value = 5
        mock_db.query.return_value = q
        result = await get_unread_count(mock_db, 1)
        assert result == 5


class TestMarkNotificationRead:
    """Cover mark_notification_read (lines 80-96)."""

    @pytest.mark.asyncio
    async def test_found_and_marked(self, mock_db):
        from app.services.notification_service import mark_notification_read
        notif = SimpleNamespace(is_read=False, read_at=None)
        q = MagicMock()
        q.filter.return_value.first.return_value = notif
        mock_db.query.return_value = q
        result = await mark_notification_read(mock_db, 1, 1)
        assert result is True
        assert notif.is_read is True
        mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_not_found(self, mock_db):
        from app.services.notification_service import mark_notification_read
        q = MagicMock()
        q.filter.return_value.first.return_value = None
        mock_db.query.return_value = q
        result = await mark_notification_read(mock_db, 999, 1)
        assert result is False


class TestMarkAllRead:
    """Cover mark_all_read (lines 98-106)."""

    @pytest.mark.asyncio
    async def test_returns_count(self, mock_db):
        from app.services.notification_service import mark_all_read
        q = MagicMock()
        q.filter.return_value.update.return_value = 3
        mock_db.query.return_value = q
        result = await mark_all_read(mock_db, 1)
        assert result == 3
        mock_db.commit.assert_called()
