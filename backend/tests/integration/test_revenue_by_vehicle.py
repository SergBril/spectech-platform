"""Топ техники по выработке: график должен показывать факт, а не нули.

Запрос суммировал Rental.moto_hours и соединял по Rental.vehicle_id - ни того,
ни другого у Rental нет. Исключение глоталось, fallback возвращал машины с
нулём часов: правдоподобный график с выдуманными данными.
"""

from datetime import date, datetime
from decimal import Decimal

PATH = "/api/v1/finance/revenue/by-vehicle"


def _shift(
    db_session, company, vehicle, hours, shift_date=date(2026, 11, 10), final=True
):
    from app.models.dispatch import Request
    from app.models.shift import ShiftReport, ShiftReportStatus, ShiftTask

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
        vehicle_id=vehicle.id,
        shift_date=shift_date,
        shift_number=1,
        status="completed",
        company_id=company.id,
    )
    db_session.add(task)
    db_session.commit()
    db_session.add(
        ShiftReport(
            shift_task_id=task.id,
            operator_moto_hours=Decimal(str(hours)),
            final_moto_hours=Decimal(str(hours)) if final else None,
            status=ShiftReportStatus.submitted,
            company_id=company.id,
        )
    )
    db_session.commit()
    return task


def _vehicle(db_session, company, name, idv):
    from app.models.catalog import Vehicle

    v = Vehicle(
        name=name,
        id_type="internal",
        id_value=idv,
        status="free",
        company_id=company.id,
    )
    db_session.add(v)
    db_session.commit()
    db_session.refresh(v)
    return v


def test_chart_sums_real_hours_and_orders_by_them(auth_client, db_session, company):
    a = _vehicle(db_session, company, "Экскаватор A", "CHART-A")
    b = _vehicle(db_session, company, "Погрузчик B", "CHART-B")
    _shift(db_session, company, a, 8)
    _shift(db_session, company, b, 12)
    _shift(db_session, company, b, 3, shift_date=date(2026, 11, 11))

    r = auth_client.get(
        PATH, params={"date_from": "2026-11-01", "date_to": "2026-11-30"}
    )
    assert r.status_code == 200, r.text
    rows = r.json()
    assert [x["vehicle_name"] for x in rows][:2] == ["Погрузчик B", "Экскаватор A"]
    assert rows[0]["moto_hours"] == 15.0
    assert rows[1]["moto_hours"] == 8.0


def test_empty_period_returns_nothing_not_fabricated_zeros(
    auth_client, db_session, company
):
    _vehicle(db_session, company, "Простаивающая машина", "CHART-IDLE")
    r = auth_client.get(
        PATH, params={"date_from": "2026-11-01", "date_to": "2026-11-30"}
    )
    assert r.status_code == 200, r.text
    assert r.json() == [], "машина без выработки не должна попадать в график с нулём"


def test_operator_hours_used_when_dispatcher_has_not_confirmed(
    auth_client, db_session, company
):
    v = _vehicle(db_session, company, "Без подтверждения", "CHART-OP")
    _shift(db_session, company, v, 6, final=False)
    r = auth_client.get(
        PATH, params={"date_from": "2026-11-01", "date_to": "2026-11-30"}
    )
    assert r.status_code == 200, r.text
    rows = r.json()
    assert rows and rows[0]["moto_hours"] == 6.0


def test_other_company_vehicle_is_excluded(auth_client, db_session, company):
    from app.models.company import Company

    other = Company(name="Чужая компания для графика", inn="9902223334")
    db_session.add(other)
    db_session.commit()
    db_session.refresh(other)
    v = _vehicle(db_session, other, "Чужой экскаватор", "CHART-OTHER")
    _shift(db_session, other, v, 20)

    r = auth_client.get(
        PATH, params={"date_from": "2026-11-01", "date_to": "2026-11-30"}
    )
    assert r.status_code == 200, r.text
    assert all(x["vehicle_name"] != "Чужой экскаватор" for x in r.json())
