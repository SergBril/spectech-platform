"""Отклик на заявку: автор отклика должен храниться и получать уведомление.

RequestAssignment не имел поля автора. Код писал и читал assigned_by: конструктор
бросал TypeError (создание заявки из смены падало), чтение давало AttributeError
и глоталось except (уведомления не доходили), присваивание молча не сохранялось.
Оператор смены брался из phantom vehicle.current_driver_id и всегда был None.
"""

from datetime import date, datetime, timedelta

import pytest


@pytest.fixture
def pending_response(db_session, company, sample_vehicle, admin_user):
    from app.models.dispatch import Request, RequestAssignment

    start = datetime(2026, 11, 12, 9, 0)
    req = Request(
        client_id=company.id,
        company_id=company.id,
        status="has_responses",
        request_type="one_time",
        work_type="earthworks",
        planned_start=start,
        planned_end=start + timedelta(hours=8),
        created_by=admin_user.id,
        source_channel="web",
    )
    db_session.add(req)
    db_session.commit()
    resp = RequestAssignment(
        request_id=req.id,
        vehicle_id=sample_vehicle.id,
        created_by_user_id=admin_user.id,
        planned_start=start,
        planned_end=start + timedelta(hours=8),
        status="pending_approval",
    )
    db_session.add(resp)
    db_session.commit()
    db_session.refresh(resp)
    return req, resp


@pytest.fixture
def planned_shift(db_session, company, sample_vehicle, admin_user):
    from app.models.dispatch import Request
    from app.models.shift import ShiftTask

    start = datetime(2026, 11, 12, 9, 0)
    internal = Request(
        client_id=company.id,
        company_id=company.id,
        status="assigned",
        request_type="one_time",
        work_type="earthworks",
        planned_start=start,
        planned_end=start + timedelta(hours=8),
        created_by=admin_user.id,
        source_channel="internal",
    )
    db_session.add(internal)
    db_session.commit()
    task = ShiftTask(
        request_id=internal.id,
        vehicle_id=sample_vehicle.id,
        shift_date=date(2026, 11, 12),
        shift_number=1,
        status="draft",
        company_id=company.id,
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)
    return task


def test_create_request_from_shift_requires_explicit_times(auth_client, planned_shift):
    """У смены нет полей времени: выдумывать часы нельзя, они питают отчёты."""
    r = auth_client.post(
        f"/api/v1/shifts/tasks/{planned_shift.id}/create-request",
        json={"work_type": "earthworks", "object_address": "Северный"},
    )
    assert r.status_code == 422, r.text


def test_create_request_from_shift_stores_author_and_operator(
    auth_client, db_session, planned_shift, sample_vehicle, admin_user
):
    from app.models.dispatch import Request, RequestAssignment

    r = auth_client.post(
        f"/api/v1/shifts/tasks/{planned_shift.id}/create-request",
        json={
            "work_type": "earthworks",
            "object_address": "Северный",
            "planned_start": "2026-11-12T09:00:00",
            "planned_end": "2026-11-12T18:00:00",
        },
    )
    assert r.status_code == 200, r.text
    req_id = r.json()["request_id"]
    req = db_session.get(Request, req_id)
    assert req.planned_start.replace(tzinfo=None) == datetime(2026, 11, 12, 9, 0)

    resp = (
        db_session.query(RequestAssignment)
        .filter(RequestAssignment.request_id == req_id)
        .one()
    )
    assert resp.created_by_user_id == admin_user.id, "автор отклика не сохранён"
    assert resp.status == "approved"


def test_approving_a_response_notifies_its_author(
    auth_client, db_session, pending_response, admin_user
):
    from app.models.telematics import Notification

    req, resp = pending_response
    r = auth_client.post(
        "/api/v1/requests/responses/bulk-action",
        json={"assignment_ids": [resp.id], "action": "approve"},
    )
    assert r.status_code == 200, r.text

    rows = (
        db_session.query(Notification)
        .filter(Notification.user_id == admin_user.id)
        .all()
    )
    assert any(
        "отклик" in (n.title or "").lower() for n in rows
    ), f"автор отклика не уведомлён: {[n.title for n in rows]}"
