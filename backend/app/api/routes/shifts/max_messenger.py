"""Модуль max_messenger для shifts router."""

from datetime import UTC, datetime
from fastapi import APIRouter, Depends, File, HTTPException, Query, Body, UploadFile
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.core.db import get_db

from fastapi import Request
from app.models.auth import User
from app.services.max_messenger_service import max_messenger_service
from app.core.config import settings
from app.api.deps import get_current_user

router = APIRouter()

async def max_webhook(request: Request, db: Session = Depends(get_db)):
    """Обработка входящих событий от MAX Bot API."""
    body = await request.json()
    event_type = body.get("type", "")
    payload = body.get("payload", {})

    if event_type in ("message", "new_message"):
        text = ""
        chat_id = ""
        if isinstance(payload, dict):
            text = payload.get("text", "")
            if not text:
                content_obj = payload.get("content", {})
                if isinstance(content_obj, dict):
                    pl = content_obj.get("payload", {})
                    if isinstance(pl, dict):
                        text = pl.get("text", "")
            chat_id = payload.get("chatId", "")
            if not chat_id:
                chat_obj = payload.get("chat", {})
                if isinstance(chat_obj, dict):
                    chat_id = chat_obj.get("id", "")

        if "/start" in str(text) and chat_id:
            parts = str(text).strip().split()
            if len(parts) >= 2:
                link_token = parts[1]
                user = db.execute(
                    select(User).where(User.telegram_link_code == link_token)
                ).scalar_one_or_none()

                if user:
                    user.max_chat_id = str(chat_id)
                    db.commit()
                    from app.services.max_messenger_service import max_messenger_service
                    msg = "Privyazka uspeshna! Vy budete poluchat uvedomleniya kak " + (user.full_name or user.email or "")
                    await max_messenger_service.send_message(str(chat_id), msg)
                else:
                    from app.services.max_messenger_service import max_messenger_service
                    await max_messenger_service.send_message(str(chat_id), "Nevernyy kod privyazki.")

    return {"ok": True}



def get_max_bind_link(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Генерирует ссылку для привязки MAX бота к аккаунту."""
    import secrets
    if not current_user.telegram_link_code:
        current_user.telegram_link_code = secrets.token_urlsafe(16)
        db.commit()
    from app.core.config import settings
    bot_username = getattr(settings, "MAX_BOT_USERNAME", "spectech_bot")
    link = "https://max.ru/" + bot_username + "?start=" + current_user.telegram_link_code
    return {"link": link, "bot_username": bot_username}



def get_max_bind_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Проверить статус привязки MAX."""
    return {
        "bound": bool(current_user.max_chat_id),
        "max_chat_id": current_user.max_chat_id,
    }



def unbind_max(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Отвязать MAX от аккаунта."""
    from app.services.audit_service import log_action
    current_user.max_chat_id = None
    db.commit()
    log_action(db, current_user.id, "update", "max_unbind", current_user.id)
    return {"message": "MAX отвязан"}



async def test_max_webhook(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Отправить тестовое сообщение через MAX текущему пользователю."""
    from app.services.max_messenger_service import max_messenger_service

    if not current_user.max_chat_id:
        raise HTTPException(status_code=400, detail="MAX not bound. Use /max/bind-link first.")

    result = await max_messenger_service.send_message(
        current_user.max_chat_id,
        "Test notification from Spectech platform. Webhook is working!"
    )
    return {"result": result}



