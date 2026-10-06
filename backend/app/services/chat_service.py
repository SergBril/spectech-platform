"""Сервис для работы с чатами."""

import json
import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.chat import (
    ChatMessage,
    ChatMessageType,
    ChatParticipant,
    ChatParticipantRole,
    RequestChat,
)
from app.models.dispatch import Request

logger = logging.getLogger("spectech.chat_service")


class ChatService:
    """Сервис для управления чатами."""

    @staticmethod
    def get_chat(db: Session, chat_id: int) -> RequestChat | None:
        return db.get(RequestChat, chat_id)

    @staticmethod
    def get_chat_by_request(db: Session, request_id: int) -> RequestChat | None:
        return (
            db.query(RequestChat)
            .filter(RequestChat.request_id == request_id)
            .first()
        )

    @staticmethod
    def ensure_chat_exists(db: Session, request_id: int) -> RequestChat:
        """Создаёт чат для заявки. Бросает ValueError если заявки нет."""
        request = db.get(Request, request_id)
        if not request:
            raise ValueError(f"Request {request_id} not found")

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
            ChatService._add_default_participants(db, chat, request)

        return chat

    @staticmethod
    def _add_default_participants(db: Session, chat: RequestChat, request: Request):
        """
        Добавляет участников по умолчанию.
        ВАЖНО: ChatParticipant.user_id — это FK на users.id.
        - created_by (users.id) — добавляем как dispatcher
        - assigned_operator_id, client_id, assigned_owner_id — это contractors/employees, пропускаем
        """
        if request.created_by:
            ChatService.add_participant(
                db,
                chat.id,
                request.created_by,
                ChatParticipantRole.dispatcher.value,
            )
            logger.info(
                "Auto-added dispatcher user_id=%s to chat_id=%s",
                request.created_by,
                chat.id,
            )

    @staticmethod
    def add_participant(
        db: Session, chat_id: int, user_id: int, role: str
    ) -> ChatParticipant:
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

        participant = ChatParticipant(chat_id=chat_id, user_id=user_id, role=role)
        db.add(participant)
        db.commit()
        db.refresh(participant)
        return participant

    @staticmethod
    def is_participant(db: Session, chat_id: int, user_id: int) -> bool:
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
    def send_message(
        db: Session,
        chat_id: int,
        sender_id: int | None,
        content: str | None = None,
        message_type: str = "text",
        sender_type: str = "user",
        file_url: str | None = None,
        attachments: dict | None = None,
        reply_to_message_id: int | None = None,
        mentions: dict | None = None,
    ) -> ChatMessage:
        """
        Отправляет сообщение в чат.
        ✅ Использует только поля, которые реально есть в модели ChatMessage.
        """
        # Валидируем тип сообщения
        try:
            ChatMessageType(message_type)
        except ValueError:
            raise ValueError(f"Invalid message type: {message_type}")

        message = ChatMessage(
            chat_id=chat_id,
            sender_id=sender_id,
            sender_type=sender_type,
            message_type=message_type,
            content=content,
            file_url=file_url,
            attachments=attachments,
            reply_to_message_id=reply_to_message_id,
            mentions=mentions,
        )
        db.add(message)
        db.commit()
        db.refresh(message)
        return message

    @staticmethod
    def send_system_event(
        db: Session, chat_id: int, event_type: str, data: dict | None = None
    ) -> ChatMessage:
        """Отправляет системное событие в чат (user_joined, user_left и т.д.)."""
        content = json.dumps(
            {"event": event_type, "data": data or {}}, ensure_ascii=False
        )
        return ChatService.send_message(
            db=db,
            chat_id=chat_id,
            sender_id=None,
            content=content,
            message_type=ChatMessageType.system_event.value,
            sender_type="system",
        )

    @staticmethod
    def get_messages(
        db: Session,
        chat_id: int,
        cursor: int | None = None,
        limit: int = 50,
        message_type: str | None = None,
    ) -> list[ChatMessage]:
        query = db.query(ChatMessage).filter(ChatMessage.chat_id == chat_id)
        if cursor:
            query = query.filter(ChatMessage.id < cursor)
        if message_type:
            query = query.filter(ChatMessage.message_type == message_type)
        return query.order_by(ChatMessage.id.desc()).limit(limit).all()

    @staticmethod
    def get_messages_cursor(
        db: Session,
        chat_id: int,
        cursor: int | None = None,
        limit: int = 50,
        message_type: str | None = None,
    ) -> tuple[list[ChatMessage], bool]:
        """
        Cursor-based пагинация.
        Возвращает (список сообщений, has_more).
        Сообщения отсортированы от старых к новым.
        """
        query = db.query(ChatMessage).filter(ChatMessage.chat_id == chat_id)
        if cursor:
            query = query.filter(ChatMessage.id < cursor)
        if message_type:
            query = query.filter(ChatMessage.message_type == message_type)

        # Берём limit + 1, чтобы понять, есть ли ещё сообщения
        messages = query.order_by(ChatMessage.id.desc()).limit(limit + 1).all()
        has_more = len(messages) > limit

        if has_more:
            messages = messages[:limit]

        # Разворачиваем: самое старое сообщение — под индексом 0
        messages.reverse()
        return messages, has_more

    @staticmethod
    def get_unread_count(db: Session, chat_id: int, user_id: int) -> int:
        """Возвращает количество непрочитанных сообщений для пользователя."""
        messages = (
            db.query(ChatMessage)
            .filter(
                ChatMessage.chat_id == chat_id,
                ChatMessage.sender_id != user_id,
            )
            .all()
        )

        unread = 0
        for msg in messages:
            is_read_by = msg.is_read_by or {}
            if str(user_id) not in is_read_by:
                unread += 1
        return unread

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