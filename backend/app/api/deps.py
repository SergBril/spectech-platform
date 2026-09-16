from fastapi import Depends, Header, HTTPException, status
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
    x_company_id: str | None = Header(default=None, alias="X-Company-Id"),
    db: Session = Depends(get_db),
) -> int:
    """
    Возвращает company_id для текущего запроса.

    Логика:
    - Если передан header X-Company-Id и пользователь superuser —
      возвращаем company_id из header (после проверки существования)
    - Иначе — возвращаем company_id пользователя
    """
    from app.models.company import Company

    # Superuser может переключаться между компаниями через header
    if x_company_id and user.is_superuser:
        try:
            requested_company_id = int(x_company_id)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid X-Company-Id header",
            )

        # Проверяем, что компания существует и активна
        company = db.get(Company, requested_company_id)
        if not company or not company.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Company {requested_company_id} not found or inactive",
            )

        return requested_company_id

    # Обычный пользователь — только своя компания
    if not user.company_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not assigned to any company",
        )
    return user.company_id
