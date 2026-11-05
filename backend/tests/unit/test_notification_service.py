from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.notification_service import (
    create_notification,
    get_unread_count,
    mark_all_read,
    mark_notification_read,
)


@pytest.fixture
def mock_db():
    return MagicMock()


class TestCreateNotification:
    """Tests for create_notification"""

    @pytest.mark.asyncio
    async def test_create_success_with_company(self, mock_db):
        mock_notification = MagicMock()
        mock_notification.id = 1
        mock_notification.title = "Test"
        mock_notification.body = "Body"
        mock_notification.channel = "in_app"
        mock_notification.is_read = False
        mock_notification.sent_at = datetime(2026, 11, 2, 10, 0)

        mock_user = MagicMock()
        mock_user.company_id = 7

        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock(side_effect=lambda n: setattr(n, "id", 1))
        mock_db.query = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        with patch("app.services.notification_service.manager") as mock_manager:
            mock_manager.broadcast_to_company = AsyncMock()
            await create_notification(db=mock_db, user_id=5, title="Test", body="Body")

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_manager.broadcast_to_company.assert_called_once()
        call_kwargs = mock_manager.broadcast_to_company.call_args
        assert call_kwargs.kwargs["company_id"] == 7

    @pytest.mark.asyncio
    async def test_create_no_company(self, mock_db):
        mock_user = MagicMock()
        mock_user.company_id = None

        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()
        mock_db.query = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        with patch("app.services.notification_service.manager") as mock_manager:
            mock_manager.broadcast_to_company = AsyncMock()
            await create_notification(db=mock_db, user_id=5, title="Test", body="Body")

        mock_manager.broadcast_to_company.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_with_alert_id(self, mock_db):
        mock_user = MagicMock()
        mock_user.company_id = 7

        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()
        mock_db.query = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        with patch("app.services.notification_service.manager") as mock_manager:
            mock_manager.broadcast_to_company = AsyncMock()
            await create_notification(
                db=mock_db, user_id=5, title="Alert", body="!", alert_id=42
            )

        # Verify Notification was created with alert_id
        added_obj = mock_db.add.call_args[0][0]
        assert added_obj.alert_id == 42


class TestGetUnreadCount:
    """Tests for get_unread_count"""

    @pytest.mark.asyncio
    async def test_returns_count(self, mock_db):
        mock_query = MagicMock()
        mock_db.query = MagicMock(return_value=mock_query)
        mock_query.filter.return_value.count.return_value = 5

        result = await get_unread_count(mock_db, user_id=5)

        assert result == 5
        mock_query.filter.return_value.count.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_zero(self, mock_db):
        mock_query = MagicMock()
        mock_db.query = MagicMock(return_value=mock_query)
        mock_query.filter.return_value.count.return_value = 0

        result = await get_unread_count(mock_db, user_id=5)
        assert result == 0


class TestMarkNotificationRead:
    """Tests for mark_notification_read"""

    @pytest.mark.asyncio
    async def test_mark_read_success(self, mock_db):
        mock_notification = MagicMock()
        mock_notification.is_read = False

        mock_query = MagicMock()
        mock_db.query = MagicMock(return_value=mock_query)
        mock_query.filter.return_value.first.return_value = mock_notification
        mock_db.commit = MagicMock()

        result = await mark_notification_read(mock_db, notification_id=1, user_id=5)

        assert result is True
        assert mock_notification.is_read is True
        assert mock_notification.read_at is not None
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_mark_read_not_found(self, mock_db):
        mock_query = MagicMock()
        mock_db.query = MagicMock(return_value=mock_query)
        mock_query.filter.return_value.first.return_value = None

        result = await mark_notification_read(mock_db, notification_id=999, user_id=5)

        assert result is False
        mock_db.commit.assert_not_called()


class TestMarkAllRead:
    """Tests for mark_all_read"""

    @pytest.mark.asyncio
    async def test_mark_all_success(self, mock_db):
        mock_query = MagicMock()
        mock_db.query = MagicMock(return_value=mock_query)
        mock_query.filter.return_value.update.return_value = 3
        mock_db.commit = MagicMock()

        result = await mark_all_read(mock_db, user_id=5)

        assert result == 3
        mock_query.filter.return_value.update.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_mark_all_none_unread(self, mock_db):
        mock_query = MagicMock()
        mock_db.query = MagicMock(return_value=mock_query)
        mock_query.filter.return_value.update.return_value = 0
        mock_db.commit = MagicMock()

        result = await mark_all_read(mock_db, user_id=5)
        assert result == 0
