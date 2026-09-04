"""
Движок алертов: применяет правила компании к данным телеметрии.
"""
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from app.models.telematics import (
    GpsPoint, Alert, AlertRule, Notification,
    AlertSeverity, AlertStatus,
)
from app.models.auth import User


# Типы правил
RULE_SPEED = "speed_limit"
RULE_GEOFENCE = "geofence_exit"
RULE_FUEL = "fuel_drain"
RULE_ENGINE = "engine_hours"
RULE_IDLE = "idle_time"
RULE_OFFLINE = "offline"


def process_point_with_rules(db: Session, point: GpsPoint, company_id: int) -> List[Alert]:
    """
    Применяет все активные правила компании к GPS-точке.
    Возвращает список созданных алертов.
    """
    rules = db.scalars(
        select(AlertRule).where(
            and_(
                AlertRule.company_id == company_id,
                AlertRule.is_active == True,
            )
        )
    ).all()

    created_alerts = []

    for rule in rules:
        alert = None

        if rule.rule_type == RULE_SPEED:
            alert = _check_speed(db, point, rule)
        elif rule.rule_type == RULE_FUEL:
            alert = _check_fuel(db, point, rule)
        elif rule.rule_type == RULE_ENGINE:
            alert = _check_engine_hours(db, point, rule)
        elif rule.rule_type == RULE_IDLE:
            alert = _check_idle(db, point, rule)

        if alert:
            created_alerts.append(alert)
            # Создаём уведомления если правило этого требует
            if rule.notify_in_app or rule.notify_email:
                _create_notifications(
                    db, alert, company_id,
                    in_app=rule.notify_in_app,
                    email=rule.notify_email,
                )

    if created_alerts:
        db.commit()

    return created_alerts


def _check_speed(db: Session, point: GpsPoint, rule: AlertRule) -> Optional[Alert]:
    """Проверка превышения скорости."""
    if point.speed is None or rule.threshold is None:
        return None

    if point.speed > rule.threshold:
        return _get_or_create_alert(
            db,
            alert_type=RULE_SPEED,
            severity=rule.severity,
            vehicle_id=point.vehicle_id,
            title=f"Превышение скорости: {point.speed:.0f} км/ч",
            description=f"Лимит: {rule.threshold:.0f} км/ч",
            details={"speed": point.speed, "limit": rule.threshold},
            occurred_at=point.recorded_at,
            company_id=company_id,
        )
    return None


def _check_fuel(db: Session, point: GpsPoint, rule: AlertRule) -> Optional[Alert]:
    """Проверка резкого падения уровня топлива."""
    if point.fuel_level is None or rule.threshold is None:
        return None

    prev = db.scalar(
        select(GpsPoint)
        .where(
            and_(
                GpsPoint.vehicle_id == point.vehicle_id,
                GpsPoint.fuel_level.isnot(None),
                GpsPoint.id < point.id,
            )
        )
        .order_by(GpsPoint.recorded_at.desc())
        .limit(1)
    )

    if prev and prev.fuel_level is not None:
        drop = prev.fuel_level - point.fuel_level
        if drop > rule.threshold:
            return _get_or_create_alert(
                db,
                alert_type=RULE_FUEL,
                severity=rule.severity,
                vehicle_id=point.vehicle_id,
                title=f"Подозрение на слив топлива: {drop:.1f} л",
                description=f"Уровень упал с {prev.fuel_level:.1f} до {point.fuel_level:.1f} л",
                details={"drop": drop, "before": prev.fuel_level, "after": point.fuel_level},
                occurred_at=point.recorded_at,
                company_id=company_id,
            )
    return None


def _check_engine_hours(db: Session, point: GpsPoint, rule: AlertRule) -> Optional[Alert]:
    """Проверка превышения суточных моточасов."""
    if point.engine_hours is None or rule.threshold is None:
        return None

    # Проверяем последнюю точку за сегодня
    today_start = point.recorded_at.replace(hour=0, minute=0, second=0, microsecond=0)
    first_point_today = db.scalar(
        select(GpsPoint)
        .where(
            and_(
                GpsPoint.vehicle_id == point.vehicle_id,
                GpsPoint.engine_hours.isnot(None),
                GpsPoint.recorded_at >= today_start,
            )
        )
        .order_by(GpsPoint.recorded_at.asc())
        .limit(1)
    )

    if first_point_today and first_point_today.engine_hours is not None:
        hours_today = point.engine_hours - first_point_today.engine_hours
        if hours_today > rule.threshold:
            return _get_or_create_alert(
                db,
                alert_type=RULE_ENGINE,
                severity=rule.severity,
                vehicle_id=point.vehicle_id,
                title=f"Превышение суточных моточасов: {hours_today:.1f} ч",
                description=f"Лимит: {rule.threshold:.0f} ч",
                details={"hours_today": hours_today, "limit": rule.threshold},
                occurred_at=point.recorded_at,
                company_id=company_id,
            )
    return None


def _check_idle(db: Session, point: GpsPoint, rule: AlertRule) -> Optional[Alert]:
    """Проверка длительного простоя с включённым двигателем."""
    if rule.threshold is None:
        return None

    if point.engine_on and point.speed is not None and point.speed < 1:
        # Ищем когда началась работа без движения
        idle_start = db.scalar(
            select(GpsPoint.recorded_at)
            .where(
                and_(
                    GpsPoint.vehicle_id == point.vehicle_id,
                    GpsPoint.engine_on == True,
                    GpsPoint.speed < 1,
                )
            )
            .order_by(GpsPoint.recorded_at.asc())
            .limit(1)
        )

        if idle_start:
            idle_minutes = (point.recorded_at - idle_start).total_seconds() / 60
            if idle_minutes > rule.threshold:
                return _get_or_create_alert(
                    db,
                    alert_type=RULE_IDLE,
                    severity=rule.severity,
                    vehicle_id=point.vehicle_id,
                    title=f"Длительный простой: {idle_minutes:.0f} мин",
                    description="Двигатель работает, техника не движется",
                    details={"idle_minutes": idle_minutes, "limit": rule.threshold},
                    occurred_at=point.recorded_at,
                    company_id=company_id,
                )
    return None


def _get_or_create_alert(
    db: Session,
    alert_type: str,
    severity: AlertSeverity,
    vehicle_id: int,
    title: str,
    description: str,
    details: dict,
    occurred_at: datetime,
    company_id: int,
) -> Optional[Alert]:
    """Создаёт алерт, избегая дублирования в течение 10 минут."""
    cutoff = occurred_at - timedelta(minutes=10)
    existing = db.scalar(
        select(Alert).where(
            and_(
                Alert.alert_type == alert_type,
                Alert.vehicle_id == vehicle_id,
                Alert.occurred_at >= cutoff,
                Alert.status == AlertStatus.active,
            )
        )
    )
    if existing:
        return None

    alert = Alert(
        alert_type=alert_type,
        severity=severity,
        status=AlertStatus.active,
        vehicle_id=vehicle_id,
        title=title,
        description=description,
        details=details,
        occurred_at=occurred_at,
        company_id=company_id,
    )
    db.add(alert)
    db.flush()
    return alert


def _create_notifications(
    db: Session,
    alert: Alert,
    company_id: int,
    in_app: bool = True,
    email: bool = False,
) -> None:
    """Создаёт уведомления для админов компании."""
    # Находим админов компании
    admins = db.scalars(
        select(User).where(
            and_(
                User.company_id == company_id,
                User.is_superuser == True,
            )
        )
    ).all()

    for admin in admins:
        if in_app:
            db.add(Notification(
                user_id=admin.id,
                alert_id=alert.id,
                channel="in_app",
                title=alert.title,
                body=alert.description or alert.title,
            ))

        if email:
            # Mock для разработки — в продакшене здесь будет реальный SMTP
            _send_email_mock(admin.email, alert.title, alert.description)
            db.add(Notification(
                user_id=admin.id,
                alert_id=alert.id,
                channel="email",
                title=alert.title,
                body=alert.description or alert.title,
            ))


def _send_email_mock(to: str, subject: str, body: str) -> None:
    """Mock отправки email. В продакшене заменить на SMTP/SendGrid."""
    print(f"📧 [EMAIL MOCK] To: {to} | Subject: {subject}")
    print(f"   Body: {body}")


def seed_default_rules(db: Session, company_id: int) -> None:
    """Создаёт правила по умолчанию для компании."""
    defaults = [
        {
            "name": "Превышение скорости 90 км/ч",
            "rule_type": RULE_SPEED,
            "threshold": 90.0,
            "severity": AlertSeverity.warning,
            "notify_in_app": True,
        },
        {
            "name": "Подозрение на слив топлива",
            "rule_type": RULE_FUEL,
            "threshold": 10.0,
            "severity": AlertSeverity.critical,
            "notify_in_app": True,
            "notify_email": True,
        },
        {
            "name": "Превышение суточных моточасов",
            "rule_type": RULE_ENGINE,
            "threshold": 12.0,
            "severity": AlertSeverity.warning,
            "notify_in_app": True,
        },
        {
            "name": "Длительный простой",
            "rule_type": RULE_IDLE,
            "threshold": 60.0,
            "severity": AlertSeverity.info,
            "notify_in_app": True,
        },
    ]

    for rule_data in defaults:
        existing = db.scalar(
            select(AlertRule).where(
                and_(
                    AlertRule.company_id == company_id,
                    AlertRule.rule_type == rule_data["rule_type"],
                )
            )
        )
        if not existing:
            db.add(AlertRule(company_id=company_id, **rule_data))

    db.commit()