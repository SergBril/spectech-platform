"""Сервис управления уведомлениями."""

from datetime import datetime

from sqlalchemy.orm import Session

from app.models.telematics import Notification
from app.services.websocket_manager import manager


async def create_notification(
    db: Session,
    user_id: int,
    title: str,
    body: str,
    channel: str = "in_app",
    alert_id: int | None = None,
) -> Notification:
    """
    Создаёт уведомление и отправляет его через WebSocket.

    Args:
        db: Database session
        user_id: ID получателя
        title: Заголовок уведомления
        body: Текст уведомления
        channel: Канал доставки (in_app, email, telegram)
        alert_id: ID связанного алерта (опционально)

    Returns:
        Созданный объект Notification
    """
    notification = Notification(
        user_id=user_id,
        alert_id=alert_id,
        channel=channel,
        title=title,
        body=body,
        is_read=False,
        sent_at=datetime.utcnow(),
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)

    # Отправляем через WebSocket в реальном времени
    await manager.broadcast_to_user(
        user_id=user_id,
        message={
            "type": "new_notification",
            "data": {
                "id": notification.id,
                "title": notification.title,
                "body": notification.body,
                "channel": notification.channel,
                "is_read": notification.is_read,
                "sent_at": notification.sent_at.isoformat(),
            },
        },
    )

    return notification


async def get_unread_count(db: Session, user_id: int) -> int:
    """Возвращает количество непрочитанных уведомлений."""
    return (
        db.query(Notification)
        .filter(Notification.user_id == user_id, Notification.is_read == False)
        .count()
    )


async def mark_notification_read(
    db: Session, notification_id: int, user_id: int
) -> bool:
    """Помечает уведомление как прочитанное."""
    notification = (
        db.query(Notification)
        .filter(Notification.id == notification_id, Notification.user_id == user_id)
        .first()
    )

    if notification:
        notification.is_read = True
        notification.read_at = datetime.utcnow()
        db.commit()
        return True
    return False


async def mark_all_read(db: Session, user_id: int) -> int:
    """Помечает все уведомления пользователя как прочитанные."""
    count = (
        db.query(Notification)
        .filter(Notification.user_id == user_id, Notification.is_read == False)
        .update({"is_read": True, "read_at": datetime.utcnow()})
    )
    db.commit()
    return count
