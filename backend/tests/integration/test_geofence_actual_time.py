"""MK-3: геозона пишет фактическое время в RequestAssignment, а не в ShiftTask.

У ShiftTask нет actual_start/actual_end - прежний код читал их (AttributeError
до записи) и писал в несуществующее поле (значение молча терялось). Фактическое
время живёт в RequestAssignment.actual_start/actual_end, доступ через
ShiftTask.assignment_id. Если назначения нет, время не выдумывается.
"""

from datetime import UTC, date, datetime, timedelta

import pytest


@pytest.fixture
def shift_with_assignment(db_session, company, sample_contractor, sample_vehicle):
    from app.models.dispatch import Request, RequestAssignment
    from app.models.shift import ShiftTask

    now = datetime.now(UTC)
    req = Request(
        client_id=sample_contractor.id,
        status="in_progress",
        request_type="one_time",
        work_type="Earthworks",
        planned_start=now,
        planned_end=now + timedelta(days=1),
        company_id=company.id,
    )
    db_session.add(req)
    db_session.commit()
    db_session.refresh(req)

    assignment = RequestAssignment(
        request_id=req.id,
        vehicle_id=sample_vehicle.id,
        planned_start=now,
        planned_end=now + timedelta(days=1),
    )
    db_session.add(assignment)
    db_session.commit()
    db_session.refresh(assignment)

    task = ShiftTask(
        request_id=req.id,
        assignment_id=assignment.id,
        vehicle_id=sample_vehicle.id,
        shift_date=date.today(),
        status="planned",
        company_id=company.id,
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)
    return {"assignment_id": assignment.id, "vehicle_id": sample_vehicle.id}


def _event(auth_client, vehicle_id, event_type, ts):
    return auth_client.post(
        "/api/v1/shifts/geofence/event",
        json={
            "vehicle_id": vehicle_id,
            "geofence_id": 1,
            "event_type": event_type,
            "timestamp": ts.isoformat(),
        },
    )


def test_enter_writes_assignment_actual_start(
    auth_client, db_session, shift_with_assignment
):
    from app.models.dispatch import RequestAssignment

    assignment_id = shift_with_assignment["assignment_id"]
    vehicle_id = shift_with_assignment["vehicle_id"]
    ts = datetime.now(UTC).replace(microsecond=0)
    r = _event(auth_client, vehicle_id, "enter", ts)
    assert r.status_code == 200, r.text
    assert r.json()["action"] == "auto_started"
    db_session.expunge_all()
    refreshed = db_session.get(RequestAssignment, assignment_id)
    assert refreshed.actual_start is not None


def test_exit_writes_assignment_actual_end(
    auth_client, db_session, shift_with_assignment
):
    from app.models.dispatch import RequestAssignment

    assignment_id = shift_with_assignment["assignment_id"]
    vehicle_id = shift_with_assignment["vehicle_id"]
    ts = datetime.now(UTC).replace(microsecond=0)
    # смена изначально planned; exit завершает её и пишет фактический конец
    r = _event(auth_client, vehicle_id, "exit", ts)
    assert r.status_code == 200, r.text
    assert r.json()["action"] == "auto_completed"
    db_session.expunge_all()
    refreshed = db_session.get(RequestAssignment, assignment_id)
    assert refreshed.actual_end is not None


def test_unassigned_shift_does_not_crash(
    auth_client, db_session, company, sample_contractor, sample_vehicle
):
    from app.models.dispatch import Request
    from app.models.shift import ShiftTask

    now = datetime.now(UTC)
    req = Request(
        client_id=sample_contractor.id,
        status="in_progress",
        request_type="one_time",
        work_type="Earthworks",
        planned_start=now,
        planned_end=now + timedelta(days=1),
        company_id=company.id,
    )
    db_session.add(req)
    db_session.commit()
    db_session.refresh(req)

    task = ShiftTask(
        request_id=req.id,
        vehicle_id=sample_vehicle.id,
        shift_date=date.today(),
        status="planned",
        company_id=company.id,
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)
    task_id = task.id
    vehicle_id = sample_vehicle.id

    ts = datetime.now(UTC).replace(microsecond=0)
    r = _event(auth_client, vehicle_id, "enter", ts)
    assert r.status_code == 200, r.text
    assert r.json()["action"] == "auto_started"
    db_session.expunge_all()
    refreshed = db_session.get(ShiftTask, task_id)
    assert refreshed.status == "in_progress"
