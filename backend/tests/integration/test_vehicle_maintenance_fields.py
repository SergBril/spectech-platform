"""Поля ТО должны быть управляемы через API и доходить до расчёта просрочки.

Интервал существовал в модели, но не был проброшен в схемы: все машины получали
дефолт 250 независимо от типа и условий работы. Регламент CAT 320D - 500 м/ч,
КАМАЗ на стройплощадке - 600 м/ч, поэтому одно число на парк неверно.
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


def _payload(**over):
    base = {
        "name": "Экскаватор тестовый",
        "id_type": "internal",
        "id_value": "TEST-MNT-001",
        "status": "free",
    }
    base.update(over)
    return base


def test_create_with_custom_interval(auth_client: TestClient, db_session: Session):
    r = auth_client.post("/api/v1/vehicles", json=_payload(maintenance_interval=600))
    assert r.status_code == 201, r.text
    assert r.json()["maintenance_interval"] == 600


def test_create_defaults_to_model_interval(
    auth_client: TestClient, db_session: Session
):
    r = auth_client.post("/api/v1/vehicles", json=_payload())
    assert r.status_code == 201, r.text
    assert r.json()["maintenance_interval"] == 250


def test_create_accepts_initial_readings(auth_client: TestClient, db_session: Session):
    """Б/у техника приходит с фактической наработкой и историей последнего ТО."""
    r = auth_client.post(
        "/api/v1/vehicles",
        json=_payload(
            engine_hours=760,
            last_maintenance_hours=500,
            maintenance_interval=250,
        ),
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert float(data["engine_hours"]) == 760
    assert float(data["last_maintenance_hours"]) == 500


def test_patch_interval_leaves_other_fields_alone(
    auth_client: TestClient, sample_vehicle
):
    vid = sample_vehicle.id
    name_before = sample_vehicle.name
    r = auth_client.patch(f"/api/v1/vehicles/{vid}", json={"maintenance_interval": 500})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["maintenance_interval"] == 500
    assert data["name"] == name_before, "частичное обновление не должно менять имя"


def test_patch_without_interval_does_not_reset_it(
    auth_client: TestClient, sample_vehicle
):
    """exclude_unset обязан защищать поля, которых нет в запросе."""
    vid = sample_vehicle.id
    assert (
        auth_client.patch(
            f"/api/v1/vehicles/{vid}", json={"maintenance_interval": 600}
        ).status_code
        == 200
    )
    r = auth_client.patch(f"/api/v1/vehicles/{vid}", json={"name": "Переименовано"})
    assert r.status_code == 200, r.text
    assert (
        r.json()["maintenance_interval"] == 600
    ), "обновление имени не должно сбрасывать интервал к дефолту"


def test_interval_must_be_positive(auth_client: TestClient, db_session: Session):
    r = auth_client.post("/api/v1/vehicles", json=_payload(maintenance_interval=0))
    assert r.status_code == 422, "нулевой интервал означал бы вечную просрочку"


def test_negative_readings_rejected(auth_client: TestClient, db_session: Session):
    r = auth_client.post("/api/v1/vehicles", json=_payload(engine_hours=-10))
    assert r.status_code == 422


def test_readings_set_via_api_reach_the_due_calculation(
    auth_client: TestClient, db_session: Session
):
    """Сквозная проверка: API -> модель -> расчёт просрочки."""
    from app.services.maintenance_service import find_vehicles_due_without_order

    r = auth_client.post(
        "/api/v1/vehicles",
        json=_payload(
            id_value="TEST-MNT-DUE",
            engine_hours=800,
            next_maintenance_hours=750,
        ),
    )
    assert r.status_code == 201, r.text
    vid = r.json()["id"]

    db_session.expire_all()
    due = {d["vehicle_id"] for d in find_vehicles_due_without_order(db_session)}
    assert (
        vid in due
    ), "800 ч при пороге 750 ч, заданные через API, обязаны считаться просрочкой"
