"""Сервис для работы с чатом по заявке."""

import json
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import select
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
    """Сервис для работы с чатами."""

    @staticmethod
    def ensure_chat_exists(db: Session, request_id: int) -> RequestChat:
        """Создаёт чат для заявки, если его нет. Бросает ValueError если заявки нет."""
        # Проверяем, что заявка существует
        request = db.get(Request, request_id)
        if not request:
            raise ValueError(f"Request {request_id} not found")

        chat = (
            db.query(RequestChat).filter(RequestChat.request_id == request_id).first()
        )
        if not chat:
            chat = RequestChat(request_id=request_id)
            db.add(chat)
            db.commit()
            db.refresh(chat)
            logger.info("Chat created for request_id=%s", request_id)
            ChatService._add_default_participants(db, chat, request_id)

        return chat

    @staticmethod
    def _add_default_participants(db: Session, chat: RequestChat, request_id: int):
        """
        Добавляет участников по умолчанию.

        ВАЖНО: ChatParticipant.user_id — это FK на users.id,
        поэтому добавляем только тех, у кого точно есть user_id:
        - created_by (диспетчер, создавший заявку) — это users.id
        """
        request = db.query(Request).filter(Request.id == request_id).first()
        if not request:
            return

        # Добавляем диспетчера (создателя заявки) — это user_id
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

        # Примечание: client_id и assigned_owner_id — это FK на contractors.id,
        # а не на users.id, поэтому мы НЕ можем их добавить как ChatParticipant.
        # Они будут добавлены при первом входе в чат через REST/WebSocket,
        # где current_user — это всегда users.id.

    @staticmethod
    def add_participant(
        db: Session, chat_id: int, user_id: int, role: str
    ) -> ChatParticipant:
        """Добавляет участника в чат."""
        # Валидируем роль
        try:
            ChatParticipantRole(role)
        except ValueError:
            raise ValueError(f"Invalid role: {role}")

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
    def send_message(
        db: Session,
        chat_id: int,
        sender_id: int | None,
        content: str,
        message_type: str = "text",
        sender_type: str = "user",
        attachments: dict | None = None,
        reply_to_message_id: int | None = None,
        mentions: dict | None = None,
    ) -> ChatMessage:
        """Отправляет сообщение в чат."""
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
            attachments=attachments,
            reply_to_message_id=reply_to_message_id,
            mentions=mentions,
        )
        db.add(message)
        db.commit()
        db.refresh(message)

        logger.info(f"Message sent in chat {chat_id} by user {sender_id}")

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
            message_type=ChatMessageType.system_event.value,
            sender_type="system",
        )

    @staticmethod
    def get_chat_by_request(db: Session, request_id: int) -> RequestChat | None:
        """Возвращает чат по заявке."""
        return (
            db.query(RequestChat).filter(RequestChat.request_id == request_id).first()
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

    @staticmethod
    def get_messages_cursor(
        db: Session,
        chat_id: int,
        cursor: Optional[int] = None,
        limit: int = 50,
        message_type: Optional[str] = None,
    ) -> tuple[list[ChatMessage], bool]:
        """
        Получает сообщения с cursor-based пагинацией.

        Args:
            db: Сессия БД
            chat_id: ID чата
            cursor: ID последнего полученного сообщения (для пагинации)
            limit: Количество сообщений (макс 200)
            message_type: Фильтр по типу сообщения

        Returns:
            Tuple из (список сообщений, has_more)
        """
        query = select(ChatMessage).where(ChatMessage.chat_id == chat_id)

        if cursor:
            query = query.where(ChatMessage.id < cursor)

        if message_type:
            try:
                ChatMessageType(message_type)
                query = query.where(ChatMessage.message_type == message_type)
            except ValueError:
                pass

        # Сортируем по ID (desc для получения новых первыми)
        # Запрашиваем limit + 1 для определения has_more
        query = query.order_by(ChatMessage.id.desc()).limit(min(limit, 200) + 1)
        messages = db.scalars(query).all()

        has_more = len(messages) > limit
        if has_more:
            messages = messages[:limit]

        # Разворачиваем для хронологического порядка (старые -> новые)
        return list(reversed(messages)), has_more

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


chat_service = ChatService()