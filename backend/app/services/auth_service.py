import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import bcrypt
from fastapi import HTTPException, status
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.auth import User, UserSession, UserStatus


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_access_token(user: User) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
        "iat": now,
    }
    return jwt.encode(
        payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )


def create_refresh_token(db: Session, user: User) -> str:
    raw_token = secrets.token_urlsafe(64)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    session = UserSession(
        user_id=user.id,
        refresh_token_hash=token_hash,
        expires_at=datetime.now(UTC)
        + timedelta(days=settings.refresh_token_expire_days),
    )
    db.add(session)
    db.flush()

    return raw_token


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


def authenticate_user(db: Session, email: str, password: str) -> User:
    user = db.scalar(select(User).where(User.email == email))

    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if user.status != UserStatus.active:
        raise HTTPException(status_code=403, detail="User account is not active")

    if not verify_password(password, user.password_hash):
        user.failed_login_attempts += 1
        db.commit()
        raise HTTPException(status_code=401, detail="Invalid email or password")

    user.failed_login_attempts = 0
    user.last_login_at = datetime.now(UTC)
    db.commit()

    return user
