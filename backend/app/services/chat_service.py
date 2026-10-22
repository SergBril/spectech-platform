"""Сервис чата между диспетчером и водителем."""
import logging
from sqlalchemy.orm import Session
from sqlalchemy import select
from datetime import datetime, UTC

logger = logging.getLogger(__name__)


async def send_chat_message(db: Session, sender_id: int, recipient_id: int, text: str, shift_task_id: int | None = None) -> dict:
    """Отправить сообщение в чат."""
    from app.models.chat import ChatMessage, ChatRoom

    # Find or create chat room
    room = db.execute(
        select(ChatRoom).where(
            ChatRoom.participant_ids.contains([sender_id, recipient_id])
        )
    ).scalar_one_or_none()

    if not room:
        room = ChatRoom(
            participant_ids=[sender_id, recipient_id],
            shift_task_id=shift_task_id,
            created_at=datetime.now(UTC),
        )
        db.add(room)
        db.flush()

    msg = ChatMessage(
        room_id=room.id,
        sender_id=sender_id,
        text=text,
        sent_at=datetime.now(UTC),
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    logger.info(f"Chat message {msg.id}: user {sender_id} → {recipient_id}")
    return {"message_id": msg.id, "room_id": room.id}
