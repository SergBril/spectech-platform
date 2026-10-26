"""Модуль checklist_configs для shifts router."""

from datetime import UTC, datetime
from fastapi import APIRouter, Depends, File, HTTPException, Query, Body, UploadFile
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.core.db import get_db

from app.models.shift import VehicleChecklistConfig
from app.api.deps import get_current_company_id, get_current_user

from datetime import UTC, datetime
from fastapi import APIRouter, Depends, File, HTTPException, Query, Body, UploadFile, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.models.auth import User
from app.api.deps import get_current_company_id, get_current_user, get_user_company_ids

from app.models.shift import VehicleChecklistConfig

router = APIRouter()

def list_checklist_configs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Список конфигураций чеклистов по типам техники."""
    from app.models.shift import VehicleChecklistConfig
    import json

    configs = db.execute(
        select(VehicleChecklistConfig)
        .where(VehicleChecklistConfig.company_id == company_id)
        .order_by(VehicleChecklistConfig.vehicle_category_id.nulls_first())
    ).scalars().all()

    return [{
        "id": c.id, "name": c.name,
        "vehicle_category_id": c.vehicle_category_id,
        "items": json.loads(c.items_json) if c.items_json else [],
        "is_active": c.is_active,
    } for c in configs]



def create_checklist_config(
    name: str = Body(...),
    vehicle_category_id: int | None = Body(default=None),
    items: list[dict] = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Создать конфигурацию чеклиста для типа техники."""
    from app.models.shift import VehicleChecklistConfig
    import json

    config = VehicleChecklistConfig(
        company_id=company_id, name=name,
        vehicle_category_id=vehicle_category_id,
        items_json=json.dumps(items),
        is_active=True, created_by=current_user.id,
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    return {"id": config.id, "message": "Конфигурация создана"}



def delete_checklist_config(
    config_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Удалить конфигурацию чеклиста."""
    from app.models.shift import VehicleChecklistConfig

    config = db.get(VehicleChecklistConfig, config_id)
    if not config or config.company_id != company_id:
        raise HTTPException(status_code=404, detail="Config not found")

    db.delete(config)
    db.commit()
    return {"message": "Конфигурация удалена"}



