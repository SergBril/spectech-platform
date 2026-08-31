from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models.auth import User
from app.models.catalog import Category

router = APIRouter()


@router.get("")
def list_categories(
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = select(Category).order_by(Category.level, Category.name).limit(limit)
    categories = db.scalars(stmt).all()
    
    return [
        {
            "id": c.id,
            "name": c.name,
            "code": c.code,
            "level": c.level,
            "parent_id": c.parent_id,
            "is_active": c.is_active,
        }
        for c in categories
    ]