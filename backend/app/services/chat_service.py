"""Сервис для работы с чатом по заявке."""
import json
import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.chat import ChatMessage, ChatParticipant, RequestChat

logger = logging.getLogger("spectech.chat_service")


class ChatService:
    """Сервис для работы с чатами."""

    @staticmethod
    def ensure_chat_exists(db: Session, request_id: int) -> RequestChat:
        """Создаёт чат для заявки, если его нет."""
        chat = (
            db.query(RequestChat)
            .filter(RequestChat.request_id == request_id)
            .first()
        )
        if not chat:
            chat = RequestChat(request_id=request_id)
            db.add(chat)
            db.commit()
            db.refresh(chat)
            logger.info("Chat created for request_id=%s", request_id)
        return chat

    @staticmethod
    def add_participant(
        db: Session, chat_id: int, user_id: int, role: str
    ) -> ChatParticipant:
        """Добавляет участника в чат."""
        existing = (
            db.query(ChatParticipant)
            .filter(
                ChatParticipant.chat_id == chat_id,
                ChatParticipant.user_id == user_id,
            )
            .first()
        )
        if existing:
            if existing.left_at is not None:
                existing.left_at = None
                existing.role = role
                db.commit()
                db.refresh(existing)
            return existing

        participant = ChatParticipant(
            chat_id=chat_id, user_id=user_id, role=role
        )
        db.add(participant)
        db.commit()
        db.refresh(participant)
        return participant

    @staticmethod
    def send_message(
        db: Session,
        chat_id: int,
        sender_id: int | None,
        content: str,
        message_type: str = "text",
        sender_type: str = "user",
        attachments: dict | None = None,
        reply_to_message_id: int | None = None,
    ) -> ChatMessage:
        """Отправляет сообщение в чат."""
        message = ChatMessage(
            chat_id=chat_id,
            sender_id=sender_id,
            sender_type=sender_type,
            message_type=message_type,
            content=content,
            attachments=attachments,
            reply_to_message_id=reply_to_message_id,
        )
        db.add(message)
        db.commit()
        db.refresh(message)
        return message

    @staticmethod
    def send_system_event(
        db: Session, chat_id: int, event_type: str, data: dict | None = None
    ) -> ChatMessage:
        """Отправляет системное событие в чат."""
        content = json.dumps(
            {"event": event_type, "data": data or {}}, ensure_ascii=False
        )
        return ChatService.send_message(
            db=db,
            chat_id=chat_id,
            sender_id=None,
            content=content,
            message_type="system_event",
            sender_type="system",
        )

    @staticmethod
    def get_chat_by_request(db: Session, request_id: int) -> RequestChat | None:
        """Возвращает чат по заявке."""
        return (
            db.query(RequestChat)
            .filter(RequestChat.request_id == request_id)
            .first()
        )

    @staticmethod
    def is_participant(db: Session, chat_id: int, user_id: int) -> bool:
        """Проверяет, является ли пользователь участником чата."""
        return (
            db.query(ChatParticipant)
            .filter(
                ChatParticipant.chat_id == chat_id,
                ChatParticipant.user_id == user_id,
                ChatParticipant.left_at == None,  # noqa: E711
            )
            .first()
            is not None
        )

    @staticmethod
    def mark_as_read(db: Session, message_id: int, user_id: int) -> None:
        """Помечает сообщение как прочитанное пользователем."""
        message = db.get(ChatMessage, message_id)
        if not message:
            return
        is_read_by = message.is_read_by or {}
        if str(user_id) not in is_read_by:
            is_read_by[str(user_id)] = datetime.utcnow().isoformat()
            message.is_read_by = is_read_by
            db.commit()


chat_service = ChatService()