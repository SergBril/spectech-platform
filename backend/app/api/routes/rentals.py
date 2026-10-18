"""REST API для аренды техники."""

import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_company_id, get_current_user, get_user_company_ids
from app.core.db import get_db
from app.models.auth import User
from app.models.rental import RentalStatus
from app.schemas.rental import (
    RentalClose,
    RentalCreate,
    RentalItemAdd,
    RentalItemRead,
    RentalRead,
    RentalUpdate,
)
from app.services.rental_service import rental_service

logger = logging.getLogger("spectech.rental_routes")
router = APIRouter(prefix="/rentals", tags=["📋 Rentals (Аренда)"])


@router.post("", response_model=RentalRead, status_code=201, summary="Создать аренду")
def create_rental(
    data: RentalCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Создаёт договор аренды в статусе DRAFT."""
    return rental_service.create_rental(
        db=db,
        rental_in=data,
        company_id=company_id,
        created_by=current_user.id,
    )


@router.get("", response_model=list[RentalRead], summary="Список аренд")
def list_rentals(
    status: RentalStatus | None = None,
    client_id: int | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_ids: list[int] = Depends(get_user_company_ids),
):
    """Возвращает список аренд с фильтрами."""
    return rental_service.list_rentals(
        db=db,
        company_ids=company_ids,
        status=status,
        client_id=client_id,
        limit=limit,
        offset=offset,
    )


@router.get("/{rental_id}", response_model=RentalRead, summary="Детали аренды")
def get_rental(
    rental_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    return rental_service.get_rental(db, rental_id, company_id)


@router.patch("/{rental_id}", response_model=RentalRead, summary="Обновить аренду")
def update_rental(
    rental_id: int,
    data: RentalUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Обновление аренды (только в статусе DRAFT)."""
    return rental_service.update_rental(db, rental_id, data, company_id)


@router.post(
    "/{rental_id}/items",
    response_model=RentalItemRead,
    status_code=201,
    summary="Добавить технику",
)
def add_rental_item(
    rental_id: int,
    data: RentalItemAdd,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Добавить позицию техники в аренду (только в DRAFT)."""
    return rental_service.add_rental_item(db, rental_id, data, company_id)


@router.delete(
    "/{rental_id}/items/{item_id}",
    status_code=204,
    summary="Удалить технику из аренды",
)
def remove_rental_item(
    rental_id: int,
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Удалить позицию из аренды (только в DRAFT)."""
    rental_service.remove_rental_item(db, rental_id, item_id, company_id)


@router.post(
    "/{rental_id}/activate",
    response_model=RentalRead,
    summary="Активировать аренду (выдать технику)",
)
def activate_rental(
    rental_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Переводит аренду из DRAFT в ACTIVE."""
    return rental_service.activate_rental(db, rental_id, company_id)


@router.post(
    "/{rental_id}/cancel",
    response_model=RentalRead,
    summary="Отменить аренду",
)
def cancel_rental(
    rental_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Отменяет аренду (DRAFT/ACTIVE → CANCELLED)."""
    return rental_service.cancel_rental(db, rental_id, company_id)


@router.post(
    "/{rental_id}/close",
    response_model=RentalRead,
    summary="Завершить аренду (принять технику обратно)",
)
def close_rental(
    rental_id: int,
    data: RentalClose,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Завершает аренду (ACTIVE → COMPLETED) с пересчётом по факту."""
    return rental_service.close_rental(db, rental_id, data, company_id)
