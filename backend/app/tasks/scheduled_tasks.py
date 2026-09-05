"""Периодические задачи, запускаемые через Celery Beat."""

import logging
from datetime import UTC, datetime, timedelta

from app.core.celery_app import celery_app

logger = logging.getLogger("spectech.tasks.scheduled")


@celery_app.task(name="app.tasks.scheduled_tasks.aggregate_all_vehicles_engine_hours")
def aggregate_all_vehicles_engine_hours():
    """Агрегирует моточасы для всей техники за вчера."""
    db = None
    try:
        from app.core.db import SessionLocal
        from app.models.catalog import Vehicle
        from app.tasks.telematics_tasks import aggregate_engine_hours

        db = SessionLocal()

        yesterday = (datetime.now(UTC) - timedelta(days=1)).date().isoformat()

        vehicles = (
            db.query(Vehicle)
            .filter(
                Vehicle.is_deleted == False,
                Vehicle.status != "archived",
            )
            .all()
        )

        logger.info(f"Starting engine hours aggregation for {len(vehicles)} vehicles")

        # Запускаем агрегацию для каждой техники асинхронно
        tasks = []
        for vehicle in vehicles:
            task = aggregate_engine_hours.delay(
                vehicle_id=vehicle.id,
                date_str=yesterday,
            )
            tasks.append(task)

        return {
            "status": "success",
            "vehicles_count": len(vehicles),
            "tasks_queued": len(tasks),
            "date": yesterday,
        }
    except Exception as e:
        logger.error(f"Failed to aggregate engine hours: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        if db:
            db.close()


@celery_app.task(name="app.tasks.scheduled_tasks.send_morning_digest")
def send_morning_digest():
    """Отправляет утренний дайджест всем админам."""
    db = None
    try:
        from sqlalchemy import func

        from app.core.db import SessionLocal
        from app.models.auth import User
        from app.models.dispatch import Request
        from app.models.finance import DocumentStatus, Invoice
        from app.models.telematics import Alert, AlertStatus
        from app.tasks.email_tasks import send_email_async

        db = SessionLocal()

        today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday = today - timedelta(days=1)

        # Собираем статистику за вчера
        alerts_count = (
            db.query(func.count(Alert.id))
            .filter(
                Alert.occurred_at >= yesterday,
                Alert.occurred_at < today,
            )
            .scalar()
            or 0
        )

        active_alerts = (
            db.query(func.count(Alert.id))
            .filter(
                Alert.status == AlertStatus.active,
            )
            .scalar()
            or 0
        )

        invoices_count = (
            db.query(func.count(Invoice.id))
            .filter(
                Invoice.invoice_date >= yesterday.date(),
                Invoice.invoice_date < today.date(),
            )
            .scalar()
            or 0
        )

        unpaid_invoices = (
            db.query(func.count(Invoice.id))
            .filter(
                Invoice.status.in_(
                    [DocumentStatus.sent, DocumentStatus.partially_paid]
                ),
            )
            .scalar()
            or 0
        )

        requests_count = (
            db.query(func.count(Request.id))
            .filter(
                Request.created_at >= yesterday,
                Request.created_at < today,
            )
            .scalar()
            or 0
        )

        # HTML шаблон дайджеста
        digest_html = f"""
        <!DOCTYPE html>
        <html>
        <head><meta charset="UTF-8"></head>
        <body style="font-family: Arial, sans-serif; padding: 20px; background-color: #f5f5f5;">
            <div style="max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px;">
                <h2 style="color: #1976d2;">📊 Утренний дайджест</h2>
                <p style="color: #666;">{today.strftime('%d.%m.%Y')}</p>

                <hr style="border: none; border-top: 1px solid #eee;">

                <h3>🚨 Алерты</h3>
                <p>Вчера: <b>{alerts_count}</b> новых</p>
                <p>Активных сейчас: <b style="color: {'red' if active_alerts > 0 else 'green'};">{active_alerts}</b></p>

                <h3>💰 Финансы</h3>
                <p>Вчера создано счетов: <b>{invoices_count}</b></p>
                <p>Неоплаченных: <b>{unpaid_invoices}</b></p>

                <h3>📋 Заявки</h3>
                <p>Вчера создано: <b>{requests_count}</b></p>

                <hr style="border: none; border-top: 1px solid #eee;">

                <p style="color: #999; font-size: 12px; margin-top: 30px;">
                    СпецТехника Про — автоматический дайджест
                </p>
            </div>
        </body>
        </html>
        """

        # Находим админов
        admins = (
            db.query(User)
            .filter(
                User.is_superuser == True,
                User.email.isnot(None),
            )
            .all()
        )

        tasks = []
        for admin in admins:
            task = send_email_async.delay(
                to_email=admin.email,
                subject=f"📊 Утренний дайджест — {today.strftime('%d.%m.%Y')}",
                body_html=digest_html,
            )
            tasks.append(task)

        logger.info(f"Morning digest sent to {len(admins)} admins")

        return {
            "status": "success",
            "admins_notified": len(admins),
            "stats": {
                "alerts_yesterday": alerts_count,
                "active_alerts": active_alerts,
                "invoices_yesterday": invoices_count,
                "unpaid_invoices": unpaid_invoices,
                "requests_yesterday": requests_count,
            },
        }
    except Exception as e:
        logger.error(f"Failed to send morning digest: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        if db:
            db.close()


@celery_app.task(name="app.tasks.scheduled_tasks.system_health_check")
def system_health_check():
    """Проверяет здоровье системы каждые 5 минут."""
    try:
        from sqlalchemy import text

        from app.core.db import SessionLocal

        db = SessionLocal()

        # Проверяем подключение к БД
        db.execute(text("SELECT 1"))
        db_status = "ok"

        # Проверяем размер таблиц
        from sqlalchemy import func

        from app.models.finance import Invoice
        from app.models.telematics import GpsPoint

        gps_count = db.query(func.count(GpsPoint.id)).scalar() or 0
        invoices_count = db.query(func.count(Invoice.id)).scalar() or 0

        db.close()

        health_data = {
            "status": "healthy",
            "database": db_status,
            "gps_points_count": gps_count,
            "invoices_count": invoices_count,
            "checked_at": datetime.now(UTC).isoformat(),
        }

        # Логируем только если что-то не так
        if db_status != "ok":
            logger.warning(f"Health check: {health_data}")

        return health_data

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "checked_at": datetime.now(UTC).isoformat(),
        }
