import logging

logger = logging.getLogger("spectech.auth")
import secrets
from datetime import UTC

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.auth import User
from app.schemas.auth import (
    ForgotPasswordRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserLogin,
    UserRead,
    UserRegister,
)
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


@router.post("/forgot-password")
def forgot_password(
    payload: ForgotPasswordRequest,
    db: Session = Depends(get_db),
):
    """Отправить письмо со ссылкой для сброса пароля."""
    import hashlib
    import secrets
    from datetime import datetime, timedelta

    from app.core.config import settings
    from app.services.email_service import EmailService

    user = db.query(User).filter(User.email == payload.email).first()

    if not user:
        return {
            "message": "Если email зарегистрирован, вы получите письмо со ссылкой для сброса"
        }

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    expires_at = datetime.now(UTC) + timedelta(hours=1)

    user.reset_token_hash = token_hash
    user.reset_token_expires_at = expires_at
    db.commit()

    reset_url = f"{settings.FRONTEND_URL}/reset-password?token={raw_token}"

    try:
        email_service = EmailService()
        email_service.send_email(
            to_email=user.email,
            subject="Сброс пароля — СпецТехника Про",
            template_name="reset_password.html",
            context={
                "full_name": user.full_name,
                "email": user.email,
                "reset_url": reset_url,
            },
        )
        print(f"✅ Reset email sent to {user.email}")
    except Exception as e:
        print(f"⚠️ Failed to send reset email: {e}")

    return {
        "message": "Если email зарегистрирован, вы получите письмо со ссылкой для сброса"
    }


@router.post("/reset-password")
def reset_password(
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db),
):
    """Установить новый пароль по токену."""
    import hashlib
    from datetime import datetime

    from app.services.auth_service import hash_password

    token_hash = hashlib.sha256(payload.token.encode()).hexdigest()
    user = db.query(User).filter(User.reset_token_hash == token_hash).first()

    if not user:
        raise HTTPException(
            status_code=400, detail="Недействительный или истёкший токен"
        )

    if not user.reset_token_expires_at or user.reset_token_expires_at < datetime.now(
        UTC
    ):
        raise HTTPException(status_code=400, detail="Срок действия токена истёк")

    user.password_hash = hash_password(payload.new_password)
    user.reset_token_hash = None
    user.reset_token_expires_at = None
    user.failed_login_attempts = 0
    db.commit()

    return {"message": "Пароль успешно изменён"}
