"""Сервис чата между диспетчером и водителем."""
import logging
from sqlalchemy.orm import Session
from sqlalchemy import select
from datetime import datetime, UTC

logger = logging.getLogger(__name__)


def send_chat_message(
    db: Session,
    sender_id: int,
    recipient_id: int,
    text: str,
    shift_task_id: int | None = None,
    message_type: str = "text",
    file_url: str | None = None,
    attachments: dict | None = None,
) -> dict:
    """Отправить сообщение в чат (синхронная версия)."""
    from app.models.chat import ChatMessage, RequestChat

    # Если shift_task_id не передан, используем 0 как fallback
    if not shift_task_id:
        shift_task_id = 0

    # Ищем существующий чат по request_id
    room = db.execute(
        select(RequestChat).where(RequestChat.request_id == shift_task_id)
    ).scalar_one_or_none()

    # Если не нашли — создаём новый
    if not room:
        room = RequestChat(
            request_id=shift_task_id,
            created_at=datetime.now(UTC),
        )
        db.add(room)
        db.flush()

    msg = ChatMessage(
        chat_id=room.id,
        sender_id=sender_id,
        content=text,
        message_type=message_type,  # ← Используем переданный тип
        sender_type="user",
        file_url=file_url,          # ← Поддержка URL файла
        attachments=attachments,    # ← Поддержка вложений
        created_at=datetime.now(UTC),
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    logger.info(f"Chat message {msg.id}: user {sender_id} → {recipient_id} (type={message_type})")
    return {
        "message_id": msg.id,
        "room_id": room.id,
        "sent_at": msg.created_at.isoformat(),
        "message_type": message_type,
        "file_url": file_url,
    }