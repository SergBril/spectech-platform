import logging

logger = logging.getLogger("spectech.auth")
import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.auth import User
from app.schemas.auth import TokenResponse, UserLogin, UserRead, UserRegister
from app.services.auth_service import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    hash_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=201)
def register(payload: UserRegister, db: Session = Depends(get_db)):
    existing = db.scalar(select(User).where(User.email == payload.email))
    if existing:
        raise HTTPException(status_code=409, detail="User already exists")

    user = User(
        email=payload.email,
        full_name=payload.full_name,
        phone=payload.phone,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    user = authenticate_user(db, payload.email, payload.password)
    access_token = create_access_token(user)
    refresh_token = create_refresh_token(db, user)
    db.commit()
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post(
    "/me/telegram-link-code",
    summary="Генерирует код для привязки Telegram",
    description="Возвращает одноразовый код для привязки Telegram-аккаунта через бот",
)
def generate_telegram_link_code(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    🔗 Генерирует одноразовый код для привязки Telegram.

    Пользователь отправляет этот код боту командой /link_account.
    """
    # Удаляем старый код, если был
    if current_user.telegram_link_code:
        current_user.telegram_link_code = None

    # Генерируем новый код
    code = secrets.token_urlsafe(16)
    current_user.telegram_link_code = code
    db.commit()

    logger.info(f"User {current_user.id} generated Telegram link code")

    return {
        "code": code,
        "message": "Отправьте этот код в Telegram бот после команды /link_account",
        "bot_command": "/link_account",
    }


@router.delete(
    "/me/telegram-link",
    summary="Отвязывает Telegram от аккаунта",
)
def unlink_telegram(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """🔗 Отвязывает Telegram-аккаунт от пользователя."""
    if not current_user.telegram_id:
        raise HTTPException(status_code=400, detail="Telegram is not linked")

    current_user.telegram_id = None
    db.commit()

    logger.info(f"User {current_user.id} unlinked Telegram")

    return {"message": "Telegram успешно отвязан"}


@router.get(
    "/me/telegram-status",
    summary="Статус привязки Telegram",
)
def get_telegram_status(
    current_user: User = Depends(get_current_user),
):
    """🔗 Возвращает статус привязки Telegram."""
    return {
        "linked": current_user.telegram_id is not None,
        "telegram_id": current_user.telegram_id,
    }
