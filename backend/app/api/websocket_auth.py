"""Аутентификация для WebSocket соединений."""
import logging
from typing import Optional
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.auth import User

logger = logging.getLogger("spectech.websocket.auth")


def verify_ws_token(token: str, db: Session) -> Optional[User]:
    """Проверяет JWT токен для WebSocket."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,  # ← ИСПРАВЛЕНО: было SECRET_KEY
            algorithms=[settings.jwt_algorithm],  # ← ИСПРАВЛЕНО: было JWT_ALGORITHM
        )
        user_id = payload.get("sub")
        if user_id is None:
            logger.warning("WS auth: no sub in token")
            return None
        
        # sub может быть строкой — конвертируем в int
        try:
            user_id = int(user_id)
        except (ValueError, TypeError):
            logger.warning(f"WS auth: invalid sub format: {user_id}")
            return None
        
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            logger.warning(f"WS auth: user {user_id} not found")
            return None
        
        return user
    except JWTError as e:
        logger.warning(f"WS auth: JWT error: {e}")
        return None
    except Exception as e:
        logger.error(f"WS auth: unexpected error: {e}", exc_info=True)
        return None