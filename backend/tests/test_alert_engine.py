from datetime import datetime, timedelta, timezone

from app.models.catalog import Category, Vehicle
from app.models.company import Company
from app.models.telematics import (
    GpsPoint, AlertRule, Alert, AlertSeverity, AlertStatus,
)
from app.services.alert_engine import (
    process_point_with_rules,
    seed_default_rules,
)
from tests.conftest import make_test_request


def setup_alert_test(db):
    """Подготовка данных для тестов алертов."""
    company = Company(name="Alert Co", legal_name='ООО "Alert"', inn="7700000001")
    db.add(company); db.flush()

    category = Category(name="Cat", code="alert_cat", level=1, company_id=company.id)
    db.add(category); db.flush()

    vehicle = Vehicle(
        id_type="vin", id_value="ALERT12345678901234",
        category_id=category.id, name="Alert Vehicle",
        status="free", company_id=company.id,
    )
    db.add(vehicle); db.flush()

    return {"company": company, "vehicle": vehicle}


def test_seed_default_rules(db):
    """Правила по умолчанию создаются корректно."""
    data = setup_alert_test(db)
    seed_default_rules(db, data["company"].id)

    rules = db.query(AlertRule).filter(
        AlertRule.company_id == data["company"].id
    ).all()
    assert len(rules) == 4

    rule_types = {r.rule_type for r in rules}
    assert "speed_limit" in rule_types
    assert "fuel_drain" in rule_types
    assert "engine_hours" in rule_types
    assert "idle_time" in rule_types


def test_speed_limit_alert(db):
    """Превышение скорости создаёт алерт."""
    data = setup_alert_test(db)

    # Создаём правило
    rule = AlertRule(
        company_id=data["company"].id,
        name="Speed 60",
        rule_type="speed_limit",
        threshold=60.0,
        severity=AlertSeverity.warning,
    )
    db.add(rule); db.commit()

    # Создаём точку с превышением
    point = GpsPoint(
        vehicle_id=data["vehicle"].id,
        latitude=55.7558,
        longitude=37.6173,
        speed=85.0,
        recorded_at=datetime.now(timezone.utc),
    )
    db.add(point); db.flush()

    alerts = process_point_with_rules(db, point, data["company"].id)

    assert len(alerts) == 1
    assert alerts[0].alert_type == "speed_limit"
    assert "85" in alerts[0].title


def test_no_alert_below_threshold(db):
    """Скорость ниже порога не создаёт алерт."""
    data = setup_alert_test(db)

    rule = AlertRule(
        company_id=data["company"].id,
        name="Speed 90",
        rule_type="speed_limit",
        threshold=90.0,
        severity=AlertSeverity.warning,
    )
    db.add(rule); db.commit()

    point = GpsPoint(
        vehicle_id=data["vehicle"].id,
        latitude=55.7558,
        longitude=37.6173,
        speed=50.0,
        recorded_at=datetime.now(timezone.utc),
    )
    db.add(point); db.flush()

    alerts = process_point_with_rules(db, point, data["company"].id)
    assert len(alerts) == 0


def test_alert_deduplication(db):
    """Дублирующиеся алерты в течение 10 минут не создаются."""
    data = setup_alert_test(db)

    rule = AlertRule(
        company_id=data["company"].id,
        name="Speed 60",
        rule_type="speed_limit",
        threshold=60.0,
        severity=AlertSeverity.warning,
    )
    db.add(rule); db.commit()

    now = datetime.now(timezone.utc)

    # Первая точка — алерт создаётся
    point1 = GpsPoint(
        vehicle_id=data["vehicle"].id,
        latitude=55.7558, longitude=37.6173,
        speed=85.0, recorded_at=now,
    )
    db.add(point1); db.flush()
    alerts1 = process_point_with_rules(db, point1, data["company"].id)
    assert len(alerts1) == 1

    # Вторая точка через 1 минуту — алерт НЕ создаётся (дубль)
    point2 = GpsPoint(
        vehicle_id=data["vehicle"].id,
        latitude=55.7559, longitude=37.6174,
        speed=90.0, recorded_at=now + timedelta(minutes=1),
    )
    db.add(point2); db.flush()
    alerts2 = process_point_with_rules(db, point2, data["company"].id)
    assert len(alerts2) == 0


def test_fuel_drain_alert(db):
    """Резкое падение топлива создаёт критический алерт."""
    data = setup_alert_test(db)

    rule = AlertRule(
        company_id=data["company"].id,
        name="Fuel drain",
        rule_type="fuel_drain",
        threshold=10.0,
        severity=AlertSeverity.critical,
    )
    db.add(rule); db.commit()

    now = datetime.now(timezone.utc)

    # Первая точка с полным баком
    point1 = GpsPoint(
        vehicle_id=data["vehicle"].id,
        latitude=55.7558, longitude=37.6173,
        fuel_level=100.0,
        recorded_at=now,
    )
    db.add(point1); db.flush()

    # Вторая точка с резким падением
    point2 = GpsPoint(
        vehicle_id=data["vehicle"].id,
        latitude=55.7559, longitude=37.6174,
        fuel_level=85.0,
        recorded_at=now + timedelta(minutes=5),
    )
    db.add(point2); db.flush()

    alerts = process_point_with_rules(db, point2, data["company"].id)

    assert len(alerts) == 1
    assert alerts[0].alert_type == "fuel_drain"
    assert alerts[0].severity == AlertSeverity.critical