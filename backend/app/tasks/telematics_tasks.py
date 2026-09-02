"""Задачи телематики через Celery."""
import logging
from datetime import datetime, timedelta, timezone

from app.core.celery_app import celery_app

logger = logging.getLogger("spectech.tasks.telematics")


@celery_app.task(name="app.tasks.telematics_tasks.aggregate_engine_hours")
def aggregate_engine_hours(vehicle_id: int, date_str: str = None):
    """Агрегирует моточасы за день для техники."""
    db = None
    try:
        from app.core.db import SessionLocal
        from app.models.telematics import GpsPoint, EngineHoursLog
        from sqlalchemy import func
        
        db = SessionLocal()
        
        if date_str:
            target_date = datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
        else:
            target_date = datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
        
        end_date = target_date + timedelta(days=1)
        
        # Получаем первую и последнюю точку за день
        first_point = db.query(GpsPoint).filter(
            GpsPoint.vehicle_id == vehicle_id,
            GpsPoint.recorded_at >= target_date,
            GpsPoint.recorded_at < end_date,
            GpsPoint.engine_hours.isnot(None),
        ).order_by(GpsPoint.recorded_at.asc()).first()
        
        last_point = db.query(GpsPoint).filter(
            GpsPoint.vehicle_id == vehicle_id,
            GpsPoint.recorded_at >= target_date,
            GpsPoint.recorded_at < end_date,
            GpsPoint.engine_hours.isnot(None),
        ).order_by(GpsPoint.recorded_at.desc()).first()
        
        if not first_point or not last_point:
            logger.info(f"No GPS data for vehicle {vehicle_id} on {target_date.date()}")
            return {"status": "skipped", "reason": "no_data"}
        
        total_hours = float(last_point.engine_hours - first_point.engine_hours)
        
        # Считаем время в простое (скорость < 1 км/ч)
        idle_count = db.query(func.count(GpsPoint.id)).filter(
            GpsPoint.vehicle_id == vehicle_id,
            GpsPoint.recorded_at >= target_date,
            GpsPoint.recorded_at < end_date,
            GpsPoint.engine_on == True,
            GpsPoint.speed < 1,
        ).scalar() or 0
        
        total_points = db.query(func.count(GpsPoint.id)).filter(
            GpsPoint.vehicle_id == vehicle_id,
            GpsPoint.recorded_at >= target_date,
            GpsPoint.recorded_at < end_date,
            GpsPoint.engine_on == True,
        ).scalar() or 1
        
        idle_hours = total_hours * (idle_count / total_points)
        work_hours = total_hours - idle_hours
        
        # Сохраняем или обновляем лог
        existing = db.query(EngineHoursLog).filter(
            EngineHoursLog.vehicle_id == vehicle_id,
            EngineHoursLog.date == target_date,
        ).first()
        
        from decimal import Decimal
        
        if existing:
            existing.hours = Decimal(str(total_hours))
            existing.idle_hours = Decimal(str(idle_hours))
            existing.work_hours = Decimal(str(work_hours))
        else:
            log = EngineHoursLog(
                vehicle_id=vehicle_id,
                date=target_date,
                hours=Decimal(str(total_hours)),
                idle_hours=Decimal(str(idle_hours)),
                work_hours=Decimal(str(work_hours)),
            )
            db.add(log)
        
        db.commit()
        
        logger.info(f"Engine hours aggregated for vehicle {vehicle_id}: {total_hours:.2f}h total")
        
        return {
            "status": "success",
            "vehicle_id": vehicle_id,
            "date": target_date.date().isoformat(),
            "total_hours": round(total_hours, 2),
            "idle_hours": round(idle_hours, 2),
            "work_hours": round(work_hours, 2),
        }
    except Exception as e:
        logger.error(f"Failed to aggregate engine hours: {e}")
        if db:
            db.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        if db:
            db.close()


@celery_app.task(name="app.tasks.telematics_tasks.cleanup_old_gps_points")
def cleanup_old_gps_points(days_old: int = 90):
    """Удаляет старые GPS точки (старше 90 дней)."""
    db = None
    try:
        from app.core.db import SessionLocal
        from app.models.telematics import GpsPoint
        
        db = SessionLocal()
        
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_old)
        
        deleted = db.query(GpsPoint).filter(
            GpsPoint.recorded_at < cutoff
        ).delete(synchronize_session=False)
        
        db.commit()
        
        logger.info(f"Cleaned up {deleted} old GPS points (older than {days_old} days)")
        
        return {
            "status": "success",
            "deleted_count": deleted,
            "days_old": days_old,
        }
    except Exception as e:
        logger.error(f"Failed to cleanup GPS points: {e}")
        if db:
            db.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        if db:
            db.close()


@celery_app.task(name="app.tasks.telematics_tasks.detect_offline_vehicles")
def detect_offline_vehicles(minutes_threshold: int = 60):
    """Определяет технику которая не передаёт данные дольше указанного времени."""
    db = None
    try:
        from app.core.db import SessionLocal
        from app.models.catalog import Vehicle
        from app.models.telematics import GpsPoint
        from sqlalchemy import func
        
        db = SessionLocal()
        
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes_threshold)
        
        # Находим технику с последней точкой старее cutoff
        subquery = db.query(
            GpsPoint.vehicle_id,
            func.max(GpsPoint.recorded_at).label("last_seen"),
        ).group_by(GpsPoint.vehicle_id).subquery()
        
        offline_vehicles = db.query(
            Vehicle.id,
            Vehicle.name,
            subquery.c.last_seen,
        ).join(
            subquery, Vehicle.id == subquery.c.vehicle_id
        ).filter(
            subquery.c.last_seen < cutoff,
            Vehicle.is_deleted == False,
        ).all()
        
        result = []
        for vehicle in offline_vehicles:
            result.append({
                "vehicle_id": vehicle.id,
                "vehicle_name": vehicle.name,
                "last_seen": vehicle.last_seen.isoformat() if vehicle.last_seen else None,
                "offline_minutes": int((datetime.now(timezone.utc) - vehicle.last_seen).total_seconds() / 60) if vehicle.last_seen else None,
            })
            logger.warning(f"Vehicle {vehicle.name} offline since {vehicle.last_seen}")
        
        logger.info(f"Found {len(result)} offline vehicles (>{minutes_threshold}min)")
        
        return {
            "status": "success",
            "offline_count": len(result),
            "vehicles": result,
            "threshold_minutes": minutes_threshold,
        }
    except Exception as e:
        logger.error(f"Failed to detect offline vehicles: {e}")
        if db:
            db.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        if db:
            db.close()