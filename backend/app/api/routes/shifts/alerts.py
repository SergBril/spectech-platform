"""Модуль alerts для shifts router."""

from datetime import UTC, datetime
from fastapi import APIRouter, Depends, File, HTTPException, Query, Body, UploadFile
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.core.db import get_db

from app.api.deps import get_current_company_id, get_current_user

from datetime import UTC, datetime
from fastapi import APIRouter, Depends, File, HTTPException, Query, Body, UploadFile, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.models.auth import User
from app.api.deps import get_current_company_id, get_current_user, get_user_company_ids



router = APIRouter()

@router.get("/alerts/idle-vehicles", summary="🚫 Простаивающая техника")
async def check_idle_vehicles(
    target_date: str | None = Body(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Проверить и уведомить о простаивающей технике."""
    from datetime import date as date_type
    from app.services.alert_service import check_and_notify_idle_vehicles

    d = date_type.fromisoformat(target_date) if target_date else date_type.today()
    result = await check_and_notify_idle_vehicles(db, company_id, d)
    return result



@router.get("/alerts/conflicts", summary="⚠️ Конфликты расписания")
async def check_schedule_conflicts(
    target_date: str | None = Body(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Проверить и уведомить о двойных назначениях водителей."""
    from datetime import date as date_type
    from app.services.alert_service import check_and_notify_conflicts

    d = date_type.fromisoformat(target_date) if target_date else date_type.today()
    result = await check_and_notify_conflicts(db, company_id, d)
    return result



