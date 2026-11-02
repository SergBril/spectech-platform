import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_company_id, get_current_user, get_user_company_ids
from app.core.db import get_db
from app.models.auth import User
from app.models.catalog import Vehicle
from app.models.telematics import (
    Alert,
    AlertRule,
    AlertStatus,
    FuelTransaction,
    Geofence,
    GpsPoint,
    Notification,
)
from app.schemas.telematics import (
    AlertAck,
    FuelTransactionCreate,
    FuelTransactionRead,
    GeofenceCreate,
    GeofenceRead,
    GpsPointCreate,
    GpsPointRead,
    NotificationRead,
    TelematicsDashboard,
)
from app.services.alert_engine import seed_default_rules
from app.services.telematics_service import (
    get_telematics_dashboard,
)

logger = logging.getLogger("spectech.telematics")

router = APIRouter()


# =========================================
# === GPS ===
# =========================================


def _check_vehicle_access(db: Session, vehicle_id: int, company_id: int) -> Vehicle:
    """Проверяет, что техника принадлежит текущей компании."""
    vehicle = db.get(Vehicle, vehicle_id)
    if not vehicle or vehicle.company_id != company_id:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return vehicle


@router.post("/gps/batch")
async def receive_gps_points(
    points: list[GpsPointCreate],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Принимает массив GPS точек (только для техники своей компании)."""
    from app.services.telematics_service import receive_gps_points_batch

    result = await receive_gps_points_batch(
        db=db,
        points_data=[p.model_dump(exclude_none=True) for p in points],
        company_id=company_id,
    )
    return result


@router.post("/gps/single", response_model=GpsPointRead, status_code=201)
async def receive_single_gps_point(
    point: GpsPointCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Принимает одну GPS точку (только для техники своей компании)."""
    from app.services.telematics_service import receive_single_gps_point as svc_receive

    try:
        result = await svc_receive(
            db=db,
            point_data=point.model_dump(exclude_none=True),
            company_id=company_id,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/gps/{vehicle_id}", response_model=list[GpsPointRead])
def get_vehicle_track(
    vehicle_id: int,
    limit: int = Query(default=1000, ge=1, le=5000),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    order: str = Query(default="asc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """История GPS-точек по технике (только своей компании)."""
    _check_vehicle_access(db, vehicle_id, company_id)

    stmt = select(GpsPoint).where(GpsPoint.vehicle_id == vehicle_id)
    if date_from:
        stmt = stmt.where(GpsPoint.recorded_at >= date_from)
    if date_to:
        stmt = stmt.where(GpsPoint.recorded_at <= date_to)
    if order == "asc":
        stmt = stmt.order_by(GpsPoint.recorded_at.asc())
    else:
        stmt = stmt.order_by(GpsPoint.recorded_at.desc())
    stmt = stmt.limit(limit)
    return db.scalars(stmt).all()


@router.get("/gps/{vehicle_id}/stats")
def get_track_stats(
    vehicle_id: int,
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Статистика трека (только для техники своей компании)."""
    from app.services.telematics_service import get_track_stats as svc_track_stats

    _check_vehicle_access(db, vehicle_id, company_id)
    return svc_track_stats(db, vehicle_id, company_id, date_from, date_to)


@router.get("/geofences", response_model=list[GeofenceRead])
def list_geofences(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_ids: list[int] = Depends(get_user_company_ids),
):
    """Список геозон (только своей компании)."""
    stmt = (
        select(Geofence)
        .where(Geofence.company_id.in_(company_ids))
        .order_by(Geofence.name)
    )
    return db.scalars(stmt).all()


@router.post("/geofences", response_model=GeofenceRead, status_code=201)
def create_geofence(
    payload: GeofenceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Создать геозону (для своей компании)."""
    gf = Geofence(**payload.model_dump(), company_id=company_id)
    db.add(gf)
    db.commit()
    db.refresh(gf)
    return gf


@router.delete("/geofences/{geofence_id}", status_code=204)
def delete_geofence(
    geofence_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Удалить геозону (только своей компании)."""
    gf = db.get(Geofence, geofence_id)
    if not gf or gf.company_id != company_id:
        raise HTTPException(status_code=404, detail="Geofence not found")
    gf.is_active = False
    db.commit()


# =========================================
# === Fuel ===
# =========================================



@router.patch("/geofences/{geofence_id}", response_model=GeofenceRead)
def update_geofence(
    geofence_id: int,
    payload: GeofenceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Обновить геозону (только своей компании)."""
    gf = db.get(Geofence, geofence_id)
    if not gf or gf.company_id != company_id:
        raise HTTPException(status_code=404, detail="Geofence not found")

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(gf, key, value)

    db.commit()
    db.refresh(gf)
    return gf


@router.get("/fuel", response_model=list[FuelTransactionRead])
def list_fuel_transactions(
    vehicle_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_ids: list[int] = Depends(get_user_company_ids),
):
    """Список заправок/сливов (только своей компании)."""
    stmt = (
        select(FuelTransaction)
        .join(Vehicle, FuelTransaction.vehicle_id == Vehicle.id)
        .where(Vehicle.company_id.in_(company_ids))
        .order_by(FuelTransaction.occurred_at.desc())
    )
    if vehicle_id:
        _check_vehicle_access(db, vehicle_id, company_id)
        stmt = stmt.where(FuelTransaction.vehicle_id == vehicle_id)
    return db.scalars(stmt.limit(100)).all()


@router.post("/fuel", response_model=FuelTransactionRead, status_code=201)
def create_fuel_transaction(
    payload: FuelTransactionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Создать запись о топливе (для техники своей компании)."""
    _check_vehicle_access(db, payload.vehicle_id, company_id)

    total_cost = None
    if payload.price_per_liter:
        total_cost = payload.volume * payload.price_per_liter
    ft = FuelTransaction(
        **payload.model_dump(),
        total_cost=total_cost,
        company_id=company_id,
    )
    db.add(ft)
    db.commit()
    db.refresh(ft)
    return ft


@router.get("/fuel/stats")
def get_fuel_stats(
    vehicle_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_ids: list[int] = Depends(get_user_company_ids),
):
    """Статистика по топливу (только для техники своей компании)."""
    stmt = (
        select(FuelTransaction)
        .join(Vehicle, FuelTransaction.vehicle_id == Vehicle.id)
        .where(Vehicle.company_id.in_(company_ids))
    )
    if vehicle_id:
        _check_vehicle_access(db, vehicle_id, company_id)
        stmt = stmt.where(FuelTransaction.vehicle_id == vehicle_id)
    transactions = db.scalars(stmt).all()

    if not transactions:
        return {
            "transactions_count": 0,
            "total_volume": 0.0,
            "total_cost": 0.0,
            "avg_consumption": None,
            "last_refuel_at": None,
            "drains_count": 0,
        }

    refuels = [t for t in transactions if t.transaction_type == "refuel"]
    drains = [t for t in transactions if t.transaction_type == "drain"]

    total_volume = float(sum(t.volume for t in refuels))
    total_cost = float(sum(t.total_cost or 0 for t in refuels))

    avg_consumption = None
    odometer_readings = [
        (t.odometer, float(t.volume)) for t in refuels if t.odometer is not None
    ]
    if len(odometer_readings) >= 2:
        odometer_readings.sort(key=lambda x: x[0])
        total_distance = odometer_readings[-1][0] - odometer_readings[0][0]
        total_fuel = sum(v for _, v in odometer_readings[1:])
        if total_distance > 0:
            avg_consumption = round(total_fuel / total_distance * 100, 2)

    last_refuel = max((t.occurred_at for t in refuels), default=None)

    return {
        "transactions_count": len(transactions),
        "refuels_count": len(refuels),
        "drains_count": len(drains),
        "total_volume": round(total_volume, 2),
        "total_cost": round(total_cost, 2),
        "avg_price_per_liter": (
            round(total_cost / total_volume, 2) if total_volume > 0 else 0
        ),
        "avg_consumption": avg_consumption,
        "last_refuel_at": last_refuel.isoformat() if last_refuel else None,
    }


@router.get("/fuel/analytics")
def get_fuel_analytics(
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    vehicle_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Расширенная аналитика топлива за период."""
    from app.services.fuel_service import fuel_service

    if vehicle_id:
        _check_vehicle_access(db, vehicle_id, company_id)

    return fuel_service.get_fuel_analytics(
        db=db,
        company_id=company_id,
        date_from=date_from,
        date_to=date_to,
        vehicle_id=vehicle_id,
    )


@router.get("/fuel/analytics/consumption")
def get_fuel_consumption(
    vehicle_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Расход топлива на моточас и на 100км по технике."""
    from app.services.fuel_service import fuel_service

    if vehicle_id:
        _check_vehicle_access(db, vehicle_id, company_id)

    return fuel_service.get_consumption_rates(
        db=db,
        company_id=company_id,
        vehicle_id=vehicle_id,
    )


@router.get("/fuel/analytics/by-vehicle")
def get_fuel_by_vehicle(
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Статистика топлива по каждой технике (для графиков)."""
    from app.services.fuel_service import fuel_service

    return fuel_service.get_fuel_by_vehicle(
        db=db,
        company_id=company_id,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/fuel/analytics/anomalies")
def detect_fuel_anomalies(
    vehicle_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Детекция аномалий: сливы, перерасход, дорогие заправки."""
    from app.services.fuel_service import fuel_service

    if vehicle_id:
        _check_vehicle_access(db, vehicle_id, company_id)

    return fuel_service.detect_anomalies(
        db=db,
        company_id=company_id,
        vehicle_id=vehicle_id,
    )


# =========================================
# === Alerts ===
# =========================================


class AlertRead(BaseModel):
    id: int
    alert_type: str
    severity: str
    status: str
    vehicle_id: int | None = None
    title: str
    description: str | None = None
    details: dict | None = None
    occurred_at: datetime
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)

    @field_validator("severity", "status", mode="before")
    @classmethod
    def _enum_to_str(cls, v):
        return v.value if hasattr(v, "value") else v


@router.get("/alerts", response_model=list[AlertRead])
def list_alerts(
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_ids: list[int] = Depends(get_user_company_ids),
):
    """Список алертов (только своей компании)."""
    stmt = (
        select(Alert)
        .where(Alert.company_id.in_(company_ids))
        .order_by(Alert.occurred_at.desc())
    )
    if status_filter:
        stmt = stmt.where(Alert.status == status_filter)
    return db.scalars(stmt.limit(limit)).all()


@router.post("/alerts/{alert_id}/acknowledge", response_model=AlertRead)
def acknowledge_alert(
    alert_id: int,
    payload: AlertAck,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Подтвердить алерт (только своей компании)."""
    alert = db.get(Alert, alert_id)
    if not alert or alert.company_id != company_id:
        raise HTTPException(status_code=404, detail="Alert not found")
    if alert.status != AlertStatus.active:
        raise HTTPException(status_code=409, detail="Alert not active")
    alert.status = AlertStatus.acknowledged
    alert.acknowledged_by = current_user.id
    alert.acknowledged_at = datetime.now(UTC)
    db.commit()
    db.refresh(alert)
    return alert


# =========================================
# === Notifications ===
# =========================================


@router.get("/notifications", response_model=list[NotificationRead])
def list_notifications(
    unread_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Список уведомлений текущего пользователя (уже изолировано по user_id)."""
    stmt = (
        select(Notification)
        .where(Notification.user_id == current_user.id)
        .order_by(Notification.sent_at.desc())
    )
    if unread_only:
        stmt = stmt.where(Notification.is_read == False)
    return db.scalars(stmt.limit(limit)).all()


@router.post("/notifications/{notification_id}/read", response_model=NotificationRead)
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    notif = db.get(Notification, notification_id)
    if not notif or notif.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Notification not found")
    notif.is_read = True
    notif.read_at = datetime.now(UTC)
    db.commit()
    db.refresh(notif)
    return notif


@router.post("/notifications/mark-all-read")
async def mark_all_notifications_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Пометить все уведомления как прочитанные."""
    from app.services.notification_service import mark_all_read

    count = await mark_all_read(db, current_user.id)
    return {"updated": count}


@router.get("/notifications/unread-count")
def get_unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from sqlalchemy import func

    count = db.scalar(
        select(func.count(Notification.id)).where(
            Notification.user_id == current_user.id,
            Notification.is_read == False,
        )
    )
    return {"unread_count": count or 0}


# =========================================
# === Dashboard ===
# =========================================


@router.get("/dashboard", response_model=TelematicsDashboard)
def get_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Дашборд телематики (только своей компании)."""
    stats = get_telematics_dashboard(db, company_id)
    return TelematicsDashboard(**stats)


# =========================================
# === Alert Rules ===
# =========================================


class AlertRuleCreate(BaseModel):
    name: str
    rule_type: str
    threshold: float | None = None
    severity: str = "warning"
    notify_email: bool = False
    notify_in_app: bool = True


class AlertRuleRead(BaseModel):
    id: int
    name: str
    rule_type: str
    threshold: float | None = None
    severity: str
    is_active: bool
    notify_email: bool
    notify_in_app: bool

    model_config = ConfigDict(from_attributes=True)

    @field_validator("severity", mode="before")
    @classmethod
    def _enum_to_str(cls, v):
        return v.value if hasattr(v, "value") else v


@router.get("/rules", response_model=list[AlertRuleRead])
def list_alert_rules(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_ids: list[int] = Depends(get_user_company_ids),
):
    """Список правил алертов (только своей компании)."""
    stmt = select(AlertRule).where(AlertRule.company_id == company_id)
    return db.scalars(stmt).all()


@router.post("/rules", response_model=AlertRuleRead, status_code=201)
def create_alert_rule(
    payload: AlertRuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Создать правило алерта (для своей компании)."""
    rule = AlertRule(
        company_id=company_id,
        **payload.model_dump(),
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.post("/rules/seed-defaults", status_code=201)
def seed_defaults(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Создать правила по умолчанию для компании."""
    seed_default_rules(db, company_id)
    return {"detail": "Default rules created"}


@router.delete("/rules/{rule_id}", status_code=204)
def delete_alert_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Удалить правило алерта (только своей компании)."""
    rule = db.get(AlertRule, rule_id)
    if not rule or rule.company_id != company_id:
        raise HTTPException(status_code=404, detail="Rule not found")
    rule.is_active = False
    db.commit()


# =========================================
# === Dashboard Summary ===
# =========================================


@router.get("/dashboard/summary", response_model=TelematicsDashboard)
def get_dashboard_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_ids: list[int] = Depends(get_user_company_ids),
):
    """Агрегированная статистика для дашборда (только своей компании)."""
    from app.services.telematics_service import get_dashboard_summary as svc_dashboard
    return svc_dashboard(db, company_ids)


@router.post("/wialon/webhook")
def receive_wialon_webhook(
    payload: dict,
    db: Session = Depends(get_db),
):
    """
    Принять webhook от Wialon.

    Wialon отправляет данные о позициях техники в формате JSON.
    Адаптер парсит payload и сохраняет точки в gps_points.

    Пример payload:
    {
        "unit_id": 1001,
        "type": "message",
        "time": 1727539200,
        "pos": {
            "x": 37.6176,
            "y": 55.7558,
            "s": 45.5,
            "c": 180
        },
        "param": {
            "avl_fuel_level": 150.0,
            "avl_engine_hours": 757.5,
            "avl_driver_id": 1
        }
    }
    """
    from app.services.telematics.wialon_adapter import wialon_adapter

    response = wialon_adapter.process_webhook(db, payload)

    if response.status == "success":
        return response
    else:
        raise HTTPException(
            status_code=400,
            detail={
                "status": response.status,
                "message": response.message,
                "errors": response.errors,
            },
        )


@router.get("/wialon/mappings")
def list_wialon_mappings():
    """
    Получить маппинг Wialon unit_id → vehicle_id.

    В production должен читаться из БД (таблица wialon_mappings).
    """
    from app.services.telematics.wialon_adapter import wialon_adapter

    mappings = [
        {
            "wialon_unit_id": unit_id,
            "vehicle_id": vehicle_id,
        }
        for unit_id, vehicle_id in wialon_adapter.UNIT_TO_VEHICLE_MAP.items()
    ]

    return {"mappings": mappings, "total": len(mappings)}


# === FUEL THEFT DETECTOR ===


@router.post("/fuel/detect-theft")
def detect_fuel_theft(
    vehicle_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """
    Запустить детектор сливов топлива.

    Если vehicle_id указан — проверяет только эту технику.
    Если не указана — проверяет всю технику компании.

    Возвращает список обнаруженных сливов.
    """
    from app.services.telematics.fuel_theft_detector import fuel_theft_detector

    if vehicle_id:
        _check_vehicle_access(db, vehicle_id, company_id)
        theft = fuel_theft_detector.check_vehicle(db, vehicle_id)
        detected = [theft] if theft else []
    else:
        detected = fuel_theft_detector.check_all_vehicles(db, company_id)

    return {
        "checked_vehicles": 1 if vehicle_id else "all",
        "thefts_detected": len(detected),
        "thefts": [
            {
                "id": t.id,
                "vehicle_id": t.vehicle_id,
                "volume_liters": float(t.volume),
                "fuel_before": t.fuel_level_before,
                "fuel_after": t.fuel_level_after,
                "occurred_at": t.occurred_at.isoformat(),
                "location": {
                    "latitude": t.location_latitude,
                    "longitude": t.location_longitude,
                },
            }
            for t in detected
        ],
    }


# === RECONCILIATION SERVICE ===


@router.post("/shifts/{shift_task_id}/reconcile")
def reconcile_shift_data(
    shift_task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """
    Выполнить сверку данных оператор vs телематика для сменного задания.

    Сравнивает данные из shift_reports с gps_points за период смены.
    Автоматически подтверждает если расхождение < 5%.
    """
    from app.models.shift import ShiftTask
    from app.services.telematics.reconciliation_service import reconciliation_service

    # Проверяем доступ к ShiftTask
    shift_task = db.get(ShiftTask, shift_task_id)
    if not shift_task or shift_task.company_id != company_id:
        raise HTTPException(status_code=404, detail="ShiftTask not found")

    # Выполняем сверку
    reconciliation = reconciliation_service.reconcile_shift_task(db, shift_task_id)

    if not reconciliation:
        raise HTTPException(
            status_code=400,
            detail="Failed to perform reconciliation",
        )

    return {
        "shift_task_id": shift_task_id,
        "reconciliation_id": reconciliation.id,
        "status": reconciliation.reconciliation_status,
        "operator_data": {
            "moto_hours": reconciliation.operator_moto_hours,
            "odometer": reconciliation.operator_odometer,
            "fuel_used": reconciliation.operator_fuel_used,
        },
        "telematics_data": {
            "moto_hours": reconciliation.telematics_moto_hours,
            "odometer": reconciliation.telematics_odometer,
            "fuel_used": reconciliation.telematics_fuel_used,
            "data_points_count": reconciliation.telematics_data_points_count,
        },
        "differences": {
            "moto_hours_diff_percent": reconciliation.moto_hours_diff_percent,
            "odometer_diff_percent": reconciliation.odometer_diff_percent,
            "fuel_diff_percent": reconciliation.fuel_diff_percent,
        },
        "decision_source": reconciliation.decision_source,
        "final_values": {
            "moto_hours": reconciliation.final_moto_hours,
            "odometer": reconciliation.final_odometer,
            "fuel_used": reconciliation.final_fuel_used,
        },
    }
