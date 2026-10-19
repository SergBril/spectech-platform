"""API админ-панели платформы."""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.db import get_db
from app.models.auth import User
from app.models.catalog import Vehicle
from app.models.company import Company
from app.models.dispatch import Request
from app.models.telematics import Notification

router = APIRouter()


def _check_platform_owner(current_user: User):
    """Проверка доступа: только владелец платформы (email из PLATFORM_OWNER_EMAIL)."""
    from fastapi import HTTPException

    if not getattr(current_user, "is_superuser", False):
        raise HTTPException(status_code=403, detail="Admin access required")
    if (
        settings.PLATFORM_OWNER_EMAIL
        and current_user.email != settings.PLATFORM_OWNER_EMAIL
    ):
        raise HTTPException(
            status_code=403, detail="Access denied: platform owner only"
        )


@router.get("/stats")
def get_platform_stats(
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """📊 Общая статистика платформы."""
    _check_platform_owner(current_user)

    # Парсинг дат
    if date_from:
        dt_from = datetime.fromisoformat(date_from).replace(tzinfo=UTC)
    else:
        dt_from = datetime.now(UTC) - timedelta(days=30)

    if date_to:
        dt_to = datetime.fromisoformat(date_to).replace(tzinfo=UTC)
    else:
        dt_to = datetime.now(UTC)

    # Общие счётчики
    total_users = db.query(func.count(User.id)).scalar() or 0
    total_companies = db.query(func.count(Company.id)).scalar() or 0
    total_vehicles = db.query(func.count(Vehicle.id)).scalar() or 0
    total_requests = db.query(func.count(Request.id)).scalar() or 0

    # Новые за период
    new_users = (
        db.query(func.count(User.id))
        .filter(User.created_at >= dt_from, User.created_at <= dt_to)
        .scalar()
        or 0
    )
    new_companies = (
        db.query(func.count(Company.id))
        .filter(Company.created_at >= dt_from, Company.created_at <= dt_to)
        .scalar()
        or 0
    )
    new_vehicles = (
        db.query(func.count(Vehicle.id))
        .filter(Vehicle.created_at >= dt_from, Vehicle.created_at <= dt_to)
        .scalar()
        or 0
    )
    new_requests = (
        db.query(func.count(Request.id))
        .filter(Request.created_at >= dt_from, Request.created_at <= dt_to)
        .scalar()
        or 0
    )

    # Техника по статусам
    vehicles_by_status = (
        db.query(Vehicle.status, func.count(Vehicle.id)).group_by(Vehicle.status).all()
    )

    # Заявки по статусам
    requests_by_status = (
        db.query(Request.status, func.count(Request.id)).group_by(Request.status).all()
    )

    return {
        "totals": {
            "users": total_users,
            "companies": total_companies,
            "vehicles": total_vehicles,
            "requests": total_requests,
        },
        "new_in_period": {
            "users": new_users,
            "companies": new_companies,
            "vehicles": new_vehicles,
            "requests": new_requests,
        },
        "vehicles_by_status": dict(vehicles_by_status),
        "requests_by_status": dict(requests_by_status),
        "period": {
            "from": dt_from.isoformat(),
            "to": dt_to.isoformat(),
        },
    }


@router.get("/provider-requests")
def get_provider_requests(
    limit: int = Query(default=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """📨 Запросы новых GPS-провайдеров."""
    _check_platform_owner(current_user)

    notifications = (
        db.query(Notification)
        .filter(Notification.channel == "system")
        .filter(Notification.title.like("%GPS-провайдера%"))
        .order_by(Notification.sent_at.desc())
        .limit(limit)
        .all()
    )

    return {
        "requests": [
            {
                "id": n.id,
                "title": n.title,
                "body": n.body,
                "user_id": n.user_id,
                "sent_at": n.sent_at.isoformat() if n.sent_at else None,
                "is_read": n.is_read,
            }
            for n in notifications
        ]
    }
