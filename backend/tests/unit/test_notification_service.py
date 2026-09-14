"""Unit тесты для сервиса уведомлений."""

import pytest

from app.models.telematics import Notification


class TestNotificationModel:
    """Тесты модели Notification."""

    def test_create_notification(self, db_session, sample_user):
        """Можно создать уведомление."""
        notif = Notification(
            user_id=sample_user.id,
            channel="in_app",
            title="Test notification",
            body="Test body",
            is_read=False,
        )
        db_session.add(notif)
        db_session.commit()
        db_session.refresh(notif)

        assert notif.id is not None
        assert notif.user_id == sample_user.id
        assert notif.is_read is False

    @pytest.mark.asyncio
    async def test_mark_as_read(self, db_session, sample_user):
        """Уведомление можно пометить как прочитанное через сервис."""
        from app.services.notification_service import mark_notification_read

        notif = Notification(
            user_id=sample_user.id,
            channel="in_app",
            title="Test",
            body="Test",
            is_read=False,
        )
        db_session.add(notif)
        db_session.commit()
        db_session.refresh(notif)

        # ✅ await для асинхронной функции
        result = await mark_notification_read(db_session, notif.id, sample_user.id)
        assert result is True

        # Обновляем объект из БД
        db_session.refresh(notif)
        assert notif.is_read is True
        assert notif.read_at is not None


@pytest.mark.asyncio
class TestNotificationService:
    """Тесты асинхронных функций notification_service."""

    async def test_get_unread_count(self, db_session, sample_user):
        """Подсчёт непрочитанных уведомлений."""
        from app.services.notification_service import get_unread_count

        # Создаём 3 уведомления: 2 непрочитанных, 1 прочитанное
        for i in range(3):
            notif = Notification(
                user_id=sample_user.id,
                channel="in_app",
                title=f"Notif {i}",
                body="Body",
                is_read=(i == 0),  # Первое прочитанное
            )
            db_session.add(notif)
        db_session.commit()

        count = await get_unread_count(db_session, sample_user.id)
        assert count == 2

    async def test_mark_all_read(self, db_session, sample_user):
        """Пометить все уведомления как прочитанные."""
        from app.services.notification_service import mark_all_read

        # Создаём 5 непрочитанных
        for i in range(5):
            notif = Notification(
                user_id=sample_user.id,
                channel="in_app",
                title=f"Notif {i}",
                body="Body",
                is_read=False,
            )
            db_session.add(notif)
        db_session.commit()

        updated = await mark_all_read(db_session, sample_user.id)
        assert updated == 5

        # Проверяем, что все прочитаны
        from app.services.notification_service import get_unread_count

        count = await get_unread_count(db_session, sample_user.id)
        assert count == 0
