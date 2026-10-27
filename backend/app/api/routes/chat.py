"""Endpoints для чата по заявке (REST + WebSocket)."""

import logging
from datetime import datetime, UTC

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
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
from app.services import storage_service
from app.services.auth_service import decode_access_token
from app.services.chat_service import send_chat_message
from app.services.websocket_manager import manager

logger = logging.getLogger("spectech.chat")
router = APIRouter(prefix="/chat", tags=["Chat"])


# ============================================================
# Pydantic схемы
# ============================================================


class FileUploadResponse(BaseModel):
    """Ответ после загрузки файла в MinIO."""
    path: str
    url: str
    size: int
    content_type: str
    original_filename: str


class MessageCreate(BaseModel):
    """Схема создания сообщения."""
    content: str = Field(default="", max_length=5000)
    message_type: ChatMessageType = Field(default=ChatMessageType.text)
    attachments: dict | None = None
    reply_to_message_id: int | None = None
    mentions: dict | None = None
    file_url: str | None = None


class MessageRead(BaseModel):
    """Схема чтения сообщения."""
    id: int
    chat_id: int
    sender_id: int | None = None
    sender_name: str | None = None
    sender_type: str
    message_type: str
    content: str | None = None
    file_url: str | None = None
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
# Вспомогательные функции (замена chat_service)
# ============================================================


def _ensure_chat_exists(db: Session, request_id: int) -> RequestChat:
    """Найти или создать чат для заявки."""
    chat = db.execute(
        select(RequestChat).where(RequestChat.request_id == request_id)
    ).scalar_one_or_none()

    if not chat:
        # Проверяем существование заявки
        from app.models.dispatch import Request as DispatchRequest
        req = db.get(DispatchRequest, request_id)
        if not req:
            raise ValueError(f"Request {request_id} not found")

        chat = RequestChat(
            request_id=request_id,
            created_at=datetime.now(UTC),
        )
        db.add(chat)
        db.flush()

    return chat


def _is_participant(db: Session, chat_id: int, user_id: int) -> bool:
    """Проверить, является ли пользователь участником чата."""
    participant = db.execute(
        select(ChatParticipant).where(
            ChatParticipant.chat_id == chat_id,
            ChatParticipant.user_id == user_id,
            ChatParticipant.left_at.is_(None),
        )
    ).scalar_one_or_none()
    return participant is not None


def _add_participant(db: Session, chat_id: int, user_id: int, role: str = "client"):
    """Добавить участника в чат."""
    if not _is_participant(db, chat_id, user_id):
        participant = ChatParticipant(
            chat_id=chat_id,
            user_id=user_id,
            role=role,
            joined_at=datetime.now(UTC),
        )
        db.add(participant)
        db.flush()


def _get_unread_count(db: Session, chat_id: int, user_id: int) -> int:
    """Получить количество непрочитанных сообщений."""
    # Упрощённая логика: считаем все сообщения не от текущего пользователя
    count = db.execute(
        select(ChatMessage)
        .where(
            ChatMessage.chat_id == chat_id,
            ChatMessage.sender_id != user_id,
        )
    ).scalars().all()
    return len(count)


def _get_chat_by_request(db: Session, request_id: int) -> RequestChat | None:
    """Получить чат по ID заявки."""
    return db.execute(
        select(RequestChat).where(RequestChat.request_id == request_id)
    ).scalar_one_or_none()


def _get_messages_cursor(
    db: Session,
    chat_id: int,
    cursor: int | None = None,
    limit: int = 50,
    message_type: str | None = None,
) -> tuple[list[ChatMessage], bool]:
    """Получить сообщения с cursor-based пагинацией."""
    stmt = (
        select(ChatMessage)
        .where(ChatMessage.chat_id == chat_id)
        .order_by(ChatMessage.id.desc())
        .limit(limit + 1)
    )
    if cursor:
        stmt = stmt.where(ChatMessage.id < cursor)
    if message_type:
        stmt = stmt.where(ChatMessage.message_type == message_type)

    messages = db.execute(stmt).scalars().all()
    has_more = len(messages) > limit
    if has_more:
        messages = messages[:limit]

    return list(reversed(messages)), has_more


def _mark_as_read(db: Session, message_id: int, user_id: int):
    """Пометить сообщение как прочитанное (stub)."""
    # В реальной реализации здесь нужно обновлять таблицу read_receipts
    pass


def _message_to_read(msg: ChatMessage, db: Session) -> MessageRead:
    """Конвертировать модель сообщения в схему ответа."""
    sender_name = None
    if msg.sender_id:
        sender = db.get(User, msg.sender_id)
        sender_name = sender.email if sender else None
    return MessageRead(
        id=msg.id,
        chat_id=msg.chat_id,
        sender_id=msg.sender_id,
        sender_name=sender_name,
        sender_type=msg.sender_type if hasattr(msg, 'sender_type') else "user",
        message_type=(
            msg.message_type.value
            if hasattr(msg.message_type, "value")
            else str(msg.message_type)
        ),
        content=msg.content,
        file_url=getattr(msg, 'file_url', None),
        attachments=getattr(msg, 'attachments', None),
        reply_to_message_id=getattr(msg, 'reply_to_message_id', None),
        is_read_by=getattr(msg, 'is_read_by', None),
        created_at=msg.created_at if hasattr(msg, 'created_at') else msg.sent_at,
    )


# ============================================================
# REST Endpoints
# ============================================================


@router.post(
    "/requests/{request_id}/upload",
    response_model=FileUploadResponse,
    status_code=201,
    summary="Загрузить файл в хранилище чата",
)
async def upload_chat_file(
    request_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Загружает файл в MinIO и возвращает метаданные."""
    try:
        chat = _ensure_chat_exists(db, request_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Request not found")

    if not _is_participant(db, chat.id, current_user.id):
        _add_participant(db, chat.id, current_user.id, ChatParticipantRole.client.value if hasattr(ChatParticipantRole, 'client') else "client")

    try:
        result = storage_service.upload_file(
            file_obj=file.file,
            filename=file.filename or "unknown",
            folder=f"chat/{request_id}",
            content_type=file.content_type,
        )
        return FileUploadResponse(**result)
    except Exception as e:
        logger.error(f"File upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {e}")


@router.post(
    "/requests/{request_id}/upload-multiple",
    response_model=list[FileUploadResponse],
    status_code=201,
    summary="Загрузить несколько файлов в хранилище чата",
)
async def upload_multiple_chat_files(
    request_id: int,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Загружает несколько файлов в MinIO за один запрос."""
    try:
        chat = _ensure_chat_exists(db, request_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Request not found")

    if not _is_participant(db, chat.id, current_user.id):
        _add_participant(db, chat.id, current_user.id, ChatParticipantRole.client.value if hasattr(ChatParticipantRole, 'client') else "client")

    results = []
    for file in files:
        try:
            result = storage_service.upload_file(
                file_obj=file.file,
                filename=file.filename or "unknown",
                folder=f"chat/{request_id}",
                content_type=file.content_type,
            )
            results.append(FileUploadResponse(**result))
        except Exception as e:
            logger.error(f"File upload failed for {file.filename}: {e}")
            continue

    if not results:
        raise HTTPException(status_code=500, detail="All file uploads failed")

    return results


@router.get("/requests/{request_id}", response_model=ChatRead)
def get_chat_by_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Получить чат по заявке. Создаёт чат, если его нет."""
    try:
        chat = _ensure_chat_exists(db, request_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Request not found")

    if not _is_participant(db, chat.id, current_user.id):
        _add_participant(db, chat.id, current_user.id, ChatParticipantRole.client.value if hasattr(ChatParticipantRole, 'client') else "client")

    last_msg = (
        db.query(ChatMessage)
        .filter(ChatMessage.chat_id == chat.id)
        .order_by(ChatMessage.created_at.desc() if hasattr(ChatMessage, 'created_at') else ChatMessage.sent_at.desc())
        .first()
    )
    last_message = _message_to_read(last_msg, db) if last_msg else None
    unread_count = _get_unread_count(db, chat.id, current_user.id)
    participants_count = (
        db.query(ChatParticipant)
        .filter(
            ChatParticipant.chat_id == chat.id,
            ChatParticipant.left_at == None,  # noqa: E711
        )
        .count()
    )

    db.commit()
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
    chat = _get_chat_by_request(db, request_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    if not _is_participant(db, chat.id, current_user.id):
        _add_participant(db, chat.id, current_user.id, ChatParticipantRole.client.value if hasattr(ChatParticipantRole, 'client') else "client")

    messages, has_more = _get_messages_cursor(
        db=db,
        chat_id=chat.id,
        cursor=cursor,
        limit=limit,
        message_type=message_type.value if message_type else None,
    )

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
        chat = _ensure_chat_exists(db, request_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Request not found")

    if not _is_participant(db, chat.id, current_user.id):
        _add_participant(db, chat.id, current_user.id, ChatParticipantRole.client.value if hasattr(ChatParticipantRole, 'client') else "client")

    # Определяем получателя
    recipient_id = None
    
    # Проверяем, является ли текущий пользователь водителем этой смены
    from app.models.contractor import DriverProfile, Employee
    my_profile = db.execute(
        select(DriverProfile).join(Employee, DriverProfile.employee_contractor_id == Employee.contractor_id)
        .where(Employee.user_id == current_user.id)
    ).scalar_one_or_none()
    
    # Получаем shift_task из чата (если есть связь)
    task = None
    if hasattr(chat, 'shift_task_id') and chat.shift_task_id:
        task = db.get(ShiftTask, chat.shift_task_id)
    elif hasattr(chat, 'request_id') and chat.request_id:
        # Пытаемся найти смену через заявку
        from app.models.shift import ShiftTask as ST
        task = db.execute(
            select(ST).where(ST.request_id == chat.request_id)
        ).scalars().first()
    
    if my_profile and task and task.operator_id == my_profile.employee_contractor_id:
        # Водитель отправляет диспетчеру (первому пользователю компании)
        from app.models.auth import UserCompany
        dispatcher_id = db.execute(
            select(UserCompany.user_id).where(UserCompany.company_id == chat.company_id if hasattr(chat, 'company_id') else 0)
            .where(UserCompany.user_id != current_user.id)
        ).scalars().first()
        recipient_id = dispatcher_id
    elif task and task.operator_id:
        # Диспетчер отправляет водителю
        driver_emp = db.get(Employee, task.operator_id)
        if driver_emp and driver_emp.user_id:
            recipient_id = driver_emp.user_id
    
    # Fallback: если не удалось определить получателя, используем 0 (системное сообщение)
    if recipient_id is None:
        recipient_id = 0

    message = send_chat_message(
        db=db,
        sender_id=current_user.id,
        recipient_id=recipient_id,
        text=data.content,
        shift_task_id=request_id,
        message_type=data.message_type.value if hasattr(data.message_type, 'value') else str(data.message_type),
        file_url=data.file_url,
        attachments=data.attachments,
    )
    
    # Если send_chat_message вернул dict, создаём объект для ответа
    if isinstance(message, dict):
        msg_obj = db.get(ChatMessage, message.get("message_id"))
        if msg_obj:
            _mark_as_read(db, msg_obj.id, current_user.id)
            return _message_to_read(msg_obj, db)

    raise HTTPException(status_code=500, detail="Failed to send message")


# ============================================================
# WebSocket Endpoint
# ============================================================


@router.websocket("/ws/{chat_id}")
async def chat_websocket(websocket: WebSocket, chat_id: int, token: str = Query(...)):
    """WebSocket для real-time чата."""
    db = SessionLocal()
    user = None
    try:
        # 1. Аутентификация
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
        if not _is_participant(db, chat.id, user.id):
            _add_participant(db, chat.id, user.id, ChatParticipantRole.client.value if hasattr(ChatParticipantRole, 'client') else "client")

        # 4. Подключаем
        await manager.connect_chat(websocket, chat_id)

        # 5. Системное сообщение о входе
        system_content = f"Пользователь {user.email} присоединился к чату"
        system_msg_data = {
            "type": "message",
            "data": {
                "id": None,
                "chat_id": chat_id,
                "sender_id": None,
                "sender_email": "system",
                "message_type": "system_event",
                "content": system_content,
                "attachments": None,
                "created_at": datetime.now(UTC).isoformat(),
            },
        }
        await manager.broadcast_to_chat(chat_id, system_msg_data)

        # 6. Основной цикл
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "message")

            if msg_type == "message":
                # Определяем получателя
                participants = db.execute(
                    select(ChatParticipant.user_id).where(
                        ChatParticipant.chat_id == chat_id,
                        ChatParticipant.user_id != user.id,
                        ChatParticipant.left_at.is_(None),
                    )
                ).scalars().all()
                recipient_id = participants[0] if participants else 0

                result = send_chat_message(
                    db=db,
                    sender_id=user.id,
                    recipient_id=recipient_id,
                    text=data.get("content", ""),
                    shift_task_id=chat.request_id if hasattr(chat, 'request_id') else None,
                    message_type=data.get("message_type", "text"),
                    file_url=data.get("file_url"),
                    attachments=data.get("attachments"),
                )

                if isinstance(result, dict):
                    msg_id = result.get("message_id")
                    msg_obj = db.get(ChatMessage, msg_id) if msg_id else None
                    if msg_obj:
                        _mark_as_read(db, msg_obj.id, user.id)
                        await manager.broadcast_to_chat(
                            chat_id,
                            {
                                "type": "message",
                                "data": {
                                    "id": msg_obj.id,
                                    "chat_id": chat_id,
                                    "sender_id": user.id,
                                    "sender_email": user.email,
                                    "message_type": getattr(msg_obj, 'message_type', 'text'),
                                    "content": msg_obj.content,
                                    "file_url": getattr(msg_obj, 'file_url', None),
                                    "attachments": getattr(msg_obj, 'attachments', None),
                                    "created_at": (msg_obj.created_at if hasattr(msg_obj, 'created_at') else msg_obj.sent_at).isoformat(),
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
                    _mark_as_read(db, message_id, user.id)

    except WebSocketDisconnect:
        manager.disconnect_chat(websocket, chat_id)
        if user:
            try:
                system_content = f"Пользователь {user.email} покинул чат"
                await manager.broadcast_to_chat(
                    chat_id,
                    {
                        "type": "message",
                        "data": {
                            "id": None,
                            "chat_id": chat_id,
                            "sender_id": None,
                            "sender_email": "system",
                            "message_type": "system_event",
                            "content": system_content,
                            "attachments": None,
                            "created_at": datetime.now(UTC).isoformat(),
                        },
                    },
                )
            except Exception:
                pass
    except Exception as e:
        logger.error("WebSocket error: %s", e)
        manager.disconnect_chat(websocket, chat_id)
    finally:
        db.close()