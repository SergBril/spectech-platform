"""Показания счётчиков смены: выработка вычисляется и СОХРАНЯЕТСЯ.

Главный регресс: odometer_distance вычислялся и присваивался task, но колонки не
было - SQLAlchemy клал атрибут на экземпляр, значение исчезало, а УПД читал None.
Поэтому тесты проверяют не "код выполнился", а "значение видно после expunge".
"""

from decimal import Decimal

import pytest

from app.services.vehicle_readings_service import ReadingsError, apply_shift_readings


@pytest.fixture
def shift_task(db_session, company, sample_vehicle, sample_contractor):
    """Смена, созданная по образцу рабочих тестов.

    Фикстуры shift_task в проекте нет вовсе, а shift_report и
    sample_reconciliation в корневом conftest от неё зависят - любой тест,
    который их запросит, получает ERROR вместо проверки.
    """
    from datetime import date, datetime, timedelta

    from app.models.dispatch import Request
    from app.models.shift import ShiftTask

    now = datetime.now()
    request = Request(
        client_id=sample_contractor.id,
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
        operator_id=sample_contractor.id,
        vehicle_id=sample_vehicle.id,
        shift_date=date.today(),
        shift_number=1,
        status="in_progress",
        company_id=company.id,
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)
    return task


@pytest.fixture
def shift_report(db_session, company, shift_task, sample_contractor):
    from app.models.shift import ShiftReport, ShiftReportStatus

    report = ShiftReport(
        shift_task_id=shift_task.id,
        operator_id=sample_contractor.id,
        status=ShiftReportStatus.submitted,
        company_id=company.id,
    )
    db_session.add(report)
    db_session.commit()
    db_session.refresh(report)
    return report


def _vehicle(db_session, task):
    from app.models.catalog import Vehicle

    return db_session.get(Vehicle, task.vehicle_id)


def test_distance_survives_a_reload(db_session, shift_task):
    """Пробег должен лежать в базе, а не на экземпляре Python."""
    from app.models.shift import ShiftTask

    task = shift_task
    tid = task.id
    apply_shift_readings(
        db_session,
        task,
        _vehicle(db_session, task),
        odometer_start=12000,
        odometer_end=12120,
    )
    db_session.commit()
    db_session.expunge_all()

    reloaded = db_session.get(ShiftTask, tid)
    assert (
        reloaded.odometer_distance is not None
    ), "пробег смены потерялся при сохранении"
    assert float(reloaded.odometer_distance) == 120.0


def test_worked_hours_are_derived_from_readings(db_session, shift_task, shift_report):
    task = shift_task
    report = shift_report
    rid = report.id
    res = apply_shift_readings(
        db_session,
        task,
        _vehicle(db_session, task),
        hours_start=760,
        hours_end=768.5,
        report=report,
    )
    db_session.commit()
    assert res["moto_hours_worked"] == 8.5

    from app.models.shift import ShiftReport

    db_session.expunge_all()
    reloaded = db_session.get(ShiftReport, rid)
    assert float(reloaded.moto_hours_end) == 768.5, "накопленное показание не сохранено"
    assert float(reloaded.operator_moto_hours) == 8.5, "выработка не сохранена"


def test_vehicle_counters_are_updated(db_session, shift_task):
    task = shift_task
    vehicle = _vehicle(db_session, task)
    vid = vehicle.id
    apply_shift_readings(
        db_session,
        task,
        vehicle,
        odometer_start=12000,
        odometer_end=12120,
        hours_start=760,
        hours_end=768.5,
    )
    db_session.commit()
    db_session.expunge_all()

    from app.models.catalog import Vehicle

    reloaded = db_session.get(Vehicle, vid)
    assert float(reloaded.odometer_km) == 12120
    assert float(reloaded.engine_hours) == 768.5


def test_operator_odometer_holds_output_not_the_meter_reading(
    db_session, shift_task, shift_report
):
    """Единая семантика: operator_* - выработка, а не показание счётчика."""
    task = shift_task
    report = shift_report
    rid = report.id
    apply_shift_readings(
        db_session,
        task,
        _vehicle(db_session, task),
        odometer_start=12000,
        odometer_end=12120,
        report=report,
    )
    db_session.commit()
    db_session.expunge_all()

    from app.models.shift import ShiftReport

    reloaded = db_session.get(ShiftReport, rid)
    assert (
        reloaded.operator_odometer == 120
    ), "в operator_odometer попало показание вместо выработки"
    assert reloaded.odometer_end == 12120


def test_end_before_start_is_rejected(db_session, shift_task):
    task = shift_task
    with pytest.raises(ReadingsError) as exc:
        apply_shift_readings(
            db_session,
            task,
            _vehicle(db_session, task),
            odometer_start=12120,
            odometer_end=12000,
        )
    assert exc.value.status_code == 422


def test_rollback_against_known_counters_is_rejected(db_session, shift_task):
    """Опечатка не должна обнулять наработку и регламент ТО."""
    task = shift_task
    vehicle = _vehicle(db_session, task)
    vehicle.engine_hours = Decimal("760.00")
    db_session.commit()

    with pytest.raises(ReadingsError) as exc:
        apply_shift_readings(db_session, task, vehicle, hours_start=700, hours_end=705)
    assert exc.value.status_code == 422
    assert (
        float(vehicle.engine_hours) == 760.0
    ), "наработка не должна измениться при отказе"


def test_repeating_the_same_readings_is_idempotent(db_session, shift_task):
    """Показания идемпотентны: повторный ввод не удваивает выработку."""
    task = shift_task
    vehicle = _vehicle(db_session, task)
    for _ in range(2):
        res = apply_shift_readings(
            db_session,
            task,
            vehicle,
            odometer_start=12000,
            odometer_end=12120,
            hours_start=760,
            hours_end=768.5,
        )
        db_session.commit()
    assert res["odometer_distance"] == 120.0
    assert res["moto_hours_worked"] == 8.5
    assert float(vehicle.engine_hours) == 768.5


def test_end_only_updates_counters_without_fabricating_output(db_session, shift_task):
    """Без начала смены выработку вычислить нельзя - и её не надо выдумывать."""
    task = shift_task
    vehicle = _vehicle(db_session, task)
    res = apply_shift_readings(
        db_session, task, vehicle, odometer_end=13000, hours_end=800
    )
    db_session.commit()
    assert res["odometer_distance"] is None
    assert res["moto_hours_worked"] is None
    assert float(vehicle.odometer_km) == 13000
    assert float(vehicle.engine_hours) == 800
