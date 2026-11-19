"""Календарь смен: пути, период, смены без водителя, подбор водителя.

Найдено по слоям: фронтенд звал несуществующие пути; обработчик списка игнорировал
date_from/date_to и отдавал последние 50 смен за все даты; схема требовала
operator_id: int, а смена без водителя законна - список падал на валидации ответа;
подбор водителей фильтровал по Employee.company_id, которого нет, и всегда давал 0.
"""

from datetime import date, datetime

import pytest


@pytest.fixture
def shift_factory(db_session, company, sample_vehicle):
    from app.models.dispatch import Request
    from app.models.shift import ShiftTask

    def make(shift_date, operator_id=None):
        req = Request(
            client_id=company.id,
            company_id=company.id,
            status="completed",
            request_type="one_time",
            work_type="Earthworks",
            planned_start=datetime(2026, 11, 10, 8, 0),
            planned_end=datetime(2026, 11, 10, 18, 0),
        )
        db_session.add(req)
        db_session.commit()
        task = ShiftTask(
            request_id=req.id,
            vehicle_id=sample_vehicle.id,
            shift_date=shift_date,
            shift_number=1,
            status="planned",
            company_id=company.id,
            operator_id=operator_id,
        )
        db_session.add(task)
        db_session.commit()
        db_session.refresh(task)
        return task

    return make


def test_unassigned_shift_is_listed(auth_client, shift_factory):
    """Смена без водителя - главный объект календаря, а не ошибка схемы."""
    t = shift_factory(date(2026, 11, 10))
    r = auth_client.get(
        "/api/v1/shifts/tasks",
        params={"date_from": "2026-11-09", "date_to": "2026-11-15"},
    )
    assert r.status_code == 200, r.text
    ids = [x["id"] for x in r.json()]
    assert t.id in ids
    assert next(x for x in r.json() if x["id"] == t.id)["operator_id"] is None


def test_period_filter_excludes_other_weeks(auth_client, shift_factory):
    inside = shift_factory(date(2026, 11, 10))
    outside = shift_factory(date(2026, 12, 20))
    r = auth_client.get(
        "/api/v1/shifts/tasks",
        params={"date_from": "2026-11-09", "date_to": "2026-11-15"},
    )
    assert r.status_code == 200, r.text
    ids = [x["id"] for x in r.json()]
    assert inside.id in ids
    assert outside.id not in ids, "календарь показывает смены вне выбранной недели"


def test_drag_and_drop_moves_the_shift(auth_client, db_session, shift_factory):
    from app.models.shift import ShiftTask

    t = shift_factory(date(2026, 11, 10))
    r = auth_client.put(
        f"/api/v1/shifts/tasks/{t.id}", json={"shift_date": "2026-11-12"}
    )
    assert r.status_code == 200, r.text
    db_session.expunge_all()
    assert db_session.get(ShiftTask, t.id).shift_date == date(2026, 11, 12)


def test_bulk_auto_assign_finds_a_company_driver(
    auth_client, db_session, company, sample_contractor, shift_factory
):
    from app.models.contractor import DriverProfile, Employee
    from app.models.shift import ShiftTask

    db_session.add(
        Employee(contractor_id=sample_contractor.id, role_in_system="driver")
    )
    db_session.add(
        DriverProfile(employee_contractor_id=sample_contractor.id, license_category="C")
    )
    db_session.commit()

    task = shift_factory(date(2026, 11, 10))
    task_id = task.id
    contractor_id = sample_contractor.id

    r = auth_client.post(
        "/api/v1/shifts/bulk-auto-assign",
        json={"date_from": "2026-11-09", "date_to": "2026-11-15"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["assigned"] == 1, f"водитель не подобран: {r.json()}"
    db_session.expunge_all()
    assert db_session.get(ShiftTask, task_id).operator_id == contractor_id
