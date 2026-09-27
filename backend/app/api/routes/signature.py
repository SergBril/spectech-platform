"""Endpoints для управления электронной подписью."""

import logging

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.models.auth import User
from app.services.edoxml.signature_service import get_signature_info

logger = logging.getLogger("spectech.signature")

router = APIRouter()


@router.get("/info")
def signature_info(current_user: User = Depends(get_current_user)):
    """
    Информация о текущем сертификате подписи.

    Показывает:
    - Субъект и издатель сертификата
    - Срок действия
    - Алгоритм подписи
    - Фазу внедрения (разработка/боевая)
    """
    return get_signature_info()
