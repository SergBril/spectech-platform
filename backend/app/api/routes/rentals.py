"""REST API РґР»СЏ Р°СЂРµРЅРґС‹ С‚РµС…РЅРёРєРё."""

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
router = APIRouter(prefix="/rentals", tags=["рџ“‹ Rentals (РђСЂРµРЅРґР°)"])


@router.post(
    "",
    response_model=RentalRead,
    status_code=201,
    summary="РЎРѕР·РґР°С‚СЊ Р°СЂРµРЅРґСѓ",
)
def create_rental(
    data: RentalCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """РЎРѕР·РґР°С‘С‚ РґРѕРіРѕРІРѕСЂ Р°СЂРµРЅРґС‹ РІ СЃС‚Р°С‚СѓСЃРµ DRAFT."""
    return rental_service.create_rental(
        db=db,
        rental_in=data,
        company_id=company_id,
        created_by=current_user.id,
    )


@router.get("", response_model=list[RentalRead], summary="РЎРїРёСЃРѕРє Р°СЂРµРЅРґ")
def list_rentals(
    status: RentalStatus | None = None,
    client_id: int | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_ids: list[int] = Depends(get_user_company_ids),
):
    """Р’РѕР·РІСЂР°С‰Р°РµС‚ СЃРїРёСЃРѕРє Р°СЂРµРЅРґ СЃ С„РёР»СЊС‚СЂР°РјРё."""
    return rental_service.list_rentals(
        db=db,
        company_ids=company_ids,
        status=status,
        client_id=client_id,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{rental_id}", response_model=RentalRead, summary="Р”РµС‚Р°Р»Рё Р°СЂРµРЅРґС‹"
)
def get_rental(
    rental_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_ids: list[int] = Depends(get_user_company_ids),
):
    return rental_service.get_rental(db, rental_id, company_ids)


@router.patch(
    "/{rental_id}", response_model=RentalRead, summary="РћР±РЅРѕРІРёС‚СЊ Р°СЂРµРЅРґСѓ"
)
def update_rental(
    rental_id: int,
    data: RentalUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """РћР±РЅРѕРІР»РµРЅРёРµ Р°СЂРµРЅРґС‹ (С‚РѕР»СЊРєРѕ РІ СЃС‚Р°С‚СѓСЃРµ DRAFT)."""
    return rental_service.update_rental(db, rental_id, data, company_id)


@router.post(
    "/{rental_id}/items",
    response_model=RentalItemRead,
    status_code=201,
    summary="Р”РѕР±Р°РІРёС‚СЊ С‚РµС…РЅРёРєСѓ",
)
def add_rental_item(
    rental_id: int,
    data: RentalItemAdd,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Р”РѕР±Р°РІРёС‚СЊ РїРѕР·РёС†РёСЋ С‚РµС…РЅРёРєРё РІ Р°СЂРµРЅРґСѓ (С‚РѕР»СЊРєРѕ РІ DRAFT)."""
    return rental_service.add_rental_item(db, rental_id, data, company_id)


@router.delete(
    "/{rental_id}/items/{item_id}",
    status_code=204,
    summary="РЈРґР°Р»РёС‚СЊ С‚РµС…РЅРёРєСѓ РёР· Р°СЂРµРЅРґС‹",
)
def remove_rental_item(
    rental_id: int,
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """РЈРґР°Р»РёС‚СЊ РїРѕР·РёС†РёСЋ РёР· Р°СЂРµРЅРґС‹ (С‚РѕР»СЊРєРѕ РІ DRAFT)."""
    rental_service.remove_rental_item(db, rental_id, item_id, company_id)


@router.post(
    "/{rental_id}/activate",
    response_model=RentalRead,
    summary="РђРєС‚РёРІРёСЂРѕРІР°С‚СЊ Р°СЂРµРЅРґСѓ (РІС‹РґР°С‚СЊ С‚РµС…РЅРёРєСѓ)",
)
def activate_rental(
    rental_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """РџРµСЂРµРІРѕРґРёС‚ Р°СЂРµРЅРґСѓ РёР· DRAFT РІ ACTIVE."""
    return rental_service.activate_rental(db, rental_id, company_id)


@router.post(
    "/{rental_id}/cancel",
    response_model=RentalRead,
    summary="РћС‚РјРµРЅРёС‚СЊ Р°СЂРµРЅРґСѓ",
)
def cancel_rental(
    rental_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """РћС‚РјРµРЅСЏРµС‚ Р°СЂРµРЅРґСѓ (DRAFT/ACTIVE в†’ CANCELLED)."""
    return rental_service.cancel_rental(db, rental_id, company_id)


@router.post(
    "/{rental_id}/close",
    response_model=RentalRead,
    summary="Р—Р°РІРµСЂС€РёС‚СЊ Р°СЂРµРЅРґСѓ (РїСЂРёРЅСЏС‚СЊ С‚РµС…РЅРёРєСѓ РѕР±СЂР°С‚РЅРѕ)",
)
def close_rental(
    rental_id: int,
    data: RentalClose,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Р—Р°РІРµСЂС€Р°РµС‚ Р°СЂРµРЅРґСѓ (ACTIVE в†’ COMPLETED) СЃ РїРµСЂРµСЃС‡С‘С‚РѕРј РїРѕ С„Р°РєС‚Сѓ."""
    return rental_service.close_rental(db, rental_id, data, company_id)
