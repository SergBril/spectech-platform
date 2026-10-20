from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.auth import User, UserStatus
from app.services.auth_service import decode_access_token
from app.services.rbac_service import check_permission

# HTTPBearer для авторизации
bearer_scheme = HTTPBearer(auto_error=False)
security = HTTPBearer(auto_error=False)  # Alias для опциональной аутентификации


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

    # Superuser без headerа — возвращаем первую активную компанию
    if user.is_superuser and not user.company_id:
        first_company = db.query(Company).filter(Company.is_active == True).first()
        if first_company:
            return first_company.id
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active companies found",
        )

    # Обычный пользователь — только своя компания
    if not user.company_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not assigned to any company",
        )
    return user.company_id


def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> User | None:
    """
    Опциональная аутентификация.
    Возвращает User если токен валиден, иначе None.

    Используется для публичных endpoints которые могут работать
    как с авторизацией (для привязки отзыва к пользователю),
    так и без неё (анонимные отзывы).
    """
    if not credentials:
        return None

    try:
        payload = decode_access_token(credentials.credentials)
        user_id = int(payload.get("sub"))
        user = db.get(User, user_id)
        return user if user and user.status == UserStatus.active else None
    except Exception:
        return None


def get_user_company_ids(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[int]:
    """Возвращает список company_id для фильтрации данных.

    Для обычных пользователей: только активная компания (user.company_id).
    Для superuser: все активные компании.
    """
    from app.models.user_company import UserCompany

    if user.is_superuser:
        from app.models.company import Company

        return list(
            db.scalars(select(Company.id).where(Company.is_active == True)).all()
        )

    # Обычный пользователь — только активная компания
    if user.company_id:
        return [user.company_id]

    # Fallback: если company_id не установлен, возвращаем все доступные
    ids = set(
        db.scalars(
            select(UserCompany.company_id).where(
                UserCompany.user_id == user.id, UserCompany.is_active == True
            )
        ).all()
    )
    return list(ids)
