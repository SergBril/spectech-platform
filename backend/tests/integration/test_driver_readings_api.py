"""Показания через API водителя: данные должны доходить до базы.

Дефект был не в вычислении, а в том, что результат не сохранялся: пробег смены
присваивался атрибуту без колонки, а наработка машины не обновлялась вовсе.
Поэтому проверки идут через маршрут и читают значения ПОСЛЕ expunge.
"""

from datetime import date, datetime, timedelta

import pytest


@pytest.fixture
def driver_task(db_session, company, sample_vehicle, admin_user):
    from app.models.contractor import Contractor, Employee
    from app.models.dispatch import Request
    from app.models.shift import ShiftTask

    operator = Contractor(
        name="Оператор тестовый",
        inn="770333333333",
        type="employee",
        company_id=company.id,
    )
    db_session.add(operator)
    db_session.commit()

    db_session.add(
        Employee(
            contractor_id=operator.id,
            user_id=admin_user.id,
            position="Оператор",
            role_in_system="operator",
        )
    )
    db_session.commit()

    now = datetime.now()
    request = Request(
        client_id=operator.id,
        status="in_progress",
        request_type="one_time",
        work_type="Earthworks",
        planned_start=now,
        planned_end=now + timedelta(days=1),
        company_id=company.id,
    )
    db_session.add(request)
    db_session.commit()

    task = ShiftTask(
        request_id=request.id,
        operator_id=operator.id,
        vehicle_id=sample_vehicle.id,
        shift_date=date.today(),
        shift_number=1,
        status="draft",
        company_id=company.id,
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)
    return task


def test_start_shift_stores_the_readings(auth_client, db_session, driver_task):
    from app.models.shift import ShiftTask

    tid = driver_task.id
    r = auth_client.post(
        f"/api/v1/driver/shifts/{tid}/start",
        data={"odometer_start": 12000, "moto_hours_start": 760},
    )
    assert r.status_code == 200, r.text

    db_session.expunge_all()
    task = db_session.get(ShiftTask, tid)
    assert task.odometer_start == 12000, "показание на начало смены не сохранилось"
    assert float(task.moto_hours_start) == 760.0


def test_report_derives_output_and_updates_the_vehicle(
    auth_client, db_session, driver_task
):
    from app.models.catalog import Vehicle
    from app.models.shift import ShiftReport, ShiftTask

    tid = driver_task.id
    vid = driver_task.vehicle_id
    assert (
        auth_client.post(
            f"/api/v1/driver/shifts/{tid}/start",
            data={"odometer_start": 12000, "moto_hours_start": 760},
        ).status_code
        == 200
    )

    r = auth_client.post(
        f"/api/v1/driver/shifts/{tid}/report",
        data={"odometer_end": 12120, "moto_hours_end": 768.5},
    )
    assert r.status_code == 200, r.text
    rid = r.json()["report_id"]

    db_session.expunge_all()
    report = db_session.get(ShiftReport, rid)
    task = db_session.get(ShiftTask, tid)
    vehicle = db_session.get(Vehicle, vid)

    assert report.operator_odometer == 120, "выработка по пробегу не вычислена"
    assert (
        float(report.operator_moto_hours) == 8.5
    ), "выработка по моточасам не вычислена"
    assert report.odometer_end == 12120
    assert (
        float(task.odometer_distance) == 120.0
    ), "пробег смены потерян - его читают УПД"
    assert float(vehicle.odometer_km) == 12120, "наработка машины не обновилась"
    assert float(vehicle.engine_hours) == 768.5


def test_legacy_report_with_ready_output_still_works(
    auth_client, db_session, driver_task
):
    """Обратная совместимость: старый вызов с выработкой за смену."""
    from app.models.shift import ShiftReport

    tid = driver_task.id
    r = auth_client.post(
        f"/api/v1/driver/shifts/{tid}/report",
        data={"moto_hours": 8.0, "odometer": 50},
    )
    assert r.status_code == 200, r.text
    rid = r.json()["report_id"]
    db_session.expunge_all()
    report = db_session.get(ShiftReport, rid)
    assert float(report.operator_moto_hours) == 8.0
    assert report.operator_odometer == 50


def test_report_without_any_readings_is_rejected(auth_client, driver_task):
    r = auth_client.post(f"/api/v1/driver/shifts/{driver_task.id}/report", data={})
    assert r.status_code == 422, "пустой отчёт не должен проходить молча"


def test_rollback_is_rejected_and_counters_stay(auth_client, db_session, driver_task):
    from app.models.catalog import Vehicle

    vid = driver_task.vehicle_id
    assert (
        auth_client.post(
            f"/api/v1/driver/shifts/{driver_task.id}/start",
            data={"moto_hours_start": 760},
        ).status_code
        == 200
    )

    r = auth_client.post(
        f"/api/v1/driver/shifts/{driver_task.id}/report",
        data={"moto_hours_end": 700},
    )
    assert r.status_code == 422, "откат счётчика обязан отвергаться"

    db_session.expunge_all()
    vehicle = db_session.get(Vehicle, vid)
    assert (
        float(vehicle.engine_hours or 0) < 700 or float(vehicle.engine_hours or 0) == 0
    ), "наработка не должна меняться при отказе"
