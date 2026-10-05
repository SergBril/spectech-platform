"""Endpoints для чата по заявке (REST + WebSocket)."""

import logging
from datetime import datetime
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
)
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import SessionLocal, get_db
from app.models.auth import User
from app.models.chat import (
    ChatMessage,
    ChatMessageType,
    ChatParticipant,
    ChatParticipantRole,
    RequestChat,
)
from app.services.auth_service import decode_access_token
from app.services.chat_service import chat_service
from app.services.websocket_manager import manager

logger = logging.getLogger("spectech.chat")

router = APIRouter(prefix="/chat", tags=["Chat"])


# ============================================================
# Pydantic схемы (ВАЖЕН ПОРЯДОК ОПРЕДЕЛЕНИЯ!)
# ============================================================


class MessageCreate(BaseModel):
    """Схема создания сообщения."""

    content: str = Field(..., min_length=1, max_length=5000)
    message_type: ChatMessageType = Field(default=ChatMessageType.text)
    attachments: dict | None = None
    reply_to_message_id: int | None = None
    mentions: dict | None = None


class MessageRead(BaseModel):
    """Схема чтения сообщения."""

    id: int
    chat_id: int
    sender_id: int | None = None
    sender_name: str | None = None
    sender_type: str
    message_type: str
    content: str | None = None
    attachments: dict | None = None
    reply_to_message_id: int | None = None
    is_read_by: dict | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatRead(BaseModel):
    """Схема чтения чата."""

    id: int
    request_id: int
    request_title: str | None = None
    participants_count: int
    unread_count: int
    last_message: MessageRead | None = None
    created_at: datetime


class MessagesCursorResponse(BaseModel):
    """Ответ с cursor-based пагинацией."""

    messages: list[MessageRead]
    next_cursor: int | None = None
    has_more: bool = False


# ============================================================
# Вспомогательная функция
# ============================================================


def _message_to_read(msg: ChatMessage, db: Session) -> MessageRead:
    sender_name = None
    if msg.sender_id:
        sender = db.get(User, msg.sender_id)
        sender_name = sender.email if sender else None
    return MessageRead(
        id=msg.id,
        chat_id=msg.chat_id,
        sender_id=msg.sender_id,
        sender_name=sender_name,
        sender_type=msg.sender_type,
        message_type=msg.message_type.value
        if hasattr(msg.message_type, "value")
        else msg.message_type,
        content=msg.content,
        attachments=msg.attachments,
        reply_to_message_id=msg.reply_to_message_id,
        is_read_by=msg.is_read_by,
        created_at=msg.created_at,
    )


# ============================================================
# REST Endpoints
# ============================================================


@router.get("/requests/{request_id}", response_model=ChatRead)
def get_chat_by_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Получить чат по заявке. Создаёт чат, если его нет."""
    try:
        chat = chat_service.ensure_chat_exists(db, request_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Request not found")

    if not chat_service.is_participant(db, chat.id, current_user.id):
        chat_service.add_participant(
            db, chat.id, current_user.id, ChatParticipantRole.client.value
        )

    last_msg = (
        db.query(ChatMessage)
        .filter(ChatMessage.chat_id == chat.id)
        .order_by(ChatMessage.created_at.desc())
        .first()
    )
    last_message = _message_to_read(last_msg, db) if last_msg else None

    unread_count = chat_service.get_unread_count(db, chat.id, current_user.id)

    participants_count = (
        db.query(ChatParticipant)
        .filter(
            ChatParticipant.chat_id == chat.id,
            ChatParticipant.left_at == None,  # noqa: E711
        )
        .count()
    )

    return ChatRead(
        id=chat.id,
        request_id=chat.request_id,
        request_title=f"Заявка #{chat.request_id}",
        participants_count=participants_count,
        unread_count=unread_count,
        last_message=last_message,
        created_at=chat.created_at,
    )


@router.get("/requests/{request_id}/messages", response_model=MessagesCursorResponse)
def get_chat_messages_cursor(
    request_id: int,
    cursor: int | None = Query(default=None, description="ID последнего сообщения"),
    limit: int = Query(default=50, ge=1, le=200),
    message_type: ChatMessageType | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """История сообщений чата с cursor-based пагинацией."""
    chat = chat_service.get_chat_by_request(db, request_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    messages, has_more = chat_service.get_messages_cursor(
        db=db,
        chat_id=chat.id,
        cursor=cursor,
        limit=limit,
        message_type=message_type.value if message_type else None,
    )

    # messages[0] - самое старое сообщение на текущей странице (после reverse)
    # Для следующей страницы нужны сообщения с id < messages[0].id
    next_cursor = messages[0].id if messages and has_more else None

    return MessagesCursorResponse(
        messages=[_message_to_read(msg, db) for msg in messages],
        next_cursor=next_cursor,
        has_more=has_more,
    )


@router.post(
    "/requests/{request_id}/messages",
    response_model=MessageRead,
    status_code=201,
)
def send_message_to_chat(
    request_id: int,
    data: MessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Отправить сообщение в чат по заявке (REST)."""
    try:
        chat = chat_service.ensure_chat_exists(db, request_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Request not found")

    if not chat_service.is_participant(db, chat.id, current_user.id):
        chat_service.add_participant(
            db, chat.id, current_user.id, ChatParticipantRole.client.value
        )

    message = chat_service.send_message(
        db=db,
        chat_id=chat.id,
        sender_id=current_user.id,
        content=data.content,
        message_type=data.message_type.value,
        attachments=data.attachments,
        reply_to_message_id=data.reply_to_message_id,
        mentions=data.mentions,
    )
    chat_service.mark_as_read(db, message.id, current_user.id)

    return _message_to_read(message, db)


# ============================================================
# WebSocket Endpoint
# ============================================================


@router.websocket("/ws/{chat_id}")
async def chat_websocket(websocket: WebSocket, chat_id: int, token: str = Query(...)):
    """
    WebSocket для real-time чата.
    Подключение: ws://localhost:8000/api/v1/chat/ws/{chat_id}?token=JWT
    """
    db = SessionLocal()
    user = None

    try:
        # 1. Аутентификация (используем auth_service, как в deps.py)
        try:
            payload = decode_access_token(token)
            user_id = int(payload.get("sub"))
        except Exception:
            await websocket.close(code=1008, reason="Invalid token")
            return

        user = db.get(User, user_id)
        if not user:
            await websocket.close(code=1008, reason="User not found")
            return

        # 2. Проверка чата
        chat = db.get(RequestChat, chat_id)
        if not chat:
            await websocket.close(code=4004, reason="Chat not found")
            return

        # 3. Добавляем в участники
        if not chat_service.is_participant(db, chat.id, user.id):
            chat_service.add_participant(
                db, chat.id, user.id, ChatParticipantRole.client.value
            )

        # 4. Подключаем
        await manager.connect_chat(websocket, chat_id)

        # 5. Системное сообщение о входе
        chat_service.send_system_event(
            db=db,
            chat_id=chat_id,
            event_type="user_joined",
            data={"user_id": user.id, "email": user.email},
        )

        # 6. Основной цикл
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "message")

            if msg_type == "message":
                message = chat_service.send_message(
                    db=db,
                    chat_id=chat_id,
                    sender_id=user.id,
                    content=data.get("content", ""),
                    message_type=data.get("message_type", "text"),
                    attachments=data.get("attachments"),
                    reply_to_message_id=data.get("reply_to_message_id"),
                )
                chat_service.mark_as_read(db, message.id, user.id)

                await manager.broadcast_to_chat(
                    chat_id,
                    {
                        "type": "message",
                        "data": {
                            "id": message.id,
                            "chat_id": chat_id,
                            "sender_id": user.id,
                            "sender_email": user.email,
                            "message_type": message.message_type,
                            "content": message.content,
                            "attachments": message.attachments,
                            "created_at": message.created_at.isoformat(),
                        },
                    },
                )

            elif msg_type == "typing":
                await manager.broadcast_to_chat(
                    chat_id,
                    {"type": "typing", "data": {"user_id": user.id}},
                )

            elif msg_type == "read":
                message_id = data.get("message_id")
                if message_id:
                    chat_service.mark_as_read(db, message_id, user.id)

    except WebSocketDisconnect:
        manager.disconnect_chat(websocket, chat_id)
        if user:
            try:
                chat_service.send_system_event(
                    db=db,
                    chat_id=chat_id,
                    event_type="user_left",
                    data={"user_id": user.id},
                )
            except Exception:
                pass
    except Exception as e:
        logger.error("WebSocket error: %s", e)
        manager.disconnect_chat(websocket, chat_id)
    finally:
        db.close()