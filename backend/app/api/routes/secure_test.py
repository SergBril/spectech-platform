from fastapi import APIRouter, Depends

from app.api.deps import get_current_user, require_permission
from app.models.auth import User

router = APIRouter(prefix="/secure-test", tags=["🔒 Secure Test (RBAC)"])


@router.get("/public")
def public_endpoint():
    """Этот endpoint доступен всем, даже без токена."""
    return {"message": "Это публичные данные. Токен не нужен."}


@router.get("/private")
def private_endpoint(current_user: User = Depends(get_current_user)):
    """Этот endpoint доступен только авторизованным пользователям."""
    return {
        "message": "Доступ разрешен!",
        "user_id": current_user.id,
        "email": current_user.email,
        "is_superuser": current_user.is_superuser,
    }


@router.get("/admin-only")
def admin_only_endpoint(
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_permission("system", "admin_access")),
):
    """Этот endpoint доступен только пользователям с правом system:admin_access."""
    return {"message": "Добро пожаловать в админ-зону!", "user": current_user.email}
