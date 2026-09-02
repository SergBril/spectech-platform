from datetime import datetime, timezone

from app.models.auth import User
from app.models.catalog import Category, Vehicle
from app.models.company import Company
from app.models.contractor import Contractor
from app.services.auth_service import hash_password
from app.services.rbac_service import init_system_data
from tests.conftest import make_test_request


def setup_telematics_data(db):
    """Подготовка данных для тестов телематики."""
    init_system_data(db)

    company = Company(name="Tel Co", legal_name='ООО "Tel"', inn="7712345679")
    db.add(company)
    db.flush()

    user = User(
        email="telematics@test.com",
        full_name="Telematics Tester",
        password_hash=hash_password("test123"),
        company_id=company.id,
        is_superuser=True,
    )
    db.add(user)
    db.flush()

    client = Contractor(
        type="client",
        name="Tel Client",
        inn="7798765433",
        company_id=company.id,
    )
    db.add(client)
    db.flush()

    category = Category(
        name="Tel Category",
        code="tel_cat",
        level=1,
        company_id=company.id,
    )
    db.add(category)
    db.flush()

    vehicle = Vehicle(
        id_type="vin",
        id_value="TEL12345678901234",
        category_id=category.id,
        name="Tel Vehicle",
        status="free",
        company_id=company.id,
    )
    db.add(vehicle)
    db.flush()

    request = make_test_request(db, client.id, category.id, company.id)
    db.add(request)
    db.commit()

    return {
        "user": user,
        "company": company,
        "vehicle": vehicle,
    }


def _setup(client, db):
    from app.api.deps import get_current_user
    from app.main import app
    data = setup_telematics_data(db)
    app.dependency_overrides[get_current_user] = lambda: data["user"]
    return data


def _clear():
    from app.main import app
    app.dependency_overrides.clear()


def test_seed_default_rules_endpoint(client, db):
    """POST /telematics/rules/seed-defaults создаёт правила."""
    _setup(client, db)
    try:
        r = client.post("/api/v1/telematics/rules/seed-defaults")
        assert r.status_code == 201
        assert r.json()["detail"] == "Default rules created"
    finally:
        _clear()


def test_list_rules_after_seed(client, db):
    """GET /telematics/rules возвращает правила после сида."""
    _setup(client, db)
    try:
        client.post("/api/v1/telematics/rules/seed-defaults")
        r = client.get("/api/v1/telematics/rules")
        assert r.status_code == 200
        rules = r.json()
        assert len(rules) == 4
        rule_types = {r["rule_type"] for r in rules}
        assert "speed_limit" in rule_types
    finally:
        _clear()


def test_create_custom_rule(client, db):
    """POST /telematics/rules создаёт пользовательское правило."""
    _setup(client, db)
    try:
        r = client.post("/api/v1/telematics/rules", json={
            "name": "Тест правило",
            "rule_type": "speed_limit",
            "threshold": 70.0,
            "severity": "warning",
        })
        assert r.status_code == 201
        body = r.json()
        assert body["name"] == "Тест правило"
        assert body["threshold"] == 70.0
        assert body["is_active"] is True
    finally:
        _clear()


def test_receive_gps_points(client, db):
    """POST /telematics/gps принимает точки."""
    d = _setup(client, db)
    try:
        r = client.post("/api/v1/telematics/gps", json={
            "points": [
                {
                    "vehicle_id": d["vehicle"].id,
                    "latitude": 55.7558,
                    "longitude": 37.6173,
                    "speed": 45.0,
                    "engine_on": True,
                    "fuel_level": 100.0,
                    "recorded_at": datetime.now(timezone.utc).isoformat(),
                }
            ]
        })
        assert r.status_code == 201
        body = r.json()
        assert len(body) == 1
        assert body[0]["vehicle_id"] == d["vehicle"].id
    finally:
        _clear()


def test_get_vehicle_track(client, db):
    """GET /telematics/gps/{vehicle_id} возвращает историю."""
    d = _setup(client, db)
    try:
        # Отправляем 3 точки
        for i in range(3):
            client.post("/api/v1/telematics/gps/single", json={
                "vehicle_id": d["vehicle"].id,
                "latitude": 55.7558 + i * 0.001,
                "longitude": 37.6173 + i * 0.001,
                "speed": 30.0 + i,
                "recorded_at": datetime.now(timezone.utc).isoformat(),
            })

        r = client.get(f"/api/v1/telematics/gps/{d['vehicle'].id}")
        assert r.status_code == 200
        track = r.json()
        assert len(track) == 3
    finally:
        _clear()


def test_create_geofence(client, db):
    """POST /telematics/geofences создаёт геозону."""
    _setup(client, db)
    try:
        r = client.post("/api/v1/telematics/geofences", json={
            "name": "МКАД-Север",
            "description": "Северная часть МКАД",
            "type": "circle",
            "center_latitude": 55.8876,
            "center_longitude": 37.4610,
            "radius_meters": 500,
        })
        assert r.status_code == 201
        body = r.json()
        assert body["name"] == "МКАД-Север"
        assert body["type"] == "circle"
        assert body["is_active"] is True
    finally:
        _clear()


def test_list_geofences(client, db):
    """GET /telematics/geofences возвращает список."""
    _setup(client, db)
    try:
        client.post("/api/v1/telematics/geofences", json={
            "name": "Зона 1",
            "type": "circle",
            "center_latitude": 55.75,
            "center_longitude": 37.61,
            "radius_meters": 1000,
        })
        r = client.get("/api/v1/telematics/geofences")
        assert r.status_code == 200
        assert len(r.json()) >= 1
    finally:
        _clear()


def test_fuel_transaction(client, db):
    """POST /telematics/fuel регистрирует заправку."""
    d = _setup(client, db)
    try:
        r = client.post("/api/v1/telematics/fuel", json={
            "vehicle_id": d["vehicle"].id,
            "transaction_type": "refuel",
            "volume": 50.0,
            "price_per_liter": 55.0,
            "fuel_level_before": 30.0,
            "fuel_level_after": 80.0,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
        })
        assert r.status_code == 201
        body = r.json()
        assert body["volume"] == "50.00"
        assert float(body["total_cost"]) == 2750.0
    finally:
        _clear()


def test_list_alerts_empty(client, db):
    """GET /telematics/alerts возвращает пустой список."""
    _setup(client, db)
    try:
        r = client.get("/api/v1/telematics/alerts")
        assert r.status_code == 200
        assert r.json() == []
    finally:
        _clear()


def test_unread_notifications_count(client, db):
    """GET /telematics/notifications/unread-count возвращает 0."""
    _setup(client, db)
    try:
        r = client.get("/api/v1/telematics/notifications/unread-count")
        assert r.status_code == 200
        assert r.json()["unread_count"] == 0
    finally:
        _clear()


def test_telematics_dashboard(client, db):
    """GET /telematics/dashboard возвращает статистику."""
    _setup(client, db)
    try:
        r = client.get("/api/v1/telematics/dashboard")
        assert r.status_code == 200
        body = r.json()
        for key in ("vehicles_online", "vehicles_moving", "active_alerts",
                    "total_fuel_today", "total_engine_hours_today",
                    "geofence_events_today"):
            assert key in body
    finally:
        _clear()


def test_full_telematics_workflow(client, db):
    """Полный цикл: правила → GPS → алерт → подтверждение."""
    d = _setup(client, db)
    try:
        # 1. Создаём правило скорости
        client.post("/api/v1/telematics/rules", json={
            "name": "Speed 50",
            "rule_type": "speed_limit",
            "threshold": 50.0,
            "severity": "warning",
        })

        # 2. Отправляем точку с превышением
        client.post("/api/v1/telematics/gps/single", json={
            "vehicle_id": d["vehicle"].id,
            "latitude": 55.7558,
            "longitude": 37.6173,
            "speed": 80.0,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        })

        # 3. Проверяем что алерт создался
        alerts = client.get("/api/v1/telematics/alerts").json()
        assert len(alerts) >= 1
        alert_id = alerts[0]["id"]
        assert alerts[0]["alert_type"] == "speed_limit"
        assert alerts[0]["status"] == "active"

        # 4. Подтверждаем алерт
        ack = client.post(
            f"/api/v1/telematics/alerts/{alert_id}/acknowledge",
            json={},
        )
        assert ack.status_code == 200
        assert ack.json()["status"] == "acknowledged"

        # 5. Проверяем что алерт больше не активен
        alerts2 = client.get("/api/v1/telematics/alerts?status=active").json()
        assert len(alerts2) == 0
    finally:
        _clear()