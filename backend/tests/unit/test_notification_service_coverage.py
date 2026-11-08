"""Coverage tests for notification_service."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_db():
    return MagicMock()


class TestCreateNotification:
    """Cover create_notification (lines 10-65)."""

    @pytest.mark.asyncio
    async def test_creates_and_broadcasts(self, mock_db):
        from app.services.notification_service import create_notification

        notif = SimpleNamespace(
            id=1,
            title="T",
            body="B",
            channel="in_app",
            is_read=False,
            sent_at=datetime(2026, 11, 6),
        )
        mock_db.refresh = MagicMock()
        # Make db.query().filter().first() return user with company_id
        user = SimpleNamespace(id=42, company_id=7)
        mock_db.query.return_value.filter.return_value.first.return_value = user

        with (
            patch("app.services.notification_service.Notification") as MockNotif,
            patch("app.services.notification_service.manager") as mock_mgr,
        ):
            MockNotif.return_value = notif
            mock_mgr.broadcast_to_company = AsyncMock()
            result = await create_notification(mock_db, 42, "T", "B", alert_id=10)

        assert result == notif
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_mgr.broadcast_to_company.assert_called_once()
        call_kwargs = mock_mgr.broadcast_to_company.call_args[1]
        assert call_kwargs["company_id"] == 7

    @pytest.mark.asyncio
    async def test_no_user_skips_broadcast(self, mock_db):
        from app.services.notification_service import create_notification

        notif = SimpleNamespace(
            id=1,
            title="T",
            body="B",
            channel="in_app",
            is_read=False,
            sent_at=datetime(2026, 11, 6),
        )
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with (
            patch("app.services.notification_service.Notification") as MockNotif,
            patch("app.services.notification_service.manager") as mock_mgr,
        ):
            MockNotif.return_value = notif
            mock_mgr.broadcast_to_company = AsyncMock()
            result = await create_notification(mock_db, 999, "T", "B")

        assert result == notif
        mock_mgr.broadcast_to_company.assert_not_called()

    @pytest.mark.asyncio
    async def test_user_no_company_skips_broadcast(self, mock_db):
        from app.services.notification_service import create_notification

        notif = SimpleNamespace(
            id=1,
            title="T",
            body="B",
            channel="in_app",
            is_read=False,
            sent_at=datetime(2026, 11, 6),
        )
        user = SimpleNamespace(id=42, company_id=None)
        mock_db.query.return_value.filter.return_value.first.return_value = user

        with (
            patch("app.services.notification_service.Notification") as MockNotif,
            patch("app.services.notification_service.manager") as mock_mgr,
        ):
            MockNotif.return_value = notif
            mock_mgr.broadcast_to_company = AsyncMock()
            result = await create_notification(mock_db, 42, "T", "B")

        assert result == notif
        mock_mgr.broadcast_to_company.assert_not_called()


class TestGetUnreadCount:
    """Cover get_unread_count (lines 68-73)."""

    @pytest.mark.asyncio
    async def test_returns_count(self, mock_db):
        from app.services.notification_service import get_unread_count

        mock_db.query.return_value.filter.return_value.count.return_value = 5
        result = await get_unread_count(mock_db, 42)
        assert result == 5


class TestMarkNotificationRead:
    """Cover mark_notification_read (lines 76-90)."""

    @pytest.mark.asyncio
    async def test_marks_read(self, mock_db):
        from app.services.notification_service import mark_notification_read

        notif = SimpleNamespace(is_read=False, read_at=None)
        mock_db.query.return_value.filter.return_value.first.return_value = notif
        result = await mark_notification_read(mock_db, 1, 42)
        assert result is True
        assert notif.is_read is True
        assert notif.read_at is not None
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_not_found_returns_false(self, mock_db):
        from app.services.notification_service import mark_notification_read

        mock_db.query.return_value.filter.return_value.first.return_value = None
        result = await mark_notification_read(mock_db, 999, 42)
        assert result is False
        mock_db.commit.assert_not_called()


class TestMarkAllRead:
    """Cover mark_all_read (lines 93-101)."""

    @pytest.mark.asyncio
    async def test_updates_all(self, mock_db):
        from app.services.notification_service import mark_all_read

        mock_db.query.return_value.filter.return_value.update.return_value = 3
        result = await mark_all_read(mock_db, 42)
        assert result == 3
        mock_db.commit.assert_called_once()
