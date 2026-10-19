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


@router.get("/reviews-stats")
def get_reviews_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reviews and ratings statistics."""
    from app.models.review import Review, ReviewStatus

    _check_platform_owner(current_user)
    total_reviews = db.query(func.count(Review.id)).scalar() or 0
    approved_reviews = (
        db.query(func.count(Review.id))
        .filter(Review.status == ReviewStatus.APPROVED)
        .scalar()
        or 0
    )
    pending_reviews = (
        db.query(func.count(Review.id))
        .filter(Review.status == ReviewStatus.PENDING)
        .scalar()
        or 0
    )
    avg_rating = (
        db.query(func.avg(Review.rating))
        .filter(Review.status == ReviewStatus.APPROVED)
        .scalar()
        or 0
    )
    avg_quality = (
        db.query(func.avg(Review.quality_rating))
        .filter(
            Review.status == ReviewStatus.APPROVED, Review.quality_rating.isnot(None)
        )
        .scalar()
        or 0
    )
    avg_punctuality = (
        db.query(func.avg(Review.punctuality_rating))
        .filter(
            Review.status == ReviewStatus.APPROVED,
            Review.punctuality_rating.isnot(None),
        )
        .scalar()
        or 0
    )
    avg_communication = (
        db.query(func.avg(Review.communication_rating))
        .filter(
            Review.status == ReviewStatus.APPROVED,
            Review.communication_rating.isnot(None),
        )
        .scalar()
        or 0
    )
    return {
        "total_reviews": total_reviews,
        "approved_reviews": approved_reviews,
        "pending_reviews": pending_reviews,
        "avg_rating": round(float(avg_rating), 2),
        "avg_quality": round(float(avg_quality), 2),
        "avg_punctuality": round(float(avg_punctuality), 2),
        "avg_communication": round(float(avg_communication), 2),
    }


@router.get("/finance-stats")
def get_finance_stats(
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Platform finance statistics."""
    from app.models.finance import DocumentStatus, Invoice, Payment

    _check_platform_owner(current_user)
    if date_from:
        dt_from = datetime.fromisoformat(date_from).replace(tzinfo=UTC)
    else:
        dt_from = datetime.now(UTC) - timedelta(days=30)
    if date_to:
        dt_to = datetime.fromisoformat(date_to).replace(tzinfo=UTC)
    else:
        dt_to = datetime.now(UTC)
    total_invoices = db.query(func.count(Invoice.id)).scalar() or 0
    total_revenue = (
        db.query(func.sum(Invoice.paid_amount))
        .filter(
            Invoice.status == DocumentStatus.paid,
            Invoice.created_at >= dt_from,
            Invoice.created_at <= dt_to,
        )
        .scalar()
        or 0
    )
    unpaid_amount = (
        db.query(func.sum(Invoice.total_amount - Invoice.paid_amount))
        .filter(
            Invoice.status.in_([DocumentStatus.draft, DocumentStatus.sent]),
            Invoice.total_amount > Invoice.paid_amount,
        )
        .scalar()
        or 0
    )
    total_payments = db.query(func.count(Payment.id)).scalar() or 0
    return {
        "total_invoices": total_invoices,
        "total_revenue": float(total_revenue),
        "unpaid_amount": float(unpaid_amount),
        "total_payments": total_payments,
        "period": {"from": dt_from.isoformat(), "to": dt_to.isoformat()},
    }


@router.get("/top-companies")
def get_top_companies(
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Top companies by activity."""
    _check_platform_owner(current_user)
    top_by_requests = (
        db.query(
            Company.id, Company.name, func.count(Request.id).label("requests_count")
        )
        .join(Request, Request.company_id == Company.id)
        .group_by(Company.id, Company.name)
        .order_by(func.count(Request.id).desc())
        .limit(limit)
        .all()
    )
    top_by_vehicles = (
        db.query(
            Company.id, Company.name, func.count(Vehicle.id).label("vehicles_count")
        )
        .join(Vehicle, Vehicle.company_id == Company.id)
        .group_by(Company.id, Company.name)
        .order_by(func.count(Vehicle.id).desc())
        .limit(limit)
        .all()
    )
    return {
        "top_by_requests": [
            {"id": c.id, "name": c.name, "count": c.requests_count}
            for c in top_by_requests
        ],
        "top_by_vehicles": [
            {"id": c.id, "name": c.name, "count": c.vehicles_count}
            for c in top_by_vehicles
        ],
    }


@router.get("/user-activity")
def get_user_activity(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """User activity metrics (DAU/WAU/MAU)."""
    _check_platform_owner(current_user)
    now = datetime.now(UTC)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    new_today = (
        db.query(func.count(User.id)).filter(User.created_at >= today_start).scalar()
        or 0
    )
    new_this_week = (
        db.query(func.count(User.id))
        .filter(User.created_at >= now - timedelta(days=7))
        .scalar()
        or 0
    )
    return {
        "new_today": new_today,
        "new_this_week": new_this_week,
    }
