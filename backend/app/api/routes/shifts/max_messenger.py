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

        if chat_id and text:
            text_clean = str(text).strip()
            from app.services.max_messenger_service import max_messenger_service

            # /start <token> — привязка аккаунта
            if text_clean.startswith("/start"):
                parts = text_clean.split()
                if len(parts) >= 2:
                    link_token = parts[1]
                    user = db.execute(
                        select(User).where(User.telegram_link_code == link_token)
                    ).scalar_one_or_none()
                    if user:
                        user.max_chat_id = str(chat_id)
                        db.commit()
                        msg = f"✅ Привязка успешна! Уведомления: {user.full_name or user.email}"
                        await max_messenger_service.send_message(str(chat_id), msg)
                    else:
                        await max_messenger_service.send_message(str(chat_id), "❌ Неверный код привязки.")
                else:
                    await max_messenger_service.send_message(str(chat_id), "Используйте ссылку из профиля для привязки.")
                return {"ok": True}

            # Find user by chat_id for other commands
            user = db.execute(
                select(User).where(User.max_chat_id == str(chat_id))
            ).scalar_one_or_none()

            if not user:
                await max_messenger_service.send_message(str(chat_id), "Сначала привяжите аккаунт через /start")
                return {"ok": True}

            # /help
            if text_clean.startswith("/help"):
                help_text = (
                    "<b>🚜 СпецТехника Про</b>\n\n"
                    "/status — Статус заявок и техники\n"
                    "/shifts — Активные смены сегодня\n"
                    "/help — Эта справка"
                )
                await max_messenger_service.send_message(str(chat_id), help_text)
                return {"ok": True}

            # /status
            if text_clean.startswith("/status"):
                from app.models.dispatch import Request, RequestStatus
                from app.models.catalog import Vehicle
                active = db.query(Request).filter(
                    Request.status.in_([RequestStatus.new, RequestStatus.processing]),
                ).count()
                avail = db.query(Vehicle).filter(Vehicle.status == "available", Vehicle.is_deleted == False).count()
                txt = f"<b>📊 Статус</b>\nАктивных заявок: {active}\nСвободной техники: {avail}"
                await max_messenger_service.send_message(str(chat_id), txt)
                return {"ok": True}

            # /shifts
            if text_clean.startswith("/shifts"):
                from datetime import date as date_type
                from app.models.shift import ShiftTask
                today = date_type.today()
                shifts = db.query(ShiftTask).filter(
                    ShiftTask.shift_date == today,
                    ShiftTask.status.in_(["planned", "confirmed", "in_progress"]),
                ).all()
                if shifts:
                    lines_txt = ["<b>📋 Смены сегодня</b>"]
                    for s in shifts[:10]:
                        v = db.get(Vehicle, s.vehicle_id)
                        vn = v.name if v else f"#{s.vehicle_id}"
                        lines_txt.append(f"• {vn} — {s.status}")
                    await max_messenger_service.send_message(str(chat_id), "\n".join(lines_txt))
                else:
                    await max_messenger_service.send_message(str(chat_id), "Нет активных смен на сегодня.")
                return {"ok": True}

            await max_messenger_service.send_message(str(chat_id), "Неизвестная команда. Используйте /help")
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



