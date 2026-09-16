from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.auth import User, UserStatus
from app.services.auth_service import decode_access_token
from app.services.rbac_service import check_permission

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    payload = decode_access_token(credentials.credentials)

    try:
        user_id = int(payload.get("sub"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid token payload")

    user = db.get(User, user_id)

    if not user or user.status != UserStatus.active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    return user


def require_permission(entity: str, action: str):
    """
    Фабрика зависимости для проверки прав.

    Использование:
        @router.post("/something")
        def endpoint(
            db: Session = Depends(get_db),
            user: User = Depends(get_current_user),
            _: None = Depends(require_permission("vehicles", "create")),
        ):
            ...
    """

    def checker(
        db: Session = Depends(get_db),
        user: User = Depends(get_current_user),
    ):

        if not check_permission(db, user, entity, action):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: {entity}:{action}",
            )
        return None

    return checker


def get_current_company_id(
    user: User = Depends(get_current_user),
) -> int:
    """
    Возвращает company_id текущего пользователя.

    Если у пользователя нет компании — возвращает 403.
    """
    if not user.company_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not assigned to any company",
        )
    return user.company_id
