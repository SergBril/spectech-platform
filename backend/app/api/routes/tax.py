"""API для справочников систем налогообложения и ставок НДС."""

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.core.constants import (
    TAX_SYSTEM_CHOICES,
    VAT_RATE_CHOICES,
    vat_rate_for_date,
)
from app.models.auth import User

router = APIRouter(prefix="/tax", tags=["tax"])


@router.get("/systems")
def list_tax_systems(current_user: User = Depends(get_current_user)):
    """Список доступных систем налогообложения."""
    return {
        "systems": TAX_SYSTEM_CHOICES,
        "default": "osno",
    }


@router.get("/vat-rates")
def list_vat_rates(current_user: User = Depends(get_current_user)):
    """Список доступных ставок НДС."""
    return {
        "rates": VAT_RATE_CHOICES,
        "default": "20",
    }


@router.get("/config")
def get_tax_config(current_user: User = Depends(get_current_user)):
    """Полная конфигурация для UI форм."""
    return {
        "systems": TAX_SYSTEM_CHOICES,
        "vat_rates": VAT_RATE_CHOICES,
        "default_system": "osno",
        "default_vat_rate": f"{vat_rate_for_date():.0f}",
    }
