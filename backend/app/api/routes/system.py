"""Системные эндпоинты: health, метрики, версия."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.services.metrics_service import get_metrics

router = APIRouter()

APP_VERSION = "0.5.0-dev"
_start_time = datetime.now(timezone.utc)


@router.get("/health")
def health():
    """Базовый health-check (быстрый, для балансировщика)."""
    return {"status": "ok", "version": APP_VERSION}


@router.get("/health/detailed")
def health_detailed(db: Session = Depends(get_db)):
    """Подробный health-check с проверкой БД и статистикой."""
    from app.models.auth import User
    from app.models.catalog import Vehicle
    from app.models.finance import Invoice
    from app.models.telematics import GpsPoint

    try:
        db_status = "ok"
        users_count = db.scalar(select(func.count(User.id))) or 0
        vehicles_count = db.scalar(select(func.count(Vehicle.id))) or 0
        invoices_count = db.scalar(select(func.count(Invoice.id))) or 0
        gps_points_count = db.scalar(select(func.count(GpsPoint.id))) or 0
    except Exception as e:
        db_status = f"error: {str(e)[:100]}"
        users_count = vehicles_count = invoices_count = gps_points_count = 0

    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "version": APP_VERSION,
        "started_at": _start_time.isoformat(),
        "current_time": datetime.now(timezone.utc).isoformat(),
        "database": {
            "status": db_status,
            "tables": {
                "users": users_count,
                "vehicles": vehicles_count,
                "invoices": invoices_count,
                "gps_points": gps_points_count,
            },
        },
    }


@router.get("/metrics")
def metrics():
    """Метрики приложения (в памяти)."""
    return get_metrics()
    from app.services.background_service import get_task_log


@router.get("/background-log")
def background_log():
    """Журнал фоновых задач (без авторизации)."""
    from app.services.background_service import get_task_log
    tasks = get_task_log()
    return {
        "tasks": tasks,
        "total": len(tasks),
    }